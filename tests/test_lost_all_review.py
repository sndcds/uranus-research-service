"""Human workflow tests; all answers fabricated here are synthetic test fixtures only."""

import copy
import socket
from pathlib import Path

import pytest

from uranus_research_service import lost_all_review as review
from uranus_research_service.blind_expansion import export, read
from uranus_research_service.controlled_evaluation import lines
from uranus_research_service.semantic_manifest import digest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def bundle():
    return review.checked(ROOT, ROOT / review.DEST)


def submission(plan, packet):
    return {
        "schema_version": "phase2d-human-annotations-v1",
        "package_sha256": digest(plan),
        "annotator": "synthetic-test-only",
        "provenance": "human-independent",
        "answers": [
            {
                "annotation_id": p["annotation_id"],
                "state": "graded",
                "grade": 0,
                "reason": "SYNTHETIC TEST ONLY",
                "supporting_fields": [],
                "occurrence_ids": [],
            }
            for p in packet
        ],
    }


def test_frozen_files_and_exact_pool(bundle):
    plan, packet, runs = bundle
    assert set(plan["case_ids"]) == set(review.CASES)
    assert len(packet) == 77
    sides = [{c["case_id"]: c for c in r["cases"]} for r in runs]
    for cid in review.CASES:
        a, b = [s[cid] for s in sides]
        expected = {h["event_id"] for r in (a, b) for h in r["ranking"][:10]}
        expected |= {e for e, grade in a["grades"].items() if grade > 0}
        actual = [p["event_id"] for p in packet if p["query_id"] == cid]
        assert set(actual) == expected
        assert len(actual) == len(set(actual))
    assert [plan["counts"][cid]["total"] for cid in review.CASES] == [16, 19, 18, 24]
    assert review.sha(ROOT / review.PIN) == plan["input_manifest_sha256"]
    assert digest(plan) == "1054abb042ed57f39e708df1c74fbea9c9f69db69c729203dd0393bd8d7dca05"
    review.verify(ROOT)


def test_same_title_different_uuid_never_collapses():
    hits = [
        {"event_id": f"00000000-0000-0000-0000-{i:012}", "title": "Same title"} for i in range(1, 4)
    ]
    a = {"ranking": hits[:2], "grades": {hits[2]["event_id"]: 1}}
    b = {"ranking": hits[1:], "grades": a["grades"]}
    ids, counts = review.pool(a, b)
    assert ids == {h["event_id"] for h in hits}
    assert counts["both_top10"] == 1


def test_deterministic_export_and_original_ui(tmp_path, bundle):
    plan, packet, _ = bundle
    assert review.prepare(ROOT, tmp_path / "a") == plan
    assert review.prepare(ROOT, tmp_path / "b") == plan
    files = sorted(
        p.relative_to(tmp_path / "a") for p in (tmp_path / "a").rglob("*") if p.is_file()
    )
    for name in files:
        assert (tmp_path / "a" / name).read_bytes() == (tmp_path / "b" / name).read_bytes()
    assert lines(tmp_path / "a/reviewer/blind-candidates.jsonl") == packet
    assert (tmp_path / "a/reviewer/review.html").read_bytes() == (
        ROOT / "benchmark/annotation/phase2d/review.html"
    ).read_bytes()
    with pytest.raises(ValueError, match="destination_must_be_new"):
        review.prepare(ROOT, tmp_path / "a")


def test_evidence_exact_occurrences_and_combined_intents(bundle):
    plan, packet, _ = bundle
    original, source, _ = export(ROOT)
    pairs = {(m["case_id"], m["event_id"]): m["annotation_id"] for m in original["mapping"]}
    evidence = {p["annotation_id"]: p for p in source}
    for p in packet:
        src = evidence[pairs[p["query_id"], p["event_id"]]]
        assert p["event"] == src["event"]  # includes full description and ALL occurrence fields
        assert p["eligible_occurrence_ids"] == src["eligible_occurrence_ids"]
        assert p["eligibility"] == src["eligibility"]
        assert p["rubric"].startswith(src["rubric"])
        assert all(s in p["rubric"] for s in review.CHECKS[p["query_id"]])
        assert p["scale"] == src["scale"]
    assert all(m["occurrence_sensitive"] for m in plan["mapping"])


@pytest.mark.parametrize(
    "field",
    ["model", "v3", "v5", "rank", "score", "delta", "gate", "lost_all_status", "historical_grade"],
)
def test_blind_schema_rejects_metadata_leaks(bundle, field):
    row = copy.deepcopy(bundle[1][0])
    row[field] = "forbidden"
    with pytest.raises(ValueError):
        review.audit([row])
    row = copy.deepcopy(bundle[1][0])
    row["event"][field] = "forbidden"
    with pytest.raises(ValueError):
        review.audit([row])


def test_no_operator_metadata_in_reviewer_files(bundle):
    review.audit(bundle[1])
    html = (ROOT / review.DEST / "reviewer/review.html").read_text()
    assert "provenance.json" not in html and "review-plan.json" not in html
    assert "connect-src 'none'" in html
    assert "localStorage.setItem" in html
    assert "textContent" in html
    assert set(read(ROOT / review.DEST / "reviewer/annotation-package.json")) == {
        "schema_version",
        "review_set_id",
        "package_sha256",
        "packet_sha256",
        "count",
    }


@pytest.mark.parametrize("grade", [-1, 4, True, 1.5, "2"])
def test_invalid_grade(bundle, grade):
    raw = submission(*bundle[:2])
    raw["answers"][0]["grade"] = grade
    with pytest.raises(ValueError):
        review.validate(raw, *bundle[:2])


def test_uncertain_and_completion(bundle):
    raw = submission(*bundle[:2])
    raw["answers"][0].update(state="uncertain", grade=None)
    out = review.imported(raw, *bundle[:2])
    unresolved = next(
        j for j in out["judgments"] if j["annotation_id"] == raw["answers"][0]["annotation_id"]
    )
    assert unresolved["grade"] is None
    result = review.evaluate(out, *bundle)
    case = next(c for c in result["cases"] if c["case_id"] == unresolved["case_id"])
    assert unresolved["event_id"] in case["unresolved"]
    assert case["historical_known_positive_loss_remains"] is None
    raw["answers"].pop()
    _, status = review.validate(raw, *bundle[:2])
    assert not status["complete"] and len(status["missing"]) == 1
    with pytest.raises(ValueError, match="review_incomplete"):
        review.imported(raw, *bundle[:2])


@pytest.mark.parametrize("mutation", ["duplicate", "unknown", "package", "foreign_occurrence"])
def test_bad_review_rejected(bundle, mutation):
    raw = submission(*bundle[:2])
    if mutation == "duplicate":
        raw["answers"].append(raw["answers"][0])
    elif mutation == "unknown":
        raw["answers"][0]["annotation_id"] = "0" * 32
    elif mutation == "package":
        raw["package_sha256"] = "0" * 64
    else:
        raw["answers"][0]["occurrence_ids"] = ["00000000-0000-0000-0000-000000000001"]
    with pytest.raises(ValueError):
        review.validate(raw, *bundle[:2])


def test_hash_mismatch(tmp_path):
    (tmp_path / Path(review.PIN).parent).mkdir(parents=True)
    review.atomic_new(tmp_path / review.PIN, {"files": {"source": "0" * 64}})
    (tmp_path / "source").write_text("changed")
    with pytest.raises(ValueError, match="frozen_input_changed"):
        review.verify(tmp_path)


def test_packet_tampering(tmp_path, bundle):
    review.prepare(ROOT, tmp_path / "packet")
    p = tmp_path / "packet/reviewer/blind-candidates.jsonl"
    p.write_text(p.read_text().replace("Participatory", "Changed"))
    with pytest.raises(ValueError, match="review_evidence_changed"):
        review.checked(ROOT, tmp_path / "packet")


def test_reproducible_offline_reevaluation_and_no_historical_writes(bundle, monkeypatch, tmp_path):
    before = {p: review.sha(ROOT / p) for p in bundle[0]["source_hashes"]}

    def blocked(*args, **kwargs):
        raise AssertionError("network/inference forbidden")

    monkeypatch.setattr(socket, "socket", blocked)
    raw = submission(*bundle[:2])
    # Synthetic fixture: new positive for each query, with actual eligible evidence references.
    old = {c["case_id"]: c["grades"] for c in bundle[2][0]["cases"]}
    for cid in review.CASES:
        p = next(p for p in bundle[1] if p["query_id"] == cid and p["event_id"] not in old[cid])
        a = next(a for a in raw["answers"] if a["annotation_id"] == p["annotation_id"])
        a.update(
            grade=2, supporting_fields=["title"], occurrence_ids=p["eligible_occurrence_ids"][:1]
        )
    derived = review.imported(raw, *bundle[:2])
    a = review.evaluate(derived, *bundle)
    b = review.evaluate(derived, *bundle)
    assert a == b
    assert len(a["cases"]) == 4
    assert a["historical_verdict"] == "v5 provisionally fails one or more gates"
    assert [c["models"]["v3"]["old_best_known_relevant_rank"] for c in a["cases"]] == [8, 9, 7, 6]
    assert [c["models"]["v5"]["old_best_known_relevant_rank"] for c in a["cases"]] == [
        20,
        17,
        13,
        15,
    ]
    review.atomic_new(tmp_path / "new-result.json", a)
    with pytest.raises(FileExistsError):
        review.atomic_new(tmp_path / "new-result.json", b)
    assert before == {p: review.sha(ROOT / p) for p in before}
    derived["judgments"][0]["grade"] = 3
    with pytest.raises(ValueError, match="derived_judgments_changed"):
        review.evaluate(derived, *bundle)
