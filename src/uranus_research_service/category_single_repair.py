"""One explicitly approved repair of one frozen rejected receipt; no continuation."""

import argparse
import asyncio
import fcntl
import json
import os
from contextlib import contextmanager
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from time import monotonic
from typing import Literal
from uuid import NAMESPACE_URL, uuid5

from pydantic import Field, StrictBool, StrictInt

from uranus_research_service import category_pair_execution as execution
from uranus_research_service.machine_blind_contracts import OCCURRENCE_FIELDS
from uranus_research_service.machine_judge import (
    APIError,
    Closed,
    atomic_new,
    digest,
    read,
    require,
    safe_id,
    sha,
)

budget = execution.budget
BASELINE = "dc59e8f65f8bebb8d2aca3a6da1a0f832585be1d"
ORIGINAL = Path("benchmark/review/category-coverage-machine-ab-v1")
DEST = ORIGINAL / "repair-v1"
BUNDLE_SHA = "1b011c47137b55aad791764867f7cdc3257f61a84e3e09a2a1bf43225faa3990"
RECEIPT_SHA = "7dd1398cdbc167eca1196a1ecfdec0bd711be5dfb964787fd83de03317ccbc43"
STATE_SHA = "20b3b8ac2cbf23f4d5893c86fd7af731ac28256ab3b474cb43ecdd6bc88ac23e"
ANNOTATION = "a0c166936ef7233017150f87aad87df5"
OCCURRENCE = "01a09f75-4a2d-7acd-b306-c188c8261312"
ROOT = "/tmp/category-pair-single-repair-v1-run"
MODEL = budget.legacy.MODEL


class Approval(Closed):
    schema_version: Literal["category-single-repair-approval-v1"]
    approved: StrictBool
    approval_reference: str = Field(min_length=1, max_length=1000)
    annotation_id: Literal[ANNOTATION]
    pass_name: Literal["machine-b"]
    original_receipt_sha256: str
    original_run_bundle_sha256: str
    original_failure_state_sha256: str
    repair_contract_sha256: str
    model: Literal[MODEL]
    prompt_sha256: str
    packet_sha256: str
    max_requests: StrictInt = Field(ge=1, le=1)
    max_amount_usd: Literal["0.10"]
    max_input_tokens: StrictInt
    max_output_tokens: StrictInt
    execution_root: str
    original_receipt_may_not_be_overwritten: StrictBool
    validator_may_not_be_relaxed: StrictBool


def original_context():
    path = ORIGINAL / "results/run-bundle.json"
    require(sha(path.read_bytes()) == BUNDLE_SHA, "original_bundle_changed")
    state = execution.validate_bundle(path)
    require(digest(state) == STATE_SHA, "original_state_changed")
    require(state["status"] == "request_failed_partial", "original_status")
    files = read(path)["files"]
    receipt_text = files[f"machine-b/responses/{ANNOTATION}.json"]
    require(sha(receipt_text.encode()) == RECEIPT_SHA, "original_receipt_changed")
    receipt = json.loads(receipt_text)
    attempt = json.loads(files[f"machine-b/attempts/{ANNOTATION}.json"])
    old_approval = json.loads(files["journal/000000.json"])["operation"]["approval"]
    require(digest(old_approval) == state["approval_sha256"], "original_approval_changed")
    c, order = budget.load(budget.DEST)
    packet, _ = budget.legacy.load_packet(budget.legacy.PACKAGE)
    candidate = next(p for p in packet if p["annotation_id"] == ANNOTATION)
    row = order["pairs"][state["completed_pairs"]]
    require(row["annotation_id"] == ANNOTATION, "original_order")
    require(
        state["current"]["passes"] == {"machine-a": "settled", "machine-b": "in_flight"},
        "original_pair_status",
    )
    try:
        budget.parse(receipt, candidate, MODEL)
    except ValueError as exc:
        require(str(exc) == "empty_occurrence_field", "original_failure_changed")
    else:
        raise ValueError("original_failure_missing")
    answer = json.loads(receipt["output"][0]["content"][0]["text"])
    require(
        "venue_accessibility" in answer["supporting_fields"]
        and OCCURRENCE in answer["occurrence_ids"],
        "original_failure_evidence",
    )
    require(
        not next(o for o in candidate["event"]["occurrences"] if o["id"] == OCCURRENCE)[
            "venue_accessibility"
        ],
        "original_field_not_empty",
    )
    prompt = budget.legacy.PROMPT.read_text()
    require(
        "Positive grades require supporting_fields naming actual nonempty fields" in prompt,
        "prompt_policy",
    )
    payload = budget.legacy.request_for(candidate, MODEL, prompt)
    require(
        sha(budget.legacy.wire(payload)) == attempt["payload_sha256"] == row["payload_sha256"],
        "original_payload_changed",
    )
    measured = budget.usage(receipt)
    old_cost = budget.price(
        measured["input_tokens"],
        measured["output_tokens"],
        measured["cached_input_tokens"] or 0,
        c["prices"],
    )
    all_cost = Decimal(0)
    original_hashes = {str(path): BUNDLE_SHA}
    for name, value in read(ORIGINAL / "artifact-sha256.json").items():
        source = ORIGINAL / name
        require(sha(source.read_bytes()) == value, "historical_artifact_changed")
        original_hashes[str(source)] = value
    original_hashes[str(ORIGINAL / "artifact-sha256.json")] = sha(
        (ORIGINAL / "artifact-sha256.json").read_bytes()
    )
    for name, text in files.items():
        if "/responses/" in name:
            u = budget.usage(json.loads(text))
            all_cost += budget.price(
                u["input_tokens"], u["output_tokens"], u["cached_input_tokens"] or 0, c["prices"]
            )
    return (
        {
            "original_run_bundle_sha256": BUNDLE_SHA,
            "original_receipt_sha256": RECEIPT_SHA,
            "original_response_id": receipt["id"],
            "original_client_request_id": attempt["client_request_id"],
            "annotation_id": ANNOTATION,
            "pass_name": "machine-b",
            "original_failure_validator": "empty_occurrence_field",
            "original_empty_field": "venue_accessibility",
            "original_occurrence_id": OCCURRENCE,
            "original_failure_state_sha256": STATE_SHA,
            "original_approval_sha256": digest(old_approval),
            "original_prompt_sha256": c["prompt_sha256"],
            "packet_sha256": c["packet_sha256"],
            "model": MODEL,
            "original_usage": measured,
            "original_request_cost_usd": str(old_cost),
            "original_run_usage_cost_usd": str(all_cost),
            "original_request_status": "rejected",
            "original_hashes": original_hashes,
            "original_completed_pairs": state["completed_pairs"],
            "original_dispatched_requests": state["dispatched_requests"],
            "original_outstanding_reservation_usd": state["outstanding_usd"],
        },
        candidate,
        payload,
        row,
        c,
        state,
    )


def contract_data():
    original, candidate, payload, row, old, state = original_context()
    contract = {
        "schema_version": "category-single-repair-contract-v1",
        "baseline_main": BASELINE,
        **original,
        "repair_attempt": 1,
        "max_requests": 1,
        "max_amount_usd": "0.10",
        "max_input_tokens": row["estimated_input_tokens"],
        "max_output_tokens": 1200,
        "prompt_sha256": original["original_prompt_sha256"],
        "prompt_changed": False,
        "prompt_policy": "Explicit positive-grade nonempty-field instruction; unchanged.",
        "parameters": old["parameters"],
        "prices": old["prices"],
        "repair_run_id": "repair-v1-" + digest([STATE_SHA, ANNOTATION])[:24],
        "repair_client_request_id": str(
            uuid5(NAMESPACE_URL, "category-single-repair-v1:" + RECEIPT_SHA)
        ),
        "payload_sha256": sha(budget.legacy.wire(payload)),
        "execution_root": ROOT,
        "conservative_request_ceiling_usd": str(budget.reservation_cost(row, old)),
        "code_sha256": {
            **budget.code_hashes(),
            "category_pair_execution.py": sha(Path(execution.__file__).read_bytes()),
            "category_single_repair.py": sha(Path(__file__).read_bytes()),
        },
        "acceptance": "Original validators plus nonempty cited fields; no output repair.",
        "continuation": "Separate reviewed execution and new explicit approval required.",
        "consensus_allowed": False,
        "reevaluation_allowed": False,
        "astra_allowed": False,
    }
    require(Decimal(contract["conservative_request_ceiling_usd"]) <= Decimal("0.10"), "repair_cap")
    require(
        contract["repair_client_request_id"] != contract["original_client_request_id"],
        "new_client_id",
    )
    return contract, candidate, payload, state


def request_binding(c):
    return {
        k: c[k]
        for k in (
            "repair_run_id",
            "repair_client_request_id",
            "payload_sha256",
            "model",
            "prompt_sha256",
            "packet_sha256",
            "parameters",
        )
    }


def prepare(directory):
    require(not directory.exists(), "exclusive_preparation")
    c, _, _, _ = contract_data()
    atomic_new(directory / "repair-contract.json", c)
    atomic_new(directory / "repair-approval-schema.json", Approval.model_json_schema())
    atomic_new(directory / "repair-request-binding.json", request_binding(c))
    atomic_new(
        directory / "artifact-sha256.json",
        {p.name: sha(p.read_bytes()) for p in sorted(directory.iterdir()) if p.is_file()},
    )


def load(directory):
    expected, candidate, payload, state = contract_data()
    require(read(directory / "repair-contract.json") == expected, "repair_contract_changed")
    require(
        read(directory / "repair-approval-schema.json") == Approval.model_json_schema(),
        "approval_schema_changed",
    )
    require(
        read(directory / "repair-request-binding.json") == request_binding(expected),
        "request_binding_changed",
    )
    for name, value in read(directory / "artifact-sha256.json").items():
        require(sha((directory / name).read_bytes()) == value, "repair_artifact_hash")
    return expected, candidate, payload, state


def check_approval(raw, c, directory):
    value = Approval.model_validate(raw).model_dump()
    require(
        value["approved"]
        and value["original_receipt_may_not_be_overwritten"]
        and value["validator_may_not_be_relaxed"],
        "explicit_repair_approval_required",
    )
    for key in (
        "annotation_id",
        "pass_name",
        "original_receipt_sha256",
        "original_run_bundle_sha256",
        "original_failure_state_sha256",
        "model",
        "prompt_sha256",
        "packet_sha256",
        "max_requests",
        "max_amount_usd",
        "max_input_tokens",
        "max_output_tokens",
        "execution_root",
    ):
        require(value[key] == c[key], "approval_binding_" + key)
    require(
        value["repair_contract_sha256"] == sha((directory / "repair-contract.json").read_bytes()),
        "approval_contract_hash",
    )
    return value


def approve(directory, reference):
    c, _, _, _ = load(directory)
    values = {key: c[key] for key in Approval.model_fields if key in c}
    values.update(
        schema_version="category-single-repair-approval-v1",
        approved=True,
        approval_reference=reference,
        original_receipt_may_not_be_overwritten=True,
        validator_may_not_be_relaxed=True,
        repair_contract_sha256=sha((directory / "repair-contract.json").read_bytes()),
    )
    return check_approval(values, c, directory)


def nonempty(value):
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, dict):
        return any(nonempty(v) for v in value.values())
    if isinstance(value, list):
        return any(nonempty(v) for v in value)
    return value is not None and value is not False


def validate_response(body, candidate, c, original_state):
    require(body.get("service_tier") == "default", "unpriced_service_tier")
    answer = budget.parse(body, candidate, c["model"])
    response_id = safe_id(body.get("id"))
    require(
        response_id
        and response_id != c["original_response_id"]
        and response_id not in original_state["response_ids"],
        "new_response_id_required",
    )
    occurrences = [
        o for o in candidate["event"]["occurrences"] if o["id"] in answer["occurrence_ids"]
    ]
    for field in answer["supporting_fields"]:
        values = (
            [o.get(field) for o in occurrences]
            if field in OCCURRENCE_FIELDS
            else occurrences
            if field == "occurrences"
            else [candidate["event"].get(field)]
        )
        require(any(nonempty(v) for v in values), "repair_empty_supporting_field")
    u = budget.usage(body)
    require(
        u["input_tokens"] <= c["max_input_tokens"] and u["output_tokens"] <= c["max_output_tokens"],
        "repair_token_ceiling",
    )
    cost = budget.price(
        u["input_tokens"], u["output_tokens"], u["cached_input_tokens"] or 0, c["prices"]
    )
    require(cost <= Decimal(c["max_amount_usd"]), "repair_cost_ceiling")
    return answer, u, cost


def outcome(body, candidate, c, state, approval_hash, error=None):
    result = {
        "schema_version": "category-single-repair-outcome-v1",
        "repair_attempt": 1,
        "repair_run_id": c["repair_run_id"],
        "repair_status": "rejected",
        "original_request_status": "rejected",
        "approval_sha256": approval_hash,
        "original_failure_state_sha256": STATE_SHA,
        "original_receipt_sha256": RECEIPT_SHA,
        "repair_response_id": safe_id(body.get("id")) if isinstance(body, dict) else None,
        "repair_receipt_sha256": None,
        "failure_category": error or "response_contract_violation",
        "original_request_cost_usd": c["original_request_cost_usd"],
        "original_run_usage_cost_usd": c["original_run_usage_cost_usd"],
        "repair_usage": None,
        "repair_cost_usd": None,
        "cumulative_usage_cost_usd": None,
        "usage_status": "unknown",
        "consensus_allowed": False,
        "continuation_allowed": False,
    }
    if body is not None and not isinstance(body, dict):
        return result
    if body is not None:
        # Cost of a rejected response is still retained when measured and priced.
        try:
            u = budget.usage(body)
            require(body.get("service_tier") == "default", "unpriced_service_tier")
            cost = budget.price(
                u["input_tokens"], u["output_tokens"], u["cached_input_tokens"] or 0, c["prices"]
            )
            result.update(
                repair_usage=u,
                repair_cost_usd=str(cost),
                usage_status="measured",
                cumulative_usage_cost_usd=str(Decimal(c["original_run_usage_cost_usd"]) + cost),
            )
        except (ValueError, KeyError, TypeError, AttributeError):
            pass
        try:
            answer, _, _ = validate_response(body, candidate, c, state)
            result.update(repair_status="accepted", answer=answer, failure_category=None)
        except (ValueError, KeyError, TypeError, AttributeError):
            result["failure_category"] = "response_contract_violation"
    return result


def finish(root, c, candidate, state, approval_hash):
    require(not (root / "repair-outcome.json").exists(), "repair_already_finalized")
    receipt = root / "repair-receipt.json"
    transport = read(root / "repair-transport.json")
    body = read(receipt) if receipt.exists() else None
    result = outcome(body, candidate, c, state, approval_hash, transport["error_category"])
    if receipt.exists():
        result["repair_receipt_sha256"] = sha(receipt.read_bytes())
    atomic_new(root / "repair-outcome.json", result)
    atomic_new(
        root / "repair-reconciliation.json",
        reconciliation(result, state, sha((root / "repair-outcome.json").read_bytes())),
    )
    return result


def reconciliation(result, state, outcome_sha):
    return {
        "schema_version": "category-single-repair-reconciliation-v1",
        "original_failure_state_sha256": STATE_SHA,
        "original_machine_b_receipt": "rejected",
        "original_receipt_sha256": RECEIPT_SHA,
        "original_journal_unchanged": True,
        "repair_outcome_sha256": outcome_sha,
        "replacement_machine_b_receipt": result["repair_status"],
        "effective_response_source": "repair-v1" if result["repair_status"] == "accepted" else None,
        "effective_pair_completion": "repaired"
        if result["repair_status"] == "accepted"
        else "incomplete",
        "repair_reconciliation_status": "ready_for_reviewed_continuation"
        if result["repair_status"] == "accepted"
        else "blocked",
        "effective_completed_pairs": state["completed_pairs"]
        + (result["repair_status"] == "accepted"),
        "original_dispatched_requests": state["dispatched_requests"],
        "repair_dispatches": 1,
        "original_ledger_status": state["status"],
        "original_reservation_unchanged_usd": state["outstanding_usd"],
        "continuation_requires_new_approval_and_reviewed_execution": True,
        "consensus_allowed": False,
        "reevaluation_allowed": False,
    }


@contextmanager
def single_run(root):
    require(
        root.is_absolute() and not root.resolve().is_relative_to(Path("benchmark").resolve()),
        "external_root",
    )
    root.mkdir(parents=True, exist_ok=True)
    with (root / ".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        require(not list(root.glob("*.json")), "repair_already_started_no_resend")
        yield


async def execute(directory, approval_path, *, judge_factory=None):
    c, candidate, payload, state = load(directory)
    approval = check_approval(read(approval_path), c, directory)
    root = Path(c["execution_root"])
    key = os.environ.get("OPENAI_API_KEY", "")
    require(bool(key), "OPENAI_API_KEY_required")
    with single_run(root):
        atomic_new(root / "repair-approval.json", approval)
        atomic_new(
            root / "repair-attempt.json",
            {
                "schema_version": "category-single-repair-attempt-v1",
                "repair_attempt": 1,
                "repair_status": "pending",
                "repair_run_id": c["repair_run_id"],
                "repair_client_request_id": c["repair_client_request_id"],
                "payload_sha256": c["payload_sha256"],
                "approval_sha256": digest(approval),
                "repair_contract_sha256": approval["repair_contract_sha256"],
                "started_at": datetime.now(UTC).isoformat(),
            },
        )
        started = monotonic()
        judge = (judge_factory or budget.legacy.CategoryJudge)(key)
        try:
            try:
                body, request_id = await judge.request(
                    "POST", "responses", payload, c["repair_client_request_id"]
                )
            except APIError as exc:
                transport = {
                    "status": "failed",
                    "error_category": exc.category,
                    "request_id": exc.request_id,
                }
            else:
                atomic_new(root / "repair-receipt.json", body)
                transport = {
                    "status": "response_received",
                    "error_category": None,
                    "request_id": request_id,
                }
            transport["latency_seconds"] = monotonic() - started
            atomic_new(root / "repair-transport.json", transport)
            return finish(root, c, candidate, state, digest(approval))
        finally:
            await judge.close()


def verify_run(directory, root):
    c, candidate, _, state = load(directory)
    approval = check_approval(read(root / "repair-approval.json"), c, directory)
    attempt = read(root / "repair-attempt.json")
    timestamp = attempt.pop("started_at")
    require(datetime.fromisoformat(timestamp).tzinfo is not None, "attempt_time")
    require(
        attempt
        == {
            "schema_version": "category-single-repair-attempt-v1",
            "repair_attempt": 1,
            "repair_status": "pending",
            "repair_run_id": c["repair_run_id"],
            "repair_client_request_id": c["repair_client_request_id"],
            "payload_sha256": c["payload_sha256"],
            "approval_sha256": digest(approval),
            "repair_contract_sha256": approval["repair_contract_sha256"],
        },
        "attempt_binding",
    )
    transport = read(root / "repair-transport.json")
    require(
        set(transport) == {"status", "error_category", "request_id", "latency_seconds"},
        "transport_schema",
    )
    require(
        type(transport["latency_seconds"]) in (int, float)
        and 0 <= transport["latency_seconds"] < float("inf"),
        "transport_latency",
    )
    receipt = root / "repair-receipt.json"
    require(
        (
            transport["status"] == "response_received"
            and transport["error_category"] is None
            and receipt.exists()
        )
        or (
            transport["status"] == "failed"
            and isinstance(transport["error_category"], str)
            and not receipt.exists()
        ),
        "transport_receipt_binding",
    )
    result = outcome(
        read(receipt) if receipt.exists() else None,
        candidate,
        c,
        state,
        digest(approval),
        transport["error_category"],
    )
    if receipt.exists():
        result["repair_receipt_sha256"] = sha(receipt.read_bytes())
    require(read(root / "repair-outcome.json") == result, "repair_outcome_changed")
    require(
        read(root / "repair-reconciliation.json")
        == reconciliation(result, state, sha((root / "repair-outcome.json").read_bytes())),
        "reconciliation_changed",
    )
    return result


def publish(directory, root, destination):
    result = verify_run(directory, root)
    names = [
        "repair-approval.json",
        "repair-attempt.json",
        "repair-transport.json",
        "repair-outcome.json",
        "repair-reconciliation.json",
    ]
    if (root / "repair-receipt.json").exists():
        names.append("repair-receipt.json")
    require(
        all(not (destination / n).exists() for n in names + ["repair-run-sha256.json"]),
        "exclusive_publish",
    )
    for name in names:
        atomic_new(destination / name, read(root / name))
        require(
            sha((destination / name).read_bytes()) == sha((root / name).read_bytes()),
            "publish_byte_identity",
        )
    atomic_new(
        destination / "repair-run-sha256.json",
        {n: sha((destination / n).read_bytes()) for n in sorted(names)},
    )
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, default=DEST)
    commands = parser.add_subparsers(dest="command", required=True)
    prep = commands.add_parser("prepare")
    prep.add_argument("--output", type=Path, default=DEST)
    commands.add_parser("validate")
    auth = commands.add_parser("approve")
    auth.add_argument("--reference", required=True)
    auth.add_argument("--output", type=Path, required=True)
    run = commands.add_parser("run")
    run.add_argument("--approval", type=Path, required=True)
    check = commands.add_parser("validate-run")
    check.add_argument("--run", type=Path, required=True)
    pub = commands.add_parser("publish")
    pub.add_argument("--run", type=Path, required=True)
    pub.add_argument("--output", type=Path, default=DEST)
    args = parser.parse_args()
    if args.command == "prepare":
        prepare(args.output)
    elif args.command == "approve":
        atomic_new(args.output, approve(args.contract, args.reference))
    elif args.command == "run":
        print(asyncio.run(execute(args.contract, args.approval))["repair_status"])
    elif args.command == "validate-run":
        print(verify_run(args.contract, args.run)["repair_status"])
    elif args.command == "publish":
        print(publish(args.contract, args.run, args.output)["repair_status"])
    else:
        load(args.contract)
        print("Prepared contract validated; no API calls.")


if __name__ == "__main__":
    main()
