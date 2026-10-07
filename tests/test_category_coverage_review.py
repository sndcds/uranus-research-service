"""No real APIs or judgments: deterministic frozen pool and synthetic contract checks."""

import copy
import json
import socket
from pathlib import Path

import httpx
import pytest

from uranus_research_service import category_coverage_review as cr
from uranus_research_service.blind_expansion import audit_blind, load, order_key, tie_prefix
from uranus_research_service.blind_review import ReviewBatch, validate_batch
from uranus_research_service.machine_judge import (
    BlindCandidate,
    OpenAIJudge,
    api_payload,
    load_blind,
    read,
    run_pass,
)


@pytest.fixture(scope="module")
def built():
    return cr.build()


@pytest.fixture(scope="module")
def historical():
    return load(Path("."))


def test_complete_target_case_set(built, historical):
    plan, packet, _, report, _, _ = built
    expected = {
        c["case_id"]
        for c in historical[2]
        if c["category"] in cr.CATEGORIES and c["excluded"] is None
    }
    assert set(plan["case_ids"]) == expected
    assert len(expected) == report["case_count"] == 20
    assert not plan["atmosphere_overlap"]
    assert set(report["by_category"]) == set(cr.CATEGORIES)
    assert len(packet) == report["pair_count"] == 1506
    assert report["by_category"] == {
        "outdoor": 36,
        "theatre": 182,
        "venue": 286,
        "accessibility": 1002,
    }
    assert len({p["annotation_id"] for p in packet}) == 1506
    assert len({(m["case_id"], m["event_id"]) for m in plan["mapping"]}) == 1506


def test_exact_pool_sources_and_ties(built, historical):
    sides = [{c["case_id"]: c for c in run["cases"]} for run in historical[4]]
    for c in built[3]["cases"]:
        a, b = (s[c["case_id"]] for s in sides)
        ids = set(c["ids"])
        for r in (a, b):
            assert {h["event_id"] for h in r["ranking"][:10]} <= ids
            assert {h["event_id"] for h in tie_prefix(r["ranking"], c["k"])} <= ids
        assert {e for e, g in a["grades"].items() if g > 0} <= ids
        groups = [set(v) for v in c["groups"].values()]
        assert set.union(*groups) == ids
        assert sum(map(len, groups)) == len(ids)  # disjoint accounting
        assert c["k"] == (20 if any(c["signals"].values()) else 10)
        for block in c["tie_blocks"]:
            r = a if block["model"] == "v3" else b
            assert len(tie_prefix(r["ranking"], block["cutoff"])) == block["end_rank"]
            assert set(block["added_ids"]) <= ids
    assert built[3]["top20_cases"] == 20
    assert built[3]["tie_cases"] == 12
    assert built[3]["large_tie_cases"] == [
        "historical-q27",
        "stepfree-da",
        "stepfree-de",
        "stepfree-en",
    ]


def synthetic(n=30):
    ranking = [
        {"event_id": str(i), "score": 1 - i / 100, "title": "identical title"} for i in range(n)
    ]
    return {"ranking": ranking, "grades": {str(i): 1 if i == 0 else 0 for i in range(n)}}


def test_uuid_not_title_dedup_and_complete_synthetic_tie():
    a = synthetic(150)
    b = copy.deepcopy(a)
    for r in (a, b):
        for h in r["ranking"][9:]:
            h["score"] = 0.5
    chosen = cr.choose(a, b, 1)
    assert chosen["k"] == 10
    assert len(chosen["ids"]) == 150  # equal title and tie do not collapse or truncate IDs
    assert chosen["large_tie_pool"] is True
    assert all(block["end_rank"] == 150 for block in chosen["tie_blocks"])


@pytest.mark.parametrize("signal", ["gap", "loss", "unknown", "jaccard"])
def test_expansion_triggers(signal):
    a, b = synthetic(), synthetic()
    if signal in ("gap", "loss"):
        b["ranking"] = b["ranking"][12:] + b["ranking"][:12]
    elif signal == "unknown":
        a["grades"] = {"0": 1}
    else:
        b["ranking"] = b["ranking"][10:] + b["ranking"][:10]
    assert cr.choose(a, b, 6)["k"] == 20


def test_full_public_evidence_and_eligibility(built, historical):
    events = {str(eid): row.model_dump(mode="json") for eid, row in historical[3].items()}
    cases = {c["case_id"]: c for c in historical[2]}
    mapping = {m["annotation_id"]: m for m in built[0]["mapping"]}
    seen_events = {}
    for p in built[1]:
        m = mapping[p["annotation_id"]]
        original = events[m["event_id"]]["event"]
        assert p["event"] == {k: v for k, v in original.items() if k != "id"}
        assert p["eligible_occurrence_ids"] == sorted(
            o["id"]
            for o in original["occurrences"]
            if o["id"] in cases[m["case_id"]]["eligible_occurrence_ids"]
        )
        assert p["eligible_occurrence_ids"]
        assert cr.CHECKS[cases[m["case_id"]]["category"]] in p["rubric"]
        seen_events.setdefault(m["event_id"], set()).add(p["annotation_id"])
        BlindCandidate.model_validate(p)
    assert any(len(ids) > 1 for ids in seen_events.values())
    assert all(len(ids) == len(set(ids)) for ids in seen_events.values())
    audit_blind(built[1])
    assert built[1] == sorted(
        built[1], key=lambda p: order_key(cr.SEED, "presentation", p["annotation_id"])
    )


@pytest.mark.parametrize(
    "field",
    ["rank", "score", "v3", "v5", "previous_grade", "machine_grade", "category", "regression"],
)
def test_blind_metadata_rejected(built, field):
    p = copy.deepcopy(built[1][0])
    p[field] = "forbidden"
    with pytest.raises(ValueError):
        audit_blind([p])


def test_every_candidate_has_promptable_closed_evidence(built):
    # Validate actual serializer for the entire pool, including long tie-block documents.
    for p in built[1]:
        request = api_payload(p, {"model": "synthetic-offline-test"}, "synthetic", {})
        body = json.loads(request["input"][0]["content"])
        assert body == {
            "annotation_id": p["annotation_id"],
            "query": {"text": p["query"], "language": p["language"]},
            "rubric": {"query_specific": p["rubric"], "scale": p["scale"]},
            "eligibility": {
                "requirements": p["eligibility"],
                "reference_time": p["reference_time"],
                "eligible_occurrence_ids": p["eligible_occurrence_ids"],
            },
            "evidence": p["event"],
        }
        assert len(request["input"]) == 1


def test_coverage_before_and_hypothetical_target(built, historical):
    selections = built[3]["cases"]
    assert cr.coverage(historical[4], selections) == (built[4], built[5])
    for cat in cr.CATEGORIES:
        for i, m in enumerate(("v3", "v5")):
            rows = [
                c
                for c in historical[4][i]["cases"]
                if c["category"] == cat and c["excluded"] is None
            ]
            for k in (10, 20):
                expected = sum(
                    sum(h["event_id"] in c["grades"] for h in c["ranking"][:k]) / k for c in rows
                ) / len(rows)
                assert built[4][cat]["models"][m][str(k)] == pytest.approx(expected)
                assert built[5][cat]["models"][m][str(k)] == 1
    before, after = cr.coverage(historical[4], [])
    assert all(c["status"] == "no_evaluable_cases" for c in before.values())
    assert all(c["models"]["v3"]["10"] is None for c in after.values())


def test_input_hash_fail_closed(monkeypatch):
    original = Path.read_bytes

    def tampered(p):
        return original(p) + (b" " if p == cr.PIN else b"")

    monkeypatch.setattr(Path, "read_bytes", tampered)
    with pytest.raises(ValueError, match="manifest_changed"):
        cr.build()


def test_offline_reproducibility_ui_and_answer_contract(tmp_path, monkeypatch, built):
    def forbidden(*args, **kwargs):
        pytest.fail("external access in preparation")

    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(httpx.Client, "request", forbidden)
    monkeypatch.setattr(httpx.AsyncClient, "request", forbidden)
    monkeypatch.setattr(OpenAIJudge, "request", forbidden)
    path = tmp_path / "package"
    cr.prepare(path)
    plan, packet = cr.checked(path)
    assert (plan, packet) == built[:2]
    assert {p.name for p in (path / "reviewer").iterdir()} == {
        "review.html",
        "blind-candidates.jsonl",
        "annotation-package.json",
    }
    assert (path / "reviewer/review.html").read_bytes() == Path(
        "benchmark/annotation/phase2d/review.html"
    ).read_bytes()
    assert read(path / "annotation-schema.json") == ReviewBatch.model_json_schema()
    review = {
        "schema_version": "phase2d-human-annotations-v1",
        "package_sha256": read(path / "reviewer/annotation-package.json")["package_sha256"],
        "annotator": "synthetic_fixture",
        "provenance": "human-independent",
        "answers": [],
    }
    assert not validate_batch(review, plan, packet).answers  # fixture only; no human file produced
    with pytest.raises(ValueError, match="destination"):
        cr.prepare(path)
    if cr.DEST.exists():
        assert {
            str(p.relative_to(path)): p.read_bytes() for p in path.rglob("*") if p.is_file()
        } == {
            str(p.relative_to(cr.DEST)): p.read_bytes() for p in cr.DEST.rglob("*") if p.is_file()
        }
    cr.verify()  # all 171 previous files retain exact SHA256


@pytest.mark.asyncio
async def test_existing_judge_two_independent_synthetic_passes(tmp_path):
    # In-memory synthetic HTTP only, no model or network execution.
    package = tmp_path / "package"
    cr.prepare(package)
    work = tmp_path / "work"
    cr.prepare_machine(package, work, "synthetic-offline-test", "synthetic-test")
    plan, packet = load_blind(work / "blind")
    assert (work / "blind/blind-candidates.jsonl").read_bytes() == (
        package / "reviewer/blind-candidates.jsonl"
    ).read_bytes()
    assert plan["planned_passes"] == ["machine-a", "machine-b"]
    seen = []

    def handler(request):
        if request.method == "GET":
            return httpx.Response(200, json={"id": plan["model"]})
        req = json.loads(request.content)
        data = json.loads(req["input"][0]["content"])
        assert set(data) == {"annotation_id", "query", "rubric", "eligibility", "evidence"}
        assert req["store"] is False
        assert req["text"]["format"]["strict"] is True
        assert "previous_response_id" not in req and "tools" not in req
        assert "category" not in data and "query_id" not in data
        seen.append((data["annotation_id"], req["instructions"]))
        answer = {
            "annotation_id": data["annotation_id"],
            "state": "uncertain",
            "grade": None,
            "confidence": 0.0,
            "reason": "SYNTHETIC TEST ONLY",
            "supporting_fields": [],
            "occurrence_ids": [],
        }
        return httpx.Response(
            200,
            json={
                "id": "synthetic_response",
                "model": plan["model"],
                "status": "completed",
                "usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
                "output": [
                    {
                        "type": "message",
                        "content": [{"type": "output_text", "text": json.dumps(answer)}],
                    }
                ],
            },
        )

    client = OpenAIJudge("synthetic-key", transport=httpx.MockTransport(handler))
    try:
        for name in ("machine-a", "machine-b"):
            rows = await run_pass(
                work / "blind", work / name, name, "synthetic-" + name, "dry-run", client
            )
            assert len(rows) == len(plan["dry_annotation_ids"])
            assert all(r["grade"] is None for r in rows)
    finally:
        await client.close()
    n = len(plan["dry_annotation_ids"])
    assert [p[0] for p in seen[:n]] == [p[0] for p in seen[n:]]
    assert seen[0][1] != seen[n][1]
    assert (work / "machine-a/machine-a.jsonl").exists()
    assert (work / "machine-b/machine-b.jsonl").exists()
    assert not (work / "machine-c").exists()
    assert len(packet) == 1506
