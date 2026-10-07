"""Seven independent blind Responses requests; no operator/ranking reads in judging."""

import argparse
import asyncio
import fcntl
import os
import time
from pathlib import Path

from uranus_research_service.machine_blind_contracts import (
    Candidate,
    read,
    require,
    schema,
    sha,
    validate_answer,
)
from uranus_research_service.machine_blind_contracts import (
    payload as blind_payload,
)
from uranus_research_service.machine_blind_review import now, parse
from uranus_research_service.machine_judge import (
    APIError,
    OpenAIJudge,
    atomic_new,
    safe_id,
    usage_of,
)
from uranus_research_service.semantic_manifest import digest

MODEL = "gpt-6-astra"
BASE = Path("benchmark/review/lost-all-v1/machine")
INPUT = BASE / "machine-review-needed.jsonl"
INPUT_SHA = "7c274d8640ffa4b74ed936c527d47a7eef7ef47fe96225fb76bf9b954da7a5d4"
PROMPT = BASE / "adjudication/prompt-v1.txt"
IDS = {
    "b1ec1a0d2cb81f1603a589de0774ee72",
    "ebe8f9e910f2473c3ed42a88310f6217",
    "cfa866001215559a48b99e6b2dd6ac36",
    "825ed6aa7430fc01244b7aa2a637f050",
    "bbf51ea2f646d78291338808505e94c0",
    "3d33d10c4f41fa7771e1810e095d5b79",
    "efc19b7b3670f4e050dd1ce7de817e6d",
}
PARAMETERS = {"reasoning": {"effort": "high"}, "max_output_tokens": 8192, "store": False}


def load_input(path=INPUT):
    from uranus_research_service.json_codec import decode

    raw = Path(path).read_bytes()
    require(sha(raw) == INPUT_SHA, "input_hash_mismatch")
    rows = [decode(line) for line in raw.splitlines()]
    require(len(rows) == 7 and {r["annotation_id"] for r in rows} == IDS, "input_ids")
    clean = []
    for row in rows:
        require(row.get("status") == "machine_conflict", "input_schema")
        # Status is operator metadata. It never reaches the projection or HTTP body.
        candidate = {k: v for k, v in row.items() if k != "status"}
        Candidate.model_validate(candidate)
        clean.append(candidate)
    return clean


def payload(candidate, prompt):
    request = blind_payload(candidate, MODEL, prompt)
    del request["temperature"]  # Astra does not support custom temperature.
    request.update(PARAMETERS)
    return request


def configuration(prompt):
    return {
        "schema_version": "blind-machine-adjudication-v1",
        "provenance": "machine_adjudication",
        "provider": "openai",
        "model": MODEL,
        "input_sha256": INPUT_SHA,
        "prompt_version": "blind-adjudication-v1",
        "prompt_sha256": sha(prompt.encode()),
        "schema_sha256": digest(schema()),
        "parameters": PARAMETERS,
        "temperature": None,
        "seed": None,
        "response_format": "responses.text.format:strict-json-schema",
        "expected_count": 7,
        "code_sha256": {
            name: sha(Path(__file__).with_name(name).read_bytes())
            for name in (
                "machine_blind_adjudication.py",
                "machine_blind_contracts.py",
                "machine_blind_review.py",
                "machine_judge.py",
            )
        },
    }


def save_once(path, value):
    if path.exists():
        require(read(path) == value, "existing_artifact_changed")
    else:
        atomic_new(path, value)


def validate_record(record, candidate, config, prompt):
    require(record["annotation_id"] == candidate["annotation_id"], "record_id")
    require(record["configuration_sha256"] == digest(config), "record_configuration")
    require(record["payload_sha256"] == digest(payload(candidate, prompt)), "record_payload")
    require(record["status"] in ("machine_adjudicated", "machine_unresolved"), "record_status")
    if record["answer"] is not None:
        answer = validate_answer(record["answer"], candidate)
        require(record["model_returned"] == MODEL, "returned_model")
        require(
            record["status"]
            == ("machine_adjudicated" if answer["state"] == "graded" else "machine_unresolved"),
            "record_state",
        )
    else:
        require(record["status"] == "machine_unresolved" and record["error_category"], "failure")


def validate(directory, input_path=INPUT, prompt_path=PROMPT):
    directory = Path(directory)
    packet = load_input(input_path)
    prompt = Path(prompt_path).read_text()
    config = configuration(prompt)
    manifest = read(directory / "adjudication-run.json")
    require(manifest["configuration"] == config, "run_configuration")
    records = read(directory / "adjudicated-answers.json")
    require(len(records) == 7 and {r["annotation_id"] for r in records} == IDS, "answer_ids")
    for c, r in zip(packet, records, strict=True):
        validate_record(r, c, config, prompt)
        require(read(directory / "records" / f"{c['annotation_id']}.json") == r, "record_copy")
    index = read(directory / "artifact-sha256.json")
    actual = {
        str(p.relative_to(directory)): sha(p.read_bytes())
        for p in directory.rglob("*")
        if p.is_file() and p.name not in (".lock", "artifact-sha256.json")
    }
    require(index == actual, "run_artifact_hashes")
    return records


async def run(input_path, destination, prompt, client, *, resume=False, sleep=asyncio.sleep):
    packet = load_input(input_path)
    config = configuration(prompt)
    destination = Path(destination)
    require(not destination.exists() or resume, "explicit_resume_required")
    # A model unavailable to this account aborts before creating result artifacts.
    await client.available(MODEL)
    destination.mkdir(parents=True, exist_ok=True)
    with (destination / ".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        mp = destination / "adjudication-run.json"
        if mp.exists():
            require(read(mp)["configuration"] == config, "resume_configuration")
        else:
            require(not resume, "resume_manifest_missing")
            atomic_new(mp, {"configuration": config, "started_at": now()})
        for i, c in enumerate(packet):
            aid = c["annotation_id"]
            final = destination / "records" / f"{aid}.json"
            if final.exists():
                validate_record(read(final), c, config, prompt)
                continue
            request = payload(c, prompt)
            require(len(str(request).encode()) < 256 * 1024, "request_size")
            for attempt in range(1, 4):
                path = destination / "attempts" / f"{aid}-{attempt}.json"
                reservation = destination / "attempts" / f"{aid}-{attempt}.started.json"
                if path.exists():
                    result = read(path)
                else:
                    interrupted = reservation.exists()
                    if not interrupted:
                        atomic_new(
                            reservation, {"payload_sha256": digest(request), "started_at": now()}
                        )
                    row = {
                        "annotation_id": aid,
                        "configuration_sha256": digest(config),
                        "payload_sha256": digest(request),
                        "attempt": attempt,
                        "timestamp": now(),
                        "status": "machine_unresolved",
                        "answer": None,
                        "usage": {},
                        "response_id": None,
                        "request_id": None,
                        "model_returned": None,
                        "error_category": None,
                    }
                    retry = False
                    start = time.monotonic()
                    if interrupted:
                        row["error_category"] = "interrupted_request_unknown_outcome"
                    else:
                        try:
                            body, rid = await client.request("POST", "responses", request)
                            row.update(
                                usage=usage_of(body),
                                request_id=rid,
                                response_id=safe_id(body.get("id")),
                                model_returned=safe_id(body.get("model")),
                            )
                            answer = parse(body, c, MODEL)
                            row["answer"] = answer
                            row["status"] = (
                                "machine_adjudicated"
                                if answer["state"] == "graded"
                                else "machine_unresolved"
                            )
                        except (APIError, ValueError, KeyError, TypeError) as error:
                            retry = isinstance(error, APIError) and error.retry
                            row["error_category"] = (
                                error.category
                                if isinstance(error, APIError)
                                else "invalid_response_contract"
                            )
                            row["request_id"] = row["request_id"] or getattr(
                                error, "request_id", None
                            )
                    row["latency_ms"] = (time.monotonic() - start) * 1000
                    result = {"record": row, "retryable": retry}
                    atomic_new(path, result)
                if not result["retryable"] or attempt == 3:
                    atomic_new(final, result["record"])
                    break
                await sleep(2**attempt)
            print(f"adjudication {i + 1}/7 persisted", flush=True)
        rows = [read(destination / "records" / f"{c['annotation_id']}.json") for c in packet]
        save_once(destination / "adjudicated-answers.json", rows)
        ledger = [
            read(p)
            for p in sorted((destination / "attempts").glob("*.json"))
            if not p.name.endswith(".started.json")
        ]
        lp = destination / "request-ledger.jsonl"
        if not lp.exists():
            atomic_new(lp, ledger, jsonl=True)
        hashes = {
            str(p.relative_to(destination)): sha(p.read_bytes())
            for p in destination.rglob("*")
            if p.is_file() and p.name not in (".lock", "artifact-sha256.json")
        }
        save_once(destination / "artifact-sha256.json", hashes)
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("run", "validate", "combine", "reevaluate"))
    parser.add_argument("--model", default=MODEL, choices=(MODEL,))
    parser.add_argument("--input", type=Path, default=INPUT)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    if args.command == "run":

        async def execute():
            client = OpenAIJudge(os.environ["OPENAI_API_KEY"])
            try:
                await run(args.input, args.output, PROMPT.read_text(), client, resume=args.resume)
            finally:
                await client.close()

        try:
            asyncio.run(execute())
        except APIError as error:
            raise SystemExit(
                f"OpenAI request rejected: {error.category}; no model fallback"
            ) from None
    elif args.command == "validate":
        records = validate(args.input)
        atomic_new(
            args.output,
            {"status": "valid", "count": len(records), "answers_sha256": digest(records)},
        )
    else:
        from uranus_research_service.machine_adjudication_analysis import combine, reevaluate

        result = combine(args.input) if args.command == "combine" else reevaluate(read(args.input))
        atomic_new(args.output, result)


if __name__ == "__main__":
    main()
