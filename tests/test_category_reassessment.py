"""Offline evidence expansion; historical bytes and evaluator policy are immutable."""

import ast
import copy
import socket
from pathlib import Path

import pytest

from uranus_research_service import category_reassessment as cr
from uranus_research_service.controlled_evaluation import POLICY, compare, metrics, summarize
from uranus_research_service.machine_judge import read, sha


@pytest.fixture(scope="module")
def loaded():
    return cr.load()


@pytest.fixture(scope="module")
def reports(loaded):
    return cr.analyze(loaded)


def test_pins_and_actual_complete_source(loaded):
    pins, labels, mapping, runs, baseline = loaded
    assert len(labels) == len(mapping) == 77
    assert {
        status: sum(j["status"] == status for j in labels)
        for status in ("machine_agreed", "machine_adjudicated")
    } == {"machine_agreed": 70, "machine_adjudicated": 7}
    assert all(type(j["grade"]) is int and 0 <= j["grade"] <= 3 for j in labels)
    assert {p["case_id"] for p in mapping.values()} == {
        "historical-q29",
        "wheelchair-da",
        "dance-en",
        "concerts-en",
    }
    assert compare(*runs) == baseline
    assert baseline["v3"] == summarize(runs[0]["cases"])
    assert baseline["policy"] == POLICY
    assert baseline["v3"]["included"] == 105
    for path, expected in pins["files"].items():
        assert sha(Path(path).read_bytes()) == expected


@pytest.mark.parametrize(
    "target",
    [
        cr.PIN,
        cr.SOURCE,
        Path("benchmark/results/v3-20261006_8cpu_001.json"),
        Path("benchmark/annotation/machine-proposals-v1.jsonl"),
        Path("benchmark/results/v3-v5-comparison-20261006_8cpu_001.json"),
    ],
)
def test_hash_mismatch_fail_closed(monkeypatch, target):
    original = Path.read_bytes

    def changed(path):
        return original(path) + (b" " if path == target else b"")

    monkeypatch.setattr(Path, "read_bytes", changed)
    with pytest.raises(ValueError, match="changed"):
        cr.verify_inputs()


def test_additive_merge_preserves_ranking_eligibility_old_grades(loaded):
    _, labels, mapping, original, _ = loaded
    frozen = copy.deepcopy(original)
    expanded, conflicts = cr.merge_runs(original, labels, mapping)
    assert original == frozen
    additions = 0
    for before, after in zip(original, expanded, strict=True):
        for old, new in zip(before["cases"], after["cases"], strict=True):
            for key in old.keys() - {"grades", "best_relevant_rank", "judged_scores"}:
                assert old[key] == new[key]
            assert set(new["grades"]) <= set(old["eligible_ids"])
            assert all(new["grades"][eid] == g for eid, g in old["grades"].items())
            new_pairs = set(new["grades"]) - set(old["grades"])
            allowed = {p["event_id"] for p in mapping.values() if p["case_id"] == old["case_id"]}
            assert new_pairs <= allowed
            additions += len(new_pairs)
            # A missing grade stays absent, including candidates outside the review pool.
            assert set(old["eligible_ids"]) - set(old["grades"]) - allowed == set(
                old["eligible_ids"]
            ) - set(new["grades"])
    assert additions == 2 * 62
    assert len(conflicts) == 5
    for conflict in conflicts:
        c = next(c for c in expanded[0]["cases"] if c["case_id"] == conflict["case_id"])
        assert c["grades"][conflict["event_id"]] == conflict["old_grade"]


def test_sensitivity_is_separate(loaded):
    _, labels, mapping, original, _ = loaded
    expanded, conflicts = cr.merge_runs(original, labels, mapping)
    overridden, same_conflicts = cr.merge_runs(original, labels, mapping, override=True)
    assert conflicts == same_conflicts
    for conflict in conflicts:
        cid, eid = conflict["case_id"], conflict["event_id"]
        primary = next(c for c in expanded[0]["cases"] if c["case_id"] == cid)
        sensitive = next(c for c in overridden[0]["cases"] if c["case_id"] == cid)
        assert primary["grades"][eid] == conflict["old_grade"]
        assert sensitive["grades"][eid] == conflict["machine_grade"]


def test_unknown_or_ineligible_event_rejected(loaded):
    _, labels, mapping, original, _ = loaded
    bad = copy.deepcopy(mapping)
    bad[labels[0]["annotation_id"]]["event_id"] = "00000000-0000-0000-0000-000000000000"
    with pytest.raises(ValueError, match="eligibility"):
        cr.merge_runs(original, labels, bad)


def test_category_counts_and_coverage(reports, loaded):
    cats = {c["category"]: c for c in reports["category-reassessment.json"]["categories"]}
    assert set(cats) == set(cr.CATEGORIES)
    expected = {
        "atmosphere": (5, 1, 16),
        "outdoor": (1, 0, 0),
        "theatre": (6, 0, 0),
        "venue": (6, 0, 0),
        "accessibility": (7, 1, 16),
    }
    for cat, (total, touched, pairs) in expected.items():
        cov = cats[cat]["coverage"]
        assert (
            cov["cases_total"],
            cov["cases_touched_by_new_judgments"],
            cov["new_query_event_pairs"],
        ) == (total, touched, pairs)
        for i, m in enumerate(("v3", "v5")):
            historical = [
                c for c in loaded[3][i]["cases"] if c["category"] == cat and not c["excluded"]
            ]
            judged = sum(
                sum(h["event_id"] in c["grades"] for h in c["ranking"][:10]) for c in historical
            )
            assert cov[f"{m}_top10_judged_before"] == pytest.approx(judged / (10 * total))
    for cat in ("outdoor", "theatre", "venue"):
        c = cats[cat]
        assert c["historical"] == c["machine_expanded"] == c["override_sensitivity"]
        assert c["assessment"] == "unchanged_no_new_coverage"
    assert (
        cats["atmosphere"]["assessment"]
        == "regression_not_supported_under_expanded_machine_judgments"
    )
    assert cats["accessibility"]["assessment"] == "insufficient_evidence"
    assert cats["accessibility"]["role"] == "diagnostic watch category"


def test_all_target_cases_and_metrics_use_existing_evaluator(reports, loaded):
    cases = reports["case-level-deltas.json"]["cases"]
    assert len(cases) == 28  # 25 evaluated, 3 exclusions retained visibly.
    assert len({c["case_id"] for c in cases}) == 28
    target = {
        "dance-en",
        "wheelchair-da",
        "historical-q11",
        "puppet-de",
        "stage-en",
        "museumsberg-de",
        "museumsberg-da",
        "museumsberg-en",
        "kuehlhaus-de",
    }
    assert target <= {c["case_id"] for c in cases}
    expanded, _ = cr.merge_runs(loaded[3], loaded[1], loaded[2])
    for c in cases:
        for i, m in enumerate(("v3", "v5")):
            if not c["historically_evaluated"]:
                assert c["models"][m]["machine-expanded"]["metrics"] is None
                continue
            actual = next(row for row in expanded[i]["cases"] if row["case_id"] == c["case_id"])
            assert c["models"][m]["machine-expanded"]["metrics"] == metrics(
                actual["grades"], [h["event_id"] for h in actual["ranking"]]
            )
    dance = next(c for c in cases if c["case_id"] == "dance-en")
    assert dance["changes_category_direction"] is True
    assert dance["models"]["v5"]["machine-expanded"]["metrics"]["Recall@10"] == 10 / 17


def test_no_io_dependencies_determinism_and_published_reports(monkeypatch, loaded, reports):
    def forbidden(*args, **kwargs):
        pytest.fail("network or external provider access in offline evaluation")

    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    import httpx

    monkeypatch.setattr(httpx.Client, "request", forbidden)
    monkeypatch.setattr(httpx.AsyncClient, "request", forbidden)
    from uranus_research_service.machine_judge import OpenAIJudge

    monkeypatch.setattr(OpenAIJudge, "request", forbidden)
    assert cr.analyze(cr.load()) == reports
    for name, report in reports.items():
        assert report["historical_verdict"] == cr.VERDICT
        assert "Exploratory" in report["caveat"]
        if "global_gate_decision" in report:
            assert report["global_gate_decision"] == "not_issued"
        if cr.DEST.exists():
            assert read(cr.DEST / name) == report
    tree = ast.parse(Path(cr.__file__).read_text())
    imported = [node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
    assert not any(
        any(s in (module or "") for s in ("encoder", "qdrant", "runtime", "database"))
        for module in imported
    )
    if cr.DEST.exists():
        index = read(cr.DEST / "artifact-sha256.json")
        assert index["code_sha256"] == sha(Path(cr.__file__).read_bytes())
        for name, expected in index["files"].items():
            assert sha((cr.DEST / name).read_bytes()) == expected
    assert cr.verify_inputs() == loaded[0]


def test_never_overwrite(tmp_path):
    with pytest.raises(ValueError, match="new_destination"):
        cr.generate(tmp_path)
