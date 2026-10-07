"""Offline synthetic usage only. Real API execution is manual and approval gated."""

import json
import socket
from collections import Counter
from copy import deepcopy
from decimal import Decimal
from pathlib import Path

import httpx
import pytest

from uranus_research_service import category_machine_cost_pilot as p
from uranus_research_service.machine_judge import atomic_new, encoded, read, sha


@pytest.fixture(scope="module")
def selection():
    return p.selection_for(p.ab.PACKAGE)


@pytest.fixture
def prepared(selection, tmp_path, monkeypatch):
    # Selection was validated once against the real frozen corpus; no provider needed.
    monkeypatch.setattr(p, "selection_for", lambda _: deepcopy(selection))
    pilot, output = tmp_path / "pilot", tmp_path / "run"
    p.prepare(p.ab.PACKAGE, pilot)
    approval = {
        "schema_version": "category-cost-pilot-approval-v1",
        "purpose": p.PURPOSE,
        "approved": True,
        "pilot_only": True,
        "approval_reference": "SYNTHETIC TEST ONLY",
        "model": p.ab.MODEL,
        "request_count": 20,
        "selection_sha256": sha((pilot / "pilot-selection.json").read_bytes()),
        "packet_sha256": selection["packet_sha256"],
        "prompt_sha256": selection["prompt_sha256"],
        "code_sha256": selection["code_sha256"],
        "max_input_tokens": selection["max_input_tokens"],
        "max_output_tokens": selection["max_output_tokens"],
        "execution_root": str(output),
    }
    path = tmp_path / "approval.json"
    atomic_new(path, approval)
    return pilot, output, path


def test_selection_deterministic_and_operational_only(selection):
    assert selection == p.selection_for(p.ab.PACKAGE)
    rows = selection["selected"]
    assert len(rows) == len({r["annotation_id"] for r in rows}) == 20
    assert Counter(r["stratum"] for r in rows) == dict.fromkeys(range(5), 4)
    assert set(r["category"] for r in rows) == set(p.CATEGORIES)
    assert sum(r["category"] == "accessibility" and r["stratum"] == 4 for r in rows) == 2
    shapes = [
        {k: v for k, v in r.items() if k not in ("category", "stratum")}
        for r in selection["population"]
    ]
    cats = {r["annotation_id"]: r["category"] for r in selection["population"]}
    assert p.select(list(reversed(shapes)), cats)[1] == rows
    assert set(rows[0]) == {
        "annotation_id",
        "payload_bytes",
        "payload_sha256",
        "stratum",
        "category",
        "estimated_input_tokens",
        "estimated_output_tokens",
        "oversized",
    }


def test_prepare_offline_exclusive(prepared, monkeypatch, tmp_path):
    monkeypatch.setattr(socket, "socket", lambda *a, **kw: pytest.fail("network"))
    output = tmp_path / "second"
    p.prepare(p.ab.PACKAGE, output)
    assert (output / "pilot-selection.json").read_bytes() == (
        prepared[0] / "pilot-selection.json"
    ).read_bytes()
    with pytest.raises(ValueError, match="output_exists"):
        p.prepare(p.ab.PACKAGE, output)


@pytest.mark.parametrize(
    "field,value",
    [
        ("approved", False),
        ("pilot_only", False),
        ("model", "other"),
        ("request_count", 3012),
        ("packet_sha256", "0" * 64),
        ("prompt_sha256", "0" * 64),
        ("selection_sha256", "0" * 64),
        ("code_sha256", "0" * 64),
        ("max_input_tokens", 1),
        ("max_output_tokens", 1),
        ("pass_name", "machine-a"),
    ],
)
def test_invalid_approval(prepared, selection, field, value):
    pilot, output, approval = prepared
    raw = read(approval)
    raw[field] = value
    with pytest.raises(ValueError):
        p.authorize(
            raw, selection, sha((pilot / "pilot-selection.json").read_bytes()), output, p.ab.MODEL
        )


def test_pilot_is_not_ab_approval(prepared):
    with pytest.raises(ValueError):
        p.ab.Approval.model_validate(read(prepared[2]))


def response(request):
    payload = json.loads(request.content)
    c = json.loads(payload["input"][0]["content"])
    answer = {
        "annotation_id": c["annotation_id"],
        "state": "uncertain",
        "grade": None,
        "uncertain": True,
        "reason": "SYNTHETIC TEST ONLY",
        "supporting_fields": [],
        "occurrence_ids": [],
    }
    return {
        "id": "resp_" + request.headers["X-Client-Request-Id"],
        "model": p.ab.MODEL,
        "status": "completed",
        "usage": {
            "input_tokens": 100,
            "output_tokens": 40,
            "total_tokens": 140,
            "input_tokens_details": {"cached_tokens": 20},
            "output_tokens_details": {"reasoning_tokens": 10},
        },
        "output": [
            {"type": "message", "content": [{"type": "output_text", "text": json.dumps(answer)}]}
        ],
    }


@pytest.mark.asyncio
async def test_actual_http_wire_twenty_only_resume_no_answers(prepared, selection):
    pilot, output, approval = prepared
    seen = []
    shapes = {r["annotation_id"]: r for r in selection["selected"]}

    def handler(request):
        seen.append(request)
        assert request.method == "POST" and request.url.path == "/v1/responses"
        payload = json.loads(request.content)
        c = json.loads(payload["input"][0]["content"])
        assert set(c) == {"annotation_id", "query", "rubric", "eligibility", "evidence"}
        assert sha(request.content) == shapes[c["annotation_id"]]["payload_sha256"]
        assert payload["model"] == p.ab.MODEL
        assert payload["store"] is False and payload["reasoning"] == {"effort": "none"}
        assert payload["text"]["format"]["strict"] is True
        assert len(payload["input"]) == 1
        assert not {"tools", "previous_response_id", "conversation"} & payload.keys()
        return httpx.Response(200, json=response(request))

    client = p.ab.CategoryJudge("SYNTHETIC_SECRET", transport=httpx.MockTransport(handler))
    try:
        await p.run(pilot, p.ab.PACKAGE, approval, output, p.ab.MODEL, client)
        before = {str(f): f.read_bytes() for f in output.rglob("*.json")}
        await p.run(pilot, p.ab.PACKAGE, approval, output, p.ab.MODEL, client, resume=True)
        assert before == {str(f): f.read_bytes() for f in output.rglob("*.json")}
        assert len(seen) == 20
        u = read(output / "pilot-usage.json")
        assert u["totals"] == {
            "input_tokens": 2000,
            "output_tokens": 800,
            "total_tokens": 2800,
            "cached_input_tokens": 400,
            "reasoning_tokens": 200,
        }
        serialized = json.dumps(u)
        for forbidden in (
            "SYNTHETIC_SECRET",
            '"grade"',
            '"answer"',
            '"reason"',
            "machine-a",
            "machine-b",
        ):
            assert forbidden not in serialized
        # Not an A/B completion record or an importable annotation.
        assert all("answer" not in r and "configuration_sha256" not in r for r in u["records"])
        with pytest.raises(FileExistsError):
            atomic_new(output / "pilot-usage.json", {})
        with pytest.raises(ValueError, match="explicit_resume"):
            await p.run(pilot, p.ab.PACKAGE, approval, output, p.ab.MODEL, client)
    finally:
        await client.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["rate_limit", "invalid", "refusal"])
async def test_no_retry_after_failure(prepared, failure):
    pilot, output, approval = prepared
    calls = []

    def handler(request):
        calls.append(request)
        if failure == "rate_limit":
            return httpx.Response(429, json={"error": "SENSITIVE PROVIDER BODY"})
        body = response(request)
        if failure == "invalid":
            body["output"][0]["content"][0]["text"] = "invalid json"
        else:
            body["output"][0]["content"][0] = {"type": "refusal", "refusal": "SENSITIVE"}
        return httpx.Response(200, json=body)

    client = p.ab.CategoryJudge("secret", transport=httpx.MockTransport(handler))
    try:
        await p.run(pilot, p.ab.PACKAGE, approval, output, p.ab.MODEL, client)
        assert len(calls) == 1
        assert not (output / "pilot-usage.json").exists()
        assert "SENSITIVE" not in (output / "records/01.json").read_text()
        with pytest.raises(ValueError, match="previous_failure_terminal"):
            await p.run(pilot, p.ab.PACKAGE, approval, output, p.ab.MODEL, client, resume=True)
        assert len(calls) == 1
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_no_approval_no_calls(prepared):
    pilot, output, approval = prepared
    approval.unlink()
    client = p.ab.CategoryJudge(
        "secret", transport=httpx.MockTransport(lambda _: pytest.fail("API"))
    )
    try:
        with pytest.raises(FileNotFoundError):
            await p.run(pilot, p.ab.PACKAGE, approval, output, p.ab.MODEL, client)
        assert not output.exists()
    finally:
        await client.close()


def test_usage_bounds():
    body = {"usage": {"input_tokens": 10, "output_tokens": 20, "total_tokens": 30}}
    assert p.usage(body)["cached_input_tokens"] is None
    body["usage"]["input_tokens_details"] = {"cached_tokens": 11}
    with pytest.raises(ValueError, match="usage_details"):
        p.usage(body)


def test_cost_projection_deterministic(selection):
    rows = [
        {
            "reservation": {
                "annotation_id": s["annotation_id"],
                "payload_sha256": s["payload_sha256"],
            },
            "response_id": f"synthetic_{i}",
            "status": "schema_validated_content_discarded",
            "usage": {
                "input_tokens": 100,
                "output_tokens": 50,
                "total_tokens": 150,
                "cached_input_tokens": 20,
                "reasoning_tokens": 0,
            },
        }
        for i, s in enumerate(selection["selected"])
    ]
    u = {
        "purpose": p.PURPOSE,
        "count": 20,
        "records": rows,
        "selection_sha256": sha(encoded(selection) + b"\n"),
        "totals": {"input_tokens": 2000},
    }
    prices = {
        "currency": "USD",
        "input_per_million": "2",
        "cached_input_per_million": "1",
        "output_per_million": "4",
    }  # Synthetic prices, not provider pricing.
    cost = read(p.ab.DEST / "cost-report.json")
    a = p.analyze(selection, u, cost, prices)
    assert a == p.analyze(selection, u, cost, prices)
    assert Decimal(a["pilot_amount_usd"]) == Decimal("0.0076")
    assert a["conservative_contract"]["input_tokens"] == cost["estimated_input_tokens"]
    assert a["projection_requests"] == 3012
    assert Decimal(a["empirical"]["lower"]["amount_usd"]) <= Decimal(
        a["empirical"]["upper"]["amount_usd"]
    )
    with pytest.raises(ValueError):
        p.analyze(selection, u, cost, {})


def test_historical_files_unchanged_and_no_inference():
    manifest = read(p.DEST / "historical-input-sha256.json")
    assert manifest["baseline_main"] == p.BASELINE
    for name, expected in manifest["files"].items():
        assert sha(Path(name).read_bytes()) == expected
    source = Path(p.__file__).read_text()
    assert "httpx.get" not in source and "encoder import" not in source
    assert "qdrant" not in source and "sqlalchemy" not in source


def test_selection_hash_mismatch(prepared):
    pilot, _, _ = prepared
    data = read(pilot / "pilot-selection.json")
    data["selected"][0]["payload_sha256"] = "0" * 64
    (pilot / "pilot-selection.json").write_text(json.dumps(data))
    with pytest.raises(ValueError, match="pilot_selection_changed"):
        p.load_selection(pilot, p.ab.PACKAGE)


@pytest.mark.asyncio
async def test_interruption_does_not_resend(prepared):
    pilot, output, approval = prepared
    calls = []

    def handler(request):
        calls.append(request)
        raise KeyboardInterrupt

    client = p.ab.CategoryJudge("secret", transport=httpx.MockTransport(handler))
    try:
        with pytest.raises(KeyboardInterrupt):
            await p.run(pilot, p.ab.PACKAGE, approval, output, p.ab.MODEL, client)
        with pytest.raises(ValueError, match="interrupted_attempt"):
            await p.run(pilot, p.ab.PACKAGE, approval, output, p.ab.MODEL, client, resume=True)
        assert len(calls) == 1
    finally:
        await client.close()


def test_recorded_usage_cannot_be_annotation():
    from uranus_research_service.machine_blind_contracts import MachineAnswer

    with pytest.raises(ValueError):
        MachineAnswer.model_validate(
            {
                "purpose": p.PURPOSE,
                "annotation_id": "a" * 32,
                "input_tokens": 100,
                "response_id": "resp_test",
            }
        )


def test_published_pilot_revalidates_offline(selection, monkeypatch):
    monkeypatch.setattr(socket, "socket", lambda *a, **kw: pytest.fail("network"))
    root = p.DEST
    index = read(root / "artifact-sha256.json")
    assert set(index["files"]) == {
        str(f.relative_to(root))
        for f in root.rglob("*")
        if f.is_file() and f.name != "artifact-sha256.json"
    }
    for name, expected in index["files"].items():
        assert sha((root / name).read_bytes()) == expected
    assert read(root / "pilot-selection.json") == selection
    records = p.validate_records(root / "run", selection)
    assert len(records) == 20
    assert all(r["model"] == p.ab.MODEL and r["retries"] == 0 for r in records)
    usage = read(root / "run/pilot-usage.json")
    assert usage["records"] == records
    result = p.analyze(
        selection,
        usage,
        read(p.ab.DEST / "cost-report.json"),
        read(root / "pilot-price-manifest.json")["prices"],
    )
    assert result == read(root / "pilot-cost-analysis.json")
    approval = read(root / "pilot-approval.json")
    p.authorize(
        approval,
        selection,
        sha((root / "pilot-selection.json").read_bytes()),
        Path(approval["execution_root"]),
        p.ab.MODEL,
    )
    assert read(root / "run/pilot-run.json")["configuration"]["approval_sha256"] == sha(
        (root / "pilot-approval.json").read_bytes()
    )
    for record in records:
        assert not {"answer", "grade", "reason", "supporting_fields", "uncertain"} & record.keys()
