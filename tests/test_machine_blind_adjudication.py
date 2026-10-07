"""Synthetic API only; the actual serialized HTTP payload is audited."""

import copy
import json
import socket
from pathlib import Path

import httpx
import pytest

from uranus_research_service.machine_adjudication_analysis import (
    VERDICT,
    combine,
    original,
    reevaluate,
)
from uranus_research_service.machine_blind_adjudication import (
    BASE,
    IDS,
    INPUT,
    INPUT_SHA,
    MODEL,
    PROMPT,
    load_input,
    run,
    validate,
)
from uranus_research_service.machine_blind_contracts import read, sha, validate_answer
from uranus_research_service.machine_judge import APIError, OpenAIJudge, atomic_new


def answer(candidate):
    return {
        "annotation_id": candidate["annotation_id"],
        "state": "graded",
        "grade": 1,
        "uncertain": False,
        "reason": "SYNTHETIC TEST ONLY: title supplies a partial aspect.",
        "supporting_fields": ["title"],
        "occurrence_ids": candidate["eligible_occurrence_ids"][:1],
    }


def response(candidate, mutation=None):
    a = answer(candidate)
    if mutation:
        a.update(mutation)
    return {
        "model": MODEL,
        "status": "completed",
        "id": "resp_synthetic",
        "usage": {"input_tokens": 1, "output_tokens": 2, "total_tokens": 3},
        "output": [
            {"type": "message", "content": [{"type": "output_text", "text": json.dumps(a)}]}
        ],
    }


def keys(value):
    if isinstance(value, dict):
        yield from value
        for v in value.values():
            yield from keys(v)
    if isinstance(value, list):
        for v in value:
            yield from keys(v)


def frozen_bytes():
    return {p: p.read_bytes() for p in Path("benchmark").rglob("*") if p.is_file()}


def test_frozen_input_only(monkeypatch, tmp_path):
    seen = []
    original_read = Path.read_bytes

    def spy(path):
        seen.append(path)
        return original_read(path)

    monkeypatch.setattr(Path, "read_bytes", spy)
    packet = load_input()
    assert len(packet) == 7 and {r["annotation_id"] for r in packet} == IDS
    assert seen == [INPUT]
    assert all("status" not in p for p in packet)
    bad = tmp_path / "changed.jsonl"
    bad.write_bytes(original_read(INPUT) + b"\n")
    with pytest.raises(ValueError, match="input_hash"):
        load_input(bad)
    assert sha(original_read(INPUT)) == INPUT_SHA


@pytest.mark.parametrize(
    "mutation",
    [
        {"grade": 4},
        {"grade": True},
        {"grade": -1},
        {"grade": 1.5},
        {"grade": None},
        {"uncertain": True},
        {"supporting_fields": []},
        {"supporting_fields": ["invented"]},
        {"occurrence_ids": []},
        {"occurrence_ids": ["00000000-0000-0000-0000-000000000000"]},
        {"annotation_id": "0" * 32},
        {"human_approved": True},
    ],
)
def test_closed_answer(mutation):
    candidate = load_input()[0]
    with pytest.raises(ValueError):
        validate_answer({**answer(candidate), **mutation}, candidate)


@pytest.mark.asyncio
async def test_http_blindness_resume_retry_and_offline_derivation(tmp_path, monkeypatch, capsys):
    packet = load_input()
    mapping = {p["annotation_id"]: p for p in packet}
    posts = []

    def handler(request):
        if request.method == "GET":
            assert request.url.path == "/v1/models/" + MODEL
            return httpx.Response(200, json={"id": MODEL})
        assert request.url.path == "/v1/responses"
        body = json.loads(request.content)
        assert set(body) == {
            "model",
            "store",
            "instructions",
            "input",
            "text",
            "reasoning",
            "max_output_tokens",
        }
        assert body["model"] == MODEL and body["store"] is False
        assert body["reasoning"] == {"effort": "high"}
        assert body["text"]["format"]["strict"] is True
        assert len(body["input"]) == 1
        data = json.loads(body["input"][0]["content"])
        assert set(data) == {
            "annotation_id",
            "query",
            "language",
            "rubric",
            "eligibility",
            "evidence",
        }
        assert not set(keys(data)) & {
            "v3",
            "v5",
            "rank",
            "score",
            "previous_grade",
            "machine_grade",
            "pass_a",
            "pass_b",
            "category",
            "query_id",
            "event_id",
        }
        p = mapping[data["annotation_id"]]
        assert "status" not in data
        assert data["evidence"]["status"] == "released"
        assert data["evidence"] == p["event"]
        assert data["rubric"]["intent_checks"] == p["intent_checks"]
        posts.append(data)
        if len(posts) == 1:
            return httpx.Response(429, json={"error": "secret-never-log"})
        mutation = (
            {"state": "uncertain", "grade": None, "uncertain": True} if p == packet[0] else None
        )
        return httpx.Response(200, json=response(p, mutation))

    client = OpenAIJudge("secret-never-log", transport=httpx.MockTransport(handler))

    async def sleep(_):
        pass

    destination = tmp_path / "run"
    await run(INPUT, destination, PROMPT.read_text(), client, sleep=sleep)
    assert len(posts) == 8
    assert validate(destination)[0]["answer"]["grade"] is None
    before = {p: p.read_bytes() for p in destination.rglob("*") if p.is_file()}
    await run(INPUT, destination, PROMPT.read_text(), client, resume=True)
    assert len(posts) == 8
    assert all(p.read_bytes() == data for p, data in before.items())
    with pytest.raises(ValueError, match="resume"):
        await run(INPUT, destination, PROMPT.read_text(), client)
    await client.close()
    assert "secret-never-log" not in capsys.readouterr().out
    assert all(
        b"secret-never-log" not in p.read_bytes() for p in destination.rglob("*") if p.is_file()
    )
    monkeypatch.setattr(
        socket, "socket", lambda *a, **k: pytest.fail("network in offline analysis")
    )
    frozen = frozen_bytes()
    combined = combine(destination)
    assert combined["counts"] == {
        "machine_agreed": 70,
        "machine_adjudicated": 6,
        "machine_unresolved": 1,
    }
    result = reevaluate(combined)
    assert result == reevaluate(combined)
    assert result["historical_verdict"] == VERDICT
    assert sum(r["unresolved_count"] for r in result["cases"]) == 2
    assert all(p.read_bytes() == data for p, data in frozen.items())
    bad = copy.deepcopy(combined)
    bad["judgments"][0]["grade"] = 99
    with pytest.raises(ValueError):
        reevaluate(bad)
    assert len(original()["judgments"]) == 77


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["json", "refusal", "model", "incomplete"])
async def test_fail_closed_no_repair(tmp_path, failure):
    packet = load_input()
    calls = []

    def handler(request):
        if request.method == "GET":
            return httpx.Response(200, json={"id": MODEL})
        p = packet[len(calls)]
        calls.append(p)
        body = response(p)
        if failure == "json":
            body["output"][0]["content"][0]["text"] = "broken-json"
        elif failure == "refusal":
            body["output"][0]["content"] = [{"type": "refusal", "refusal": "no"}]
        elif failure == "model":
            body["model"] = "different-model"
        else:
            body["status"] = "incomplete"
        return httpx.Response(200, json=body)

    client = OpenAIJudge("synthetic", transport=httpx.MockTransport(handler))
    await run(INPUT, tmp_path / "run", PROMPT.read_text(), client)
    await client.close()
    rows = validate(tmp_path / "run")
    assert len(calls) == 7
    assert all(r["status"] == "machine_unresolved" and r["answer"] is None for r in rows)


@pytest.mark.asyncio
async def test_unavailable_no_fallback_or_results(tmp_path):
    calls = []

    def handler(request):
        calls.append(str(request.url))
        return httpx.Response(404, json={"error": "provider body not exposed"})

    client = OpenAIJudge("synthetic", transport=httpx.MockTransport(handler))
    with pytest.raises(APIError, match="http_rejected"):
        await run(INPUT, tmp_path / "run", PROMPT.read_text(), client)
    await client.close()
    assert calls == ["https://api.openai.com/v1/models/" + MODEL]
    assert not (tmp_path / "run").exists()


def test_exclusive_atomic_write(tmp_path):
    p = tmp_path / "result.json"
    atomic_new(p, {"synthetic": True})
    before = p.read_bytes()
    with pytest.raises(FileExistsError):
        atomic_new(p, {"synthetic": False})
    assert p.read_bytes() == before


def test_published_when_present():
    directory = BASE / "adjudication/run"
    if directory.exists():
        records = validate(directory)
        assert len(records) == 7
        combined = read(BASE / "adjudication/machine-consensus-plus-adjudication-v1.json")
        assert combined == combine(directory)
        assert reevaluate(combined) == read(
            BASE / "adjudication/machine-adjudicated-reevaluation-v1.json"
        )


def test_published_artifact_index_and_original_seal():
    index = BASE / "adjudication/artifact-sha256.json"
    if index.exists():
        for name, checksum in read(index)["files"].items():
            assert sha(Path(name).read_bytes()) == checksum
    for name, checksum in read(BASE / "consensus-seal.json")["files"].items():
        assert sha((BASE / name).read_bytes()) == checksum
