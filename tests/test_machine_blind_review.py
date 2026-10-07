"""Synthetic-only tests; real API execution is operator-only, never required by CI."""

import copy
import json
import socket
from pathlib import Path

import httpx
import pytest

from uranus_research_service.machine_blind_analysis import (
    compare,
    consensus,
    follow_up,
    reevaluate,
    validate_run,
)
from uranus_research_service.machine_blind_contracts import (
    PACKET_SHA,
    PROMPT,
    load_packet,
    payload,
    read,
    schema,
    sha,
    validate_answer,
)
from uranus_research_service.machine_blind_review import identity, parse, run
from uranus_research_service.machine_judge import APIError, OpenAIJudge, atomic_new
from uranus_research_service.semantic_manifest import digest

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "benchmark/review/lost-all-v1"
MODEL = "gpt-5.4-mini-2026-03-17"


@pytest.fixture(scope="module")
def packet():
    return load_packet(PACKAGE)[0]


def answer(p, grade=0):
    return {
        "annotation_id": p["annotation_id"],
        "state": "graded",
        "grade": grade,
        "uncertain": False,
        "reason": "SYNTHETIC TEST ONLY",
        "supporting_fields": ["title"] if grade else [],
        "occurrence_ids": p["eligible_occurrence_ids"][:1] if grade else [],
    }


def batch(packet, pass_id):
    conf = identity(MODEL, pass_id, "synthetic-" + pass_id, PROMPT.read_text())
    return {
        "manifest": {"configuration": conf, "started_at": "2026-10-07T00:00:00+00:00"},
        "completed_at": "2026-10-07T00:01:00+00:00",
        "records": [
            {
                "answer": answer(p),
                "configuration_sha256": digest(conf),
                "request_id": "synthetic-" + pass_id + p["annotation_id"],
                "response_id": "synthetic-" + pass_id + p["annotation_id"],
                "attempt": 1,
                "completed_at": "2026-10-07T00:01:00+00:00",
                "latency_ms": 1,
                "usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
            }
            for p in packet
        ],
        "summary": {
            "count": 77,
            "failed_cases": 0,
            "failed_attempts": 0,
            "retry_count": 0,
            "unknown_attempts": 0,
            "usage": {"input_tokens": 77, "output_tokens": 77, "total_tokens": 154},
        },
    }


def body(p):
    return {
        "model": MODEL,
        "status": "completed",
        "id": "response_synthetic",
        "usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
        "output": [
            {"type": "message", "content": [{"type": "output_text", "text": json.dumps(answer(p))}]}
        ],
    }


def test_only_two_blind_files_read(monkeypatch, packet):
    original = Path.read_bytes
    seen = []

    def record(path):
        seen.append(path)
        return original(path)

    monkeypatch.setattr(Path, "read_bytes", record)
    rows, _ = load_packet(PACKAGE)
    assert len(rows) == len({p["annotation_id"] for p in rows}) == 77
    assert set(seen) == {
        PACKAGE / "reviewer/blind-candidates.jsonl",
        PACKAGE / "reviewer/annotation-package.json",
    }
    assert sha(original(PACKAGE / "reviewer/blind-candidates.jsonl")) == PACKET_SHA


def test_prompt_allowlist_and_independent_requests(packet):
    for p in packet:
        request = payload(p, MODEL, PROMPT.read_text())
        content = json.loads(request["input"][0]["content"])
        assert set(content) == {
            "annotation_id",
            "query",
            "language",
            "rubric",
            "eligibility",
            "evidence",
        }
        assert set(request) == {
            "model",
            "store",
            "instructions",
            "input",
            "text",
            "temperature",
            "reasoning",
            "max_output_tokens",
        }
        assert "tools" not in request and "previous_response_id" not in request
        assert content["evidence"] == p["event"]
        assert p["query_id"] not in request["input"][0]["content"]

        def keys(v):
            if isinstance(v, dict):
                yield from v.keys()
                for item in v.values():
                    yield from keys(item)
            elif isinstance(v, list):
                for item in v:
                    yield from keys(item)

        assert not set(keys(content)) & {
            "model",
            "v3",
            "v5",
            "rank",
            "score",
            "previous_grade",
            "lost_all",
            "delta",
        }
    assert "untrusted evidence" in PROMPT.read_text()
    assert schema()["additionalProperties"] is False


@pytest.mark.parametrize("field", ["model", "v3", "rank", "score", "previous_grade"])
def test_metadata_injection_rejected(packet, field):
    p = copy.deepcopy(packet[0])
    p[field] = "forbidden"
    with pytest.raises(ValueError):
        payload(p, MODEL, PROMPT.read_text())


@pytest.mark.parametrize("grade", [-1, 4, True, 1.5, "2"])
def test_grade_invalid(packet, grade):
    a = answer(packet[0])
    a["grade"] = grade
    with pytest.raises(ValueError):
        validate_answer(a, packet[0])


def test_uncertain_null_and_positive_evidence(packet):
    a = answer(packet[0])
    a.update(state="uncertain", grade=None, uncertain=True)
    assert validate_answer(a, packet[0])["grade"] is None
    a["grade"] = 0
    with pytest.raises(ValueError):
        validate_answer(a, packet[0])
    a = answer(packet[0], 3)
    a["occurrence_ids"] = []
    with pytest.raises(ValueError):
        validate_answer(a, packet[0])


def test_invalid_json_and_refusal_fail_closed(packet):
    b = body(packet[0])
    b["output"][0]["content"][0]["text"] = "{broken"
    with pytest.raises(ValueError):
        parse(b, packet[0], MODEL)
    b["output"][0]["content"][0] = {"type": "refusal", "refusal": "no"}
    with pytest.raises(ValueError):
        parse(b, packet[0], MODEL)


@pytest.mark.parametrize("fault", ["missing", "duplicate", "unknown", "human", "binding"])
def test_import_validation(packet, fault):
    b = batch(packet, "a")
    if fault == "missing":
        b["records"].pop()
    elif fault == "duplicate":
        b["records"][-1] = b["records"][0]
    elif fault == "unknown":
        b["records"][0]["answer"]["annotation_id"] = "0" * 32
    elif fault == "human":
        b["manifest"]["configuration"]["provenance"] = "human_approved"
    else:
        b["manifest"]["configuration"]["packet_sha256"] = "0" * 64
    with pytest.raises(ValueError):
        validate_run(b, packet)


def test_agreement_consensus_and_blind_followup(packet):
    a, b = batch(packet, "a"), batch(packet, "b")
    b["records"][0]["answer"] = answer(packet[0], 3)
    b["records"][1]["answer"].update(state="uncertain", grade=None, uncertain=True)
    report = compare(a, b, packet)
    assert report["summary"]["machine_agreed"] == 75
    assert report["summary"]["machine_conflict"] == 1
    assert report["summary"]["machine_uncertain"] == 1
    assert report["summary"]["extreme_0_3"] == 1
    cs = consensus(report, packet)
    assert [r["grade"] for r in cs["judgments"][:2]] == [None, None]
    triage = follow_up(report, packet)
    assert len(triage) == 2
    for row in triage:
        original = next(p for p in packet if p["annotation_id"] == row["annotation_id"])
        assert {k: v for k, v in row.items() if k != "status"} == original
        assert set(row) == set(original) | {"status"}
    report["rows"][0]["grade"] = 3
    with pytest.raises(ValueError):
        consensus(report, packet)
    with pytest.raises(ValueError):
        compare(a, a, packet)


@pytest.mark.asyncio
async def test_retry_resume_atomic_actual_payload_and_key_privacy(tmp_path, packet, capsys):
    counter = {"post": 0}
    by_id = {p["annotation_id"]: p for p in packet}

    def handler(req):
        if req.method == "GET":
            return httpx.Response(200, json={"id": MODEL})
        counter["post"] += 1
        actual = json.loads(req.content)
        assert req.headers["authorization"] == "Bearer synthetic-secret-never-log"
        assert "cookie" not in req.headers
        content = json.loads(actual["input"][0]["content"])
        p = by_id[content["annotation_id"]]
        assert actual == payload(p, MODEL, PROMPT.read_text())
        if counter["post"] == 1:
            return httpx.Response(429, text="secret provider body")
        b = body(p)
        b["id"] = "synthetic_" + str(counter["post"])
        return httpx.Response(200, json=b, headers={"x-request-id": "synthetic-id"})

    client = OpenAIJudge("synthetic-secret-never-log", transport=httpx.MockTransport(handler))

    async def no_sleep(_):
        pass

    try:
        first = await run(
            PACKAGE,
            tmp_path / "run-a",
            MODEL,
            "a",
            "synthetic-a",
            PROMPT.read_text(),
            client,
            sleep=no_sleep,
        )
        assert counter["post"] == 78 and first["summary"]["retry_count"] == 1
        with pytest.raises(ValueError, match="explicit_resume"):
            await run(
                PACKAGE, tmp_path / "run-a", MODEL, "a", "synthetic-a", PROMPT.read_text(), client
            )
        second = await run(
            PACKAGE,
            tmp_path / "run-a",
            MODEL,
            "a",
            "synthetic-a",
            PROMPT.read_text(),
            client,
            resume=True,
        )
        assert first == second and counter["post"] == 78
        assert len(validate_run(first, packet)) == 77
        with pytest.raises(FileExistsError):
            atomic_new(tmp_path / "run-a/annotations-pass-a.json", {})
    finally:
        await client.close()
    captured = capsys.readouterr()
    assert "synthetic-secret-never-log" not in captured.out + captured.err
    for p in (tmp_path / "run-a").rglob("*.json"):
        assert "synthetic-secret-never-log" not in p.read_text()
        assert "secret provider body" not in p.read_text()


@pytest.mark.asyncio
async def test_invalid_api_cannot_retry_repair(tmp_path, packet):
    counter = 0

    def handler(req):
        nonlocal counter
        if req.method == "GET":
            return httpx.Response(200, json={"id": MODEL})
        counter += 1
        return httpx.Response(200, content=b"{broken", headers={"content-type": "application/json"})

    client = OpenAIJudge("synthetic-key", transport=httpx.MockTransport(handler))
    try:
        with pytest.raises(APIError):
            await run(
                PACKAGE, tmp_path / "run-a", MODEL, "a", "synthetic", PROMPT.read_text(), client
            )
        with pytest.raises(ValueError, match="previous_nonretryable"):
            await run(
                PACKAGE,
                tmp_path / "run-a",
                MODEL,
                "a",
                "synthetic",
                PROMPT.read_text(),
                client,
                resume=True,
            )
        assert counter == 1
    finally:
        await client.close()


def test_offline_reevaluation_preserves_historical_unknowns(packet, monkeypatch):
    def no_network(*args, **kwargs):
        raise AssertionError("network forbidden")

    monkeypatch.setattr(socket, "socket", no_network)
    a, b = batch(packet, "a"), batch(packet, "b")
    b["records"][0]["answer"].update(state="needs_more_context", grade=None, uncertain=True)
    report = compare(a, b, packet)
    cs = consensus(report, packet)
    assert cs["judgments"][0]["grade"] is None
    before = {
        p: sha(p.read_bytes()) for p in (ROOT / "benchmark/results").rglob("*") if p.is_file()
    }
    result = reevaluate(report, ROOT, PACKAGE)
    assert result == reevaluate(report, ROOT, PACKAGE)
    assert result["historical_verdict"] == "v5 provisionally fails one or more gates"
    assert result["label"].startswith("machine-only exploratory reevaluation")
    assert sum(c["unresolved_count"] for c in result["cases"]) == 2
    assert len(result["cases"]) == 8
    assert before == {p: sha(p.read_bytes()) for p in before}
    assert all(c["machine_consensus_metrics"]["Recall@10"] is None for c in result["cases"])


def test_frozen_baseline_and_no_overwrite():
    base = PACKAGE / "machine/frozen-input-sha256.json"
    assert (
        sha(base.read_bytes()) == "5dbb37cf63cd53cadde9d684cac13f284f453552fc6bd8add57a198415ebe8f5"
    )
    pins = read(base)
    for name, expected in pins["files"].items():
        assert sha((ROOT / name).read_bytes()) == expected
    for name in (
        "benchmark/ground-truth-v1.jsonl",
        "benchmark/review/lost-all-v1/reviewer/blind-candidates.jsonl",
    ):
        with pytest.raises(FileExistsError):
            atomic_new(ROOT / name, {"provenance": "machine_proposed"})
        assert sha((ROOT / name).read_bytes()) == pins["files"][name]


def test_response_schema_snapshot():
    assert read(PACKAGE / "machine/response-schema-v1.json") == schema()


def test_published_real_runs_and_accounting(packet):
    base = PACKAGE / "machine"
    a, b = [read(base / f"annotations-pass-{p}.json") for p in "ab"]
    report = compare(a, b, packet)
    assert report == read(base / "agreement-report.json")
    assert report["summary"] == {
        "machine_agreed": 70,
        "machine_conflict": 7,
        "machine_uncertain": 0,
        "extreme_0_3": 0,
        "conflict_grade_pairs": {"0-1": 1, "1-2": 2, "2-3": 4},
    }
    assert consensus(report, packet) == read(base / "machine-consensus-v1.json")
    follow = [
        json.loads(line) for line in (base / "machine-review-needed.jsonl").read_text().splitlines()
    ]
    assert follow == follow_up(report, packet) and len(follow) == 7
    for run_result in (a, b):
        config = run_result["manifest"]["configuration"]
        assert config["model"] == MODEL
        for name, expected in config["code_sha256"].items():
            assert sha((ROOT / "src/uranus_research_service" / name).read_bytes()) == expected
    seal = read(base / "consensus-seal.json")
    for name, expected in seal["files"].items():
        assert sha((base / name).read_bytes()) == expected
    partial = read(base / "initial-pass-a-partial.json")
    assert partial["status"] == "aborted-not-used-for-consensus"
    assert partial["completed_count"] == len(partial["records"]) == 51
    ledger = [json.loads(line) for line in (base / "request-ledger.jsonl").read_text().splitlines()]
    accounting = read(base / "execution-accounting.json")
    assert len(ledger) == accounting["judging_requests"] == 206
    assert sum(r["status"] == "failed" for r in ledger) == 1
    assert accounting["usage"] == {
        k: sum(r["usage"][k] for r in ledger)
        for k in ("input_tokens", "output_tokens", "total_tokens")
    }
    assert reevaluate(report, ROOT, PACKAGE) == read(base / "machine-only-reevaluation-v1.json")
