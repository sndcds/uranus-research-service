"""Artifact checks for machine proposals; no external providers or human-label writes."""

import copy
import csv
import importlib.util
import json
from collections import Counter
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "machine_annotations", ROOT / "scripts/machine_annotations.py"
)
a = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(a)


@pytest.fixture(scope="module")
def data():
    cases = a.read_lines(ROOT / "benchmark/ground-truth-v1.jsonl")
    rows = a.read_lines(ROOT / "benchmark/snapshots/public-events-20261005/events.jsonl")
    events = {r["event"]["id"]: r for r in rows}
    proposals = a.read_lines(a.OUT / "machine-proposals-v1.jsonl")
    return proposals, cases, events


def test_complete_proposals_and_unchanged_evidence(data):
    proposals, cases, events = data
    a.validate(proposals, cases, events)
    assert len(proposals) == 2352
    assert len(cases) == 120
    assert all(c["expected_no_hit"] is None and c["review_status"] == "generated" for c in cases)
    assert all(j["relevance"] is None for c in cases for j in c["judgments"])


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("proposed_relevance", -1),
        ("proposed_relevance", 4),
        ("proposed_relevance", True),
        ("confidence", "low"),
        ("reason", ""),
        ("supporting_fields", []),
        ("evidence", []),
        ("document_hash", "0" * 64),
        ("source_snapshot_hash", "0" * 64),
        ("approved_by", "machine"),
    ],
)
def test_reject_invalid_positive_proposal(data, field, value):
    proposals, cases, events = data
    modified = copy.deepcopy(proposals)
    p = next(p for p in modified if p["proposed_relevance"] == 3)
    p[field] = value
    with pytest.raises(AssertionError):
        a.validate(modified, cases, events)


def test_reject_missing_or_duplicate_pair(data):
    proposals, cases, events = data
    with pytest.raises(AssertionError):
        a.validate(proposals[:-1], cases, events)
    with pytest.raises(AssertionError):
        a.validate([*proposals[:-1], proposals[0]], cases, events)


def test_reject_unresolvable_quote_and_occurrence(data):
    proposals, cases, events = data
    modified = copy.deepcopy(proposals)
    p = next(p for p in modified if p["proposed_relevance"] and p["occurrence_ids"])
    p["occurrence_ids"] = []
    with pytest.raises(AssertionError):
        a.validate(modified, cases, events)
    modified = copy.deepcopy(proposals)
    p = next(p for p in modified if p["proposed_relevance"])
    p["evidence"][0]["quote"] = "Invented evidence that does not occur in the snapshot"
    with pytest.raises(AssertionError):
        a.validate(modified, cases, events)


def test_queue_priority_and_blank_human_fields(data):
    proposals, _, _ = data
    with (a.OUT / "human-review-queue-v1.csv").open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    expected = sorted(proposals, key=a.priority)
    assert [(r["case_id"], r["event_id"]) for r in rows] == [
        (p["case_id"], p["event_id"]) for p in expected
    ]
    for row, p in zip(rows, expected, strict=True):
        assert not row["human_decision"] and not row["human_notes"]
        assert int(row["proposed_relevance"]) == p["proposed_relevance"]
        assert row["reason"] == p["reason"]
        if p["no_hit_candidate"]:
            assert p["review_required"] and row["review_required"] == "True"


def test_reproduction_and_translation_consistency(data):
    proposals, cases, events = data
    by_case = {c["id"]: c for c in cases}
    observed = {}
    calibration = a.load_manual_calibration(cases, events)
    for p in proposals:
        score, confidence, reason, evidence, occurrences = a.assess(
            events[p["event_id"]]["event"], by_case[p["case_id"]], p["rubric_id"]
        )
        base = dict(
            p,
            proposed_relevance=score,
            confidence=confidence,
            reason=reason,
            evidence=evidence,
            occurrence_ids=occurrences,
            supporting_fields=list(dict.fromkeys(x["field"] for x in evidence)),
        )
        final = a.apply_calibration(
            p["case_id"],
            p["event_id"],
            base,
            calibration,
            by_case[p["case_id"]],
            events[p["event_id"]]["event"],
        )
        for key in ("proposed_relevance", "confidence", "reason", "evidence", "occurrence_ids"):
            assert final[key] == p[key]
        # Translation consistency remains a property of heuristics, not exact-pair policy.
        key = p["rubric_id"], p["event_id"]
        assert observed.setdefault(key, score) == score


def test_report_matches_artifacts(data):
    proposals, cases, _ = data
    report = json.loads((a.OUT / "machine-proposals-v1-validation.json").read_text())
    assert report["dataset_status"] == "draft"
    assert report["human_approval_created"] is False
    assert report["candidates_processed"] == len(proposals)
    assert report["cases_processed"] == len(cases)
    assert report["score_counts"] == dict(Counter(str(p["proposed_relevance"]) for p in proposals))
    assert report["confidence_distribution"] == dict(Counter(p["confidence"] for p in proposals))
    assert report["required_review_pairs"] == sum(p["review_required"] for p in proposals)


def test_no_biography_as_chamber_program_or_organizer_as_family_offer(data):
    proposals, _, _ = data
    for p in proposals:
        if p["rubric_id"] == "chamber" and p["event_id"].endswith("e3170146"):
            assert p["proposed_relevance"] == 0
        if p["case_id"] == "historical-q01" and p["event_id"].endswith("862e6c95"):
            assert p["proposed_relevance"] == 1
        if p["case_id"] == "historical-q08" and p["event_id"].endswith("2c1291f5"):
            assert p["proposed_relevance"] == 2
            assert p["calibration_applied"]


def test_access_restriction_is_retained_and_not_transferred(data):
    proposals, _, events = data
    p = next(
        p
        for p in proposals
        if p["case_id"] == "historical-q03" and p["event_id"].endswith("af01f14a")
    )
    assert p["proposed_relevance"] == 1
    assert p["requires_occurrence_review"]
    event = events[p["event_id"]]["event"]
    assert len(p["occurrence_ids"]) < len(event["occurrences"])
    assert any(
        "nicht barrierefrei" in x["quote"] for x in p["evidence"] if "accessibility" in x["field"]
    )


def test_all_calibration_pairs_dominate_any_heuristic(data):
    proposals, cases, events = data
    calibration = a.load_manual_calibration(cases, events)
    assert len(calibration["decisions"]) == 275
    by_case = {c["id"]: c for c in cases}
    by_pair = {(p["case_id"], p["event_id"]): p for p in proposals}
    for (cid, eid), decision in calibration["decisions"].items():
        recorded = by_pair[cid, eid]
        assert recorded["proposed_relevance"] == decision["expected_relevance"]
        for arbitrary_score in range(4):
            base = dict(
                recorded,
                proposed_relevance=arbitrary_score,
                reason="wrong heuristic",
                evidence=[],
                supporting_fields=[],
                occurrence_ids=[],
                confidence="low",
            )
            fixed = a.apply_calibration(
                cid, eid, base, calibration, by_case[cid], events[eid]["event"]
            )
            assert fixed["proposed_relevance"] == decision["expected_relevance"]
            assert fixed["evidence"] == recorded["evidence"]
            if fixed["proposed_relevance"] == 3:
                assert fixed["evidence"] and fixed["confidence"] == "high"
            assert fixed["status"] == "machine-proposed"
            assert not {
                "reviewer_a",
                "reviewer_b",
                "approved_by",
                "approved_at",
                "review_status",
            } & set(fixed)
            if recorded["rubric_id"] in a.SENSITIVE:
                assert fixed["requires_occurrence_review"]
                if fixed["proposed_relevance"]:
                    assert fixed["occurrence_ids"]


@pytest.mark.parametrize(
    "mutation", ["missing_evidence", "fake_quote", "wrong_title", "duplicate", "approval"]
)
def test_invalid_calibration_stops_before_output(data, tmp_path, mutation):
    _, cases, events = data
    policy = json.loads(a.CALIBRATION_PATH.read_text())
    decision = next(
        d for c in policy["cases"].values() for d in c["decisions"] if d["expected_relevance"] == 3
    )
    if mutation == "missing_evidence":
        decision["evidence"] = []
    elif mutation == "fake_quote":
        decision["evidence"][0]["quote"] = "Not present in the frozen source"
    elif mutation == "wrong_title":
        decision["event_title"] = "Invented title"
    elif mutation == "approval":
        decision["approved_by"] = "not-a-human"
    else:
        policy["cases"]["historical-q01"]["decisions"].append(copy.deepcopy(decision))
    path = tmp_path / "invalid-calibration.json"
    path.write_text(json.dumps(policy))
    with pytest.raises(AssertionError):
        a.load_manual_calibration(cases, events, path)


def test_unresolved_pairs_never_force_a_score(data):
    proposals, cases, events = data
    calibration = a.load_manual_calibration(cases, events)
    by_case = {c["id"]: c for c in cases}
    for p in proposals:
        key = p["case_id"], p["event_id"]
        if key in calibration["pending"]:
            score = a.assess(events[key[1]]["event"], by_case[key[0]], p["rubric_id"])[0]
            assert p["proposed_relevance"] == score
            assert p["manual_calibration_review_required"] and p["review_required"]
            assert not p.get("calibration_applied")


def test_conflict_preserves_explicit_zero_and_genuine_counterevidence(data):
    proposals, _, _ = data
    p = next(
        p
        for p in proposals
        if p["case_id"] == "historical-q05" and p["event_id"].endswith("d04e91bc")
    )
    assert p["proposed_relevance"] == 0
    assert p["calibration_evidence_conflict"] and p["review_required"]
    assert any("QUECHUA SPRACHKURS" in e["quote"] for e in p["evidence"])


def test_calibration_review_order():
    base = dict(
        case_id="case",
        event_id="event",
        no_hit_candidate=False,
        confidence="medium",
        requires_occurrence_review=False,
        proposed_relevance=0,
    )
    levels = [
        dict(base, proposed_relevance=3),
        dict(base, proposed_relevance=2),
        dict(base, calibration_evidence_conflict=True),
        dict(base, confidence="low"),
        dict(base, requires_occurrence_review=True),
        dict(base, no_hit_candidate=True),
        base,
    ]
    assert [a.priority(p)[0] for p in levels] == list(range(7))
