"""No live API: immutable real bindings, synthetic independent one-request responses."""

import json
from copy import deepcopy
from decimal import Decimal
from pathlib import Path

import httpx
import pytest

from uranus_research_service import category_single_repair as r
from uranus_research_service.machine_judge import APIError, atomic_new, digest, read, sha


@pytest.fixture(scope="module")
def context():
    return r.contract_data()


@pytest.fixture
def setup(context, tmp_path, monkeypatch):
    values = deepcopy(context)
    values[0]["execution_root"] = str(tmp_path / "run")
    monkeypatch.setattr(r, "contract_data", lambda: deepcopy(values))
    directory = tmp_path / "contract"
    r.prepare(directory)
    approval = r.approve(directory, "SYNTHETIC TEST AUTHORIZATION ONLY")
    auth_path = tmp_path / "approval.json"
    atomic_new(auth_path, approval)
    monkeypatch.setenv("OPENAI_API_KEY", "synthetic-secret-never-log")
    return directory, auth_path, values


def response(candidate, grade=1, fields=None):
    answer = {
        "annotation_id": r.ANNOTATION,
        "state": "graded",
        "grade": grade,
        "uncertain": False,
        "reason": "SYNTHETIC TEST ONLY; no real judgment",
        "supporting_fields": ["space_accessibility"] if fields is None else fields,
        "occurrence_ids": [r.OCCURRENCE],
    }
    return {
        "id": "resp_synthetic_new_repair",
        "model": r.MODEL,
        "status": "completed",
        "service_tier": "default",
        "usage": {
            "input_tokens": 100,
            "output_tokens": 10,
            "total_tokens": 110,
            "input_tokens_details": {"cached_tokens": 20},
            "output_tokens_details": {"reasoning_tokens": 0},
        },
        "output": [
            {"type": "message", "content": [{"type": "output_text", "text": json.dumps(answer)}]}
        ],
    }


def saved_files(root):
    return {p.name: sha(p.read_bytes()) for p in root.glob("*.json")}


def saved_text(root):
    return "".join(p.read_text() for p in root.glob("*.json"))


class Judge:
    def __init__(self, value):
        self.value, self.calls = value, []

    async def request(self, *args):
        self.calls.append(args)
        if isinstance(self.value, BaseException):
            raise self.value
        return deepcopy(self.value), "req_synthetic_repair"

    async def close(self):
        pass


def test_exact_scope_and_bindings(context):
    c, _, payload, state = context
    assert c["annotation_id"] == "a0c166936ef7233017150f87aad87df5"
    assert c["pass_name"] == "machine-b" and c["max_requests"] == c["repair_attempt"] == 1
    assert c["original_receipt_sha256"] == r.RECEIPT_SHA
    assert c["original_failure_state_sha256"] == digest(state) == r.STATE_SHA
    assert c["original_run_bundle_sha256"] == r.BUNDLE_SHA
    assert c["model"] == "gpt-5.4-mini-2026-03-17"
    assert c["original_request_cost_usd"] == "0.00095565"
    assert Decimal(c["original_run_usage_cost_usd"]) == Decimal("0.08962620")
    assert c["prompt_changed"] is False
    assert payload["instructions"] == r.budget.legacy.PROMPT.read_text()
    assert c["prompt_sha256"] == c["original_prompt_sha256"]
    assert c["conservative_request_ceiling_usd"] == "0.01526175"
    assert c["max_input_tokens"] == 13149 and c["max_output_tokens"] == 1200
    assert c["repair_client_request_id"] != c["original_client_request_id"]
    with pytest.raises(ValueError, match="no_consensus"):
        r.budget.require_complete(state)


@pytest.mark.parametrize(
    "field,value",
    [
        ("annotation_id", "0" * 32),
        ("pass_name", "machine-a"),
        ("max_requests", 2),
        ("model", "another-model"),
        ("packet_sha256", "0" * 64),
        ("prompt_sha256", "0" * 64),
        ("original_receipt_sha256", "0" * 64),
        ("original_run_bundle_sha256", "0" * 64),
        ("original_failure_state_sha256", "0" * 64),
        ("repair_contract_sha256", "0" * 64),
        ("max_amount_usd", "1.00"),
        ("max_input_tokens", 14000),
        ("max_output_tokens", 1300),
        ("approved", False),
        ("original_receipt_may_not_be_overwritten", False),
        ("validator_may_not_be_relaxed", False),
        ("execution_root", "/tmp/other-run"),
    ],
)
async def test_invalid_approval_prevents_transport(setup, tmp_path, field, value):
    directory, approval_path, values = setup
    approval = read(approval_path)
    approval[field] = value
    bad = tmp_path / "bad.json"
    atomic_new(bad, approval)
    judge = Judge(response(values[1]))
    with pytest.raises(ValueError):
        await r.execute(directory, bad, judge_factory=lambda _: judge)
    assert not judge.calls


async def test_no_approval_no_request(setup, tmp_path):
    directory, _, values = setup
    judge = Judge(response(values[1]))
    with pytest.raises(FileNotFoundError):
        await r.execute(directory, tmp_path / "missing.json", judge_factory=lambda _: judge)
    assert not judge.calls


async def test_accepted_receipt_then_append_only_reconciliation(setup, tmp_path, monkeypatch):
    directory, approval, values = setup
    root = Path(values[0]["execution_root"])
    judge = Judge(response(values[1]))
    original_finish = r.finish

    def checked_finish(*args):
        assert (root / "repair-receipt.json").exists()
        assert not (root / "repair-outcome.json").exists()
        return original_finish(*args)

    monkeypatch.setattr(r, "finish", checked_finish)
    result = await r.execute(directory, approval, judge_factory=lambda _: judge)
    assert len(judge.calls) == 1 and result["repair_status"] == "accepted"
    rec = read(root / "repair-reconciliation.json")
    assert rec["original_machine_b_receipt"] == "rejected"
    assert rec["effective_response_source"] == "repair-v1"
    assert rec["effective_pair_completion"] == "repaired"
    assert rec["effective_completed_pairs"] == 28
    assert rec["repair_reconciliation_status"] == "ready_for_reviewed_continuation"
    assert rec["original_ledger_status"] == "request_failed_partial"
    assert rec["consensus_allowed"] is False
    assert r.verify_run(directory, root) == result
    published = tmp_path / "published"
    r.publish(directory, root, published)
    assert r.verify_run(directory, published) == result
    with pytest.raises(ValueError, match="exclusive_publish"):
        r.publish(directory, root, published)
    hashes = saved_files(root)
    with pytest.raises(ValueError, match="no_resend"):
        await r.execute(directory, approval, judge_factory=lambda _: judge)
    assert hashes == saved_files(root)
    assert len(judge.calls) == 1
    assert Decimal(result["repair_cost_usd"]) == Decimal("0.00010650")
    assert result["cumulative_usage_cost_usd"] == "0.08973270"
    assert "synthetic-secret-never-log" not in saved_text(root)


@pytest.mark.parametrize(
    "failure",
    [
        "empty",
        "unknown",
        "refusal",
        "malformed",
        "wrong_model",
        "foreign_occurrence",
        "output_ceiling",
        "input_ceiling",
        "old_id",
    ],
)
async def test_bad_response_terminal_no_repair_or_retry(setup, failure):
    directory, approval, values = setup
    c, candidate, _, _ = values
    body = response(candidate)
    if failure == "empty":
        body = response(candidate, fields=["venue_accessibility"])
    elif failure == "unknown":
        body = response(candidate, fields=["not_a_real_field"])
    elif failure == "refusal":
        body["output"][0]["content"] = [{"type": "refusal", "refusal": "SYNTHETIC"}]
    elif failure == "malformed":
        body["output"][0]["content"][0]["text"] = "{broken"
    elif failure == "wrong_model":
        body["model"] = "other-model"
    elif failure == "old_id":
        body["id"] = c["original_response_id"]
    elif failure == "foreign_occurrence":
        a = json.loads(body["output"][0]["content"][0]["text"])
        a["occurrence_ids"] = ["00000000-0000-0000-0000-000000000000"]
        body["output"][0]["content"][0]["text"] = json.dumps(a)
    else:
        field = "output_tokens" if failure == "output_ceiling" else "input_tokens"
        body["usage"][field] = c["max_" + field] + 1
        body["usage"]["total_tokens"] = (
            body["usage"]["input_tokens"] + body["usage"]["output_tokens"]
        )
    judge = Judge(body)
    result = await r.execute(directory, approval, judge_factory=lambda _: judge)
    assert result["repair_status"] == "rejected" and len(judge.calls) == 1
    root = Path(c["execution_root"])
    assert read(root / "repair-receipt.json") == body
    assert read(root / "repair-reconciliation.json")["repair_reconciliation_status"] == "blocked"
    assert r.verify_run(directory, root) == result


@pytest.mark.parametrize("error", ["rate_limit", "temporary_http", "network"])
async def test_transient_also_terminal(setup, error):
    directory, approval, values = setup
    judge = Judge(APIError(error, retry=True))
    result = await r.execute(directory, approval, judge_factory=lambda _: judge)
    assert result["repair_status"] == "rejected" and len(judge.calls) == 1
    assert result["repair_cost_usd"] is None and result["usage_status"] == "unknown"
    assert not (Path(values[0]["execution_root"]) / "repair-receipt.json").exists()


async def test_crash_never_resends(setup):
    directory, approval, values = setup
    judge = Judge(KeyboardInterrupt())
    with pytest.raises(KeyboardInterrupt):
        await r.execute(directory, approval, judge_factory=lambda _: judge)
    assert (
        read(Path(values[0]["execution_root"]) / "repair-attempt.json")["repair_status"]
        == "pending"
    )
    with pytest.raises(ValueError, match="no_resend"):
        await r.execute(directory, approval, judge_factory=lambda _: judge)
    assert len(judge.calls) == 1


async def test_actual_http_request_is_exact_original_blind_payload(setup):
    directory, approval, values = setup
    c, candidate, payload, _ = values
    captured = []

    def handler(req):
        assert req.url.path == "/v1/responses"
        assert sha(req.content) == c["payload_sha256"]
        assert json.loads(req.content) == payload
        assert req.headers["X-Client-Request-Id"] == c["repair_client_request_id"]
        captured.append(req.content)
        return httpx.Response(200, json=response(candidate))

    def factory(key):
        return r.budget.legacy.CategoryJudge(key, transport=httpx.MockTransport(handler))

    await r.execute(directory, approval, judge_factory=factory)
    assert len(captured) == 1
    assert payload["store"] is False and payload["reasoning"] == {"effort": "none"}
    assert payload["temperature"] == 0 and payload["max_output_tokens"] == 1200
    assert "tools" not in payload and "previous_response_id" not in payload
    content = json.loads(payload["input"][0]["content"])
    assert set(content) == {
        "annotation_id",
        "query",
        "rubric",
        "eligibility",
        "evidence",
    }
    assert "original_response_id" not in content and "repair_attempt" not in content


def test_stricter_whitespace_and_negative_citations(context):
    c, candidate, _, state = deepcopy(context)
    for occ in candidate["event"]["occurrences"]:
        if occ["id"] == r.OCCURRENCE:
            occ["space_accessibility"] = "  \n "
    with pytest.raises(ValueError, match="repair_empty"):
        r.validate_response(response(candidate), candidate, c, state)
    with pytest.raises(ValueError, match="repair_empty"):
        r.validate_response(response(candidate, grade=0), candidate, c, state)


def test_real_original_artifacts_unchanged(context):
    c = context[0]
    for path, expected in c["original_hashes"].items():
        assert sha(Path(path).read_bytes()) == expected
    code = Path(r.__file__).read_text()
    assert "Ledger(" not in code
    assert "classify(" not in code
    assert "retry_count" not in code
    assert "gpt-6-astra" not in code


@pytest.mark.parametrize("binding", ["BUNDLE_SHA", "RECEIPT_SHA", "STATE_SHA"])
def test_original_hash_mismatch_fails_closed(monkeypatch, binding):
    monkeypatch.setattr(r, binding, "0" * 64)
    with pytest.raises(ValueError, match="original_.*changed"):
        r.original_context()


@pytest.mark.parametrize("status", [429, 500, 503])
async def test_real_transport_statuses_never_retry(setup, status):
    directory, approval, _ = setup
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(status, json={"error": "SYNTHETIC PRIVATE ERROR DO NOT LOG"})

    def factory(key):
        return r.budget.legacy.CategoryJudge(key, transport=httpx.MockTransport(handler))

    result = await r.execute(directory, approval, judge_factory=factory)
    assert result["repair_status"] == "rejected"
    assert len(calls) == 1
    assert "SYNTHETIC PRIVATE ERROR" not in saved_text(Path(setup[2][0]["execution_root"]))


async def test_outcome_tampering_rejected_on_offline_audit(setup):
    directory, approval, values = setup
    judge = Judge(response(values[1], fields=["venue_accessibility"]))
    await r.execute(directory, approval, judge_factory=lambda _: judge)
    root = Path(values[0]["execution_root"])
    result = read(root / "repair-outcome.json")
    result["repair_status"] = "accepted"
    # Deliberately corrupt a synthetic fixture, never a historical/live artifact.
    (root / "repair-outcome.json").write_text(json.dumps(result))
    with pytest.raises(ValueError, match="repair_outcome_changed"):
        r.verify_run(directory, root)


@pytest.mark.parametrize(
    "body",
    [
        [],
        None,
        {
            "output": "invalid-envelope",
            "model": r.MODEL,
            "status": "completed",
            "service_tier": "default",
        },
    ],
)
async def test_malformed_provider_envelope_is_terminal(setup, body):
    directory, approval, _ = setup
    judge = Judge(body)
    result = await r.execute(directory, approval, judge_factory=lambda _: judge)
    assert result["repair_status"] == "rejected" and len(judge.calls) == 1
    assert result["failure_category"] == "response_contract_violation"


def test_prepared_artifacts_match_frozen_code_and_context(context):
    contract = read(r.DEST / "repair-contract.json")
    assert contract == context[0]
    assert read(r.DEST / "repair-request-binding.json") == r.request_binding(contract)
    assert read(r.DEST / "repair-approval-schema.json") == r.Approval.model_json_schema()
    for name, expected in read(r.DEST / "artifact-sha256.json").items():
        assert sha((r.DEST / name).read_bytes()) == expected


def test_published_real_repair_revalidates_offline(monkeypatch):
    import socket

    def forbidden(*args, **kwargs):
        raise AssertionError("offline audit must not access network")

    monkeypatch.setattr(socket, "create_connection", forbidden)
    outcome = r.verify_run(r.DEST, r.DEST)
    assert outcome["repair_status"] == "accepted"
    assert (
        outcome["repair_response_id"] == "resp_095618ad43f47a30016ac71392005c87d294f616816111acfb"
    )
    assert outcome["repair_usage"] == {
        "input_tokens": 1927,
        "output_tokens": 147,
        "total_tokens": 2074,
        "cached_input_tokens": 0,
        "reasoning_tokens": 0,
    }
    assert outcome["repair_cost_usd"] == "0.00210675"
    assert outcome["cumulative_usage_cost_usd"] == "0.09173295"
    assert outcome["original_request_status"] == "rejected"
    assert outcome["consensus_allowed"] is False and outcome["continuation_allowed"] is False
    for name, expected in read(r.DEST / "repair-run-sha256.json").items():
        assert sha((r.DEST / name).read_bytes()) == expected


def test_real_reconciliation_does_not_unlock_old_state(context):
    rec = read(r.DEST / "repair-reconciliation.json")
    assert rec["effective_completed_pairs"] == 28
    assert rec["repair_reconciliation_status"] == "ready_for_reviewed_continuation"
    assert context[3]["status"] == "request_failed_partial"
    assert context[3]["completed_pairs"] == 27
    with pytest.raises(ValueError, match="no_consensus"):
        r.budget.require_complete(context[3])
    assert rec["original_reservation_unchanged_usd"] == "0.01526175"
