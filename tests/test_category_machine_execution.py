"""Synthetic transport only: no API key, provider network or real judgments."""

import json
import socket
import subprocess
import sys
from pathlib import Path

import httpx
import pytest

from uranus_research_service import category_machine_execution as m
from uranus_research_service.machine_judge import APIError, read, sha


@pytest.fixture(scope="module")
def prepared(tmp_path_factory):
    path = tmp_path_factory.mktemp("category-contract") / "dry"
    m.prepare(m.PACKAGE, path, m.MODEL)
    return path


@pytest.fixture(scope="module")
def loaded(prepared):
    return m.load_execution(m.PACKAGE, prepared, m.MODEL)


def approval(directory, root):
    c, cost = read(directory / "execution-contract.json"), read(directory / "cost-report.json")
    return {
        "schema_version": "category-two-pass-approval-v1",
        "authorization": "explicit-operator-cost-approval",
        "approval_reference": "SYNTHETIC TEST ONLY; NEVER AN OPERATOR APPROVAL",
        "model": m.MODEL,
        "packet_sha256": m.PACKET_SHA,
        "prompt_sha256": c["prompt_sha256"],
        "contract_sha256": sha((directory / "execution-contract.json").read_bytes()),
        "cost_report_sha256": sha((directory / "cost-report.json").read_bytes()),
        "pair_count": 1506,
        "pass_count": 2,
        "request_count": 3012,
        "passes": {"machine-a": "approved", "machine-b": "approved", "machine-c": "forbidden"},
        "max_input_tokens": cost["estimated_input_tokens"] * 3,
        "max_output_tokens": cost["estimated_output_token_ceiling"] * 3,
        "execution_root": str(root),
    }


def test_fixed_pool_and_two_pass_contract(loaded):
    c, cost, packet, prompt, shapes = loaded
    assert c["pair_count"] == len(packet) == len(shapes) == 1506
    assert c["passes"] == ["machine-a", "machine-b"] and c["pass_count"] == 2
    assert c["planned_requests"] == cost["planned_requests"] == 3012
    assert c["machine-c"] == "disabled"
    assert c["model"] == m.MODEL
    assert len(set(c["run_ids"].values())) == 2
    assert c["prompt_sha256"] == sha(prompt.encode())
    assert c["packet_sha256"] == m.PACKET_SHA
    assert cost["operator_prices"] is cost["estimated_amount_usd"] is None
    assert sum(x["pairs"] for x in cost["per_category"].values()) == 1506
    assert len(cost["per_query"]) == 20
    assert set(cost["per_category"]) == {"outdoor", "theatre", "venue", "accessibility"}
    assert not any(s["oversized"] for s in shapes)


def test_all_actual_http_payloads_are_blind(loaded):
    _, cost, packet, prompt, shapes = loaded
    for candidate, s in zip(packet, shapes, strict=True):
        payload = m.request_for(candidate, m.MODEL, prompt)
        request = httpx.Request("POST", m.URL, json=payload)
        assert sha(request.content) == s["payload_sha256"]
        assert len(request.content) == s["payload_bytes"]
        assert s["estimated_input_tokens"] == len(request.content) + m.FRAMING_ALLOWANCE
        assert payload["model"] == m.MODEL and payload["store"] is False
        assert payload["text"]["format"]["strict"] is True
        assert len(payload["input"]) == 1
        assert "tools" not in payload and "previous_response_id" not in payload
        body = json.loads(payload["input"][0]["content"])
        assert body == {
            "annotation_id": candidate["annotation_id"],
            "query": {"text": candidate["query"], "language": candidate["language"]},
            "rubric": {"query_specific": candidate["rubric"], "scale": candidate["scale"]},
            "eligibility": {
                "requirements": candidate["eligibility"],
                "reference_time": candidate["reference_time"],
                "eligible_occurrence_ids": candidate["eligible_occurrence_ids"],
            },
            "evidence": candidate["event"],
        }
    assert cost["estimated_input_tokens"] == 2 * sum(s["estimated_input_tokens"] for s in shapes)
    assert cost["estimated_output_token_ceiling"] == 3012 * 1200
    assert cost["per_pass"]["machine-a"] == cost["per_pass"]["machine-b"]


def test_cost_determinism_and_optional_operator_prices(loaded):
    c, _, _, _, shapes = loaded
    # Synthetic strata are isolated from the real published category statistics.
    mapping = {s["annotation_id"]: "synthetic-query" for s in shapes}
    args = (shapes, c, mapping, {"synthetic-query": "synthetic-category"})
    prices = {"currency": "USD", "input_per_million": "1.25", "output_per_million": "3.50"}
    a = m.cost_report(*args, prices)
    assert a == m.cost_report(*args, prices)
    assert a["estimated_amount_usd"] == m.amount(
        a["estimated_input_tokens"], a["estimated_output_token_ceiling"], prices
    )
    assert len(a["top20_largest_requests"]) == 20
    assert set(a["input_tokens_per_request"]) == {"min", "p50", "p90", "p95", "p99", "max"}
    with pytest.raises(ValueError):
        m.cost_report(*args, {**prices, "input_per_million": "NaN"})


def test_offline_dry_run_reproduces_old_files_unchanged(tmp_path, prepared, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("network in dry-run")

    before = {str(p): sha(p.read_bytes()) for p in m.PACKAGE.rglob("*") if p.is_file()}
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(httpx.Client, "request", forbidden)
    monkeypatch.setattr(httpx.AsyncClient, "request", forbidden)
    monkeypatch.setattr(m.CategoryJudge, "request", forbidden)
    other = tmp_path / "dry"
    m.prepare(m.PACKAGE, other, m.MODEL)
    assert {p.name: p.read_bytes() for p in other.iterdir()} == {
        p.name: p.read_bytes() for p in prepared.iterdir()
    }
    assert before == {str(p): sha(p.read_bytes()) for p in m.PACKAGE.rglob("*") if p.is_file()}
    assert not any("annotations" in p.name or p.name == "approval.json" for p in other.iterdir())
    with pytest.raises(ValueError, match="new_destination"):
        m.prepare(m.PACKAGE, other, m.MODEL)
    with pytest.raises(ValueError, match="sealed_pool_directory"):
        m.prepare(m.PACKAGE, m.PACKAGE / "never-created", m.MODEL)
    if m.DEST.exists():
        assert {p.name: p.read_bytes() for p in other.iterdir()} == {
            p.name: p.read_bytes() for p in m.DEST.iterdir()
        }


@pytest.mark.parametrize("args", [["--pass-name", "machine-c"], ["--model", "other-model"]])
def test_cli_rejects_c_and_other_models(args):
    result = subprocess.run(
        [sys.executable, "-m", m.__name__, "run", "--model", m.MODEL, *args], capture_output=True
    )
    assert result.returncode == 2


@pytest.mark.parametrize(
    "field,value",
    [
        ("model", "other-model"),
        ("packet_sha256", "0" * 64),
        ("prompt_sha256", "0" * 64),
        ("request_count", 4518),
        ("pass_count", 3),
        ("pair_count", 77),
        ("cost_report_sha256", "0" * 64),
        ("contract_sha256", "0" * 64),
        ("passes", {"machine-a": "approved", "machine-b": "approved", "machine-c": "approved"}),
        ("max_input_tokens", 1),
        ("max_output_tokens", 1),
        ("max_amount_usd", "1"),
    ],
)
def test_manipulated_approval_rejected(prepared, loaded, tmp_path, field, value):
    raw = approval(prepared, tmp_path)
    raw[field] = value
    with pytest.raises(ValueError):
        m.approve(raw, loaded[0], prepared, "machine-a", tmp_path / "machine-a")


def test_no_approval_and_wrong_destination(prepared, loaded, tmp_path):
    with pytest.raises(ValueError):
        m.approve(None, loaded[0], prepared, "machine-a", tmp_path / "machine-a")
    with pytest.raises(ValueError, match="approved_destination"):
        m.approve(
            approval(prepared, tmp_path), loaded[0], prepared, "machine-b", tmp_path / "machine-a"
        )
    with pytest.raises(ValueError, match="pass_c"):
        m.approve(
            approval(prepared, tmp_path), loaded[0], prepared, "machine-c", tmp_path / "machine-c"
        )


def test_input_hash_fail_closed(monkeypatch):
    orig = Path.read_bytes
    monkeypatch.setattr(
        Path,
        "read_bytes",
        lambda p: orig(p) + (b" " if p.name == "blind-candidates.jsonl" else b""),
    )
    with pytest.raises(ValueError, match="packet_changed"):
        m.load_packet(m.PACKAGE)


def test_legacy_plan_and_code_changes_fail_closed(prepared, monkeypatch):
    orig = m.read

    def changed(path):
        value = orig(path)
        if Path(path).name == "execution-contract.json":
            value["passes"].append("machine-c")
        return value

    monkeypatch.setattr(m, "read", changed)
    with pytest.raises(ValueError, match="execution_contract_changed"):
        m.load_execution(m.PACKAGE, prepared, m.MODEL)


def test_oversize_keeps_full_evidence(loaded, monkeypatch):
    _, _, packet, prompt, _ = loaded
    before = m.wire(m.request_for(packet[0], m.MODEL, prompt))
    monkeypatch.setattr(m, "CONTEXT_SAFETY_CAP", 1)
    row = m.shape(packet[0], m.MODEL, prompt)
    assert row["oversized"]
    assert row["payload_sha256"] == sha(before)
    assert row["payload_bytes"] == len(before)


@pytest.fixture
def small_runtime(monkeypatch, loaded):
    c, cost, packet, prompt, shapes = loaded
    # Unit tests exercise persistence with two synthetic answers, not 1506 real requests.
    small = (c, cost, packet[:2], prompt, shapes[:2])
    monkeypatch.setattr(m, "load_execution", lambda *args: small)
    return small


def response_for(request):
    data = json.loads(request.content)
    candidate = json.loads(data["input"][0]["content"])
    answer = {
        "annotation_id": candidate["annotation_id"],
        "state": "uncertain",
        "grade": None,
        "uncertain": True,
        "reason": "SYNTHETIC TEST FIXTURE ONLY",
        "supporting_fields": [],
        "occurrence_ids": [],
    }
    return {
        "id": "resp_" + request.headers["X-Client-Request-Id"],
        "model": m.MODEL,
        "status": "completed",
        "usage": {"input_tokens": 10, "output_tokens": 10, "total_tokens": 20},
        "output": [
            {"type": "message", "content": [{"type": "output_text", "text": json.dumps(answer)}]}
        ],
    }


@pytest.mark.asyncio
async def test_independent_passes_actual_wire_resume_atomic(prepared, small_runtime, tmp_path):
    seen = []

    def handler(request):
        assert request.method == "POST" and request.url.path == "/v1/responses"
        seen.append(request)
        return httpx.Response(200, json=response_for(request))

    client = m.CategoryJudge(
        "SYNTHETIC_SECRET_NOT_FOR_LOGGING", transport=httpx.MockTransport(handler)
    )
    raw = approval(prepared, tmp_path)
    try:
        for name in m.PASSES:
            output = tmp_path / name
            await m.execute(m.PACKAGE, prepared, output, m.MODEL, name, raw, client)
            before = {str(p): p.read_bytes() for p in output.rglob("*.json")}
            await m.execute(m.PACKAGE, prepared, output, m.MODEL, name, raw, client, resume=True)
            assert before == {str(p): p.read_bytes() for p in output.rglob("*.json")}
            with pytest.raises(ValueError, match="explicit_resume"):
                await m.execute(m.PACKAGE, prepared, output, m.MODEL, name, raw, client)
        assert len(seen) == 4
        assert [r.content for r in seen[:2]] == [r.content for r in seen[2:]]
        assert len({r.headers["X-Client-Request-Id"] for r in seen}) == 4
        for request, s in zip(seen[:2], small_runtime[4], strict=True):
            assert sha(request.content) == s["payload_sha256"]
        ids = [read(p)["response_id"] for p in tmp_path.glob("*/records/*.json")]
        assert len(set(ids)) == 4
        for p in tmp_path.rglob("*.json"):
            assert b"SYNTHETIC_SECRET_NOT_FOR_LOGGING" not in p.read_bytes()
        altered = {**raw, "operator": "different"}
        with pytest.raises(ValueError, match="resume_identity_changed"):
            await m.execute(
                m.PACKAGE,
                prepared,
                tmp_path / "machine-a",
                m.MODEL,
                "machine-a",
                altered,
                client,
                resume=True,
            )
    finally:
        await client.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "failure,retries",
    [
        (429, True),
        (500, True),
        (502, True),
        (503, True),
        (504, True),
        (408, False),
        (400, False),
        ("network", True),
        ("invalid", False),
        ("bad-body", False),
        ("refusal", False),
    ],
)
async def test_retry_only_transient(prepared, small_runtime, tmp_path, failure, retries):
    calls, waits = [], []

    def handler(request):
        calls.append(request)
        if len(calls) == 1:
            if failure == "network":
                raise httpx.ConnectError("synthetic", request=request)
            if type(failure) is int:
                return httpx.Response(failure, json={"not_persisted": "SENSITIVE_TEST_ERROR_BODY"})
            if failure == "bad-body":
                return httpx.Response(200, json=[])
            body = response_for(request)
            part = body["output"][0]["content"][0]
            if failure == "invalid":
                part["text"] = "{broken"
            else:
                body["output"][0]["content"] = [
                    {"type": "refusal", "refusal": "SENSITIVE_TEST_ERROR_BODY"}
                ]
            return httpx.Response(200, json=body)
        return httpx.Response(200, json=response_for(request))

    async def sleep(seconds):
        waits.append(seconds)

    client = m.CategoryJudge("synthetic", transport=httpx.MockTransport(handler))
    output = tmp_path / "machine-a"
    raw = approval(prepared, tmp_path)
    try:
        if retries:
            await m.execute(
                m.PACKAGE, prepared, output, m.MODEL, "machine-a", raw, client, sleep=sleep
            )
            assert len(calls) == 3 and waits == [2]
        else:
            with pytest.raises(APIError):
                await m.execute(
                    m.PACKAGE, prepared, output, m.MODEL, "machine-a", raw, client, sleep=sleep
                )
            assert len(calls) == 1 and not waits
            with pytest.raises(ValueError, match="previous_terminal_failure"):
                await m.execute(
                    m.PACKAGE, prepared, output, m.MODEL, "machine-a", raw, client, resume=True
                )
            assert len(calls) == 1
        for p in output.rglob("*.json"):
            assert "SENSITIVE_TEST_ERROR_BODY" not in p.read_text()
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_run_without_approval_never_requests(prepared, small_runtime, tmp_path):
    class Forbidden:
        async def request(self, *args):
            pytest.fail("request before approval")

    with pytest.raises(ValueError):
        await m.execute(
            m.PACKAGE, prepared, tmp_path / "machine-a", m.MODEL, "machine-a", None, Forbidden()
        )
    assert not (tmp_path / "machine-a").exists()


@pytest.mark.asyncio
async def test_recover_completed_record_without_resend(prepared, small_runtime, tmp_path):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json=response_for(request))

    client = m.CategoryJudge("synthetic", transport=httpx.MockTransport(handler))
    raw = approval(prepared, tmp_path)
    output = tmp_path / "machine-a"
    try:
        await m.execute(m.PACKAGE, prepared, output, m.MODEL, "machine-a", raw, client)
        saved = sorted((output / "records").glob("*.json"))[0]
        original = saved.read_bytes()
        saved.unlink()  # Synthetic crash between immutable completion and final publication.
        await m.execute(m.PACKAGE, prepared, output, m.MODEL, "machine-a", raw, client, resume=True)
        assert len(calls) == 2 and saved.read_bytes() == original
        with pytest.raises(FileExistsError):
            m.atomic_new(saved, {"synthetic": "must not overwrite"})
        assert saved.read_bytes() == original
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_orphan_reservation_stops_resume(prepared, small_runtime, tmp_path):
    calls = []

    def handler(request):
        calls.append(request)
        raise RuntimeError("SYNTHETIC process interruption")

    client = m.CategoryJudge("synthetic", transport=httpx.MockTransport(handler))
    raw = approval(prepared, tmp_path)
    output = tmp_path / "machine-a"
    try:
        with pytest.raises(RuntimeError):
            await m.execute(m.PACKAGE, prepared, output, m.MODEL, "machine-a", raw, client)
        with pytest.raises(ValueError, match="interrupted_attempt"):
            await m.execute(
                m.PACKAGE, prepared, output, m.MODEL, "machine-a", raw, client, resume=True
            )
        assert len(calls) == 1
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_budget_stops_before_extra_http_request(
    prepared, small_runtime, tmp_path, monkeypatch
):
    original = m.approve

    def synthetic_reduced_corpus_budget(*args):
        a = original(*args)  # Real approval validation remains exercised.
        # Shrink runtime quotas to one attempt for the two-row synthetic corpus only.
        a["max_input_tokens"] = 2 * small_runtime[4][0]["estimated_input_tokens"]
        a["max_output_tokens"] = 2 * m.OUTPUT_CAP
        return a

    monkeypatch.setattr(m, "approve", synthetic_reduced_corpus_budget)
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json=response_for(request))

    client = m.CategoryJudge("synthetic", transport=httpx.MockTransport(handler))
    try:
        with pytest.raises(ValueError, match="budget_exhausted"):
            await m.execute(
                m.PACKAGE,
                prepared,
                tmp_path / "machine-a",
                m.MODEL,
                "machine-a",
                approval(prepared, tmp_path),
                client,
            )
        assert len(calls) == 1
    finally:
        await client.close()


def test_prompt_change_blocks_execution(prepared, tmp_path, monkeypatch):
    prompt = tmp_path / "changed-prompt.txt"
    prompt.write_text(m.PROMPT.read_text() + "\nchanged")
    monkeypatch.setattr(m, "PROMPT", prompt)
    with pytest.raises(ValueError, match="execution_contract_changed"):
        m.load_execution(m.PACKAGE, prepared, m.MODEL)
