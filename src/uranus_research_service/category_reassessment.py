"""Offline category follow-up; reuse the frozen evaluator and additive label merge."""

import argparse
import copy
from collections import Counter
from pathlib import Path

from uranus_research_service.controlled_evaluation import compare, require
from uranus_research_service.lost_all_review import checked
from uranus_research_service.machine_adjudication_analysis import combine
from uranus_research_service.machine_analysis import expanded_cases
from uranus_research_service.machine_blind_adjudication import BASE
from uranus_research_service.machine_judge import atomic_new, digest, read, sha

CATEGORIES = ("atmosphere", "outdoor", "theatre", "venue", "accessibility")
BUILD = "20261006_8cpu_001"
PIN = Path("benchmark/contracts/category-reassessment-20261007-input-sha256.json")
PIN_SHA = "f2b8fbdfef91accbc1330ce5c60ce88f9cf101ea39b5b824672be86a12a4c1e5"
SOURCE = BASE / "adjudication/machine-consensus-plus-adjudication-v1.json"
SOURCE_SHA = "44bf662e9bc8dc4a80ce431a45a30d5a954ca2c2addec2b985d08d4e29f82722"
DEST = Path("benchmark/results/category-reassessment-20261007")
CAVEAT = (
    "Exploratory machine-assisted follow-up evaluation of a targeted, nonrandom four-query pool; "
    "not Human Ground Truth, not a historical correction or global gate/production approval."
)
VERDICT = "v5 provisionally fails one or more gates"
MODES = ("historical", "machine-expanded", "machine-override-exploratory")


def verify_inputs():
    require(sha(PIN.read_bytes()) == PIN_SHA, "input_manifest_changed")
    pins = read(PIN)
    for name, expected in pins["files"].items():
        require(sha(Path(name).read_bytes()) == expected, f"frozen_input_changed:{name}")
    require(sha(SOURCE.read_bytes()) == SOURCE_SHA, "machine_source_changed")
    return pins


def load():
    pins = verify_inputs()
    source = read(SOURCE)
    require(source == combine(BASE / "adjudication/run"), "adjudication_binding")
    require(source["counts"] == {"machine_agreed": 70, "machine_adjudicated": 7}, "machine_counts")
    rows = source["judgments"]
    require(len(rows) == len({r["annotation_id"] for r in rows}) == 77, "machine_ids")
    require(all(type(r["grade"]) is int and 0 <= r["grade"] <= 3 for r in rows), "machine_grade")
    _, packet, runs = checked(Path("."), BASE.parent)
    mapping = {
        p["annotation_id"]: {"case_id": p["query_id"], "event_id": p["event_id"]} for p in packet
    }
    require(set(mapping) == {r["annotation_id"] for r in rows}, "mapping_ids")
    # Existing merge contract expects provenance/confidence. These runs do not provide
    # calibrated confidence; None explicitly records that fact, not a fabricated value.
    labels = [{**r, "consensus_type": r["status"], "confidence": None} for r in rows]
    historical = read(Path(f"benchmark/results/v3-v5-comparison-{BUILD}.json"))
    require(compare(*runs) == historical, "historical_reproduction_mismatch")
    require(historical["verdict"] == VERDICT, "historical_verdict")
    return pins, labels, mapping, runs, historical


def merge_runs(original_runs, labels, mapping, *, override=False):
    runs, all_conflicts = [], []
    for source in original_runs:
        run = copy.deepcopy(source)
        _, conflicts = expanded_cases(source["cases"], labels, mapping)
        if override:
            by_id = {c["case_id"]: c for c in run["cases"]}
            for row in labels:
                pair = mapping[row["annotation_id"]]
                by_id[pair["case_id"]]["grades"].pop(pair["event_id"], None)
        run["cases"], _ = expanded_cases(run["cases"], labels, mapping)
        run["judgment_source_hash"] = digest(
            {
                "historical": source["judgment_source_hash"],
                "machine_source": SOURCE_SHA,
                "override": override,
            }
        )
        for old, new in zip(source["cases"], run["cases"], strict=True):
            for key in old.keys() - {"grades", "best_relevant_rank", "judged_scores"}:
                require(old[key] == new[key], f"immutable_case_field:{key}")
            if not override:
                require(
                    all(new["grades"][eid] == grade for eid, grade in old["grades"].items()),
                    "historical_grade_changed",
                )
        runs.append(run)
        all_conflicts.append(conflicts)
    require(all_conflicts[0] == all_conflicts[1], "conflicts_differ_between_models")
    return runs, all_conflicts[0]


def category_gate(report, category):
    return next(g for g in report["gates"] if g["gate"] == f"category:{category}:Recall@10")


def classification(category, historical, expanded, coverage):
    """Predeclared coverage-aware interpretation; not a new benchmark gate."""
    if not coverage["new_query_event_pairs"]:
        return "unchanged_no_new_coverage"
    if category == "accessibility":
        return "insufficient_evidence"  # Watch category, never a failed historical category.
    if expanded["delta"] >= 0:
        return "regression_not_supported_under_expanded_machine_judgments"
    if expanded["delta"] > historical["delta"] + 1e-12:
        return "regression_weakened"
    adequate = (
        coverage["fraction_cases_touched"] >= 0.8
        and min(coverage[f"{m}_top10_judged_after"] for m in ("v3", "v5")) >= 0.9
    )
    return "regression_still_supported" if adequate else "insufficient_evidence"


def focused(report, mode):
    """Do not publish a fresh global gate verdict for this targeted follow-up."""
    return {
        "mode": mode,
        "caveat": CAVEAT,
        "historical_verdict": VERDICT,
        "evaluation_label": "exploratory sensitivity analysis" if "override" in mode else CAVEAT,
        "evaluator_version": report["evaluator_version"],
        "policy": report["policy"],
        "original_included_case_count": report["v3"]["included"],
        "category_gates": [category_gate(report, cat) for cat in CATEGORIES],
        "metrics": {
            m: {cat: report[m]["by"]["category"][cat] for cat in CATEGORIES} for m in ("v3", "v5")
        },
        "global_gate_decision": "not_issued",
    }


def analyze(loaded):
    pins, labels, mapping, original, historical = loaded
    expanded, conflicts = merge_runs(original, labels, mapping)
    overridden, override_conflicts = merge_runs(original, labels, mapping, override=True)
    require(conflicts == override_conflicts, "sensitivity_conflict_set")
    runs = dict(zip(MODES, (original, expanded, overridden), strict=True))
    reports = {
        "historical": historical,
        "machine-expanded": compare(*expanded),
        "machine-override-exploratory": compare(*overridden),
    }
    by_mode = {
        mode: [{c["case_id"]: c for c in run["cases"]} for run in pair]
        for mode, pair in runs.items()
    }
    machine = {
        (mapping[j["annotation_id"]]["case_id"], mapping[j["annotation_id"]]["event_id"]): j
        for j in labels
    }
    cases, categories = [], []
    for old in original[0]["cases"]:
        cid, cat = old["case_id"], old["category"]
        if cat not in CATEGORIES:
            continue
        additions = [
            {"event_id": eid, "grade": j["grade"], "provenance": j["status"]}
            for (query, eid), j in sorted(machine.items())
            if query == cid and eid not in old["grades"]
        ]
        row = {
            "case_id": cid,
            "language": old["language"],
            "category": cat,
            "historically_evaluated": old["excluded"] is None,
            "excluded_reason": old["excluded"],
            "new_judgments": additions,
            "new_positive_ids": [j["event_id"] for j in additions if j["grade"] > 0],
            "new_zero_ids": [j["event_id"] for j in additions if j["grade"] == 0],
            "historical_conflicts": [c for c in conflicts if c["case_id"] == cid],
            "models": {},
        }
        for i, m in enumerate(("v3", "v5")):
            values = {}
            for mode in MODES:
                c = by_mode[mode][i][cid]
                ranks = [h["event_id"] for h in c["ranking"]]
                values[mode] = {
                    "metrics": reports[mode][m]["per_case"].get(cid),
                    "best_relevant_rank": c["best_relevant_rank"],
                    "coverage": {
                        str(k): sum(e in c["grades"] for e in ranks[:k]) / len(ranks[:k])
                        for k in (10, 20)
                    },
                    "positive_top10_ids": [e for e in ranks[:10] if c["grades"].get(e, 0) > 0],
                    "new_positive_top10_ids": [
                        e for e in ranks[:10] if e in row["new_positive_ids"]
                    ],
                }
            row["models"][m] = values
        row["recall_at_10_deltas"] = {
            mode: (
                reports[mode]["v5"]["per_case"][cid]["Recall@10"]
                - reports[mode]["v3"]["per_case"][cid]["Recall@10"]
            )
            if old["excluded"] is None
            else None
            for mode in MODES
        }
        cases.append(row)
    for cat in CATEGORIES:
        selected = [c for c in cases if c["category"] == cat and c["historically_evaluated"]]
        touched = [c for c in selected if c["new_judgments"]]
        cov = {
            "cases_total": len(selected),
            "cases_touched_by_new_judgments": len(touched),
            "new_query_event_pairs": sum(len(c["new_judgments"]) for c in selected),
            "fraction_cases_touched": len(touched) / len(selected),
            "all_query_cases_including_excluded": sum(c["category"] == cat for c in cases),
        }
        for m in ("v3", "v5"):
            for mode, suffix in (("historical", "before"), ("machine-expanded", "after")):
                cov[f"{m}_top10_judged_{suffix}"] = sum(
                    c["models"][m][mode]["coverage"]["10"] for c in selected
                ) / len(selected)
                cov[f"{m}_top20_judged_{suffix}"] = sum(
                    c["models"][m][mode]["coverage"]["20"] for c in selected
                ) / len(selected)
        h, e = (category_gate(reports[mode], cat) for mode in MODES[:2])
        assessment = classification(cat, h, e, cov)
        categories.append(
            {
                "category": cat,
                "role": "diagnostic watch category"
                if cat == "accessibility"
                else "historically failed category",
                "historical": h,
                "machine_expanded": e,
                "override_sensitivity": category_gate(reports[MODES[2]], cat),
                "coverage": cov,
                "assessment": assessment,
                "confidence": "exact arithmetic; low confidence in category generalization",
                "limitations": [
                    "targeted nonrandom lost-all pool; machine labels, not human judgments",
                    (
                        "unchanged due to no new applicable judgments; "
                        "insufficient new coverage to materially reassess this category"
                    )
                    if not touched
                    else (
                        "only one targeted query newly covered; "
                        "other category cases retain historical draft coverage"
                    ),
                ],
            }
        )
        for row in selected:
            other_delta = sum(
                c["recall_at_10_deltas"]["machine-expanded"]
                if c is not row
                else c["recall_at_10_deltas"]["historical"]
                for c in selected
            ) / len(selected)
            row["changes_category_direction"] = (other_delta < 0) != (e["delta"] < 0)
            row["category_delta_contribution_change"] = (
                row["recall_at_10_deltas"]["machine-expanded"]
                - row["recall_at_10_deltas"]["historical"]
            ) / len(selected)
    metadata = {
        "caveat": CAVEAT,
        "historical_verdict": VERDICT,
        "baseline_main": pins["baseline_main"],
        "input_manifest_sha256": PIN_SHA,
        "machine_source_sha256": SOURCE_SHA,
    }
    return {
        "historical-baseline.json": {
            **metadata,
            **focused(historical, "historical"),
            "historical_metrics_reproduced_exactly": True,
        },
        "machine-expanded-comparison.json": {**metadata, **focused(reports[MODES[1]], MODES[1])},
        "machine-override-sensitivity.json": {**metadata, **focused(reports[MODES[2]], MODES[2])},
        "category-reassessment.json": {**metadata, "categories": categories},
        "case-level-deltas.json": {**metadata, "cases": cases},
        "coverage-delta.json": {
            **metadata,
            "denominator": (
                "historically evaluated cases only; macro judged fraction; exclusions fixed"
            ),
            "categories": {c["category"]: c["coverage"] for c in categories},
        },
        "historical-label-conflicts.json": {
            **metadata,
            "primary_policy": "retain every historical grade; only unjudged pairs added",
            "sensitivity_policy": "explicit machine override on the 77 reviewed pairs only",
            "machine_pairs": len(labels),
            "new_pairs_all_four_queries": sum(
                pair[1] not in by_mode["historical"][0][pair[0]]["grades"] for pair in machine
            ),
            "conflicts": conflicts,
            "conflicts_by_case": dict(Counter(c["case_id"] for c in conflicts)),
        },
    }


def generate(output):
    output = Path(output)
    require(not output.exists(), "new_destination_required")
    reports = analyze(load())
    for name, report in reports.items():
        atomic_new(output / name, report)
    atomic_new(
        output / "artifact-sha256.json",
        {
            "caveat": CAVEAT,
            "input_manifest_sha256": PIN_SHA,
            "code_sha256": sha(Path(__file__).read_bytes()),
            "files": {p.name: sha(p.read_bytes()) for p in sorted(output.iterdir())},
        },
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEST)
    args = parser.parse_args()
    generate(args.output)


if __name__ == "__main__":
    main()
