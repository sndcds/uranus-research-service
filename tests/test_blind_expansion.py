"""All human-like values below are synthetic test fixtures, never annotation artifacts."""

import copy
import hashlib
from pathlib import Path

import pytest
from pydantic import ValidationError

from uranus_research_service.blind_expansion import (
    PIN_PATH,
    audit_blind,
    coverage,
    export,
    load,
    read,
    select,
    tie_prefix,
    verify_inputs,
    write_new,
)
from uranus_research_service.blind_review import (
    Adjudication,
    Answer,
    ReviewBatch,
    agreement,
    conflicts,
    freeze,
    import_batch,
    prepare_freeze,
    review_inputs_hash,
    validate_batch,
)
from uranus_research_service.semantic_manifest import digest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def exported():
    return export(ROOT)


def test_historical_inputs_byte_identical():
    pins = verify_inputs(ROOT)
    assert pins["baseline_commit"] == "1ff0439134ecdd30ab65a4a3e3665de0ad65244d"
    required = {
        "benchmark/ground-truth-v1.jsonl",
        "benchmark/annotation/machine-proposals-v1.jsonl",
        "benchmark/annotation/manual-calibration-v1.json",
        "benchmark/results/v3-v5-comparison-20261006_8cpu_001.json",
        "benchmark/results/chunks-v3-20261006_8cpu_001.json",
        "benchmark/results/chunks-v5-20261006_8cpu_001.json",
    }
    assert required <= pins["files"].keys()
    # This anchor prevents weakening protection by changing both a historical file and its pin.
    assert (
        hashlib.sha256((ROOT / PIN_PATH).read_bytes()).hexdigest()
        == "35789109e88d35f587bf3b26e28a92519c52003294979a1fce7cb4c6ad711998"
    )


def test_hash_mismatch_rejected(tmp_path):
    (tmp_path / "benchmark/contracts").mkdir(parents=True)
    write_new(tmp_path / "original", {"value": 1})
    pins = {"schema_version": "phase2d-input-sha256-v1", "files": {"original": "0" * 64}}
    write_new(tmp_path / PIN_PATH, pins)
    with pytest.raises(ValueError, match="input_changed"):
        verify_inputs(tmp_path)


def test_deterministic_sampling_and_ids(exported):
    bundle, packet, runs = exported
    cases = [dict(c) for c in runs[0]["cases"]]
    assert select(cases, runs, bundle["sampling"]) == bundle["selection"]
    reordered = [dict(run, cases=list(reversed(run["cases"]))) for run in runs]
    # Source ordering is not used for sampling or blind IDs.
    assert select(list(reversed(cases)), reordered, bundle["sampling"]) == bundle["selection"]
    assert len({p["annotation_id"] for p in packet}) == len(packet)
    assert bundle["annotation_order"] == [p["annotation_id"] for p in packet]
    assert len({(p["case_id"], p["event_id"]) for p in bundle["mapping"]}) == len(packet)
    assert all(p["event_id"].replace("-", "") != p["annotation_id"] for p in bundle["mapping"])


def test_tie_blocks_complete():
    rows = [{"event_id": str(i), "score": v} for i, v in enumerate([1, 0.5, 0.5, 0.5, 0.2])]
    assert tie_prefix(rows, 2) == rows[:4]
    assert tie_prefix(rows, 20) == rows
    assert tie_prefix([], 20) == []


def test_symmetric_union_and_existing_positives(exported):
    bundle, _, runs = exported
    sides = [{c["case_id"]: c for c in r["cases"]} for r in runs]
    for row in bundle["selection"]["cases"]:
        cid = row["case_id"]
        expected = {e for e, grade in sides[0][cid]["grades"].items() if grade > 0}
        for side in sides:
            expected.update(h["event_id"] for h in tie_prefix(side[cid]["ranking"], row["k"]))
        assert expected == {m["event_id"] for m in bundle["mapping"] if m["case_id"] == cid}
        if cid in bundle["sampling"]["total_loss"]:
            assert row["k"] >= 20
    assert len({r["case_id"] for r in bundle["selection"]["cases"]}) == len(
        bundle["selection"]["cases"]
    )


def test_blind_packet_metadata_allowlist(exported):
    _, packet, _ = exported
    audit_blind(packet)
    for field in ("model", "v3", "v5", "rank", "score", "gate", "regression", "expected_outcome"):
        row = copy.deepcopy(packet[0])
        row[field] = "leak"
        with pytest.raises(ValueError, match="blind_metadata_leak"):
            audit_blind([row])
    row = copy.deepcopy(packet[0])
    row["event"]["score"] = 1
    with pytest.raises(ValidationError):
        audit_blind([row])
    row = copy.deepcopy(packet[0])
    row["event"]["description"] = "A public event about v5, model, score and rank."
    audit_blind([row])  # Public content is not rejected by substring.


def test_snapshot_and_stored_rankings_are_only_sources(exported):
    _, _, _, _, runs = load(ROOT)
    assert [r["cases"] for r in runs] == [r["cases"] for r in exported[2]]
    for name in ("blind_expansion.py", "blind_review.py", "blind_cli.py"):
        code = (ROOT / "src/uranus_research_service" / name).read_text()
        for forbidden in ("httpx", "EncoderClient", "QdrantClient", "embed(", "upsert("):
            assert forbidden not in code


@pytest.fixture
def human_fixture():
    """Tiny, explicitly synthetic independent-human records for workflow tests only."""
    aid, eid, oid = "a" * 32, "e" * 32, "00000000-0000-0000-0000-000000000002"
    bundle = {
        "mapping": [
            {
                "annotation_id": aid,
                "case_id": "synthetic",
                "event_id": eid,
                "document_hash": "d" * 64,
                "occurrence_sensitive": True,
            }
        ],
        "input_manifest_sha256": "c" * 64,
        "rubric_questions": [],
    }
    packet = [
        {
            "annotation_id": aid,
            "eligible_occurrence_ids": [oid],
            "event": {
                "title": "Synthetic fixture",
                "description": "Explicit fixture evidence",
                "occurrences": [{"id": oid, "venue_accessibility": "Fixture ramp"}],
            },
        }
    ]

    def make(who, grade=2, state="graded"):
        return {
            "schema_version": "phase2d-human-annotations-v1",
            "package_sha256": digest(bundle),
            "annotator": who,
            "provenance": "human-independent",
            "answers": [
                {
                    "annotation_id": aid,
                    "state": state,
                    "grade": grade,
                    "reason": "Synthetic fixture only",
                    "supporting_fields": ["description"],
                    "occurrence_ids": [oid],
                }
            ],
        }

    return bundle, packet, make


@pytest.mark.parametrize("grade", [-1, 4, True, 1.5, "2"])
def test_invalid_grades(human_fixture, grade):
    bundle, packet, make = human_fixture
    with pytest.raises(ValidationError):
        validate_batch(make("synthetic-a", grade), bundle, packet)


def test_unknown_uncertain_and_context_are_not_zero(human_fixture):
    bundle, packet, make = human_fixture
    for state in ("uncertain", "needs_more_context", "pending"):
        result = validate_batch(make("synthetic-a", None, state), bundle, packet)
        assert result.answers[0].grade is None
    with pytest.raises(ValueError, match="state_grade_mismatch"):
        validate_batch(make("synthetic-a", 0, "uncertain"), bundle, packet)
    raw = make("synthetic-a")
    raw["answers"][0]["annotation_id"] = "f" * 32
    with pytest.raises(ValueError, match="unknown_annotation"):
        validate_batch(raw, bundle, packet)


def test_duplicates_binding_and_no_machine_provenance(human_fixture):
    bundle, packet, make = human_fixture
    for change, match in (
        ("duplicate", "duplicate_answer"),
        ("package", "annotation_package"),
        ("machine", "human-independent"),
    ):
        raw = make("synthetic-a")
        if change == "duplicate":
            raw["answers"].append(raw["answers"][0])
        elif change == "package":
            raw["package_sha256"] = "0" * 64
        else:
            raw["provenance"] = "machine_suggestion"
        with pytest.raises(ValueError, match=match):
            validate_batch(raw, bundle, packet)


def test_occurrence_sensitive_positives(human_fixture):
    bundle, packet, make = human_fixture
    raw = make("synthetic-a")
    raw["answers"][0]["occurrence_ids"] = []
    with pytest.raises(ValueError, match="occurrence_sensitive_positive"):
        validate_batch(raw, bundle, packet)
    raw = make("synthetic-a")
    raw["answers"][0]["supporting_fields"] = ["venue_accessibility"]
    validate_batch(raw, bundle, packet)
    raw["answers"][0]["occurrence_ids"] = ["00000000-0000-0000-0000-000000000003"]
    with pytest.raises(ValueError, match="occurrence_not_eligible"):
        validate_batch(raw, bundle, packet)


def test_independent_agreement_and_conflicts(human_fixture):
    bundle, packet, make = human_fixture
    a = validate_batch(make("synthetic-a", 0), bundle, packet)
    b = validate_batch(make("synthetic-b", 2), bundle, packet)
    result = agreement(a, b, bundle, packet)
    assert result["confusion_matrix_0_3"][0][2] == 1
    assert result["raw_agreement"] == 0
    assert result["cohen_kappa"] == 0
    rows = conflicts(a, b, bundle, packet, {"synthetic": {}})
    assert rows[0]["adjudication_required"] and rows[0]["reason"] == "human_disagreement"
    assert rows[0]["old_grade"] is None
    with pytest.raises(ValueError, match="independent_annotators"):
        agreement(a, a, bundle, packet)


def test_uncertain_excluded_from_agreement(human_fixture):
    bundle, packet, make = human_fixture
    a = validate_batch(make("synthetic-a", None, "uncertain"), bundle, packet)
    b = validate_batch(make("synthetic-b", 0), bundle, packet)
    result = agreement(a, b, bundle, packet)
    assert result["graded_pairs"] == 0 and result["raw_agreement"] is None
    assert result["unresolved_pair"] == 1


def test_existing_judgments_never_automatically_replaced(human_fixture):
    bundle, packet, make = human_fixture
    a, b = [validate_batch(make(name), bundle, packet) for name in ("synthetic-a", "synthetic-b")]
    old = {"synthetic": {"e" * 32: 0}}
    before = copy.deepcopy(old)
    rows = conflicts(a, b, bundle, packet, old)
    assert rows[0]["reason"] == "existing_draft_judgment_conflict"
    result = import_batch(make("synthetic-a"), bundle, packet)
    assert result["status"] == "draft"
    assert old == before


def make_adjudication(a, b, bundle, answers):
    return {
        "schema_version": "phase2d-human-adjudication-v1",
        "package_sha256": digest(bundle),
        "review_inputs_sha256": review_inputs_hash(a, b),
        "adjudicator": "synthetic-adjudicator",
        "provenance": "human-adjudication",
        "answers": answers,
    }


def test_freeze_blocks_incomplete_conflicts_and_missing_approval(human_fixture):
    bundle, packet, make = human_fixture
    a = validate_batch(make("synthetic-a", 0), bundle, packet)
    b = validate_batch(make("synthetic-b", 2), bundle, packet)
    ad = make_adjudication(a, b, bundle, [])
    with pytest.raises(ValueError, match="open_or_unknown_adjudication"):
        prepare_freeze(a, b, ad, bundle, packet, {"synthetic": {}})
    b = validate_batch(make("synthetic-b", None, "uncertain"), bundle, packet)
    with pytest.raises(ValueError, match="incomplete_human_reviews"):
        prepare_freeze(a, b, ad, bundle, packet, {"synthetic": {}})
    with pytest.raises(ValidationError):
        freeze({"status": "draft"}, {})


def test_deterministic_freeze_explicit_approval_bound_to_inputs(human_fixture):
    bundle, packet, make = human_fixture
    a, b = [validate_batch(make(name), bundle, packet) for name in ("synthetic-a", "synthetic-b")]
    ad = make_adjudication(a, b, bundle, [a.answers[0].model_dump(mode="json")])
    old = {"synthetic": {"e" * 32: 0}}
    draft = prepare_freeze(a, b, ad, bundle, packet, old)
    approval = {
        "schema_version": "phase2d-human-approval-v1",
        "draft_sha256": digest(draft),
        "approved_at": "2026-10-06T00:00:00Z",
        "approval_reference": "SYNTHETIC TEST ONLY",
        "authorized_by": "synthetic-person",
        "authorization": "explicit-human-approval",
        "rubric_decisions": {},
    }
    assert freeze(draft, approval) == freeze(
        prepare_freeze(a, b, ad, bundle, packet, old), approval
    )
    assert draft["status"] == "draft" and old["synthetic"]["e" * 32] == 0
    assert draft["conflicts"][0]["resolution_status"] == "resolved"
    unresolved = copy.deepcopy(draft)
    unresolved["open_conflict_count"] = 1
    with pytest.raises(ValueError, match="open_conflicts"):
        freeze(unresolved, approval)
    changed = copy.deepcopy(draft)
    changed["judgments"][0]["grade"] = 1
    with pytest.raises(ValueError, match="approval_draft_mismatch"):
        freeze(changed, approval)
    ad["review_inputs_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="adjudication_inputs_changed"):
        prepare_freeze(a, b, ad, bundle, packet, old)


def test_coverage_explicit_unknown_not_zero(exported):
    bundle, _, runs = exported
    report = coverage(runs, bundle)
    for row in report["per_case"]:
        assert row["positive"] + row["zero"] + row["unjudged"] == row["returned"]
    assert any(r["unjudged"] == 10 for r in report["per_case"] if r["k"] == 10)
    assert len(report["per_case"]) == 480


def test_write_once_protects_existing_files(tmp_path):
    p = tmp_path / "artifact.json"
    write_new(p, {"historical": True})
    before = p.read_bytes()
    with pytest.raises(FileExistsError):
        write_new(p, {"historical": False})
    assert p.read_bytes() == before


def test_no_human_artifacts_or_reevaluation_fabricated():
    base = ROOT / "benchmark/annotation/phase2d"
    for name in (
        "annotations-a.jsonl",
        "annotations-b.jsonl",
        "adjudicated.jsonl",
        "frozen-judgments.jsonl",
    ):
        assert not (base / name).exists()
    assert not (ROOT / "benchmark/results/phase2d/v3-v5-expanded-comparison.json").exists()
    html = (base / "review.html").read_text()
    assert "connect-src 'none'" in html and "textContent" in html
    assert "fetch(" not in html and "innerHTML" not in html
    assert '<option value="3">' in html


def test_schemas_closed():
    assert ReviewBatch.model_json_schema()["additionalProperties"] is False
    assert Adjudication.model_json_schema()["additionalProperties"] is False
    assert Answer.model_json_schema()["additionalProperties"] is False


def test_committed_packet_and_schemas_match_generator(exported):
    from uranus_research_service.controlled_evaluation import lines

    bundle, packet, _ = exported
    base = ROOT / "benchmark/annotation/phase2d"
    assert read(base / "blind-mapping.json") == bundle
    assert lines(base / "blind-candidates.jsonl") == packet
    assert read(base / "annotation-package.json")["package_sha256"] == digest(bundle)
    assert read(base / "annotation-schema.json") == ReviewBatch.model_json_schema()
    assert read(base / "adjudication-schema.json") == Adjudication.model_json_schema()
    assert bundle["rubric_questions"] == []


def test_phase2d_artifact_hashes():
    index = read(ROOT / "benchmark/results/phase2d/artifact-sha256.json")
    for path, sha in index["files"].items():
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == sha
