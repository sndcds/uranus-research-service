"""Offline analytical invariants; no model weights or external services."""

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / f"scripts/{name}.py")
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


a = module("analyze_retrieval_regressions")
p = module("summarize_adapter_diagnostics")
w = module("isolated_adapter_diagnostics")


def test_unjudged_is_not_false_positive():
    case = {
        "grades": {"yes": 2, "no": 0},
        "ranking": [{"event_id": "unknown"}, {"event_id": "yes"}, {"event_id": "no"}],
    }
    assert a.coverage(case) == {"judged": 2, "known_positive": 1, "known_zero": 1, "unjudged": 1}


def test_reconstruction_reproducible_and_loss_ranks_preserved():
    result = a.analyze(ROOT)
    assert result == a.read(ROOT / "benchmark/results/v5-regression-reconstruction-20261006.json")
    for cid, expected in zip(a.LOSSES, [(8, 20), (9, 17), (7, 13), (6, 15)], strict=True):
        c = result["cases"][cid]
        assert tuple(min(h["rank"] for h in c[m]["relevant"]) for m in ("v3", "v5")) == expected
        assert c["v5"]["coverage_top10"]["known_positive"] == 0
        for m in ("v3", "v5"):
            assert len(c[m]["relevant"]) == len(c["positive_ids"])
            assert all(h["chunk"]["text"] and h["chunk"]["contexts"] for h in c[m]["relevant"])
    outdoor = [c for c in result["cases"].values() if c["category"] == "outdoor"]
    assert len(outdoor) == 1
    assert (
        outdoor[0]["v5"]["metrics"]["Recall@10"] - outdoor[0]["v3"]["metrics"]["Recall@10"]
        == -0.125
    )


def test_content_relocation_preserves_characters_not_pooling_causality():
    result = w.variants("abcEVIDENCEdef", 3, 11)
    assert result["evidence_only"] == "EVIDENCE"
    for name in ("original", "evidence_first", "evidence_middle", "evidence_last"):
        assert sorted(result[name]) == sorted(result["original"])
    with pytest.raises(ValueError, match="span_bounds"):
        w.variants("abc", 2, 4)


def test_parity_metrics_and_tied_ranking():
    vector = [1.0] + [0.0] * 1023
    metrics = p.vector_metrics(vector, vector)
    assert metrics["cosine_similarity"] == 1
    assert metrics["max_absolute_difference"] == metrics["mean_absolute_difference"] == 0
    assert p.ranking(vector, {"b": vector, "a": vector}, ["b", "a"]) == ["a", "b"]
    for bad in ([0.0] * 1024, [True] + [0.0] * 1023, [float("nan")] * 1024, [1.0]):
        with pytest.raises(ValueError):
            p.vector_metrics(vector, bad)


@pytest.fixture
def parity_workers(tmp_path):
    report = p.read(ROOT / "benchmark/results/v3-benchmark-onnx-parity-20261006.json")
    for mode, metadata in report["provenance"].items():
        worker = dict(metadata)
        kinds = ("query", "passage") if mode == "onnx" else (mode.split("-")[1],)
        side = "onnx" if mode == "onnx" else "native"
        worker["vectors"] = {
            kind: [r[side + "_vector"] for r in report["vectors"] if r["kind"] == kind]
            for kind in kinds
        }
        (tmp_path / f"{mode}.json").write_text(json.dumps(worker))
    return tmp_path, report


def test_exact_graph_parity_recomputed_offline(parity_workers):
    workers, saved = parity_workers
    result = p.assemble(ROOT, workers, ROOT / "benchmark/diagnostics/20261006-regression-plan.json")
    assert result["status"] == saved["status"] == "PASS"
    assert result["summary"] == saved["summary"]
    assert result["vectors"] == saved["vectors"]
    assert result["rankings"] == saved["rankings"]
    assert result["test_code_sha256"] == saved["test_code_sha256"]
    assert len(result["vectors"]) == 26
    assert all(r["spearman_deterministic_order"] == 1 for r in result["rankings"])


@pytest.mark.parametrize(
    "field",
    [
        "plan_sha256",
        "test_code_sha256",
        "export_sha256",
        "model_revision",
        "encoder_commit",
        "encoder_source_sha256",
        "source_sha256",
    ],
)
def test_parity_wrong_identity_rejected(parity_workers, field):
    workers, _ = parity_workers
    path = workers / "onnx.json"
    worker = p.read(path)
    worker[field] = {} if field.endswith("source_sha256") else "changed"
    path.write_text(json.dumps(worker))
    with pytest.raises(ValueError):
        p.assemble(ROOT, workers, ROOT / "benchmark/diagnostics/20261006-regression-plan.json")


def test_diagnostic_canonical_scores_reproduce_stored_scores():
    report = p.read(ROOT / "benchmark/results/v5-regression-diagnostics-20261006.json")
    reconstruction = p.read(ROOT / "benchmark/results/v5-regression-reconstruction-20261006.json")
    assert report["test_code_sha256"] == p.sha(ROOT / "scripts/isolated_adapter_diagnostics.py")
    assert report["plan_sha256"] == p.sha(
        ROOT / "benchmark/diagnostics/20261006-regression-plan.json"
    )
    assert report["canonical_forward_max_difference"] == {"query": 0.0, "passage": 0.0}
    matches = set()
    for c in report["cases"]:
        stored = reconstruction["cases"][c["case_id"]]["v5"]
        for score in c["scores"]:
            if score["query_variant"] != "canonical" or score["document_variant"] != "canonical":
                continue
            for hit in stored["top10"] + stored["relevant"] + [stored["strongest_judged_zero"]]:
                if (
                    hit["event_id"] == score["event_id"]
                    and hit["chunk"]["content_hash"] == score["text_id"]
                ):
                    assert abs(hit["score"] - score["score"]) < 1e-6
                    matches.add((c["case_id"], score["event_id"], score["text_id"]))
    assert len(matches) == 13
