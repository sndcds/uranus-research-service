"""Reviewed continuation of the frozen A/B partial run after accepted repair.

Append-only journal covering pairs 28..1505. Never mutates the original ledger
or repair artefacts. Separate approval, separate state machine, separate budget
accounting with no counter resets.
"""

import argparse
import asyncio
import os
from collections import Counter
from copy import deepcopy
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from time import monotonic
from typing import Literal
from uuid import NAMESPACE_URL, uuid5

from pydantic import Field, StrictBool, StrictInt

from uranus_research_service import category_pair_budget as budget
from uranus_research_service import category_pair_execution as execution
from uranus_research_service import category_single_repair as repair
from uranus_research_service.machine_blind_analysis import classify
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

BASELINE = "8aaf03823fb719f3c7c4b82415c53e6009947ddc"
ORIGINAL = Path("benchmark/review/category-coverage-machine-ab-v1")
REPAIR = ORIGINAL / "repair-v1"
DEST = Path("benchmark/review/category-coverage-machine-ab-continuation-v1")
MODEL = budget.legacy.MODEL
CAP = "12.00"
TOTAL_PAIRS = 1506
COMPLETED_EFF = 28
REMAINING = TOTAL_PAIRS - COMPLETED_EFF  # 1478
CONTINUATION_REQUEST_CAP = REMAINING * 2  # 2956

# Frozen SHA-256 bindings from the original and repair phases.
ORIG_BUNDLE_SHA = "1b011c47137b55aad791764867f7cdc3257f61a84e3e09a2a1bf43225faa3990"
ORIG_OUTCOME_SHA = "541a27a6e2038605f30546688f9a4a69f8cb58b9bb68578a736e78ca846a2277"
ORIG_APPROVAL_SHA = "52d9dc8b01acbeb07a60debd0a30d2077df8212dde91ce347f057b9a1781a870"
ORIG_FAILURE_STATE_SHA = "20b3b8ac2cbf23f4d5893c86fd7af731ac28256ab3b474cb43ecdd6bc88ac23e"
ORIG_RECEIPT_SHA = "7dd1398cdbc167eca1196a1ecfdec0bd711be5dfb964787fd83de03317ccbc43"
REPAIR_CONTRACT_SHA = "79a91d9ce3094f6f3599129aff117f9c2447a53102549af1ebee8202cef104b0"
REPAIR_RECEIPT_SHA = "c9e35848d70e12e01fe4d9986947f6e782117bdde7f368d2c5535cae6237f4a6"
REPAIR_OUTCOME_SHA = "26b3eb308605d9cebec950b362a93c2dd2095242c7e060ae7f55c6b00aa4f2c3"
REPAIR_RECON_SHA = "a2f74cfb524d36971d1a634188e0a6d1f135b197a0e299c668e11fa2c0b64813"
REPAIR_APPROVAL_SHA = "01584b65f6af212051f3f445ffb60ac3a00a7cff02e40bd1085874a458acde71"

# Historical cost figures carried forward.
HISTORICAL_SETTLED_USD = "0.08867055"
HISTORICAL_RESERVATION_USD = "0.01526175"
HISTORICAL_ORIGINAL_RUN_USAGE_USD = "0.08962620"
HISTORICAL_REJECTED_REQ_COST_USD = "0.00095565"
HISTORICAL_REPAIR_COST_USD = "0.00210675"
HISTORICAL_CUMULATIVE_USD = "0.09173295"

# Historical token totals.
HISTORICAL_INPUT_TOKENS = 103430
HISTORICAL_OUTPUT_TOKENS = 8093
HISTORICAL_CACHED_TOKENS = 36096
HISTORICAL_REASONING_TOKENS = 0
REPAIR_INPUT_TOKENS = 1927
REPAIR_OUTPUT_TOKENS = 147
REPAIR_CACHED_TOKENS = 0
REPAIR_REASONING_TOKENS = 0

PASSES = budget.PASSES
SEED_CONT = "category-coverage-paired-continuation-order-v1"


class ContinuationApproval(Closed):
    schema_version: Literal["category-pair-continuation-approval-v1"]
    authorization: Literal["explicit-operator-cost-approval"]
    approval_reference: str = Field(min_length=1, max_length=1000)
    contract_review_reference: str = Field(min_length=1, max_length=1000)
    previous_original_approval_sha256: str
    original_failure_state_sha256: str
    repair_reconciliation_sha256: str
    continuation_contract_sha256: str
    request_order_sha256: str
    model: Literal[MODEL]
    prompt_sha256: str
    packet_sha256: str
    prices_sha256: str
    effective_completed_pairs: Literal[28]
    remaining_pairs: Literal[1478]
    hard_cap_usd: Literal["12.00"]
    passes: dict
    max_input_tokens: StrictInt
    max_output_tokens: StrictInt
    execution_root: str
    approved: StrictBool


def code_hashes():
    return {
        **budget.code_hashes(),
        "category_pair_execution.py": sha(Path(execution.__file__).read_bytes()),
        "category_single_repair.py": sha(Path(repair.__file__).read_bytes()),
        "category_pair_continuation.py": sha(Path(__file__).read_bytes()),
    }


def verify_frozen_bindings():
    """Verify all frozen SHA-256 bindings from original and repair phases."""
    # Original run bundle
    bundle_path = ORIGINAL / "results/run-bundle.json"
    require(sha(bundle_path.read_bytes()) == ORIG_BUNDLE_SHA, "original_bundle_changed")

    # Original execution outcome
    outcome_path = ORIGINAL / "execution-outcome.json"
    require(sha(outcome_path.read_bytes()) == ORIG_OUTCOME_SHA, "original_outcome_changed")

    # Original approval
    orig_approval = read(ORIGINAL / "approval.json")
    require(digest(orig_approval) == ORIG_APPROVAL_SHA, "original_approval_changed")

    # Original failure state (via replay)
    state = execution.validate_bundle(bundle_path)
    require(digest(state) == ORIG_FAILURE_STATE_SHA, "original_failure_state_changed")
    require(state["status"] == "request_failed_partial", "original_status")
    require(state["completed_pairs"] == 27, "original_completed_pairs")

    # Repair contract
    require(
        sha((REPAIR / "repair-contract.json").read_bytes()) == REPAIR_CONTRACT_SHA,
        "repair_contract_changed",
    )

    # Repair receipt
    require(
        sha((REPAIR / "repair-receipt.json").read_bytes()) == REPAIR_RECEIPT_SHA,
        "repair_receipt_changed",
    )

    # Repair outcome
    repair_outcome = read(REPAIR / "repair-outcome.json")
    require(
        sha((REPAIR / "repair-outcome.json").read_bytes()) == REPAIR_OUTCOME_SHA,
        "repair_outcome_changed",
    )
    require(repair_outcome["repair_status"] == "accepted", "repair_not_accepted")

    # Repair reconciliation
    repair_recon = read(REPAIR / "repair-reconciliation.json")
    require(
        sha((REPAIR / "repair-reconciliation.json").read_bytes()) == REPAIR_RECON_SHA,
        "repair_reconciliation_changed",
    )
    require(
        repair_recon["repair_reconciliation_status"] == "ready_for_reviewed_continuation",
        "repair_not_ready",
    )
    require(repair_recon["effective_completed_pairs"] == 28, "effective_pairs_wrong")

    # Repair approval
    repair_appr = read(REPAIR / "repair-approval.json")
    require(digest(repair_appr) == REPAIR_APPROVAL_SHA, "repair_approval_changed")

    # Historical artifacts unchanged
    for name, expected in read(ORIGINAL / "artifact-sha256.json").items():
        require(sha((ORIGINAL / name).read_bytes()) == expected, "historical_artifact_changed")
    for name, expected in read(REPAIR / "artifact-sha256.json").items():
        require(sha((REPAIR / name).read_bytes()) == expected, "repair_artifact_changed")


def effective_start_state():
    """Compute the effective start state for continuation."""
    verify_frozen_bindings()
    c, order = budget.load(budget.DEST)

    # The original ledger state
    original_state = execution.validate_bundle(ORIGINAL / "results/run-bundle.json")
    require(original_state["completed_pairs"] == 27, "original_pairs")
    require(original_state["dispatched_requests"] == 56, "original_dispatches")
    require(original_state["status"] == "request_failed_partial", "original_status")

    # Repair reconciliation tells us effective pairs = 28
    recon = read(REPAIR / "repair-reconciliation.json")
    require(recon["effective_completed_pairs"] == 28, "effective_pairs")

    # Compute spent amounts from historical data
    # Effective actual spend = original settled + rejected req cost + repair cost
    # The original settled already excludes the rejected B (it wasn't settled).
    # But the rejected B WAS billed by the provider. So total actual =
    # original_settled (which includes the rejected B's cost in usage_priced)
    # Actually: usage_priced_cost = 0.08962620 includes ALL 56 receipts.
    # settled_cost = 0.08867055 (excludes the unsettled B's portion minus reservation)
    # Let me trace this carefully:
    # - 56 receipts were all sent and billed -> usage_priced = 0.08962620
    # - Of those, 55 were settled (28 A + 27 B) -> settled_cost = 0.08867055
    # - The 56th (rejected B) contributed: 0.08962620 - 0.08867055 = 0.00095565
    # - There was also an outstanding reservation of 0.01526175 for that B slot
    #
    # Effective accounting:
    # - The rejected B cost (0.00095565) was ACTUALLY incurred but not settled
    # - The repair REPLACED the rejected B logically, costing 0.00210675
    # - The old reservation (0.01526175) should NOT be double-counted going forward
    #
    # Effective actual spend for continuation purposes:
    # = original settled (includes all 55 settled receipts)
    # + rejected B actual cost (was billed, not settled)
    # + repair actual cost
    # = 0.08867055 + 0.00095565 + 0.00210675 = 0.09173295
    #
    # The old reservation is NOT carried forward as outstanding.

    effective_actual_usd = Decimal(HISTORICAL_CUMULATIVE_USD)
    effective_outstanding_usd = Decimal("0")  # reservation consumed/replaced

    # Reserved tokens carry-forward: the original had reserved_input_per_pass and
    # reserved_output_per_pass tracking cumulative reservations. Since we're
    # starting fresh for continuation pairs, we track only continuation reserves.
    # But the per_pass ceilings were computed for ALL 1506 pairs. We need to
    # subtract the already-consumed portion.
    # Per-pass ceiling = estimated_input_tokens // 2 and estimated_output_token_ceiling // 2
    # These are PER PASS ceilings for the ENTIRE run. We need to track what was
    # already consumed in the first 28 pairs (well, 28 A + 27 B + 1 rejected B).

    # For simplicity and safety, compute consumed tokens from the historical receipts.
    # Original consumed: HISTORICAL_INPUT_TOKENS, HISTORICAL_OUTPUT_TOKENS, etc.
    # Repair consumed: REPAIR_INPUT_TOKENS, REPAIR_OUTPUT_TOKENS, etc.
    # BUT: the per_pass ceilings in the original contract track RESERVATIONS, not
    # actual consumption. And the original run admitted 28 pairs worth of reservations.
    #
    # For the continuation, we start with zero per-pass reservations and the
    # remaining budget under the hard cap. The per-pass ceilings are global caps
    # on the entire run, so we need to carry forward the consumed portions.

    # Get the per-row estimates for the first 28 pairs
    consumed_input = 0
    consumed_output = 0
    for i in range(COMPLETED_EFF):
        row = order["pairs"][i]
        consumed_input += row["estimated_input_tokens"]
        consumed_output += row["estimated_output_tokens"]

    return {
        "status": "ready",
        "completed_pairs": COMPLETED_EFF,  # effective 28
        "current": None,
        "actual_usd": str(effective_actual_usd),
        "outstanding_usd": str(effective_outstanding_usd),
        "reserved_input_per_pass": consumed_input,
        "reserved_output_per_pass": consumed_output,
        "dispatched_requests": 0,  # continuation dispatches start at 0
        "response_ids": [],
        "approval_sha256": None,  # set on initialize
        # Bookkeeping fields for separated accounting
        "continuation_phase": True,
        "original_completed_pairs": 27,
        "repair_completed_pairs": 1,
        "effective_completed_pairs": COMPLETED_EFF,
        "remaining_pairs": REMAINING,
        "original_dispatches": 56,
        "repair_dispatches": 1,
        "continuation_dispatches": 0,
    }


def cont_admit(state, contract, order):
    """Admit next continuation pair (index >= 28)."""
    require(state["status"] == "ready" and state["current"] is None, "cannot_admit")
    index = state["completed_pairs"]
    require(index < TOTAL_PAIRS, "all_pairs_complete")
    require(index >= COMPLETED_EFF, "continuation_range_only")
    row = order["pairs"][index]
    both = 2 * budget.reservation_cost(row, contract)
    result = deepcopy(state)
    if Decimal(state["actual_usd"]) + Decimal(state["outstanding_usd"]) + both > Decimal(CAP):
        result["status"] = "budget_exhausted_partial"
        return result
    if (
        state["reserved_input_per_pass"] + row["estimated_input_tokens"]
        > contract["per_pass_input_ceiling"]
        or state["reserved_output_per_pass"] + row["estimated_output_tokens"]
        > contract["per_pass_output_ceiling"]
    ):
        result["status"] = "technical_limit_partial"
        return result
    result["reserved_input_per_pass"] += row["estimated_input_tokens"]
    result["reserved_output_per_pass"] += row["estimated_output_tokens"]
    result["outstanding_usd"] = str(both)
    result["current"] = {
        "annotation_id": row["annotation_id"],
        "payload_sha256": row["payload_sha256"],
        "reservation_each_usd": str(both / 2),
        "passes": dict.fromkeys(PASSES, "reserved"),
    }
    result["status"] = "pair_reserved"
    return result


def cont_dispatch(state, pass_name):
    """Dispatch a continuation request. Caps at CONTINUATION_REQUEST_CAP."""
    require(pass_name in PASSES and state["current"] is not None, "pass_or_pair")
    require(state["status"] in ("pair_reserved", "pair_partial"), "dispatch_state")
    require(state["current"]["passes"][pass_name] == "reserved", "never_resend")
    if pass_name == "machine-b":
        require(state["current"]["passes"]["machine-a"] == "settled", "a_before_b")
    result = deepcopy(state)
    result["current"]["passes"][pass_name] = "in_flight"
    result["status"] = "in_flight"
    result["dispatched_requests"] += 1
    result["continuation_dispatches"] += 1
    require(
        result["continuation_dispatches"] <= CONTINUATION_REQUEST_CAP, "continuation_request_cap"
    )
    return result


def cont_settle(state, pass_name, measured, response_id, contract, order):
    """Settle a continuation receipt."""
    require(
        state["status"] == "in_flight"
        and pass_name in PASSES
        and state["current"]["passes"][pass_name] == "in_flight",
        "settlement_state",
    )
    require(
        set(measured)
        == {
            "input_tokens",
            "output_tokens",
            "total_tokens",
            "cached_input_tokens",
            "reasoning_tokens",
        },
        "usage_fields",
    )
    verified = budget.usage(
        {
            "usage": {
                **{k: measured[k] for k in ("input_tokens", "output_tokens", "total_tokens")},
                "input_tokens_details": {"cached_tokens": measured["cached_input_tokens"]},
                "output_tokens_details": {"reasoning_tokens": measured["reasoning_tokens"]},
            }
        }
    )
    require(verified == measured, "usage_contract")
    row = order["pairs"][state["completed_pairs"]]
    require(
        measured["input_tokens"] <= row["estimated_input_tokens"]
        and measured["output_tokens"] <= row["estimated_output_tokens"],
        "usage_exceeds_reservation",
    )
    require(response_id and response_id not in state["response_ids"], "response_id")
    actual = budget.price(
        measured["input_tokens"],
        measured["output_tokens"],
        measured["cached_input_tokens"] or 0,
        contract["prices"],
    )
    require(actual <= Decimal(state["current"]["reservation_each_usd"]), "cost_exceeds_reservation")
    result = deepcopy(state)
    result["actual_usd"] = str(Decimal(state["actual_usd"]) + actual)
    result["outstanding_usd"] = str(
        Decimal(state["outstanding_usd"]) - Decimal(state["current"]["reservation_each_usd"])
    )
    result["response_ids"].append(response_id)
    result["current"]["passes"][pass_name] = "settled"
    require(
        Decimal(result["actual_usd"]) + Decimal(result["outstanding_usd"]) <= Decimal(CAP),
        "hard_cap",
    )
    if all(v == "settled" for v in result["current"]["passes"].values()):
        result["completed_pairs"] += 1
        result["current"] = None
        result["status"] = "complete" if result["completed_pairs"] == TOTAL_PAIRS else "ready"
    else:
        result["status"] = "pair_partial"
    return result


def cont_transition(state, operation, contract, order, output):
    """State machine transition for continuation journal."""
    kind = operation["kind"]
    allowed = {
        "initialize": {"kind", "approval"},
        "admit": {"kind"},
        "dispatch": {"kind", "pass_name"},
        "settle": {"kind", "pass_name", "response_sha256"},
        "fail": {"kind"},
    }
    require(kind in allowed and set(operation) == allowed[kind], "operation_schema")
    if kind == "initialize":
        approval = operation["approval"]
        require(state is None, "already_initialized")
        checked = check_cont_approval(approval, contract, order, output, contract_dir=DEST)
        init = effective_start_state()
        init["approval_sha256"] = digest(checked)
        return init
    require(state is not None, "approval_required")
    if kind == "admit":
        return cont_admit(state, contract, order)
    if kind == "dispatch":
        return cont_dispatch(state, operation["pass_name"])
    if kind == "fail":
        require(state["status"] == "in_flight", "failure_state")
        result = deepcopy(state)
        result["status"] = "request_failed_partial"
        return result
    # settle
    pass_name = operation["pass_name"]
    resp_dir = output / pass_name / "responses"
    resp_path = resp_dir / f"{state['current']['annotation_id']}.json"
    require(sha(resp_path.read_bytes()) == operation["response_sha256"], "response_hash")
    body = read(resp_path)
    require(body.get("service_tier") == "default", "unpriced_service_tier")
    candidate = _packet_lookup(state["current"]["annotation_id"])
    budget.parse(body, candidate, contract["model"])
    return cont_settle(
        state, pass_name, budget.usage(body), safe_id(body.get("id")), contract, order
    )


_packet_cache = None


def _packet_lookup(annotation_id):
    global _packet_cache
    if _packet_cache is None:
        pkt, _ = budget.legacy.load_packet(budget.legacy.PACKAGE)
        _packet_cache = {p["annotation_id"]: p for p in pkt}
    return _packet_cache[annotation_id]


def check_cont_approval(raw, contract, order, output, contract_dir=DEST):
    """Validate continuation approval against frozen bindings."""
    a = ContinuationApproval.model_validate(raw).model_dump(by_alias=True)
    require(a["approved"] is True, "not_approved")
    require(a["authorization"] == "explicit-operator-cost-approval", "auth_type")
    require(a["approval_reference"].strip(), "approval_reference")
    require(a["contract_review_reference"].strip(), "contract_review_reference")

    # Frozen binding checks
    require(
        a["previous_original_approval_sha256"] == ORIG_APPROVAL_SHA, "original_approval_binding"
    )
    require(a["original_failure_state_sha256"] == ORIG_FAILURE_STATE_SHA, "failure_state_binding")
    require(a["repair_reconciliation_sha256"] == REPAIR_RECON_SHA, "repair_reconciliation_binding")
    require(a["model"] == MODEL, "model_binding")
    require(a["prompt_sha256"] == contract["prompt_sha256"], "prompt_binding")
    require(a["packet_sha256"] == contract["packet_sha256"], "packet_binding")
    require(a["prices_sha256"] == contract["prices_sha256"], "prices_binding")
    require(a["effective_completed_pairs"] == 28, "effective_pairs_binding")
    require(a["remaining_pairs"] == 1478, "remaining_pairs_binding")
    require(a["hard_cap_usd"] == "12.00", "cap_binding")
    require(
        a["passes"] == {"machine-a": "approved", "machine-b": "approved", "machine-c": "forbidden"},
        "pass_binding",
    )
    require(
        a["request_order_sha256"] == sha((budget.DEST / "request-order.json").read_bytes()),
        "order_binding",
    )
    require(
        a["continuation_contract_sha256"]
        == sha((contract_dir / "continuation-contract.json").read_bytes()),
        "contract_binding",
    )

    root = Path(a["execution_root"])
    require(
        root.is_absolute()
        and output.resolve() == root.resolve()
        and not root.resolve().is_relative_to(Path("benchmark").resolve()),
        "execution_root",
    )
    return a


def contract_data():
    """Build the continuation contract from frozen original + repair bindings."""
    verify_frozen_bindings()
    c, order = budget.load(budget.DEST)

    # Compute consumed reservations for first 28 pairs
    consumed_input = sum(order["pairs"][i]["estimated_input_tokens"] for i in range(COMPLETED_EFF))
    consumed_output = sum(
        order["pairs"][i]["estimated_output_tokens"] for i in range(COMPLETED_EFF)
    )

    contract = {
        "schema_version": "category-pair-continuation-contract-v1",
        "baseline_main": BASELINE,
        "original_baseline_main": budget.BASELINE,
        "model": MODEL,
        "parameters": c["parameters"],
        "response_schema_sha256": c["response_schema_sha256"],
        "packet_sha256": c["packet_sha256"],
        "prompt_sha256": c["prompt_sha256"],
        "prices": c["prices"],
        "prices_sha256": c["prices_sha256"],
        "order_digest": c["order_digest"],
        "code_sha256": code_hashes(),
        "pair_count": TOTAL_PAIRS,
        "pass_count": 2,
        "passes": list(PASSES),
        "machine-c": "forbidden",
        "max_attempts_per_request": 1,
        "operator_hard_cap_usd": CAP,
        "max_input_tokens": c["max_input_tokens"],
        "max_output_tokens": c["max_output_tokens"],
        "per_pass_input_ceiling": c["per_pass_input_ceiling"],
        "per_pass_output_ceiling": c["per_pass_output_ceiling"],
        "consumed_input_per_pass_first_28": consumed_input,
        "consumed_output_per_pass_first_28": consumed_output,
        "continuation_start_index": COMPLETED_EFF,
        "remaining_pairs": REMAINING,
        "continuation_request_cap": CONTINUATION_REQUEST_CAP,
        "budget_rule": (
            "effective actual spend + effective outstanding + both reservations <= 12.00"
        ),
        "reservation_rule": "uncached input byte estimate plus 1200 output tokens, each pass",
        "token_rule": "conservative input/output reservations never refunded",
        "budget_stop": "budget_exhausted_partial",
        "retry_rule": "single attempt; no retry on 429/5xx/network/refusal/schema/evidence",
        "evidence_rule": "same validators as original; no repair-validator leak to normal requests",
        "consensus_rule": "only at 1506 effective complete pairs",
        "frozen_bindings": {
            "pr18_run_bundle_sha256": ORIG_BUNDLE_SHA,
            "pr18_failure_state_sha256": ORIG_FAILURE_STATE_SHA,
            "pr18_outcome_sha256": ORIG_OUTCOME_SHA,
            "pr18_approval_sha256": ORIG_APPROVAL_SHA,
            "pr19_repair_contract_sha256": REPAIR_CONTRACT_SHA,
            "pr19_repair_receipt_sha256": REPAIR_RECEIPT_SHA,
            "pr19_repair_outcome_sha256": REPAIR_OUTCOME_SHA,
            "pr19_repair_reconciliation_sha256": REPAIR_RECON_SHA,
            "pr19_repair_approval_sha256": REPAIR_APPROVAL_SHA,
            "original_ab_execution_contract_sha256": c["legacy_contract_sha256"],
            "original_legacy_cost_report_sha256": c["legacy_cost_report_sha256"],
            "request_order_sha256": sha((budget.DEST / "request-order.json").read_bytes()),
            "packet_sha256": c["packet_sha256"],
            "prompt_sha256": c["prompt_sha256"],
            "model": MODEL,
            "prices_sha256": c["prices_sha256"],
        },
        "budget_reconciliation": {
            "original_settled_cost_usd": HISTORICAL_SETTLED_USD,
            "original_outstanding_reservation_usd": HISTORICAL_RESERVATION_USD,
            "original_rejected_request_cost_usd": HISTORICAL_REJECTED_REQ_COST_USD,
            "repair_cost_usd": HISTORICAL_REPAIR_COST_USD,
            "cumulative_actual_cost_usd": HISTORICAL_CUMULATIVE_USD,
            "rule": (
                "Historical ledger reservation remains in original immutable ledger. "
                "Effective continuation accounting replaces it with actual rejected request cost "
                "+ actual repair cost. No double reservation for future admission."
            ),
        },
        "effective_start_state": {
            "status": "ready",
            "effective_completed_pairs": COMPLETED_EFF,
            "remaining_pairs": REMAINING,
            "effective_actual_usd": HISTORICAL_CUMULATIVE_USD,
            "effective_outstanding_usd": "0",
            "original_dispatches": 56,
            "repair_dispatches": 1,
            "continuation_dispatches": 0,
        },
        "effective_b_source_overlay": {
            "annotation_id": "a0c166936ef7233017150f87aad87df5",
            "machine_b_effective_source": "repair-v1",
            "all_others": "original_or_continuation_receipt",
        },
        "consensus_allowed": False,
        "astra_allowed": False,
        "reevaluation_allowed": False,
        "pass_c_allowed": False,
        "semantic_query": False,
    }
    return contract


def prepare(output=DEST):
    """Write the continuation contract and approval schema."""
    contract = contract_data()
    require(not output.exists() or not any(output.iterdir()), "exclusive_destination")
    output.mkdir(parents=True, exist_ok=True)
    atomic_new(output / "continuation-contract.json", contract)
    schema = ContinuationApproval.model_json_schema()
    atomic_new(output / "continuation-approval-schema.json", schema)
    start = effective_start_state()
    atomic_new(output / "effective-start-state.json", start)
    atomic_new(
        output / "artifact-sha256.json",
        {p.name: sha(p.read_bytes()) for p in sorted(output.iterdir()) if p.is_file()},
    )


def approve(reference, output=DEST, execution_root="/tmp/category-pair-continuation-v1-run"):
    """Generate the continuation approval. Explicit operator action only."""
    c, order = budget.load(budget.DEST)
    approval = {
        "schema_version": "category-pair-continuation-approval-v1",
        "authorization": "explicit-operator-cost-approval",
        "approval_reference": reference,
        "contract_review_reference": (
            f"Continuation after PR #18 partial + PR #19 accepted repair; baseline {BASELINE}"
        ),
        "previous_original_approval_sha256": ORIG_APPROVAL_SHA,
        "original_failure_state_sha256": ORIG_FAILURE_STATE_SHA,
        "repair_reconciliation_sha256": REPAIR_RECON_SHA,
        "continuation_contract_sha256": sha((output / "continuation-contract.json").read_bytes()),
        "request_order_sha256": sha((budget.DEST / "request-order.json").read_bytes()),
        "model": MODEL,
        "prompt_sha256": c["prompt_sha256"],
        "packet_sha256": c["packet_sha256"],
        "prices_sha256": c["prices_sha256"],
        "effective_completed_pairs": 28,
        "remaining_pairs": 1478,
        "hard_cap_usd": "12.00",
        "passes": {"machine-a": "approved", "machine-b": "approved", "machine-c": "forbidden"},
        "max_input_tokens": c["max_input_tokens"],
        "max_output_tokens": c["max_output_tokens"],
        "execution_root": execution_root,
        "approved": True,
    }
    check_cont_approval(approval, c, order, Path(execution_root), contract_dir=output)
    return approval


class ContinuationLedger:
    """Append-only continuation journal. Never touches the original ledger."""

    def __init__(self, directory, output):
        require(
            output.is_absolute()
            and not output.resolve().is_relative_to(Path("benchmark").resolve()),
            "external_ledger_root_required",
        )
        self.directory, self.output = directory, output
        self.contract = read(directory / "continuation-contract.json")
        c, self.order = budget.load(budget.DEST)
        self.packet = _packet_lookup
        self.state, self.tail, self.events, self.lock = None, None, 0, None

    def __enter__(self):
        import fcntl

        self.output.mkdir(parents=True, exist_ok=True)
        self.lock = (self.output / ".lock").open("a")
        try:
            fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            journal = self.output / "journal"
            if journal.exists():
                for i, path in enumerate(sorted(journal.glob("*.json"))):
                    require(path.name == f"{i:06}.json", "journal_gap")
                    event = read(path)
                    require(
                        set(event) == {"previous_sha256", "operation", "state_sha256"}
                        and event["previous_sha256"] == self.tail,
                        "journal_chain",
                    )
                    self.state = cont_transition(
                        self.state, event["operation"], self.contract, self.order, self.output
                    )
                    require(digest(self.state) == event["state_sha256"], "journal_state")
                    self.tail, self.events = sha(path.read_bytes()), i + 1
            return self
        except BaseException:
            self.lock.close()
            raise

    def __exit__(self, *_):
        self.lock.close()

    def append(self, operation):
        require(self.lock is not None and not self.lock.closed, "ledger_lock_required")
        state = cont_transition(self.state, operation, self.contract, self.order, self.output)
        event = {
            "previous_sha256": self.tail,
            "operation": operation,
            "state_sha256": digest(state),
        }
        path = self.output / "journal" / f"{self.events:06}.json"
        atomic_new(path, event)
        self.state, self.tail, self.events = state, sha(path.read_bytes()), self.events + 1
        return deepcopy(state)

    def response_path(self, pass_name):
        require(pass_name in PASSES and self.state and self.state["current"], "response_pair")
        return (
            self.output / pass_name / "responses" / f"{self.state['current']['annotation_id']}.json"
        )

    def request_intent(self, pass_name):
        require(pass_name in PASSES and self.state and self.state["current"], "request_pair")
        require(
            not self.response_path(pass_name).exists(),
            "saved_response_requires_reconciliation",
        )
        candidate = self.packet(self.state["current"]["annotation_id"])
        payload = budget.legacy.request_for(
            candidate, self.contract["model"], budget.legacy.PROMPT.read_text()
        )
        require(
            sha(budget.legacy.wire(payload)) == self.state["current"]["payload_sha256"],
            "payload_binding",
        )
        self.append({"kind": "dispatch", "pass_name": pass_name})
        client_id = str(
            uuid5(
                NAMESPACE_URL,
                f"continuation:{self.output.resolve()}:{digest(self.contract)}"
                f":{candidate['annotation_id']}:{pass_name}",
            )
        )
        return {
            "client_request_id": client_id,
            "run_id": "cont-" + digest([SEED_CONT, candidate["annotation_id"], pass_name])[:24],
            "payload": payload,
        }

    def record_response(self, pass_name, body):
        require(
            self.state["status"] == "in_flight"
            and pass_name in PASSES
            and self.state["current"]["passes"][pass_name] == "in_flight",
            "receipt_state",
        )
        path = self.response_path(pass_name)
        if path.exists():
            require(read(path) == body, "never_overwrite_response")
        else:
            atomic_new(path, body)
        return self.append(
            {"kind": "settle", "pass_name": pass_name, "response_sha256": sha(path.read_bytes())}
        )

    def resume_action(self):
        require(self.state is not None, "approval_required")
        status = self.state["status"]
        if status == "in_flight":
            name = next(k for k, v in self.state["current"]["passes"].items() if v == "in_flight")
            return (
                "reconcile_saved_response_offline"
                if self.response_path(name).exists()
                else "operator_audit_required_no_resend"
            )
        return {
            "ready": "admit_next_pair",
            "pair_reserved": "dispatch_machine_a",
            "pair_partial": "dispatch_reserved_machine_b_only",
            "budget_exhausted_partial": "new_explicit_approval_required",
            "technical_limit_partial": "blocked_technical_limit",
            "request_failed_partial": "operator_audit_required_no_resend",
            "complete": "complete_no_more_requests",
        }[status]


def binding(approval):
    return {
        "schema_version": "category-pair-continuation-execution-v1",
        "baseline_main": BASELINE,
        "approval_sha256": digest(approval),
        "execution_code_sha256": sha(Path(__file__).read_bytes()),
        "analysis_code_sha256": sha(
            Path(__file__).with_name("machine_blind_analysis.py").read_bytes()
        ),
        "purpose": "machine_proposed",
        "max_attempts": 1,
    }


async def drive(book, judge):
    """Continuation ledger drives admission, dispatch, settlement."""
    while True:
        action = book.resume_action()
        if action == "admit_next_pair":
            book.append({"kind": "admit"})
            continue
        if action == "reconcile_saved_response_offline":
            name = next(k for k, v in book.state["current"]["passes"].items() if v == "in_flight")
            try:
                book.record_response(name, read(book.response_path(name)))
            except (ValueError, KeyError, TypeError, AttributeError):
                book.append({"kind": "fail"})
            continue
        if action not in ("dispatch_machine_a", "dispatch_reserved_machine_b_only"):
            return book.state
        name = "machine-a" if action == "dispatch_machine_a" else "machine-b"
        aid = book.state["current"]["annotation_id"]
        intent = book.request_intent(name)
        started = monotonic()
        metadata = {
            "annotation_id": aid,
            "pass_name": name,
            "run_id": intent["run_id"],
            "client_request_id": intent["client_request_id"],
            "payload_sha256": sha(budget.legacy.wire(intent["payload"])),
            "started_at": datetime.now(UTC).isoformat(),
            "attempt": 1,
            "retries": 0,
        }
        try:
            body, request_id = await judge.request(
                "POST", "responses", intent["payload"], intent["client_request_id"]
            )
        except APIError as exc:
            metadata.update(status="transport_failure", error_category=exc.category)
            metadata["latency_seconds"] = monotonic() - started
            atomic_new(book.output / name / "attempts" / f"{aid}.json", metadata)
            book.append({"kind": "fail"})
            return book.state
        metadata.update(
            status="response_received", request_id=request_id, latency_seconds=monotonic() - started
        )
        atomic_new(book.response_path(name), body)
        atomic_new(book.output / name / "attempts" / f"{aid}.json", metadata)
        try:
            book.record_response(name, body)
        except (ValueError, KeyError, TypeError, AttributeError):
            book.append({"kind": "fail"})
            return book.state
        if name == "machine-b" and book.state["completed_pairs"] % 50 == 0:
            print(
                f"effective_pairs={book.state['completed_pairs']} "
                f"remaining={TOTAL_PAIRS - book.state['completed_pairs']} "
                f"continuation_requests={book.state['continuation_dispatches']} "
                f"actual_total_usd={book.state['actual_usd']} "
                f"remaining_budget_usd={Decimal(CAP) - Decimal(book.state['actual_usd'])}"
            )


async def execute(output, approval_path, *, resume=False, judge_factory=None):
    approval = read(approval_path)
    with ContinuationLedger(DEST, output) as book:
        checked = check_cont_approval(
            approval, book.contract, book.order, output, contract_dir=DEST
        )
        manifest = binding(checked)
        if book.state is None:
            require(not resume, "no_run_to_resume")
            atomic_new(output / "execution.json", manifest)
            book.append({"kind": "initialize", "approval": checked})
        else:
            require(resume, "explicit_resume_required")
            require(read(output / "execution.json") == manifest, "execution_binding")
            require(book.state["approval_sha256"] == digest(checked), "approval_binding")
        judge = (judge_factory or budget.legacy.CategoryJudge)(os.environ.get("OPENAI_API_KEY", ""))
        try:
            return await drive(book, judge)
        finally:
            await judge.close()


def summarize(book):
    """Cost report separating original, repair, and continuation phases."""
    cont_passes = {}
    for name in PASSES:
        totals = Counter()
        cost = Decimal(0)
        for path in sorted((book.output / name / "responses").glob("*.json")):
            body = read(path)
            try:
                measured = budget.usage(body)
            except (ValueError, KeyError, TypeError, AttributeError):
                totals["unknown_usage_receipts"] += 1
                continue
            for key, value in measured.items():
                if value is not None:
                    totals[key] += value
            cost += budget.price(
                measured["input_tokens"],
                measured["output_tokens"],
                measured["cached_input_tokens"] or 0,
                book.contract["prices"],
            )
            totals["receipts"] += 1
            totals["settled"] += body.get("id") in book.state["response_ids"]
        cont_passes[name] = {**totals, "measured_receipt_cost_usd": str(cost)}

    cont_input = sum(cont_passes[n].get("input_tokens", 0) for n in PASSES)
    cont_output = sum(cont_passes[n].get("output_tokens", 0) for n in PASSES)
    cont_cached = sum(cont_passes[n].get("cached_input_tokens", 0) for n in PASSES)
    cont_reasoning = sum(cont_passes[n].get("reasoning_tokens", 0) for n in PASSES)

    return {
        "schema_version": "category-pair-continuation-cost-report-v1",
        "status": book.state["status"],
        "original_pr18_phase": {
            "api_calls": 56,
            "input_tokens": HISTORICAL_INPUT_TOKENS,
            "output_tokens": HISTORICAL_OUTPUT_TOKENS,
            "cached_input_tokens": HISTORICAL_CACHED_TOKENS,
            "reasoning_tokens": HISTORICAL_REASONING_TOKENS,
            "cost_usd": HISTORICAL_ORIGINAL_RUN_USAGE_USD,
        },
        "repair_phase": {
            "api_calls": 1,
            "input_tokens": REPAIR_INPUT_TOKENS,
            "output_tokens": REPAIR_OUTPUT_TOKENS,
            "cached_input_tokens": REPAIR_CACHED_TOKENS,
            "reasoning_tokens": REPAIR_REASONING_TOKENS,
            "cost_usd": HISTORICAL_REPAIR_COST_USD,
        },
        "continuation_phase": {
            "api_calls": book.state["continuation_dispatches"],
            "input_tokens": cont_input,
            "output_tokens": cont_output,
            "cached_input_tokens": cont_cached,
            "reasoning_tokens": cont_reasoning,
            "cost_usd": str(
                sum(Decimal(cont_passes[n]["measured_receipt_cost_usd"]) for n in PASSES)
            ),
            "passes": cont_passes,
        },
        "total": {
            "provider_calls": 56 + 1 + book.state["continuation_dispatches"],
            "input_tokens": HISTORICAL_INPUT_TOKENS + REPAIR_INPUT_TOKENS + cont_input,
            "output_tokens": HISTORICAL_OUTPUT_TOKENS + REPAIR_OUTPUT_TOKENS + cont_output,
            "cached_input_tokens": HISTORICAL_CACHED_TOKENS + REPAIR_CACHED_TOKENS + cont_cached,
            "reasoning_tokens": (
                HISTORICAL_REASONING_TOKENS + REPAIR_REASONING_TOKENS + cont_reasoning
            ),
            "total_usage_priced_usd": book.state["actual_usd"],
        },
        "remaining_budget_usd": str(Decimal(CAP) - Decimal(book.state["actual_usd"])),
        "effective_completed_pairs": book.state["completed_pairs"],
        "remaining_pairs": TOTAL_PAIRS - book.state["completed_pairs"],
        "no_reevaluation": True,
        "no_pass_c": True,
        "no_astra": True,
        "semantic_query": False,
    }


def effective_b_overlay(book):
    """Deterministic B-source overlay: pair 27 uses repair-v1, all others use receipts."""
    overlay = {}
    # Pair index 27 (the repaired pair) uses repair-v1 for machine-b
    repair_annotation = "a0c166936ef7233017150f87aad87df5"
    overlay[27] = {
        "annotation_id": repair_annotation,
        "machine_b_source": "repair-v1",
        "machine_b_receipt_path": str(REPAIR / "repair-receipt.json"),
    }
    return overlay


def consensus(book):
    """Consensus only at 1506 effective complete pairs."""
    require(
        book.state["status"] == "complete"
        and book.state["completed_pairs"] == TOTAL_PAIRS
        and book.state["current"] is None
        and Decimal(book.state["outstanding_usd"]) == 0,
        "no_consensus_or_export_for_partial",
    )
    rows, conflicts = [], []
    for idx, pair in enumerate(book.order["pairs"]):
        aid = pair["annotation_id"]
        candidate = book.packet(aid)
        ans_a = budget.parse(
            read(_effective_receipt_path(book, idx, "machine-a")),
            candidate,
            book.contract["model"],
        )
        if idx == 27:
            # Use repair receipt for machine-b
            ans_b = budget.parse(
                read(REPAIR / "repair-receipt.json"),
                candidate,
                book.contract["model"],
            )
        else:
            ans_b = budget.parse(
                read(_effective_receipt_path(book, idx, "machine-b")),
                candidate,
                book.contract["model"],
            )
        result = {"annotation_id": aid, **classify(ans_a, ans_b)}
        rows.append(result)
        if result["status"] != "machine_agreed":
            conflicts.append(candidate)
    return {
        "provenance": "machine_proposed",
        "records": rows,
        "counts": dict(Counter(r["status"] for r in rows)),
    }, conflicts


def _effective_receipt_path(book, pair_index, pass_name):
    """Get the effective receipt path for a pair index and pass."""
    aid = book.order["pairs"][pair_index]["annotation_id"]
    if pair_index < COMPLETED_EFF:
        # Original receipts from the run bundle
        bundle = read(ORIGINAL / "results/run-bundle.json")
        key = f"{pass_name}/responses/{aid}.json"
        # Extract from bundle to temp for parsing
        text = bundle["files"][key]
        # Write to temp and return path
        tmp = book.output / "_overlay" / pass_name / f"{aid}.json"
        if not tmp.exists():
            atomic_new(tmp, read(text.encode()))
        return tmp
    else:
        return book.output / pass_name / "responses" / f"{aid}.json"


def export_run(output, destination):
    """Export continuation run bundle and optionally consensus."""
    require(not destination.exists(), "exclusive_export_required")
    with ContinuationLedger(DEST, output) as book:
        require(book.state is not None, "missing_run")
        files = {str(p.relative_to(output)): p.read_text() for p in sorted(output.rglob("*.json"))}
        bundle = {
            "schema_version": "category-pair-continuation-receipts-v1",
            "files": files,
            "sha256": {k: sha(v.encode()) for k, v in files.items()},
        }
        atomic_new(destination / "continuation-run-bundle.json", bundle)
        atomic_new(destination / "usage-cost-report.json", summarize(book))
        atomic_new(destination / "execution-outcome.json", execution_outcome(book))
        if book.state["status"] == "complete":
            agreed, conflicts = consensus(book)
            atomic_new(destination / "machine-consensus.json", agreed)
            atomic_new(destination / "conflict-pool.jsonl", conflicts, jsonl=True)
        atomic_new(
            destination / "artifact-sha256.json",
            {p.name: sha(p.read_bytes()) for p in sorted(destination.iterdir()) if p.is_file()},
        )


def execution_outcome(book):
    """Final execution outcome summary."""
    return {
        "schema_version": "category-pair-continuation-outcome-v1",
        "status": book.state["status"],
        "effective_completed_pairs": book.state["completed_pairs"],
        "remaining_pairs": TOTAL_PAIRS - book.state["completed_pairs"],
        "original_complete_pairs": 27,
        "repair_completed_pairs": 1,
        "continuation_complete_pairs": book.state["completed_pairs"] - COMPLETED_EFF,
        "original_dispatches": 56,
        "repair_dispatches": 1,
        "continuation_dispatches": book.state["continuation_dispatches"],
        "total_provider_calls": 56 + 1 + book.state["continuation_dispatches"],
        "effective_a_judgments": book.state["completed_pairs"],
        "effective_b_judgments": book.state["completed_pairs"],
        "consensus": (
            "generated" if book.state["status"] == "complete" else "not_generated_incomplete"
        ),
        "conflict_pool": (
            "generated" if book.state["status"] == "complete" else "not_generated_incomplete"
        ),
        "pass_c_calls": 0,
        "astra_calls": 0,
        "reevaluation": False,
        "semantic_query": False,
        "no_pass_c": True,
        "no_astra": True,
    }


def validate_bundle(path):
    """Replay continuation journal offline for audit."""
    bundle = read(path)
    require(set(bundle) == {"schema_version", "files", "sha256"}, "bundle_schema")
    require(bundle["schema_version"] == "category-pair-continuation-receipts-v1", "bundle_version")
    require(set(bundle["files"]) == set(bundle["sha256"]), "bundle_hash_keys")
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        for name, content in bundle["files"].items():
            rel = Path(name)
            require(not rel.is_absolute() and ".." not in rel.parts, "bundle_path")
            require(sha(content.encode()) == bundle["sha256"][name], "bundle_hash")
            target = root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content)
        approval = read(root / "journal/000000.json")["operation"]["approval"]
        book = ContinuationLedger(DEST, Path(approval["execution_root"]))
        require(read(root / "execution.json") == binding(approval), "execution_binding")
        for i, file in enumerate(sorted((root / "journal").glob("*.json"))):
            require(file.name == f"{i:06}.json", "journal_gap")
            event = read(file)
            require(
                set(event) == {"previous_sha256", "operation", "state_sha256"}
                and event["previous_sha256"] == book.tail,
                "journal_chain",
            )
            book.state = cont_transition(event["operation"], book.contract, book.order, root)
            require(digest(book.state) == event["state_sha256"], "journal_state")
            book.tail = sha(file.read_bytes())
        require(book.state is not None, "missing_run")
        return book.state


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prep = commands.add_parser("prepare")
    prep.add_argument("--output", type=Path, default=DEST)
    auth = commands.add_parser("approve")
    auth.add_argument("--reference", required=True)
    auth.add_argument("--output", type=Path, default=DEST)
    auth.add_argument("--execution-root", default="/tmp/category-pair-continuation-v1-run")
    run = commands.add_parser("run")
    run.add_argument("--output", type=Path, required=True)
    run.add_argument("--approval", type=Path, required=True)
    run.add_argument("--resume", action="store_true")
    export = commands.add_parser("export")
    export.add_argument("--run", type=Path, required=True)
    export.add_argument("--output", type=Path, required=True)
    check = commands.add_parser("validate")
    check.add_argument("--bundle", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "prepare":
        prepare(args.output)
    elif args.command == "approve":
        atomic_new(
            args.output / "continuation-approval.json",
            approve(args.reference, args.output, args.execution_root),
        )
        art_path = args.output / "artifact-sha256.json"
        if art_path.exists():
            art_path.unlink()
        atomic_new(
            art_path,
            {p.name: sha(p.read_bytes()) for p in sorted(args.output.iterdir()) if p.is_file()},
        )
    elif args.command == "run":
        state = asyncio.run(execute(args.output, args.approval, resume=args.resume))
        print(state["status"])
    elif args.command == "export":
        export_run(args.run, args.output)
    else:
        print(validate_bundle(args.bundle)["status"])


if __name__ == "__main__":
    main()
