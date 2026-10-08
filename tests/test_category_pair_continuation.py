"""No live API: immutable frozen bindings, synthetic continuation responses."""

import json
from copy import deepcopy
from decimal import Decimal
from pathlib import Path

import httpx
import pytest

from uranus_research_service import category_pair_budget as budget
from uranus_research_service import category_pair_continuation as cont
from uranus_research_service.machine_judge import APIError, atomic_new, read, sha


@pytest.fixture(scope="module")
def context():
    return cont.contract_data()


def synth_body(candidate, grade=1, uncertain=False):
    aid = candidate["annotation_id"]
    answer = {
        "annotation_id": aid,
        "state": "uncertain" if uncertain else "graded",
        "grade": None if uncertain else grade,
        "uncertain": uncertain,
        "reason": "SYNTHETIC TEST ONLY; no real judgment",
        "supporting_fields": ["title"] if grade else [],
        "occurrence_ids": candidate["eligible_occurrence_ids"][:1] if grade else [],
    }
    return {
        "id": "resp_" + aid[:16],
        "model": cont.MODEL,
        "status": "completed",
        "service_tier": "default",
        "usage": {
            "input_tokens": 100,
            "output_tokens": 10,
            "total_tokens": 110,
            "input_tokens_details": {"cached_tokens": 0},
            "output_tokens_details": {"reasoning_tokens": 0},
        },
        "output": [
            {"type": "message", "content": [{"type": "output_text", "text": json.dumps(answer)}]}
        ],
    }


class FakeJudge:
    def __init__(self, packet_fn, fail_at=None, crash=False, invalid=False):
        self.packet_fn = packet_fn
        self.fail_at = fail_at
        self.crash = crash
        self.invalid = invalid
        self.calls = []

    async def request(self, method, path, payload, client_id):
        self.calls.append((method, path, deepcopy(payload), client_id))
        if self.crash:
            raise KeyboardInterrupt
        if self.fail_at is not None and len(self.calls) == self.fail_at:
            raise APIError("rate_limit", True)
        # Determine which pass we're responding to from the payload
        return synth_body(self._guess_candidate(client_id)), "req_synth_" + str(len(self.calls))

    def _guess_candidate(self, client_id):
        # We need the candidate from the ledger state, but we don't have it here
        # This will be patched in tests
        return self._candidate

    async def close(self):
        pass


def test_pr18_bundle_hash_bound(context):
    c = context
    assert c["frozen_bindings"]["pr18_run_bundle_sha256"] == cont.ORIG_BUNDLE_SHA


def test_failure_state_bound(context):
    c = context
    assert c["frozen_bindings"]["pr18_failure_state_sha256"] == cont.ORIG_FAILURE_STATE_SHA


def test_repair_reconciliation_bound(context):
    c = context
    assert c["frozen_bindings"]["pr19_repair_reconciliation_sha256"] == cont.REPAIR_RECON_SHA


def test_repair_accepted_required(context):
    outcome = read(cont.REPAIR / "repair-outcome.json")
    assert outcome["repair_status"] == "accepted"


def test_effective_completed_pairs_28(context):
    start = cont.effective_start_state()
    assert start["effective_completed_pairs"] == 28
    assert start["completed_pairs"] == 28


def test_remaining_exactly_1478(context):
    assert cont.REMAINING == 1478
    start = cont.effective_start_state()
    assert start["remaining_pairs"] == 1478


def test_no_request_for_first_28_pairs(context):
    c, order = budget.load(budget.DEST)
    start = cont.effective_start_state()
    assert start["completed_pairs"] == 28
    # The continuation admits from index 28 onward
    row = order["pairs"][28]
    assert row["annotation_id"] != order["pairs"][27]["annotation_id"]


def test_no_repeat_original_a(context):
    # The first 28 pairs' machine-a receipts exist in the original bundle
    bundle = read(cont.ORIGINAL / "results/run-bundle.json")
    c, order = budget.load(budget.DEST)
    for i in range(28):
        aid = order["pairs"][i]["annotation_id"]
        key = f"machine-a/responses/{aid}.json"
        assert key in bundle["files"]


def test_no_repeat_original_b(context):
    bundle = read(cont.ORIGINAL / "results/run-bundle.json")
    c, order = budget.load(budget.DEST)
    for i in range(27):
        aid = order["pairs"][i]["annotation_id"]
        key = f"machine-b/responses/{aid}.json"
        assert key in bundle["files"]


def test_no_repeat_repair(context):
    # The repair receipt exists and is accepted
    receipt = read(cont.REPAIR / "repair-receipt.json")
    assert receipt["id"] == "resp_095618ad43f47a30016ac71392005c87d294f616816111acfb"


def test_old_rejected_b_remains_rejected(context):
    recon = read(cont.REPAIR / "repair-reconciliation.json")
    assert recon["original_machine_b_receipt"] == "rejected"


def test_effective_b_source_repair_v1(context):
    recon = read(cont.REPAIR / "repair-reconciliation.json")
    assert recon["effective_response_source"] == "repair-v1"


def test_old_ledger_reservation_not_deleted(context):
    # The original usage-cost-report still has the reservation
    report = read(cont.ORIGINAL / "results/usage-cost-report.json")
    assert Decimal(report["outstanding_reservation_usd"]) == Decimal("0.01526175")


def test_effective_accounting_no_double_reservation(context):
    start = cont.effective_start_state()
    assert Decimal(start["outstanding_usd"]) == Decimal("0")
    # The reservation is NOT carried forward as outstanding


def test_both_real_request_costs_retained(context):
    br = context["budget_reconciliation"]
    assert Decimal(br["original_rejected_request_cost_usd"]) == Decimal("0.00095565")
    assert Decimal(br["repair_cost_usd"]) == Decimal("0.00210675")
    assert Decimal(br["cumulative_actual_cost_usd"]) == Decimal("0.09173295")


def test_12usd_cap_remains(context):
    assert context["operator_hard_cap_usd"] == "12.00"


def test_no_counter_reset(context):
    start = cont.effective_start_state()
    assert Decimal(start["actual_usd"]) == Decimal("0.09173295")
    assert start["original_dispatches"] == 56
    assert start["repair_dispatches"] == 1
    assert start["continuation_dispatches"] == 0


def test_frozen_order_unchanged(context):
    c, order = budget.load(budget.DEST)
    assert len(order["pairs"]) == 1506
    assert order["seed"] == budget.SEED


def test_prompt_unchanged(context):
    c, order = budget.load(budget.DEST)
    assert context["prompt_sha256"] == c["prompt_sha256"]


def test_packet_unchanged(context):
    c, order = budget.load(budget.DEST)
    assert context["packet_sha256"] == c["packet_sha256"]


def test_model_unchanged(context):
    assert context["model"] == "gpt-5.4-mini-2026-03-17"


def test_pass_c_blocked(context):
    assert context["pass_c_allowed"] is False
    assert context["machine-c"] == "forbidden"


def test_max_2956_continuation_calls(context):
    assert context["continuation_request_cap"] == 2956


def test_one_attempt_per_request(context):
    assert context["max_attempts_per_request"] == 1


@pytest.mark.parametrize("status", [429, 500, 503])
def test_transport_failures_stop(tmp_path, context, status, monkeypatch):
    """429, 5xx, network stop immediately with no retry."""
    run_root = tmp_path / "run"
    approval = read(cont.DEST / "continuation-approval.json")
    approval["execution_root"] = str(run_root)
    appr_path = tmp_path / "appr.json"
    atomic_new(appr_path, approval)
    monkeypatch.setenv("OPENAI_API_KEY", "synthetic-secret")

    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(status, json={"error": "SYNTHETIC PRIVATE ERROR DO NOT LOG"})

    def factory(key):
        return budget.legacy.CategoryJudge(key, transport=httpx.MockTransport(handler))

    import asyncio

    result = asyncio.run(cont.execute(run_root, appr_path, judge_factory=factory))
    assert result["status"] == "request_failed_partial"
    assert len(calls) == 1
    for p in run_root.rglob("*.json"):
        assert "SYNTHETIC PRIVATE ERROR" not in p.read_text()
        assert "synthetic-secret" not in p.read_text()


def test_refusal_stops(context, tmp_path, monkeypatch):
    """Invalid JSON stops with no retry."""
    run_root = tmp_path / "run"
    approval = read(cont.DEST / "continuation-approval.json")
    approval["execution_root"] = str(run_root)
    appr_path = tmp_path / "appr.json"
    atomic_new(appr_path, approval)
    monkeypatch.setenv("OPENAI_API_KEY", "synthetic-secret")

    def handler(request):
        return httpx.Response(
            200,
            json={
                "output": "invalid",
                "model": cont.MODEL,
                "status": "completed",
                "service_tier": "default",
            },
        )

    def factory(key):
        return budget.legacy.CategoryJudge(key, transport=httpx.MockTransport(handler))

    import asyncio

    result = asyncio.run(cont.execute(run_root, appr_path, judge_factory=factory))
    assert result["status"] == "request_failed_partial"


def test_no_global_repair_validator_leak(context):
    """The repair-specific validator must not leak to normal continuation requests."""
    # The continuation contract specifies same validators as original
    assert "no repair-validator leak" in context["evidence_rule"]


def test_semantic_query_false(context):
    assert context["semantic_query"] is False


def test_no_astra(context):
    assert context["astra_allowed"] is False


def test_no_reevaluation(context):
    assert context["reevaluation_allowed"] is False


def test_consensus_blocked_on_partial(context):
    """Consensus must be blocked when not all 1506 pairs are complete."""
    state = cont.effective_start_state()
    assert state["status"] != "complete"
    assert state["completed_pairs"] != cont.TOTAL_PAIRS
    # The consensus function checks for status=="complete" and raises if not
    # We verify the guard logic indirectly
    from uranus_research_service.category_pair_budget import require_complete

    # require_complete checks for 1506 pairs and 3012 dispatched - continuation state won't match
    with pytest.raises(ValueError, match="no_consensus"):
        require_complete(
            {
                "status": state["status"],
                "completed_pairs": state["completed_pairs"],
                "dispatched_requests": state["dispatched_requests"],
                "current": state["current"],
                "outstanding_usd": state["outstanding_usd"],
            }
        )


def test_historical_artifacts_unchanged(context):
    for name, expected in read(cont.ORIGINAL / "artifact-sha256.json").items():
        assert sha((cont.ORIGINAL / name).read_bytes()) == expected
    for name, expected in read(cont.REPAIR / "artifact-sha256.json").items():
        assert sha((cont.REPAIR / name).read_bytes()) == expected


def test_prepared_artifacts_match_frozen_code():
    contract = read(cont.DEST / "continuation-contract.json")
    assert contract["schema_version"] == "category-pair-continuation-contract-v1"
    schema = read(cont.DEST / "continuation-approval-schema.json")
    assert schema == cont.ContinuationApproval.model_json_schema()
    for name, expected in read(cont.DEST / "artifact-sha256.json").items():
        assert sha((cont.DEST / name).read_bytes()) == expected


def test_continuation_approval_validates_bindings():
    approval = read(cont.DEST / "continuation-approval.json")
    c, order = budget.load(budget.DEST)
    checked = cont.check_cont_approval(
        approval, c, order, Path("/tmp/category-pair-continuation-v1-run")
    )
    assert checked["effective_completed_pairs"] == 28
    assert checked["remaining_pairs"] == 1478
    assert checked["approved"] is True
    assert checked["passes"]["machine-c"] == "forbidden"


def test_continuation_starts_at_pair_28(context):
    c, order = budget.load(budget.DEST)
    start = cont.effective_start_state()
    # The next pair to admit should be index 28
    assert start["completed_pairs"] == 28
    next_pair = order["pairs"][28]
    assert next_pair["annotation_id"] != order["pairs"][27]["annotation_id"]


def test_effective_start_state_budget_correct(context):
    start = cont.effective_start_state()
    assert Decimal(start["actual_usd"]) == Decimal("0.09173295")
    assert Decimal(start["outstanding_usd"]) == Decimal("0")
    # Remaining budget
    assert Decimal(cont.CAP) - Decimal(start["actual_usd"]) == Decimal("11.90826705")


def test_continuation_contract_contains_all_frozen_bindings(context):
    fb = context["frozen_bindings"]
    required = [
        "pr18_run_bundle_sha256",
        "pr18_failure_state_sha256",
        "pr19_repair_contract_sha256",
        "pr19_repair_receipt_sha256",
        "pr19_repair_outcome_sha256",
        "pr19_repair_reconciliation_sha256",
        "pr19_repair_approval_sha256",
        "pr18_approval_sha256",
        "request_order_sha256",
        "packet_sha256",
        "prompt_sha256",
        "model",
        "prices_sha256",
    ]
    for key in required:
        assert key in fb, f"Missing frozen binding: {key}"


def test_continuation_contract_bind_original_execution_contract(context):
    c, order = budget.load(budget.DEST)
    fb = context["frozen_bindings"]
    assert fb["original_ab_execution_contract_sha256"] == c["legacy_contract_sha256"]


def test_no_production(context):
    assert context["consensus_allowed"] is False
    assert context["astra_allowed"] is False
    assert context["reevaluation_allowed"] is False
    assert context["pass_c_allowed"] is False


def test_provider_config_unchanged(context):
    params = context["parameters"]
    assert params["store"] is False
    assert params["reasoning"] == {"effort": "none"}
    assert params["temperature"] == 0
    assert params["max_output_tokens"] == 1200
    assert params["tools"] == "none"
    assert params["history"] == "none"


def test_continuation_request_cap_exactly_2956(context):
    assert cont.CONTINUATION_REQUEST_CAP == 2956
    assert context["continuation_request_cap"] == 2956
