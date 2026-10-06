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
    for p in proposals:
        score, confidence, reason, evidence, occurrences = a.assess(
            events[p["event_id"]]["event"], by_case[p["case_id"]], p["rubric_id"]
        )
        assert (score, confidence, reason, evidence, occurrences) == (
            p["proposed_relevance"],
            p["confidence"],
            p["reason"],
            p["evidence"],
            p["occurrence_ids"],
        )
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
            assert p["proposed_relevance"] == 0


def test_access_restriction_is_retained_and_not_transferred(data):
    proposals, _, events = data
    p = next(
        p
        for p in proposals
        if p["case_id"] == "historical-q03" and p["event_id"].endswith("af01f14a")
    )
    assert p["proposed_relevance"] == 2
    assert p["requires_occurrence_review"]
    event = events[p["event_id"]]["event"]
    assert len(p["occurrence_ids"]) < len(event["occurrences"])
    assert any(
        "nicht barrierefrei" in x["quote"] for x in p["evidence"] if "accessibility" in x["field"]
    )
