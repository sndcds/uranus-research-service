"""Artifact checks for machine proposals; no external providers or human-label writes."""

import copy
import csv
import hashlib
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
    assert len(calibration["decisions"]) == 280
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
    assert not calibration["pending"]
    # Exercise the unresolved safety path without keeping resolved artifacts pending.
    p = next(p for p in proposals if p["case_id"] == "historical-q05")
    key = p["case_id"], p["event_id"]
    calibration["decisions"].pop(key)
    calibration["pending"][key] = {"reason": "Unresolved test policy"}
    case = next(c for c in cases if c["id"] == key[0])
    result = a.apply_calibration(*key, p, calibration, case, events[key[1]]["event"])
    assert result["proposed_relevance"] == p["proposed_relevance"]
    assert result["manual_calibration_review_required"] and result["review_required"]
    assert result["confidence"] == "low" and not result["calibration_applied"]


def test_conflict_preserves_explicit_zero_and_genuine_counterevidence(data):
    proposals, cases, events = data
    p = next(
        p
        for p in proposals
        if p["case_id"] == "historical-q05" and p["event_id"].endswith("d04e91bc")
    )
    assert p["proposed_relevance"] == 1 and not p["calibration_evidence_conflict"]
    calibration = a.load_manual_calibration(cases, events)
    key = p["case_id"], p["event_id"]
    calibration["decisions"][key].update(
        expected_relevance=0,
        calibration_evidence_conflict=True,
        conflict_reason="Synthetic conflicting policy for final-layer regression only",
    )
    case = next(c for c in cases if c["id"] == key[0])
    result = a.apply_calibration(*key, p, calibration, case, events[key[1]]["event"])
    assert result["proposed_relevance"] == 0
    assert result["calibration_evidence_conflict"] and result["review_required"]
    assert any("QUECHUA SPRACHKURS" in e["quote"] for e in result["evidence"])


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


# Exact pairs reviewed against full frozen evidence, relative to PR head 29c8527.
FINAL_REVIEW_PAIRS = [
    ("historical-q03", "01a0c369-117f-7172-aed1-c50b052af59d", 2),
    ("historical-q05", "019e6df1-b798-7db1-bd65-ca7bd04e91bc", 1),
    ("historical-q06", "019eba56-fe7d-79dc-9683-d2eac4ebb2f1", 0),
    ("historical-q06", "019e84a4-d625-79fa-99f6-ca653015e6e1", 0),
    ("historical-q07", "019e63f7-ebeb-7952-9304-e496b02e3588", 0),
    ("historical-q07", "019daf20-38e6-7283-9746-c604f6523e33", 0),
    ("historical-q07", "019e262e-5660-76c8-93cc-c7736848b4d3", 0),
    ("historical-q08", "01a05c60-d7d5-7197-84da-a18469bce542", 0),
    ("historical-q08", "01a0f032-2002-72db-8819-57013c0b40b8", 0),
    ("historical-q08", "019ddd54-2a60-76c7-8ccb-8d67862e6c95", 0),
    ("historical-q12", "019db91a-89d5-7c5a-90ae-7596e488a1eb", 2),
    ("historical-q12", "019f1c76-eb40-79ea-88e1-4ee976848158", 0),
    ("historical-q14", "01a0b3aa-28bf-7a09-9295-6c17ab731dc5", 0),
    ("historical-q14", "019fa7f6-e5bd-78a2-8f48-2806521951b8", 1),
    ("historical-q14", "019df20e-4efc-7c01-8c4a-8880af01f14a", 0),
    ("historical-q14", "01a06ade-f5ed-7571-9630-854d88fec839", 1),
    ("historical-q02", "019e63f7-ebeb-7952-9304-e496b02e3588", 0),
    ("historical-q03", "019daf9b-da9a-7524-9b5c-0f77457ab198", 2),
    ("historical-q03", "019e2bbb-892a-7482-a463-bb1da6b27ee5", 2),
    ("historical-q07", "01a042e9-cf5a-7252-aff4-043771488e9c", 0),
    ("historical-q11", "01a06b28-2fd0-7080-93ee-c732aba7077d", 0),
]


@pytest.mark.parametrize(("case_id", "event_id", "score"), FINAL_REVIEW_PAIRS)
def test_final_review_decision_is_fixed_and_evidence_bound(data, case_id, event_id, score):
    proposals, cases, events = data
    calibration = a.load_manual_calibration(cases, events)
    decision = calibration["decisions"][case_id, event_id]
    proposal = next(p for p in proposals if (p["case_id"], p["event_id"]) == (case_id, event_id))
    assert decision["expected_relevance"] == proposal["proposed_relevance"] == score
    assert decision["policy_source"] == "frozen-evidence-final-review"
    assert not decision["calibration_evidence_conflict"]
    assert not proposal["calibration_evidence_conflict"]
    assert (case_id, event_id) not in calibration["pending"]
    assert not proposal.get("manual_calibration_review_required")
    if score:
        assert proposal["reason"] and proposal["supporting_fields"] and proposal["evidence"]
        for item in proposal["evidence"]:
            value = a.resolve(events[event_id]["event"], item["field"])
            assert item["quote"] == value or item["quote"] in value
    if case_id == "historical-q03":
        assert proposal["requires_occurrence_review"] and proposal["occurrence_ids"]
        event = events[event_id]["event"]
        assert set(proposal["occurrence_ids"]) == {o["id"] for o in event["occurrences"]}
        if not event["title"].startswith("Reading Party"):
            for i, occurrence in enumerate(event["occurrences"]):
                item = next(
                    x
                    for x in proposal["evidence"]
                    if x["field"] == f"occurrences.{i}.space_accessibility"
                )
                assert "stufenlos" in item["quote"] and "nicht barrierefrei" in item["quote"]
                assert item["quote"] == occurrence["space_accessibility"]


def test_final_review_scope_and_no_unresolved_conflicts(data):
    proposals, cases, events = data
    calibration = a.load_manual_calibration(cases, events)
    keys = {(cid, eid) for cid, eid, _ in FINAL_REVIEW_PAIRS}
    reviewed = {key for key, d in calibration["decisions"].items() if "final_review" in d}
    assert reviewed == keys and len(keys) == 21
    assert not calibration["pending"]
    assert all(not d["calibration_evidence_conflict"] for d in calibration["decisions"].values())
    assert all(not p.get("calibration_evidence_conflict") for p in proposals)
    # Preserve all 2,331 other proposal contents, including every q15+ proposal. Only the
    # shared calibration file digest necessarily changes on other calibrated q01–q14 rows.
    unchanged = [
        {key: value for key, value in p.items() if key != "manual_calibration_sha256"}
        for p in proposals
        if (p["case_id"], p["event_id"]) not in keys
    ]
    digest = hashlib.sha256(
        json.dumps(unchanged, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()
    assert digest == "1e8fc2f6aa34cb7c7a1257852e987ac7f3764c07bd61da511d963d8eb5b4d7c8"
