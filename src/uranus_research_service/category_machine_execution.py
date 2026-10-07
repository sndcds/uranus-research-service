"""Pinned category A/B execution contract. Dry-run is offline; real runs require approval."""

import argparse
import asyncio
import fcntl
import math
import os
import time
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Literal
from uuid import NAMESPACE_URL, uuid5

import httpx
from pydantic import Field, StrictInt

from uranus_research_service.category_coverage_review import DEST as PACKAGE
from uranus_research_service.category_coverage_review import checked
from uranus_research_service.machine_blind_contracts import PROMPT, schema
from uranus_research_service.machine_blind_review import parse
from uranus_research_service.machine_judge import (
    APIError,
    BlindCandidate,
    Closed,
    OpenAIJudge,
    api_payload,
    atomic_new,
    digest,
    read,
    read_lines,
    require,
    safe_id,
    sha,
    usage_of,
)

BASELINE = "376cbda3c1818ec0f06e31a8ccb6b3112c2fc0e6"
MODEL = "gpt-5.4-mini-2026-03-17"
PASSES = ("machine-a", "machine-b")
COUNT = 1506
DEST = Path("benchmark/review/category-coverage-two-pass-v1")
PACKET_SHA = "6b2b54c3c254d97f2972b04d122cc8e415eeff87e09d164d09a7902c45f3cd54"
META_SHA = "0e043cfd64ee821eac75ca71540d0888634a60226ab3e643baae37f4feb581a0"
PLAN_SHA = "ced8eedf32d8b16ee4fd58ff49514b58710cbbddecadec00100335ced88ce606"
MAX_BYTES = 256 * 1024
CONTEXT_SAFETY_CAP = 131072  # Local operator policy, NOT a claim of provider context capacity.
OUTPUT_CAP = 1200
FRAMING_ALLOWANCE = 4096
ATTEMPTS = 3
URL = "https://api.openai.com/v1/responses"
CODE_FILES = (
    "category_machine_execution.py",
    "category_coverage_review.py",
    "machine_judge.py",
    "machine_blind_contracts.py",
    "machine_blind_review.py",
    "blind_review.py",
    "json_codec.py",
    "ground_truth_snapshot.py",
)


class Prices(Closed):
    currency: Literal["USD"]
    input_per_million: str = Field(pattern=r"^\d+(\.\d+)?$")
    output_per_million: str = Field(pattern=r"^\d+(\.\d+)?$")


class PassApproval(Closed):
    # Aliases match the actual CLI identifiers, with C expressly forbidden.
    a: Literal["approved"] = Field(alias="machine-a")
    b: Literal["approved"] = Field(alias="machine-b")
    c: Literal["forbidden"] = Field(alias="machine-c")


class Approval(Closed):
    schema_version: Literal["category-two-pass-approval-v1"]
    authorization: Literal["explicit-operator-cost-approval"]
    approval_reference: str = Field(min_length=1, max_length=500)
    model: Literal[MODEL]
    packet_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    prompt_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    contract_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    cost_report_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    pair_count: Literal[1506]
    pass_count: Literal[2]
    request_count: Literal[3012]
    passes: PassApproval
    max_input_tokens: StrictInt = Field(gt=0)
    max_output_tokens: StrictInt = Field(gt=0)
    max_amount_usd: str | None = Field(default=None, pattern=r"^\d+(\.\d+)?$")
    execution_root: str = Field(min_length=1)
    operator: str | None = None
    approved_at: str | None = None


class CategoryJudge(OpenAIJudge):
    """Reuse transport with this workflow's narrower retry policy (no HTTP 408 retry)."""

    def __init__(self, key, *, transport=None):
        super().__init__(key, transport=transport)

        async def reject_nontransient(response):
            if response.status_code == 408:
                raise APIError("http_rejected")

        self.client.event_hooks["response"] = [reject_nontransient]


def code_hashes():
    return {
        **{n: sha(Path(__file__).with_name(n).read_bytes()) for n in CODE_FILES},
        "uv.lock": sha(Path("uv.lock").read_bytes()),
    }


def load_packet(package):
    # The execution worker only loads the frozen blind files, never rankings or labels.
    packet_file = package / "reviewer/blind-candidates.jsonl"
    metadata_file = package / "reviewer/annotation-package.json"
    require(sha(packet_file.read_bytes()) == PACKET_SHA, "packet_changed")
    require(sha(metadata_file.read_bytes()) == META_SHA, "metadata_changed")
    rows, meta = read_lines(packet_file), read(metadata_file)
    require(len(rows) == len({r["annotation_id"] for r in rows}) == meta["count"] == COUNT, "count")
    require(digest(rows) == meta["packet_sha256"], "packet_digest")
    for r in rows:
        BlindCandidate.model_validate(r)
    return rows, meta


def request_for(candidate, model, prompt):
    require(model == MODEL, "exact_model_required")
    # Reuse the closed generic blind projection with the established 77-pair answer schema.
    return api_payload(candidate, {"model": model}, prompt, schema())


def wire(request):
    # This is httpx's actual json= serialization used by the unchanged OpenAIJudge transport.
    return httpx.Request("POST", URL, json=request).content


def shape(candidate, model, prompt):
    request = request_for(candidate, model, prompt)
    data = wire(request)
    estimate = len(data) + FRAMING_ALLOWANCE
    return {
        "annotation_id": candidate["annotation_id"],
        "payload_sha256": sha(data),
        "payload_bytes": len(data),
        "estimated_input_tokens": estimate,
        "estimated_output_tokens": OUTPUT_CAP,
        "oversized": len(data) > MAX_BYTES or estimate + OUTPUT_CAP > CONTEXT_SAFETY_CAP,
    }


def distribution(values):
    values = sorted(values)
    return {
        "min": min(values),
        **{f"p{p}": values[math.ceil(len(values) * p / 100) - 1] for p in (50, 90, 95, 99)},
        "max": max(values),
    }


def amount(input_tokens, output_tokens, prices):
    return str(
        (
            Decimal(input_tokens) * Decimal(prices["input_per_million"])
            + Decimal(output_tokens) * Decimal(prices["output_per_million"])
        )
        / Decimal(1000000)
    )


def cost_report(shapes, contract, mapping, categories, prices=None):
    if prices is not None:
        prices = Prices.model_validate(prices).model_dump()
    total = sum(r["estimated_input_tokens"] for r in shapes)
    output = len(shapes) * OUTPUT_CAP
    by_query, by_category = {}, {}
    for r in shapes:
        cid = mapping[r["annotation_id"]]
        cat = categories[cid]
        for key, table in ((cid, by_query), (cat, by_category)):
            row = table.setdefault(
                key, {"pairs": 0, "input_tokens_per_pass": 0, "input_tokens_two_passes": 0}
            )
            row["pairs"] += 1
            row["input_tokens_per_pass"] += r["estimated_input_tokens"]
            row["input_tokens_two_passes"] += 2 * r["estimated_input_tokens"]
            row["output_token_ceiling_two_passes"] = row["pairs"] * OUTPUT_CAP * 2
            row["estimated_total_tokens_two_passes"] = (
                row["input_tokens_two_passes"] + row["output_token_ceiling_two_passes"]
            )
    return {
        "schema_version": "category-two-pass-cost-v1",
        "model": contract["model"],
        "packet_sha256": PACKET_SHA,
        "prompt_sha256": contract["prompt_sha256"],
        "pair_count": COUNT,
        "pass_count": 2,
        "planned_requests": COUNT * 2,
        "estimation_method": "httpx-json-utf8-bytes-plus-4096-framing-v1",
        "tokenizer": "no model-specific tokenizer available in locked local environment",
        "method_limit": (
            "Conservative estimate, not provider-tokenizer measurement or guaranteed billing. "
            "One input token per serialized UTF-8 byte including schema/envelope, plus 4096 "
            "framing allowance. Output uses the configured maximum, not a predicted mean."
        ),
        "per_pass": {
            p: {
                "requests": COUNT,
                "estimated_input_tokens": total,
                "estimated_output_tokens": output,
                "max_output_tokens_per_request": OUTPUT_CAP,
                "estimated_total_tokens": total + output,
                "input_tokens_per_request": distribution(
                    [r["estimated_input_tokens"] for r in shapes]
                ),
                "estimated_output_tokens_per_request": OUTPUT_CAP,
            }
            for p in PASSES
        },
        "estimated_input_tokens": total * 2,
        "estimated_output_token_ceiling": output * 2,
        "estimated_total_tokens": (total + output) * 2,
        "input_tokens_per_request": distribution([r["estimated_input_tokens"] for r in shapes]),
        "payload_bytes_per_request": distribution([r["payload_bytes"] for r in shapes]),
        "top20_largest_requests": sorted(
            shapes, key=lambda r: (-r["estimated_input_tokens"], r["annotation_id"])
        )[:20],
        "per_query": by_query,
        "per_category": by_category,
        "retry_ceiling": {
            "max_attempts_per_pair_per_pass": ATTEMPTS,
            "maximum_http_attempts": COUNT * 2 * ATTEMPTS,
            "estimated_input_tokens": total * 2 * ATTEMPTS,
            "output_token_ceiling": output * 2 * ATTEMPTS,
            "requires_additional_budget": True,
        },
        "operator_prices": prices,
        "estimated_amount_usd": amount(total * 2, output * 2, prices) if prices else None,
        "retry_ceiling_amount_usd": amount(total * 2 * ATTEMPTS, output * 2 * ATTEMPTS, prices)
        if prices
        else None,
    }


def contract_for(model, prompt):
    binding = digest({"model": model, "packet": PACKET_SHA, "prompt": sha(prompt.encode())})[:20]
    contract = {
        "schema_version": "category-two-pass-execution-v1",
        "status": "prepared-not-approved",
        "baseline_main": BASELINE,
        "model": model,
        "pair_count": COUNT,
        "passes": list(PASSES),
        "pass_count": 2,
        "planned_requests": COUNT * 2,
        "machine-c": "disabled",
        "adjudication": "separate later task, conflicts only",
        "packet_sha256": PACKET_SHA,
        "metadata_sha256": META_SHA,
        "review_plan_sha256": PLAN_SHA,
        "prompt_sha256": sha(prompt.encode()),
        "prompt_source": str(PROMPT),
        "prompt_version": "focused-judge-v1-unchanged",
        "response_schema_sha256": digest(schema()),
        "parameters": {
            "temperature": 0,
            "reasoning": {"effort": "none"},
            "max_output_tokens": OUTPUT_CAP,
            "store": False,
            "seed": None,
            "tools": "none",
            "history": "none",
        },
        "safety_policy": {
            "maximum_http_payload_bytes": MAX_BYTES,
            "estimated_context_token_cap": CONTEXT_SAFETY_CAP,
            "provider_limit_verified": False,
            "automatic_truncation": False,
        },
        "run_ids": {p: f"category-{binding}-{p}" for p in PASSES},
        "code_sha256": code_hashes(),
    }
    return contract


def prepare(package, output, model, prices=None):
    require(model == MODEL, "exact_model_required")
    require(not output.exists(), "new_destination_required")
    require(not output.resolve().is_relative_to(package.resolve()), "sealed_pool_directory")
    # Preparation may read operator metadata for count/category token statistics only.
    plan, packet = checked(package)
    require(sha((package / "review-plan.json").read_bytes()) == PLAN_SHA, "review_plan_changed")
    require(load_packet(package)[0] == packet, "packet_binding")
    selection = read(package / "selection-report.json")
    categories = {r["case_id"]: r["category"] for r in selection["cases"]}
    require(len(categories) == len(set(plan["case_ids"])) == 20, "query_count")
    require(
        set(categories.values()) == {"outdoor", "theatre", "venue", "accessibility"}, "categories"
    )
    require(not plan["atmosphere_overlap"], "atmosphere_forbidden")
    prompt = PROMPT.read_text()
    contract = contract_for(model, prompt)
    shapes = [shape(c, model, prompt) for c in packet]
    oversized = [r["annotation_id"] for r in shapes if r["oversized"]]
    report = cost_report(
        shapes,
        contract,
        {m["annotation_id"]: m["case_id"] for m in plan["mapping"]},
        categories,
        prices,
    )
    for name, value in (
        ("execution-contract.json", contract),
        ("cost-report.json", report),
        ("request-shape-report.json", {"requests_per_pass": shapes, "oversized": oversized}),
        ("response-schema.json", schema()),
        ("approval-schema.json", Approval.model_json_schema()),
        ("prompt-binding.json", {"source": str(PROMPT), "sha256": contract["prompt_sha256"]}),
    ):
        atomic_new(output / name, value)
    atomic_new(
        output / "artifact-sha256.json",
        {"files": {p.name: sha(p.read_bytes()) for p in sorted(output.iterdir())}},
    )
    require(not oversized, "oversized_requests_reported_no_execution")
    return report


def load_execution(package, directory, model):
    require(model == MODEL, "exact_model_required")
    packet, _ = load_packet(package)
    index = read(directory / "artifact-sha256.json")
    names = {
        "execution-contract.json",
        "cost-report.json",
        "request-shape-report.json",
        "response-schema.json",
        "approval-schema.json",
        "prompt-binding.json",
    }
    require(set(index["files"]) == names, "execution_artifact_set")
    for name, checksum in index["files"].items():
        require(sha((directory / name).read_bytes()) == checksum, "execution_artifact_changed")
    c, cost = read(directory / "execution-contract.json"), read(directory / "cost-report.json")
    require(c["code_sha256"] == code_hashes(), "execution_code_changed")
    require(c == contract_for(model, PROMPT.read_text()), "execution_contract_changed")
    require(
        c["model"] == model
        and c["passes"] == list(PASSES)
        and c["pass_count"] == 2
        and c["pair_count"] == COUNT
        and c["planned_requests"] == COUNT * 2
        and c["machine-c"] == "disabled",
        "two_pass_contract",
    )
    require(c["packet_sha256"] == PACKET_SHA and c["metadata_sha256"] == META_SHA, "pool_binding")
    prompt = PROMPT.read_text()
    require(sha(prompt.encode()) == c["prompt_sha256"], "prompt_changed")
    require(read(directory / "response-schema.json") == schema(), "response_schema_changed")
    require(
        read(directory / "approval-schema.json") == Approval.model_json_schema(),
        "approval_schema_changed",
    )
    shapes = [shape(p, model, prompt) for p in packet]
    require(
        read(directory / "request-shape-report.json")
        == {"requests_per_pass": shapes, "oversized": []},
        "request_shape_changed_or_oversized",
    )
    require(
        cost["packet_sha256"] == PACKET_SHA and cost["prompt_sha256"] == c["prompt_sha256"],
        "cost_binding",
    )
    require(
        cost["estimated_input_tokens"] == 2 * sum(s["estimated_input_tokens"] for s in shapes),
        "input_cost_changed",
    )
    require(cost["estimated_output_token_ceiling"] == 2 * COUNT * OUTPUT_CAP, "output_cost_changed")
    return c, cost, packet, prompt, shapes


def approve(raw, contract, directory, pass_name, output):
    require(pass_name in PASSES, "pass_c_forbidden")
    a = Approval.model_validate(raw).model_dump(by_alias=True)
    require(
        all(type(raw[k]) is int for k in ("pair_count", "pass_count", "request_count")),
        "integer_counts",
    )
    require(a["approval_reference"].strip(), "approval_reference")
    for key in ("model", "packet_sha256", "prompt_sha256", "pair_count", "pass_count"):
        require(a[key] == contract[key], "approval_binding")
    require(
        a["contract_sha256"] == sha((directory / "execution-contract.json").read_bytes()),
        "approval_contract",
    )
    require(
        a["cost_report_sha256"] == sha((directory / "cost-report.json").read_bytes()),
        "approval_cost",
    )
    root = Path(a["execution_root"])
    require(
        root.is_absolute() and output.resolve() == root.resolve() / pass_name,
        "approved_destination",
    )
    require(
        not root.resolve().is_relative_to(Path("benchmark").resolve()),
        "execution_outside_benchmark",
    )
    cost = read(directory / "cost-report.json")
    require(a["max_input_tokens"] >= cost["estimated_input_tokens"], "input_budget_too_small")
    require(
        a["max_output_tokens"] >= cost["estimated_output_token_ceiling"], "output_budget_too_small"
    )
    if a["max_amount_usd"] is not None:
        require(cost["operator_prices"] is not None, "amount_requires_prices")
        require(
            Decimal(amount(a["max_input_tokens"], a["max_output_tokens"], cost["operator_prices"]))
            <= Decimal(a["max_amount_usd"]),
            "amount_budget_too_small",
        )
    return a


def timestamp():
    return datetime.now(UTC).isoformat()


async def execute(
    package,
    directory,
    output,
    model,
    pass_name,
    approval,
    client,
    *,
    resume=False,
    sleep=asyncio.sleep,
):
    require(pass_name in PASSES, "pass_c_forbidden")
    c, cost, packet, prompt, shapes = load_execution(package, directory, model)
    a = approve(approval, c, directory, pass_name, output)
    config = {
        "contract_sha256": sha((directory / "execution-contract.json").read_bytes()),
        "approval_sha256": digest(a),
        "code_sha256": code_hashes(),
        "pass_name": pass_name,
        "run_id": c["run_ids"][pass_name],
        "model": model,
        "packet_sha256": PACKET_SHA,
        "prompt_sha256": c["prompt_sha256"],
        "provenance": "machine_proposed",
    }
    require(not output.exists() or resume, "explicit_resume_required")
    output.mkdir(parents=True, exist_ok=True)
    with (output / ".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        manifest = output / "manifest.json"
        if manifest.exists():
            require(read(manifest)["configuration"] == config, "resume_identity_changed")
        else:
            require(not resume, "resume_manifest_missing")
            atomic_new(manifest, {"configuration": config, "started_at": timestamp()})
        # Reserve full conservative estimated cost even for interrupted/failed attempts.
        # Budgets are split equally: separate A/B directories cannot double-spend a shared cap.
        shape_by_id = {s["annotation_id"]: s for s in shapes}
        require(
            {p.stem for p in (output / "records").glob("*.json")} <= set(shape_by_id),
            "unknown_saved_record",
        )
        charged_input, charged_output, seen_responses = 0, 0, set()
        for path in sorted((output / "attempts").glob("*.request.json")):
            m = read(path)
            require(m["configuration_sha256"] == digest(config), "attempt_identity")
            require(m["annotation_id"] in shape_by_id, "attempt_id")
            require(
                type(m["attempt"]) is int
                and 1 <= m["attempt"] <= ATTEMPTS
                and path.name == f"{m['annotation_id']}-{m['attempt']}.request.json",
                "attempt_filename",
            )
            s = shape_by_id[m["annotation_id"]]
            require(m["payload_sha256"] == s["payload_sha256"], "attempt_payload")
            require(
                m["reserved_input_tokens"] == s["estimated_input_tokens"]
                and m["reserved_output_tokens"] == OUTPUT_CAP,
                "reservation_changed",
            )
            charged_input += m["reserved_input_tokens"]
            charged_output += m["reserved_output_tokens"]
        for candidate in packet:
            aid = candidate["annotation_id"]
            s = shape_by_id[aid]
            request = request_for(candidate, model, prompt)
            require(sha(wire(request)) == s["payload_sha256"], "wire_payload_changed")
            final = output / "records" / f"{aid}.json"
            if final.exists():
                record = read(final)
                verify_record(record, candidate, config, model, output, seen_responses)
                continue
            for attempt in range(1, ATTEMPTS + 1):
                stem = f"{aid}-{attempt}"
                reservation = output / "attempts" / f"{stem}.request.json"
                completion = output / "attempts" / f"{stem}.result.json"
                if reservation.exists():
                    require(completion.exists(), "interrupted_attempt_requires_operator_audit")
                    previous = read(completion)
                    if previous["status"] == "success":
                        record = previous["record"]
                        verify_record(record, candidate, config, model, output, seen_responses)
                        atomic_new(final, record)
                        break
                    require(
                        previous["retryable"]
                        and previous["error_category"]
                        in {"network", "rate_limit", "temporary_http"},
                        "previous_terminal_failure",
                    )
                    continue
                require(
                    charged_input + s["estimated_input_tokens"] <= a["max_input_tokens"] // 2,
                    "approved_input_budget_exhausted",
                )
                require(
                    charged_output + OUTPUT_CAP <= a["max_output_tokens"] // 2,
                    "approved_output_budget_exhausted",
                )
                client_id = str(uuid5(NAMESPACE_URL, f"{digest(config)}:{aid}:{attempt}"))
                meta = {
                    "configuration_sha256": digest(config),
                    "annotation_id": aid,
                    "attempt": attempt,
                    "client_request_id": client_id,
                    "payload_sha256": s["payload_sha256"],
                    "reserved_input_tokens": s["estimated_input_tokens"],
                    "reserved_output_tokens": OUTPUT_CAP,
                    "started_at": timestamp(),
                }
                atomic_new(reservation, meta)
                charged_input += s["estimated_input_tokens"]
                charged_output += OUTPUT_CAP
                started, usage, response_id, request_id = time.monotonic(), {}, None, None
                try:
                    body, request_id = await client.request("POST", "responses", request, client_id)
                    usage, response_id = usage_of(body), safe_id(body.get("id"))
                    answer = parse(body, candidate, model)
                    require(
                        usage["input_tokens"] + usage["output_tokens"] == usage["total_tokens"],
                        "usage_total",
                    )
                    require(
                        response_id and response_id not in seen_responses,
                        "duplicate_or_missing_response_id",
                    )
                    require(
                        usage["input_tokens"] <= s["estimated_input_tokens"]
                        and usage["output_tokens"] <= OUTPUT_CAP,
                        "usage_exceeds_reservation",
                    )
                    body_path = output / "responses" / f"{stem}.json"
                    atomic_new(body_path, body)
                    record = {
                        **meta,
                        "answer": answer,
                        "response_id": response_id,
                        "request_id": request_id,
                        "response_file": f"responses/{stem}.json",
                        "response_sha256": sha(body_path.read_bytes()),
                        "usage": usage,
                        "latency_ms": (time.monotonic() - started) * 1000,
                        "retry_count": attempt - 1,
                        "completed_at": timestamp(),
                    }
                    atomic_new(completion, {"status": "success", "record": record})
                    atomic_new(final, record)
                    seen_responses.add(response_id)
                    break
                except (APIError, ValueError, KeyError, TypeError, AttributeError) as error:
                    retry = (
                        isinstance(error, APIError)
                        and error.retry
                        and error.category in {"network", "rate_limit", "temporary_http"}
                    )
                    category = (
                        error.category if isinstance(error, APIError) else "response_contract"
                    )
                    atomic_new(
                        completion,
                        {
                            **meta,
                            "status": "failed",
                            "retryable": retry,
                            "error_category": category,
                            "usage": usage,
                            "response_id": response_id,
                            "request_id": request_id or getattr(error, "request_id", None),
                            "latency_ms": (time.monotonic() - started) * 1000,
                            "completed_at": timestamp(),
                        },
                    )
                    if not retry:
                        raise APIError(category) from None
                    if attempt < ATTEMPTS:
                        await sleep(2**attempt)
            require(final.exists(), "attempt_budget_exhausted")
        return {"pass_name": pass_name, "accepted": len(packet), "run_id": config["run_id"]}


def verify_record(record, candidate, config, model, output, seen):
    require(record["configuration_sha256"] == digest(config), "record_identity")
    require(record["annotation_id"] == candidate["annotation_id"], "record_id")
    relative = Path(record["response_file"])
    require(
        relative.parts == ("responses", f"{candidate['annotation_id']}-{record['attempt']}.json"),
        "response_path",
    )
    require(type(record["attempt"]) is int and 1 <= record["attempt"] <= ATTEMPTS, "record_attempt")
    stem = f"{candidate['annotation_id']}-{record['attempt']}"
    reservation = read(output / "attempts" / f"{stem}.request.json")
    require(all(record.get(k) == v for k, v in reservation.items()), "record_reservation")
    require(
        read(output / "attempts" / f"{stem}.result.json")
        == {"status": "success", "record": record},
        "record_completion",
    )
    path = output / relative
    require(sha(path.read_bytes()) == record["response_sha256"], "response_changed")
    body = read(path)
    require(parse(body, candidate, model) == record["answer"], "record_answer_changed")
    require(
        record["usage"] == usage_of(body) and record["response_id"] == safe_id(body.get("id")),
        "record_response_identity",
    )
    require(record["response_id"] and record["response_id"] not in seen, "duplicate_response_id")
    seen.add(record["response_id"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("dry-run", "validate", "run"))
    parser.add_argument("--package", type=Path, default=PACKAGE)
    parser.add_argument("--contract", type=Path, default=DEST)
    parser.add_argument("--model", required=True, choices=(MODEL,))
    parser.add_argument("--output", type=Path)
    parser.add_argument("--pass-name", choices=PASSES)
    parser.add_argument("--approval", type=Path)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--input-price-per-million")
    parser.add_argument("--output-price-per-million")
    args = parser.parse_args()
    try:
        if args.command == "dry-run":
            require(args.output, "output_required")
            prices = None
            require(
                bool(args.input_price_per_million) == bool(args.output_price_per_million),
                "both_prices_required",
            )
            if args.input_price_per_million:
                prices = {
                    "currency": "USD",
                    "input_per_million": args.input_price_per_million,
                    "output_per_million": args.output_price_per_million,
                }
            report = prepare(args.package, args.output, args.model, prices)
            print(
                f"Offline dry-run: {report['planned_requests']} planned requests; "
                "no judgments or approval."
            )
        elif args.command == "validate":
            load_execution(args.package, args.contract, args.model)
            print("Valid two-pass contract; no execution authorized.")
        else:
            require(
                args.approval and args.pass_name and args.output, "approval_pass_output_required"
            )
            raw = read(args.approval)
            c, _, _, _, _ = load_execution(args.package, args.contract, args.model)
            approve(raw, c, args.contract, args.pass_name, args.output)  # before client/key/network

            async def real_run():
                client = CategoryJudge(os.environ.get("OPENAI_API_KEY"))
                try:
                    return await execute(
                        args.package,
                        args.contract,
                        args.output,
                        args.model,
                        args.pass_name,
                        raw,
                        client,
                        resume=args.resume,
                    )
                finally:
                    await client.close()

            print(asyncio.run(real_run()))
    except (
        APIError,
        ValueError,
        KeyError,
        TypeError,
        FileNotFoundError,
        FileExistsError,
        BlockingIOError,
    ):
        parser.exit(
            2,
            "Stopped: frozen input, contract, approval, budget, resume or provider "
            "validation failed. No fallback.\n",
        )


if __name__ == "__main__":
    main()
