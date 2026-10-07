"""Two stateless machine passes over the fixed 77-pair blind packet; never human labels."""

import argparse
import asyncio
import fcntl
import os
import re
import time
from datetime import UTC, datetime
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from uranus_research_service.ground_truth_snapshot import canonical_bytes
from uranus_research_service.json_codec import decode
from uranus_research_service.machine_blind_contracts import (
    META_SHA,
    PACKET_SHA,
    PARAMETERS,
    PROMPT,
    load_packet,
    payload,
    read,
    require,
    sha,
    validate_answer,
)
from uranus_research_service.machine_judge import (
    APIError,
    OpenAIJudge,
    atomic_new,
    safe_id,
    usage_of,
)
from uranus_research_service.semantic_manifest import digest


def now():
    return datetime.now(UTC).isoformat()


def identity(model, pass_id, run_id, prompt):
    require(pass_id in ("a", "b"), "pass_id")
    require(re.fullmatch(r"[a-z0-9][a-z0-9.-]{1,99}", model), "explicit_model")
    require(re.fullmatch(r"[a-z0-9_-]{1,100}", run_id), "run_id")
    return {
        "schema_version": "blind-machine-pass-v1",
        "provenance": "machine_proposed",
        "provider": "openai",
        "model": model,
        "pass_id": pass_id,
        "run_id": run_id,
        "parameters": PARAMETERS,
        "prompt_version": "focused-judge-v1",
        "prompt_sha256": sha(prompt.encode()),
        "packet_sha256": PACKET_SHA,
        "package_file_sha256": META_SHA,
        "expected_count": 77,
        "code_sha256": {
            name: sha(Path(__file__).with_name(name).read_bytes())
            for name in (
                "machine_blind_contracts.py",
                "machine_judge.py",
                "machine_blind_review.py",
            )
        },
    }


def parse(body, candidate, model):
    require(body.get("model") == model and body.get("status") == "completed", "response_identity")
    parts = [p for o in body["output"] if o.get("type") == "message" for p in o["content"]]
    require(len(parts) == 1 and parts[0].get("type") == "output_text", "response_refusal_or_shape")
    require(
        set(usage_of(body)) == {"input_tokens", "output_tokens", "total_tokens"}, "usage_missing"
    )
    return validate_answer(decode(parts[0]["text"]), candidate)


async def run(
    package,
    destination,
    model,
    pass_id,
    run_id,
    prompt,
    client,
    *,
    resume=False,
    sleep=asyncio.sleep,
):
    packet, _ = load_packet(package)
    config = identity(model, pass_id, run_id, prompt)
    if destination.exists():
        require(resume, "explicit_resume_required")
    else:
        destination.mkdir(parents=True)
    with (destination / ".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        mp = destination / "manifest.json"
        if mp.exists():
            manifest = read(mp)
            require(manifest["configuration"] == config, "resume_identity_changed")
        else:
            require(not resume, "resume_manifest_missing")
            manifest = {"configuration": config, "started_at": now()}
            atomic_new(mp, manifest)
        await client.available(model)
        for i, candidate in enumerate(packet):
            aid = candidate["annotation_id"]
            final = destination / "records" / f"{aid}.json"
            if final.exists():
                saved = read(final)
                require(saved["configuration_sha256"] == digest(config), "record_identity")
                validate_answer(saved["answer"], candidate)
                continue
            request = payload(candidate, model, prompt)
            require(len(canonical_bytes(request)) <= 256 * 1024, "request_size")
            for attempt in range(1, 4):
                reservation = destination / "attempts" / f"{aid}-{attempt}.request.json"
                completion = destination / "attempts" / f"{aid}-{attempt}.result.json"
                if reservation.exists():
                    if completion.exists():
                        prev = read(completion)
                        if prev["status"] == "success":
                            row = prev["record"]
                            require(
                                row["configuration_sha256"] == digest(config), "recovery_identity"
                            )
                            validate_answer(row["answer"], candidate)
                            atomic_new(final, row)
                            break
                        require(prev["retryable"], "previous_nonretryable_failure")
                    continue
                client_id = str(uuid5(NAMESPACE_URL, f"{digest(config)}:{aid}:{attempt}"))
                meta = {
                    "annotation_id": aid,
                    "attempt": attempt,
                    "request_sha256": digest(request),
                    "client_request_id": client_id,
                    "started_at": now(),
                    "configuration_sha256": digest(config),
                }
                atomic_new(reservation, meta)
                start = time.monotonic()
                usage, rid, response_id = {}, None, None
                try:
                    body, rid = await client.request("POST", "responses", request, client_id)
                    usage, response_id = usage_of(body), safe_id(body.get("id"))
                    answer = parse(body, candidate, model)
                    row = {
                        "answer": answer,
                        "configuration_sha256": digest(config),
                        "request_id": rid,
                        "response_id": response_id,
                        "attempt": attempt,
                        "completed_at": now(),
                        "latency_ms": (time.monotonic() - start) * 1000,
                        "usage": usage,
                    }
                    atomic_new(completion, {**meta, "status": "success", "record": row})
                    atomic_new(final, row)
                    break
                except (APIError, ValueError, KeyError, TypeError) as error:
                    retryable = isinstance(error, APIError) and error.retry
                    category = (
                        error.category
                        if isinstance(error, APIError)
                        else "invalid_response_contract"
                    )
                    atomic_new(
                        completion,
                        {
                            **meta,
                            "status": "failed",
                            "retryable": retryable,
                            "error_category": category,
                            "request_id": rid or getattr(error, "request_id", None),
                            "response_id": response_id,
                            "usage": usage,
                            "completed_at": now(),
                        },
                    )
                    if not retryable:
                        raise APIError(category) from None
                    if attempt < 3:
                        await sleep(2**attempt)
            require(final.exists(), "attempt_budget_exhausted")
            print(f"Pass {pass_id}: {i + 1}/{len(packet)} persisted", flush=True)
        records = [read(destination / "records" / f"{c['annotation_id']}.json") for c in packet]
        attempts = [read(p) for p in sorted((destination / "attempts").glob("*.result.json"))]
        usage_rows = [
            r["record"]["usage"] if r["status"] == "success" else r.get("usage", {})
            for r in attempts
        ]
        result = {
            "manifest": manifest,
            "completed_at": max(r["completed_at"] for r in records),
            "records": records,
            "summary": {
                "count": len(records),
                "failed_cases": 0,
                "failed_attempts": sum(r["status"] == "failed" for r in attempts),
                "retry_count": sum(r["attempt"] > 1 for r in attempts),
                "unknown_attempts": len(list((destination / "attempts").glob("*.request.json")))
                - len(attempts),
                "usage": {
                    k: sum(u.get(k, 0) for u in usage_rows)
                    for k in ("input_tokens", "output_tokens", "total_tokens")
                },
            },
        }
        dest = destination / f"annotations-pass-{pass_id}.json"
        if dest.exists():
            require(read(dest) == result, "completed_run_changed")
        else:
            atomic_new(dest, result)
        return result


async def execute(args):
    key = os.environ.get("OPENAI_API_KEY")
    require(key, "OPENAI_API_KEY_required")
    client = OpenAIJudge(key)
    try:
        await run(
            args.package,
            args.output,
            args.model,
            args.pass_id,
            args.run_id,
            args.prompt.read_text(),
            client,
            resume=args.resume,
        )
    finally:
        await client.close()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("command", choices=("run", "import", "compare", "consensus", "reevaluate"))
    p.add_argument("--package", type=Path, default=Path("benchmark/review/lost-all-v1"))
    p.add_argument("--root", type=Path, default=Path.cwd())
    p.add_argument("--model")
    p.add_argument("--pass-id", choices=("a", "b"))
    p.add_argument("--run-id")
    p.add_argument("--prompt", type=Path, default=PROMPT)
    p.add_argument("--resume", action="store_true")
    p.add_argument("--input", type=Path)
    p.add_argument("--a", type=Path)
    p.add_argument("--b", type=Path)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    try:
        if args.command == "run":
            require(args.model and args.pass_id and args.run_id, "explicit_run_configuration")
            asyncio.run(execute(args))
        else:
            from uranus_research_service.machine_blind_analysis import dispatch

            dispatch(args)
    except (APIError, ValueError, KeyError, TypeError, OSError):
        p.exit(
            2,
            "Machine operation stopped: input, provider or resume validation failed. "
            "Inspect safe attempt metadata. No fallback or repair.\n",
        )


if __name__ == "__main__":
    main()
