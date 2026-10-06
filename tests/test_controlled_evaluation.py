"""Deterministic benchmark gates without model weights, services or live data."""

import copy
import json
import shutil
from pathlib import Path

import pytest

from uranus_research_service import controlled_evaluation as e
from uranus_research_service.controlled_runner import collection_name, documents
from uranus_research_service.semantic_manifest import digest

ROOT = Path(__file__).resolve().parents[1]


def hit(eid, score, pid=None):
    return {"event_id": eid, "score": score, "point_id": pid or eid}


def case(cid="example", language="de"):
    return {
        "case_id": cid,
        "language": language,
        "category": "accessibility",
        "query_group": "group",
        "eligible_ids": ["a", "b", "c"],
        "eligible_occurrence_ids": [],
        "eligibility_hash": digest(["a", "b", "c"]),
        "grades": {"a": 3, "b": 1, "c": 0},
        "excluded": None,
        "ranking": [hit("a", 0.8), hit("c", 0.6), hit("b", 0.3)],
        "best_relevant_rank": 1,
        "judged_scores": [
            {"event_id": "a", "grade": 3, "score": 0.8},
            {"event_id": "b", "grade": 1, "score": 0.3},
            {"event_id": "c", "grade": 0, "score": 0.6},
        ],
        "latency_ms": {"embedding": 1.0, "qdrant": 2.0, "aggregation": 0.1, "total": 3.1},
    }


def report(model):
    return {
        "benchmark_schema_version": "controlled-retrieval-v1",
        "evaluator_version": e.EVALUATOR,
        "execution_profile": "8cpu-8threads",
        "source_snapshot_hash": "snapshot",
        "query_set_hash": "queries",
        "judgment_source_hash": "labels",
        "reference_time": "2026-10-05",
        "input_sha256": {},
        "policy": e.POLICY,
        "documents": {"a": "hash"},
        "build_id": "test_001",
        "manifest_digest": "manifest-" + model,
        "model": {"model": "jina-" + model},
        "cases": [case(lang, lang) for lang in ("de", "da", "en")],
    }


def test_frozen_inputs_and_included_cases():
    identity, cases, events = e.inputs(ROOT)
    assert len(cases) == 120 and len(events) == 611
    assert len([c for c in cases if not c["excluded"]]) == 105
    assert {c["case_id"] for c in cases if c["excluded"] == "unresolved_no_hit"} == e.NO_HIT
    assert (
        len([c for c in cases if c["excluded"] == "no_judged_positive_not_confirmed_negative"]) == 9
    )
    assert identity["evaluator_version"] == e.EVALUATOR
    assert documents(events) == documents(events)


@pytest.mark.parametrize(
    "name", json.loads((ROOT / "benchmark/contracts/phase2b2c-input-sha256.json").read_text())
)
def test_frozen_input_change_stops(name, tmp_path):
    shutil.copytree(
        ROOT / "benchmark", tmp_path / "benchmark", ignore=shutil.ignore_patterns("results")
    )
    p = tmp_path / name
    p.write_bytes(p.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="frozen_input_changed"):
        e.inputs(tmp_path)


@pytest.mark.parametrize(
    "field",
    [
        "query_set_hash",
        "source_snapshot_hash",
        "reference_time",
        "evaluator_version",
        "execution_profile",
        "judgment_source_hash",
        "policy",
        "documents",
    ],
)
def test_comparison_identity_mismatch_rejected(field):
    a, b = report("v3"), report("v5")
    b[field] = "changed"
    with pytest.raises(ValueError, match="comparison_mismatch"):
        e.compare(a, b)


@pytest.mark.parametrize(
    "field", ["eligible_ids", "eligible_occurrence_ids", "eligibility_hash", "grades", "excluded"]
)
def test_per_case_mismatch_rejected(field):
    a, b = report("v3"), report("v5")
    b["cases"][0][field] = "changed"
    with pytest.raises(ValueError, match="comparison_mismatch"):
        e.compare(a, b)


def test_graded_metrics_and_unknown_rank_are_explicit():
    result = e.metrics({"a": 3, "b": 1, "c": 0}, ["unknown", "a", "c", "b"])
    assert result["Recall@5"] == 1 and result["MRR@10"] == 0.5
    expected = (7 / e.math.log2(3) + 1 / e.math.log2(5)) / (7 + 1 / e.math.log2(3))
    assert result["nDCG@10"] == pytest.approx(expected)
    assert e.metrics({"a": 3, "b": 1}, ["b", "a"], minimum=2)["MRR@10"] == 0.5
    with pytest.raises(ValueError, match="duplicate_event"):
        e.metrics({"a": 1}, ["a", "a"])


def test_aggregation_max_ties_and_duplicate_chunks():
    chunks = [hit("b", 0.5, "b2"), hit("a", 0.5, "a2"), hit("a", 0.1, "a1"), hit("b", 0.5, "b1")]
    expected = [hit("a", 0.5, "a2"), hit("b", 0.5, "b1")]
    assert e.aggregate(chunks) == e.aggregate(list(reversed(chunks))) == expected
    assert e.aggregate(chunks * 3) == expected
    with pytest.raises(ValueError, match="invalid_score"):
        e.aggregate([hit("a", float("nan"))])


def test_no_hit_excluded_even_with_positive_machine_label():
    runs = [case()]
    nohit = case("koreanopera-en", "en")
    nohit["excluded"] = "unresolved_no_hit"
    nohit["ranking"] = []
    result = e.summarize([*runs, nohit])
    assert result["overall"] == e.summarize(runs)["overall"]
    assert result["included"] == 1
    assert "koreanopera-en" in e.thresholds([*runs, nohit])["unresolved_no_hit_exploratory"]


def test_gate_calculations_and_identical_topk_semantics():
    a, b = report("v3"), report("v5")
    same = e.compare(a, b)
    assert all(g["pass"] for g in same["gates"])
    assert same["v3"]["overall"] == same["v5"]["overall"]
    assert same["source_snapshot_hash"] == a["source_snapshot_hash"]
    assert same["run_provenance"]["v5"]["manifest_digest"] == b["manifest_digest"]
    b["cases"][0]["ranking"] = [hit("c", 0.5)]
    b["cases"][0]["best_relevant_rank"] = None
    result = e.compare(a, b)
    assert result["lost_all_relevant"] == ["de"]
    recall = next(g for g in result["gates"] if g["gate"] == "Recall@10")
    assert recall["delta"] == pytest.approx(-1 / 3) and not recall["pass"]
    assert e.compare(a, b) == result
    assert json.dumps(result, sort_keys=True) == json.dumps(e.compare(a, b), sort_keys=True)


def test_threshold_curve_confusion_matrix():
    result = e.thresholds([case()])
    row = next(r for r in result["overall"] if r["threshold"] == 0.5)
    assert (row["tp"], row["fp"], row["fn"], row["tn"]) == (1, 1, 1, 0)
    assert row["precision"] == row["recall"] == row["F1"] == 0.5
    assert row["false_positive_rate"] == 1
    assert result == e.thresholds([copy.deepcopy(case())])


@pytest.mark.parametrize(
    "model,build", [("v3", "prod/alias"), ("v5", "../live"), ("v2", "ok"), ("v3", "")]
)
def test_collection_names_cannot_escape_benchmark_namespace(model, build):
    with pytest.raises(ValueError, match="benchmark_identity"):
        collection_name(model, build)


def test_separate_model_collection_names():
    assert collection_name("v3", "test_001") == "benchmark_events_jina_v3_test_001"
    assert collection_name("v5", "test_001") == "benchmark_events_jina_v5_test_001"


def test_missing_language_is_not_a_pass():
    a, b = report("v3"), report("v5")
    a["cases"] = a["cases"][:1]
    b["cases"] = b["cases"][:1]
    with pytest.raises(ValueError, match="missing_language_coverage"):
        e.compare(a, b)


def test_v3_response_contracts_match_reused_response_validators():
    # The v3 request model stays v3; only identical, model-neutral response schemas
    # are shared. These snapshots are from Encoder commit 48ce71550d5dad8c697facd3767aef8b4be97cc1.
    from uranus_research_service.encoder_contracts import ChunkResponse, EmbedResponse

    for contract in (ChunkResponse, EmbedResponse):
        frozen = json.loads(
            (ROOT / f"benchmark/contracts/encoder-v3/{contract.__name__}.json").read_text()
        )
        assert contract.model_json_schema() == frozen


@pytest.mark.parametrize("name", ["ChunkResponse", "EmbedResponse"])
def test_provider_validation_errors_do_not_echo_bodies(name):
    import traceback

    from uranus_research_service import encoder_contracts
    from uranus_research_service.controlled_runner import closed_response

    raw = {"provider_secret": "body-must-not-be-logged"}
    contract = getattr(encoder_contracts, name)
    with pytest.raises(ValueError, match="^encoder_response_contract$") as caught:
        closed_response(contract, raw)
    assert "body-must-not-be-logged" not in "".join(traceback.format_exception(caught.value))
    assert caught.value.__suppress_context__ is True


def test_thread_profile_probes_and_documented_launcher_are_reproducible():
    import ast
    import hashlib

    identity, cases, events = e.inputs(ROOT)
    path = ROOT / "benchmark/contracts/thread-parity-probes-v1.json"
    probes = json.loads(path.read_text())
    assert probes["input_sha256"] == identity["input_sha256"]
    assert probes["source_snapshot_hash"] == identity["source_snapshot_hash"]
    assert {p["language"] for p in probes["queries"]} == {"de", "da", "en"}
    for probe in probes["queries"]:
        case = next(c for c in cases if c["case_id"] == probe["case_id"])
        assert (probe["text"], probe["language"]) == (case["query"], case["language"])
    docs = documents(events)
    for probe in probes["passages"]:
        assert hashlib.sha256(probe["text"].encode()).hexdigest() == probe["content_hash"]
        assert any(probe["text"] in s["text"] for s in docs[probe["event_id"]]["sections"])
    source = (ROOT / "docs/controlled-benchmark-reproduction.md").read_text()
    launcher = source.split("```python\n", 1)[1].split("```", 1)[0]
    ast.parse(launcher)  # Never import the native Encoder into the Research Service.
    provenance = json.loads((ROOT / "benchmark/contracts/model-provenance.json").read_text())
    assert (
        hashlib.sha256(launcher.encode()).hexdigest() == provenance["v5"]["thread_launcher_sha256"]
    )
    assert hashlib.sha256(path.read_bytes()).hexdigest() == provenance["v5"]["thread_probe_sha256"]
