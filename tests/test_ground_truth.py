"""Synthetic contract tests only; these labels never enter the public annotation dataset."""

import csv
import hashlib
import io
import json
from datetime import UTC, date, datetime
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

import pytest
from pydantic import ValidationError

from uranus_research_service.ground_truth import (
    Eligibility,
    GroundTruthCase,
    Judgment,
    QueryProposal,
    annotation_csv,
    coverage,
    import_annotations,
    prepare_pool,
    validate_cases,
)
from uranus_research_service.ground_truth_cli import load_cases, main
from uranus_research_service.ground_truth_snapshot import (
    SnapshotRow,
    load_snapshot,
    project_event,
    serialize_events,
)
from uranus_research_service.semantic_manifest import digest

ROOT = Path("benchmark")
SNAPSHOT = ROOT / "snapshots/public-events-20261005/events.jsonl"
MANIFEST = ROOT / "snapshots/public-events-20261005/manifest.json"


def event(i=1):
    raw = {
        "uuid": str(UUID(int=i)),
        "release_status": "released",
        "title": "Public concert",
        "description": "Jazz live",
        "private_contact": "never export",
        "further_dates": [
            {
                "uuid": str(UUID(int=100 + i)),
                "event_uuid": str(UUID(int=i)),
                "release_status": "released",
                "start_date": "2026-10-10",
                "venue_city": "Flensburg",
            }
        ],
    }
    return project_event(raw, date(1900, 1, 1), date(2100, 12, 31))


@pytest.fixture
def corpus():
    events = [event(i) for i in range(1, 41)]
    rows, _ = serialize_events(events)
    manifest = SimpleNamespace(
        source_snapshot_hash=digest([r.model_dump(mode="json") for r in rows]),
        reference_time=datetime(2026, 10, 5, tzinfo=UTC),
    )
    return manifest, {r.event.id: r for r in rows}


def query(**kw):
    return QueryProposal(
        id="q1", query="Live music", language="en", category="music", query_group="live", **kw
    )


def judged_case(corpus, no_hit=False):
    m, rows = corpus
    c = prepare_pool([query()], m, rows)[0][0].model_dump(mode="json")
    for j in c["judgments"]:
        j.update(
            relevance=0 if no_hit else 3,
            relevance_a=0 if no_hit else 3,
            reviewer_a="test-human",
            reason="Synthetic unit assertion, not ground truth",
            supporting_fields=["description"],
        )
    c.update(
        review_status="approved",
        expected_no_hit=no_hit,
        approved_by="test-human",
        approved_at="2026-10-06T00:00:00Z",
        no_hit_review_scope="full_eligible_corpus" if no_hit else None,
    )
    return c


@pytest.mark.parametrize("bad", [-1, 4, True, "3", 1.5])
def test_invalid_relevance(corpus, bad):
    c = judged_case(corpus)
    c["judgments"][0]["relevance"] = bad
    with pytest.raises(ValidationError):
        GroundTruthCase.model_validate(c)


def test_schema_duplicates_and_hash_binding(corpus):
    m, rows = corpus
    c = GroundTruthCase.model_validate(judged_case(corpus))
    validate_cases([c], m, rows)
    with pytest.raises(ValueError, match="case_count"):
        validate_cases([c, c], m, rows)
    value = c.model_dump(mode="json")
    value["judgments"].append(value["judgments"][0])
    with pytest.raises(ValueError, match="duplicate_event"):
        GroundTruthCase.model_validate(value)
    with pytest.raises(ValueError, match="snapshot_mismatch"):
        validate_cases([c.model_copy(update={"source_snapshot_hash": "0" * 64})], m, rows)
    wrong = c.model_copy(
        update={"judgments": [c.judgments[0].model_copy(update={"document_hash": "0" * 64})]}
    )
    with pytest.raises(ValueError, match="document_hash"):
        validate_cases([wrong], m, rows)


@pytest.mark.parametrize(
    "mutation",
    ["no_hit_positive", "non_no_hit_zero", "empty", "no_reviewer", "no_scope", "no_approval"],
)
def test_human_review_and_no_hit_consistency(corpus, mutation):
    c = judged_case(corpus, no_hit=True)
    if mutation == "no_hit_positive":
        c["judgments"][0].update(relevance=3, relevance_a=3)
    if mutation == "non_no_hit_zero":
        c["expected_no_hit"] = False
    if mutation == "empty":
        c["judgments"] = []
    if mutation == "no_reviewer":
        c["judgments"][0]["reviewer_a"] = None
    if mutation == "no_scope":
        c["no_hit_review_scope"] = None
    if mutation == "no_approval":
        c["approved_by"] = None
    with pytest.raises(ValueError):
        GroundTruthCase.model_validate(c)


def test_independent_annotations_require_adjudication(corpus):
    j = judged_case(corpus)["judgments"][0]
    j.update(reviewer_b="second-human", relevance_b=1)
    with pytest.raises(ValueError, match="adjudication"):
        Judgment.model_validate(j)
    j["adjudicated_relevance"] = 3
    assert Judgment.model_validate(j).relevance == 3
    j["reviewer_b"] = "test-human"
    with pytest.raises(ValueError, match="independent"):
        Judgment.model_validate(j)


def test_deterministic_snapshot_and_public_projection():
    a, b = event(1), event(2)
    rows, encoded = serialize_events([a, b])
    assert serialize_events([b, a])[1] == encoded
    assert b"private_contact" not in encoded and b"never export" not in encoded
    raw = rows[0].model_dump(mode="json")
    raw["event"]["description"] = "changed"
    with pytest.raises(ValueError, match="hash_mismatch"):
        SnapshotRow.model_validate(raw)


def test_pool_is_blind_deterministic_and_unjudged(corpus):
    m, rows = corpus
    history = {"q1": [str(UUID(int=i)) for i in range(1, 11)]}
    first, audit = prepare_pool([query()], m, rows, history)
    second, _ = prepare_pool([query()], m, rows, {"q1": list(reversed(history["q1"]))})
    assert first == second
    assert len(first[0].judgments) == 20 and audit[0]["historical_overlap"] == 10
    assert all(j.relevance is None for j in first[0].judgments)
    text = annotation_csv(first, rows)
    assert not {"rank", "score", "model", "source"} & set(next(csv.reader(io.StringIO(text))))
    assert first[0].review_status == "generated" and first[0].expected_no_hit is None
    assert coverage(first)["dataset_status"] == "draft"


def test_annotation_roundtrip_never_approves(corpus):
    m, rows = corpus
    cases, _ = prepare_pool([query()], m, rows)
    view = annotation_csv(cases, rows)
    assert import_annotations(cases, rows, view) == cases
    entries = list(csv.DictReader(io.StringIO(view)))
    entries[0].update(
        relevance="3",
        relevance_a="3",
        reviewer_a="human",
        reason="Direct public description",
        supporting_fields="description",
    )
    out = io.StringIO()
    w = csv.DictWriter(out, fieldnames=list(entries[0]))
    w.writeheader()
    w.writerows(entries)
    revised = import_annotations(cases, rows, out.getvalue())
    assert revised[0].judgments[0].relevance == 3 and revised[0].review_status == "generated"
    entries[0]["document_hash"] = "0" * 64
    out = io.StringIO()
    w = csv.DictWriter(out, fieldnames=list(entries[0]))
    w.writeheader()
    w.writerows(entries)
    with pytest.raises(ValueError, match="evidence_changed"):
        import_annotations(cases, rows, out.getvalue())


def test_hard_filters_share_occurrence(corpus):
    e = event()
    d = e.occurrences[0]
    e = e.model_copy(
        update={
            "occurrences": [
                d.model_copy(update={"city": "Kiel"}),
                d.model_copy(update={"start_date": date(2026, 10, 11)}),
            ]
        }
    )
    f = Eligibility(
        city="Flensburg", date_from=date(2026, 10, 10), date_to=date(2026, 10, 10), weekdays=[6]
    )
    assert not f.accepts(e) and f.accepts(event())
    m, rows = corpus
    cases, _ = prepare_pool([query(eligibility=Eligibility(city="Kiel"))], m, rows)
    assert cases[0].judgments == []
    wrong = GroundTruthCase.model_validate(judged_case(corpus)).model_copy(
        update={"eligibility": Eligibility(city="Kiel")}
    )
    with pytest.raises(ValueError, match="outside_eligibility"):
        validate_cases([wrong], m, rows)


def test_groups_duplicates_and_coverage(corpus):
    m, rows = corpus
    qs = [
        query(),
        QueryProposal(
            id="q2", query="Live musiC!", language="en", category="music", query_group="live"
        ),
    ]
    with pytest.raises(ValueError, match="duplicate_query"):
        prepare_pool(qs, m, rows)
    qs[1] = qs[1].model_copy(update={"query": "Live music tonight", "language": "de"})
    cases, _ = prepare_pool(qs, m, rows)
    assert coverage(cases)["query_groups"] == {"live": ["q1", "q2"]}
    c = GroundTruthCase.model_validate(judged_case(corpus))
    r = coverage([c])
    assert r["approved_queries"] == 1 and r["approved"]["multi_relevant_count"] == 1
    assert r["approved"]["unique_relevant_events"] == 20 and r["dataset_status"] == "draft"


def test_committed_public_artifacts_and_reports(tmp_path):
    m, rows = load_snapshot(SNAPSHOT, MANIFEST)
    cases = validate_cases(load_cases(ROOT / "ground-truth-v1.jsonl"), m, rows)
    assert len(rows) == 611 and len(cases) == 120
    assert all(
        c.review_status == "generated" and all(j.relevance is None for j in c.judgments)
        for c in cases
    )
    assert coverage(cases) == json.loads((ROOT / "ground-truth-v1-report.json").read_text())
    # CSV newline normalization is explicit, not an evidence change.
    assert (
        annotation_csv(cases, rows).encode()
        == (ROOT / "annotation/ground-truth-v1.csv").read_bytes()
    )
    assert (
        hashlib.sha256(
            Path("scripts/export_public_ground_truth_source.py").read_bytes()
        ).hexdigest()
        == m.exporter_sha256
    )
    with pytest.raises(SystemExit, match="ground_truth_operation_failed"):
        main(
            [
                "validate-ground-truth",
                "--snapshot",
                str(SNAPSHOT),
                "--manifest",
                str(MANIFEST),
                "--cases",
                str(ROOT / "ground-truth-v1.jsonl"),
                "--require-approved",
                "--output",
                str(tmp_path / "out.json"),
            ]
        )
    data = SNAPSHOT.read_bytes()
    p = tmp_path / "altered.jsonl"
    p.write_bytes(data + b"\n")
    with pytest.raises(ValueError, match="file_hash"):
        load_snapshot(p, MANIFEST)


@pytest.mark.parametrize(
    "field,value", [("language", "fr"), ("category", "unknown"), ("id", "bad ID")]
)
def test_closed_query_schema(field, value):
    data = query().model_dump(mode="json")
    data[field] = value
    with pytest.raises(ValidationError):
        QueryProposal.model_validate(data)


def test_unknown_uuid_and_unpublished_source_rejected(corpus):
    c = judged_case(corpus)
    c["judgments"][0]["event_id"] = "not-a-uuid"
    with pytest.raises(ValidationError):
        GroundTruthCase.model_validate(c)
    with pytest.raises(ValueError, match="non_public"):
        project_event({"release_status": "draft"}, date(1900, 1, 1), date(2100, 12, 31))


def test_schema_and_markdown_snapshots():
    from uranus_research_service.ground_truth import coverage_markdown
    from uranus_research_service.ground_truth_snapshot import SnapshotManifest

    for model in (GroundTruthCase, SnapshotRow, SnapshotManifest):
        assert model.model_json_schema() == json.loads(
            (ROOT / "schemas" / f"{model.__name__}.json").read_text()
        )
    manifest, _ = load_snapshot(SNAPSHOT, MANIFEST)
    report = coverage(load_cases(ROOT / "ground-truth-v1.jsonl"))
    assert (
        coverage_markdown(report, manifest) == Path("docs/retrieval-ground-truth-v1.md").read_text()
    )


def test_near_duplicate_grouping_requires_review(corpus):
    m, rows = corpus
    a = query().model_copy(update={"query": "Live music tonight"})
    b = a.model_copy(
        update={"id": "q2", "query": "Live music tonight now", "query_group": "different"}
    )
    cases, _ = prepare_pool([a, b], m, rows)
    assert not coverage(cases)["coverage_gates"]["paraphrase_review"]
    cases[1] = cases[1].model_copy(update={"query_group": "live"})
    assert coverage(cases)["coverage_gates"]["paraphrase_review"]
