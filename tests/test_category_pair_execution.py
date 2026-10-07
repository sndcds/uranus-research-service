"""Synthetic transport only. The real frozen Ledger handles every spending decision."""

import json
from copy import deepcopy
from pathlib import Path

import httpx
import pytest

from tests import test_category_pair_budget as fixtures
from uranus_research_service import category_pair_execution as e
from uranus_research_service.machine_judge import APIError, atomic_new, read

prepared = fixtures.prepared
approval = fixtures.approval
ledger = fixtures.ledger
body = fixtures.body


class Judge:
    def __init__(self, book, fail_at=2, crash=False, invalid=False):
        self.book, self.fail_at, self.crash, self.invalid = book, fail_at, crash, invalid
        self.calls = []

    async def request(self, method, path, payload, client_id):
        self.calls.append((method, path, deepcopy(payload), client_id))
        assert self.book.state["status"] == "in_flight"
        if self.crash:
            raise KeyboardInterrupt
        if len(self.calls) == self.fail_at:
            raise APIError("rate_limit", True)
        name = next(k for k, v in self.book.state["current"]["passes"].items() if v == "in_flight")
        return body(self.book, name, valid=not self.invalid), "req_synthetic"


async def test_one_attempt_no_retry_and_separate_payloads(ledger):
    judge = Judge(ledger)
    state = await e.drive(ledger, judge)
    assert state["status"] == "request_failed_partial"
    assert len(judge.calls) == 2 and state["completed_pairs"] == 0
    assert judge.calls[0][2] == judge.calls[1][2]
    assert judge.calls[0][3] != judge.calls[1][3]
    assert state["current"]["passes"] == {"machine-a": "settled", "machine-b": "in_flight"}
    await e.drive(ledger, judge)
    assert len(judge.calls) == 2
    with pytest.raises(ValueError, match="no_consensus"):
        e.consensus(ledger)


async def test_receipt_precedes_settlement_and_invalid_no_retry(ledger, monkeypatch):
    original = ledger.append

    def append(op):
        if op["kind"] == "settle":
            assert ledger.response_path(op["pass_name"]).is_file()
        return original(op)

    monkeypatch.setattr(ledger, "append", append)
    judge = Judge(ledger, invalid=True)
    assert (await e.drive(ledger, judge))["status"] == "request_failed_partial"
    assert len(judge.calls) == 1
    assert ledger.response_path("machine-a").exists()


async def test_crash_no_blind_resend(ledger):
    judge = Judge(ledger, crash=True)
    with pytest.raises(KeyboardInterrupt):
        await e.drive(ledger, judge)
    assert ledger.resume_action() == "operator_audit_required_no_resend"
    assert (await e.drive(ledger, judge))["status"] == "in_flight"
    assert len(judge.calls) == 1


async def test_saved_receipt_reconciles_offline_then_only_b(ledger):
    ledger.append({"kind": "admit"})
    ledger.request_intent("machine-a")
    atomic_new(ledger.response_path("machine-a"), body(ledger, "machine-a"))
    judge = Judge(ledger, fail_at=1)
    await e.drive(ledger, judge)
    assert len(judge.calls) == 1
    assert ledger.state["current"]["passes"]["machine-a"] == "settled"
    assert ledger.state["dispatched_requests"] == 2


@pytest.mark.parametrize(
    "status", ["budget_exhausted_partial", "technical_limit_partial", "request_failed_partial"]
)
async def test_terminal_stops_no_transport(ledger, status):
    ledger.state["status"] = status
    judge = Judge(ledger)
    await e.drive(ledger, judge)
    assert not judge.calls


async def test_actual_http_payload_and_receipt(ledger):
    calls = []

    def respond(request):
        payload = json.loads(request.content)
        calls.append(payload)
        assert request.url.path == "/v1/responses"
        assert payload["model"] == "gpt-5.4-mini-2026-03-17"
        assert payload["store"] is False
        assert payload["reasoning"] == {"effort": "none"}
        assert "previous_response_id" not in payload
        assert not payload.get("tools")
        assert payload["text"]["format"]["strict"] is True
        assert "SYNTHETIC TEST ONLY" not in request.content.decode()
        assert "historical_grade" not in request.content.decode()
        if len(calls) == 2:
            return httpx.Response(429)
        return httpx.Response(200, json=body(ledger, "machine-a"))

    judge = e.budget.legacy.CategoryJudge(
        "synthetic-secret", transport=httpx.MockTransport(respond)
    )
    try:
        await e.drive(ledger, judge)
    finally:
        await judge.close()
    assert len(calls) == 2 and calls[0] == calls[1]
    assert all("synthetic-secret" not in p.read_text() for p in ledger.output.rglob("*.json"))
    report = e.summarize(ledger)
    assert report["passes"]["machine-a"]["settled"] == 1
    assert report["unknown_usage_possible"] is True


async def test_offline_export_replay_tampering_and_no_partial_consensus(ledger, approval, tmp_path):
    atomic_new(ledger.output / "execution.json", e.binding(approval))
    await e.drive(ledger, Judge(ledger))
    # Release lock before the ordinary exporter reacquires it.
    ledger.lock.close()
    dest = tmp_path / "published"
    e.export_run(ledger.output, dest)
    assert not (dest / "machine-consensus.json").exists()
    state = e.validate_bundle(dest / "run-bundle.json")
    assert state == ledger.state
    bundle = read(dest / "run-bundle.json")
    key = next(k for k in bundle["files"] if "/responses/" in k)
    bundle["files"][key] += " "
    atomic_new(tmp_path / "tampered.json", bundle)
    with pytest.raises(ValueError, match="bundle_hash"):
        e.validate_bundle(tmp_path / "tampered.json")
    with pytest.raises(ValueError, match="exclusive_export"):
        e.export_run(ledger.output, dest)


def test_binding_changes_fail_resume(approval):
    before = e.binding(approval)
    modified = deepcopy(approval)
    modified["model"] = "other"
    assert e.binding(modified) != before


def test_no_parallel_budget_logic_or_retrieval():
    code = Path(e.__file__).read_text()
    assert "require_complete(book.state)" in code
    assert "reservation_cost(" not in code and "budget.admit(" not in code
    assert "await judge.request(" in code
    for forbidden in ("qdrant", "encoder", "sqlalchemy", "asyncpg", "sleep(", "reevaluate("):
        assert forbidden not in code


async def test_execute_requires_approval_and_explicit_resume(
    ledger, approval, tmp_path, monkeypatch
):
    approval_file = tmp_path / "approval.json"
    atomic_new(approval_file, approval)
    atomic_new(ledger.output / "execution.json", e.binding(approval))
    ledger.lock.close()
    calls = []

    def forbidden(*args, **kwargs):
        calls.append(args)
        raise AssertionError("transport must not be constructed")

    monkeypatch.setattr(e.budget.legacy, "CategoryJudge", forbidden)
    with pytest.raises(ValueError, match="explicit_resume"):
        await e.execute(ledger.output, approval_file)
    changed = deepcopy(approval)
    changed["max_amount_usd"] = "99.00"
    atomic_new(tmp_path / "wrong.json", changed)
    with pytest.raises(ValueError):
        await e.execute(ledger.output, tmp_path / "wrong.json", resume=True)
    assert calls == []


def test_complete_gate_precedes_consensus_reads(ledger, monkeypatch):
    def forbidden(*args):
        raise AssertionError("no reads before completion")

    monkeypatch.setattr(e, "read", forbidden)
    with pytest.raises(ValueError, match="no_consensus"):
        e.consensus(ledger)


def test_unchanged_historical_files():
    # Frozen source and legacy code bindings are verified by the original loader.
    contract, order = e.budget.load(e.budget.DEST)
    assert contract["max_attempts_per_request"] == 1
    assert len(order["pairs"]) == 1506
    assert e.budget.preflight(contract, order)["legacy_full_envelope_usd"] == "44.2444125"


def test_complete_consensus_reuses_classification_and_keeps_followup_blind(ledger, monkeypatch):
    # Synthetic completion fixture; production completion is verified by Ledger replay.
    ledger.state.update(
        status="complete",
        completed_pairs=1506,
        dispatched_requests=3012,
        current=None,
        outstanding_usd="0",
    )
    identifiers = [r["annotation_id"] for r in ledger.order["pairs"]]

    def response(path):
        aid = path.stem
        uncertain = aid == identifiers[0]
        grade = None if uncertain else int(aid == identifiers[1] and "machine-b" in path.parts)
        answer = {
            "annotation_id": aid,
            "state": "uncertain" if uncertain else "graded",
            "grade": grade,
            "uncertain": uncertain,
            "reason": "SYNTHETIC TEST ONLY",
            "supporting_fields": [],
            "occurrence_ids": [],
        }
        if grade:
            # A synthetic positive still uses valid frozen supporting-field paths.
            answer["supporting_fields"] = ["title"]
            answer["occurrence_ids"] = ledger.packet[aid]["eligible_occurrence_ids"][:1]
        return {
            "model": e.budget.legacy.MODEL,
            "status": "completed",
            "usage": {"input_tokens": 100, "output_tokens": 10, "total_tokens": 110},
            "output": [
                {
                    "type": "message",
                    "content": [{"type": "output_text", "text": json.dumps(answer)}],
                }
            ],
        }

    monkeypatch.setattr(e, "read", response)
    result, followup = e.consensus(ledger)
    assert result["counts"] == {
        "machine_agreed": 1504,
        "machine_uncertain": 1,
        "machine_conflict": 1,
    }
    assert followup == [ledger.packet[aid] for aid in identifiers[:2]]
    assert all("status" not in row and "grade" not in row for row in followup)


def test_published_partial_run_offline_and_no_consensus(monkeypatch):
    import socket

    def forbidden(*args, **kwargs):
        raise AssertionError("published validation must remain offline")

    monkeypatch.setattr(socket, "create_connection", forbidden)
    root = Path("benchmark/review/category-coverage-machine-ab-v1/results")
    state = e.validate_bundle(root / "run-bundle.json")
    assert state["status"] == "request_failed_partial"
    assert state["completed_pairs"] == 27 and state["dispatched_requests"] == 56
    assert state["current"]["passes"] == {"machine-a": "settled", "machine-b": "in_flight"}
    with pytest.raises(ValueError, match="no_consensus"):
        e.budget.require_complete(state)
    assert not (root / "machine-consensus.json").exists()
    assert not (root / "conflict-pool.jsonl").exists()
    for name, expected in read(root / "artifact-sha256.json").items():
        assert e.sha((root / name).read_bytes()) == expected


def test_published_costs_include_rejected_receipt_without_settling_it():
    from decimal import Decimal

    root = Path("benchmark/review/category-coverage-machine-ab-v1/results")
    bundle = read(root / "run-bundle.json")
    cost = Decimal(0)
    count = 0
    for path, text in bundle["files"].items():
        if "/responses/" in path:
            measured = e.budget.usage(json.loads(text))
            cost += e.budget.price(
                measured["input_tokens"],
                measured["output_tokens"],
                measured["cached_input_tokens"],
                read(root / "usage-cost-report.json")["prices"],
            )
            count += 1
    assert count == 56
    assert cost == Decimal("0.08962620")
    report = read(root / "usage-cost-report.json")
    assert Decimal(report["settled_cost_usd"]) == Decimal("0.08867055")
    assert Decimal(report["outstanding_reservation_usd"]) == Decimal("0.01526175")
