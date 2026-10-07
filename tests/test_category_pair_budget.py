"""New paired budget semantics: offline only; every response/approval is synthetic."""

import json
import socket
from copy import deepcopy
from decimal import Decimal
from pathlib import Path

import pytest

from uranus_research_service import category_pair_budget as p
from uranus_research_service.machine_judge import atomic_new, digest, read, sha


@pytest.fixture(scope="module")
def prepared(tmp_path_factory):
    directory = tmp_path_factory.mktemp("paired-contract") / "contract"
    p.prepare(directory)
    c, order = p.load(directory)
    return directory, c, order


@pytest.fixture
def approval(prepared, tmp_path):
    directory, c, order = prepared
    return {
        "schema_version": "category-pair-budget-approval-v1",
        "authorization": "explicit-operator-cost-approval",
        "approval_reference": "SYNTHETIC TEST ONLY; not operator authorization",
        "contract_review_reference": "SYNTHETIC REVIEW FIXTURE ONLY",
        "kind": "initial",
        "contract_sha256": sha((directory / "execution-contract.json").read_bytes()),
        "order_sha256": sha((directory / "request-order.json").read_bytes()),
        **{
            k: c[k]
            for k in (
                "packet_sha256",
                "prompt_sha256",
                "model",
                "legacy_contract_sha256",
                "legacy_cost_report_sha256",
                "prices_sha256",
                "pair_count",
                "pass_count",
                "request_count",
                "max_input_tokens",
                "max_output_tokens",
            )
        },
        "passes": {"machine-a": "approved", "machine-b": "approved", "machine-c": "forbidden"},
        "max_amount_usd": "12.00",
        "execution_root": str(tmp_path / "run"),
        "previous_approval_sha256": None,
        "stopped_state_sha256": None,
    }


@pytest.fixture
def ledger(prepared, approval, monkeypatch):
    directory, c, order = prepared
    # Already verified real frozen bindings once; avoid repeated 1506-payload serialization.
    monkeypatch.setattr(p, "load", lambda _: (deepcopy(c), deepcopy(order)))
    with p.Ledger(directory, Path(approval["execution_root"])) as book:
        book.append({"kind": "initialize", "approval": approval})
        yield book


def measured(inp=100, out=10, cached=0):
    return {
        "input_tokens": inp,
        "output_tokens": out,
        "total_tokens": inp + out,
        "cached_input_tokens": cached,
        "reasoning_tokens": 0,
    }


def body(book, pass_name, *, valid=True, cached=0):
    aid = book.state["current"]["annotation_id"]
    answer = {
        "annotation_id": aid,
        "state": "uncertain",
        "grade": None,
        "uncertain": True,
        "reason": "SYNTHETIC TEST ONLY",
        "supporting_fields": [],
        "occurrence_ids": [],
    }
    return {
        "id": f"resp_{aid}_{pass_name}",
        "model": p.legacy.MODEL,
        "status": "completed",
        "service_tier": "default",
        "usage": {
            "input_tokens": 100,
            "output_tokens": 10,
            "total_tokens": 110,
            "input_tokens_details": {"cached_tokens": cached},
            "output_tokens_details": {"reasoning_tokens": 0},
        },
        "output": [
            {
                "type": "message",
                "content": [
                    {"type": "output_text", "text": json.dumps(answer) if valid else "invalid JSON"}
                ],
            }
        ],
    }


def test_frozen_contract_and_deterministic_order(prepared):
    directory, c, order = prepared
    assert c["pair_count"] == len(order["pairs"]) == 1506
    assert c["request_count"] == 3012 and c["passes"] == list(p.PASSES)
    assert c["machine-c"] == "forbidden" and c["max_attempts_per_request"] == 1
    assert c["operator_hard_cap_usd"] == "12.00"
    assert c["max_input_tokens"] == 37306150 and c["max_output_tokens"] == 3614400
    assert p.ordered(list(reversed(order["pairs"]))) == order["pairs"]
    pre = read(directory / "budget-preflight.json")
    assert pre["legacy_full_envelope_usd"] == "44.2444125"
    assert pre["legacy_12_usd_guard_result"] == "amount_budget_too_small"
    assert pre["first_pair_fits_money_cap"] and not pre["full_completion_guaranteed"]
    assert pre["api_requests"] == 0
    assert {r["annotation_id"] for r in order["pairs"]} == {
        r["annotation_id"] for r in p.legacy.load_packet(p.legacy.PACKAGE)[0]
    }
    assert set(order["pairs"][0]) == {
        "annotation_id",
        "payload_sha256",
        "payload_bytes",
        "estimated_input_tokens",
        "estimated_output_tokens",
        "oversized",
    }


@pytest.mark.parametrize(
    "key,value",
    [
        ("model", "other"),
        ("max_amount_usd", "12.01"),
        ("max_input_tokens", 1),
        ("max_output_tokens", 1),
        ("pair_count", 1),
        ("request_count", 3013),
        ("pass_count", 3),
        ("prompt_sha256", "changed"),
        ("packet_sha256", "changed"),
        ("prices_sha256", "changed"),
        ("order_sha256", "changed"),
        ("contract_sha256", "changed"),
        ("legacy_contract_sha256", "changed"),
        ("legacy_cost_report_sha256", "changed"),
        ("approval_reference", " "),
        ("contract_review_reference", ""),
        ("execution_root", "/tmp/wrong"),
    ],
)
def test_invalid_approval(prepared, approval, key, value):
    directory, c, order = prepared
    root = Path(approval["execution_root"])
    approval[key] = value
    with pytest.raises(ValueError):
        p.check_approval(approval, c, order, directory, root)


def test_new_approval_accepted_old_guard_unchanged(prepared, approval, tmp_path):
    directory, c, order = prepared
    assert (
        p.check_approval(approval, c, order, directory, Path(approval["execution_root"]))[
            "max_amount_usd"
        ]
        == "12.00"
    )
    with pytest.raises(ValueError):
        p.legacy.Approval.model_validate(approval)
    # Independently demonstrate legacy full-envelope rejection, with its real unchanged function.
    old = read(p.legacy.DEST / "execution-contract.json")
    cost = read(p.legacy.DEST / "cost-report.json")
    cost["operator_prices"] = {
        k: c["prices"][k] for k in ("currency", "input_per_million", "output_per_million")
    }
    d = tmp_path / "priced"
    atomic_new(d / "execution-contract.json", old)
    atomic_new(d / "cost-report.json", cost)
    a = {k: v for k, v in approval.items() if k in p.legacy.Approval.model_fields}
    a.update(
        schema_version="category-two-pass-approval-v1",
        contract_sha256=sha((d / "execution-contract.json").read_bytes()),
        cost_report_sha256=sha((d / "cost-report.json").read_bytes()),
    )
    with pytest.raises(ValueError, match="amount_budget_too_small"):
        p.legacy.approve(a, old, d, "machine-a", Path(a["execution_root"]) / "machine-a")


def test_pair_budget_is_atomic_and_preserves_b(ledger):
    s = ledger.append({"kind": "admit"})
    reserved = Decimal(s["outstanding_usd"])
    assert reserved > 0
    with pytest.raises(ValueError, match="a_before_b"):
        ledger.request_intent("machine-b")
    a = ledger.request_intent("machine-a")
    after_a = ledger.record_response("machine-a", body(ledger, "machine-a", cached=50))
    assert after_a["completed_pairs"] == 0 and after_a["status"] == "pair_partial"
    assert Decimal(after_a["outstanding_usd"]) == reserved / 2
    assert ledger.resume_action() == "dispatch_reserved_machine_b_only"
    with pytest.raises(ValueError, match="cannot_admit"):
        ledger.append({"kind": "admit"})
    b = ledger.request_intent("machine-b")
    assert a["payload"] == b["payload"] and a["client_request_id"] != b["client_request_id"]
    assert set(json.loads(b["payload"]["input"][0]["content"])) == {
        "annotation_id",
        "query",
        "rubric",
        "eligibility",
        "evidence",
    }
    assert "SYNTHETIC TEST ONLY" not in json.dumps(b["payload"])
    assert b["payload"]["store"] is False and b["payload"]["reasoning"] == {"effort": "none"}
    assert not {"tools", "previous_response_id"} & b["payload"].keys()
    final = ledger.record_response("machine-b", body(ledger, "machine-b"))
    assert final["completed_pairs"] == 1 and final["current"] is None
    assert Decimal(final["outstanding_usd"]) == 0
    assert final["reserved_output_per_pass"] == 1200  # No token refund for short answers.
    assert Decimal(final["actual_usd"]) == Decimal("0.00020625")
    with pytest.raises(ValueError):
        ledger.request_intent("machine-c")


def test_budget_exhaustion_balanced_prefix(prepared, approval):
    _, c, order = prepared
    s = p.initial_state(approval)
    while s["status"] == "ready":
        s = p.admit(s, c, order)
        if s["status"] != "pair_reserved":
            break
        row = order["pairs"][s["completed_pairs"]]
        for name in p.PASSES:
            s = p.dispatch(s, name)
            s = p.settle(
                s,
                name,
                measured(row["estimated_input_tokens"], 1200),
                f"r_{s['completed_pairs']}_{name}",
                c,
                order,
            )
            assert Decimal(s["actual_usd"]) + Decimal(s["outstanding_usd"]) <= 12
    assert s["status"] == "budget_exhausted_partial" and 0 < s["completed_pairs"] < 1506
    assert s["current"] is None and s["dispatched_requests"] == 2 * s["completed_pairs"]
    with pytest.raises(ValueError):
        p.admit(s, c, order)
    with pytest.raises(ValueError, match="no_consensus"):
        p.require_complete(s)
    with pytest.raises(ValueError, match="new_explicit"):
        p.continue_budget(s, approval)
    new = {
        **approval,
        "kind": "continuation",
        "approval_reference": "SYNTHETIC NEW APPROVAL",
        "previous_approval_sha256": s["approval_sha256"],
        "stopped_state_sha256": digest(s),
    }
    resumed = p.continue_budget(s, new)
    for key in (
        "actual_usd",
        "reserved_input_per_pass",
        "reserved_output_per_pass",
        "completed_pairs",
    ):
        assert resumed[key] == s[key]
    assert p.admit(resumed, c, order)["status"] == "budget_exhausted_partial"


def test_full_low_usage_maintains_hard_token_limits(prepared, approval):
    _, c, order = prepared
    s = p.initial_state(approval)
    for i in range(1506):
        s = p.admit(s, c, order)
        for name in p.PASSES:
            s = p.settle(p.dispatch(s, name), name, measured(), f"response_{i}_{name}", c, order)
    p.require_complete(s)
    assert s["reserved_input_per_pass"] == c["per_pass_input_ceiling"]
    assert s["reserved_output_per_pass"] == c["per_pass_output_ceiling"]
    assert s["dispatched_requests"] == 3012


@pytest.mark.parametrize("counter", ["reserved_input_per_pass", "reserved_output_per_pass"])
def test_technical_limits_independent_of_money(prepared, approval, counter):
    _, c, order = prepared
    s = p.initial_state(approval)
    s[counter] = c["per_pass_input_ceiling" if "input" in counter else "per_pass_output_ceiling"]
    result = p.admit(s, c, order)
    assert result["status"] == "technical_limit_partial" and result["dispatched_requests"] == 0


def test_resume_lock_and_no_resend(ledger, prepared):
    ledger.append({"kind": "admit"})
    ledger.request_intent("machine-a")
    assert ledger.resume_action() == "operator_audit_required_no_resend"
    with pytest.raises(ValueError):
        ledger.request_intent("machine-a")
    with pytest.raises(BlockingIOError), p.Ledger(prepared[0], ledger.output):
        pass
    # Simulate crash after atomic response publication, before settlement journal append.
    response = body(ledger, "machine-a")
    atomic_new(ledger.response_path("machine-a"), response)
    assert ledger.resume_action() == "reconcile_saved_response_offline"
    ledger.lock.close()
    with p.Ledger(prepared[0], ledger.output) as resumed:
        assert resumed.resume_action() == "reconcile_saved_response_offline"
        resumed.record_response("machine-a", response)
        assert resumed.resume_action() == "dispatch_reserved_machine_b_only"
        with pytest.raises(ValueError):
            resumed.request_intent("machine-a")


def test_failure_holds_reservation(ledger):
    before = ledger.append({"kind": "admit"})
    ledger.request_intent("machine-a")
    failed = ledger.append({"kind": "fail"})
    assert failed["outstanding_usd"] == before["outstanding_usd"]
    assert ledger.resume_action() == "operator_audit_required_no_resend"
    with pytest.raises(ValueError):
        ledger.append({"kind": "admit"})
    with pytest.raises(ValueError):
        ledger.request_intent("machine-b")


@pytest.mark.parametrize("fault", ["json", "tier", "model", "usage", "overbudget"])
def test_invalid_response_no_refund_or_repair(ledger, fault):
    ledger.append({"kind": "admit"})
    ledger.request_intent("machine-a")
    before = deepcopy(ledger.state)
    response = body(ledger, "machine-a", valid=fault != "json")
    if fault == "tier":
        response["service_tier"] = "priority"
    if fault == "model":
        response["model"] = "other"
    if fault == "usage":
        response["usage"]["input_tokens_details"]["cached_tokens"] = 101
    if fault == "overbudget":
        response["usage"].update(input_tokens=999999, total_tokens=1000009)
    with pytest.raises(ValueError):
        ledger.record_response("machine-a", response)
    assert ledger.state == before
    with pytest.raises(ValueError, match="never_overwrite"):
        ledger.record_response("machine-a", body(ledger, "machine-a"))


def test_journal_tampering_rejected(ledger, prepared):
    ledger.append({"kind": "admit"})
    path = ledger.output / "journal/000001.json"
    data = read(path)
    data["previous_sha256"] = "0" * 64
    path.write_text(json.dumps(data))
    ledger.lock.close()
    with pytest.raises(ValueError, match="journal_chain"), p.Ledger(prepared[0], ledger.output):
        pass


def test_offline_no_approval_no_transport(prepared, tmp_path, monkeypatch):
    monkeypatch.setattr(socket, "socket", lambda *a, **k: pytest.fail("network"))
    directory, _, _ = prepared
    copy = tmp_path / "regenerated"
    p.prepare(copy)
    for file in directory.iterdir():
        assert file.read_bytes() == (copy / file.name).read_bytes()
    with p.Ledger(directory, tmp_path / "unapproved") as book:
        with pytest.raises(ValueError, match="approval_required"):
            book.append({"kind": "admit"})
    assert not list(copy.glob("*approval.json"))
    source = Path(p.__file__).read_text()
    assert "OPENAI_API_KEY" not in source and "CategoryJudge(" not in source
    assert "async def" not in source


def test_pair_reservation_exact_boundary_and_not_just_a(prepared, approval):
    _, c, order = prepared
    each = p.reservation_cost(order["pairs"][0], c)
    s = p.initial_state(approval)
    s["actual_usd"] = str(Decimal("12.00") - each)
    stopped = p.admit(s, c, order)
    assert stopped["status"] == "budget_exhausted_partial"
    assert stopped["current"] is None and stopped["dispatched_requests"] == 0
    s["actual_usd"] = str(Decimal("12.00") - 2 * each)
    allowed = p.admit(s, c, order)
    assert allowed["status"] == "pair_reserved"
    assert Decimal(allowed["actual_usd"]) + Decimal(allowed["outstanding_usd"]) == 12


def test_unknown_cache_no_discount_and_reasoning_not_double_billed(prepared, approval):
    _, c, order = prepared
    s = p.dispatch(p.admit(p.initial_state(approval), c, order), "machine-a")
    u = measured(cached=None)
    u["reasoning_tokens"] = 5
    result = p.settle(s, "machine-a", u, "resp_synthetic", c, order)
    assert Decimal(result["actual_usd"]) == Decimal("0.00012")
    for bad in (
        {**u, "input_tokens": -1},
        {**u, "cached_input_tokens": 101},
        {**u, "reasoning_tokens": 11},
        {**u, "total_tokens": 999},
    ):
        with pytest.raises(ValueError):
            p.settle(s, "machine-a", bad, "resp_synthetic", c, order)


def test_artifact_tampering_fail_closed(prepared, tmp_path):
    import shutil

    directory = tmp_path / "changed-contract"
    shutil.copytree(prepared[0], directory)
    order = read(directory / "request-order.json")
    order["pairs"].reverse()
    (directory / "request-order.json").write_text(json.dumps(order))
    with pytest.raises(ValueError, match="artifact_changed"):
        p.load(directory)


def test_no_transport_cli(tmp_path):
    import subprocess
    import sys

    result = subprocess.run([sys.executable, "-m", p.__name__, "run"], capture_output=True)
    assert result.returncode != 0 and b"invalid choice" in result.stderr
    assert b"OPENAI_API_KEY" not in result.stderr


def test_continuation_requires_both_state_and_approval(prepared, approval):
    _, c, order = prepared
    s = p.initial_state(approval)
    s["actual_usd"] = "12.00"
    stopped = p.admit(s, c, order)
    a = {
        **approval,
        "kind": "continuation",
        "previous_approval_sha256": s["approval_sha256"],
        "stopped_state_sha256": digest(stopped),
    }
    for key in ("previous_approval_sha256", "stopped_state_sha256"):
        with pytest.raises(ValueError, match="new_explicit_approval_required"):
            p.continue_budget(stopped, {**a, key: "wrong"})
    resumed = p.continue_budget(stopped, a)
    assert resumed["actual_usd"] == "12.00"
    assert p.admit(resumed, c, order)["status"] == "budget_exhausted_partial"


def test_published_contract_reproducible(prepared):
    for source in prepared[0].iterdir():
        assert source.read_bytes() == (p.DEST / source.name).read_bytes()
    c, order = p.load(p.DEST)
    assert len(set(c["run_ids"].values())) == 2
    assert c["pass_output_directories"] == {name: name for name in p.PASSES}
    assert c["parameters"] == read(p.legacy.DEST / "execution-contract.json")["parameters"]
    assert c["preparation_only"] is True and c["transport_enabled"] is False
    assert set(f.name for f in p.DEST.iterdir()) == {
        "execution-contract.json",
        "request-order.json",
        "approval-schema.json",
        "budget-preflight.json",
        "artifact-sha256.json",
    }
    assert len(order["pairs"]) == 1506


def test_pass_c_approval_forbidden(prepared, approval):
    directory, c, order = prepared
    approval["passes"]["machine-c"] = "approved"
    with pytest.raises(ValueError):
        p.check_approval(approval, c, order, directory, Path(approval["execution_root"]))


def test_no_ledger_writes_in_historical_tree(prepared):
    output = Path("benchmark/forbidden-ledger-test").resolve()
    assert not output.exists()
    with pytest.raises(ValueError, match="external_ledger_root_required"):
        p.Ledger(prepared[0], output)
    assert not output.exists()
