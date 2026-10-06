"""Exploratory offline deblinding; only callable after complete machine consensus sealing."""

import copy
from collections import Counter

from uranus_research_service.machine_consensus import CAVEAT, verify_seal
from uranus_research_service.machine_judge import atomic_new, digest, read, read_lines, require, sha


def expanded_cases(original, consensus, mapping):
    cases = copy.deepcopy(original)
    by_case = {c["case_id"]: c for c in cases}
    conflicts = []
    for row in consensus:
        pair = mapping[row["annotation_id"]]
        c, eid = by_case[pair["case_id"]], pair["event_id"]
        require(eid in c["eligible_ids"], "consensus_eligibility")
        if eid in c["grades"]:
            if c["grades"][eid] != row["grade"]:
                conflicts.append(
                    {
                        **pair,
                        "old_grade": c["grades"][eid],
                        "machine_grade": row["grade"],
                        "consensus_type": row["consensus_type"],
                        "confidence": row["confidence"],
                        "resolution": "historical-retained-not-adjudicated",
                    }
                )
        else:
            c["grades"][eid] = row["grade"]
    for c in cases:
        c["best_relevant_rank"] = next(
            (i + 1 for i, h in enumerate(c["ranking"]) if c["grades"].get(h["event_id"], 0) > 0),
            None,
        )
        c["judged_scores"] = [
            {"event_id": h["event_id"], "score": h["score"], "grade": c["grades"][h["event_id"]]}
            for h in c["ranking"]
            if h["event_id"] in c["grades"]
        ]
    return cases, conflicts


def historical_agreement(consensus, mapping, cases):
    by_case = {c["case_id"]: c for c in cases}
    rows = []
    for row in consensus:
        m = mapping[row["annotation_id"]]
        c = by_case[m["case_id"]]
        if m["event_id"] in c["grades"]:
            gap = abs(c["grades"][m["event_id"]] - row["grade"])
            rows.append({"language": c["language"], "category": c["category"], "gap": gap})

    def summary(values):
        return {
            "count": len(values),
            "exact": sum(r["gap"] == 0 for r in values),
            "within_one": sum(r["gap"] <= 1 for r in values),
            "material": sum(r["gap"] >= 2 for r in values),
        }

    return {
        "overall": summary(rows),
        "by": {
            f: {v: summary([r for r in rows if r[f] == v]) for v in sorted({r[f] for r in rows})}
            for f in ("language", "category")
        },
        "caveat": "Historical draft labels are imperfect policy references, "
        "not human-certified truth.",
    }


def gate_sensitive(pair, cases, comparison):
    """Post-judgment 0/3 endpoint screening, not new labels or optimization."""
    from uranus_research_service.controlled_evaluation import metrics

    a, b = (side[pair["case_id"]] for side in cases)
    if a["excluded"]:
        return False
    delta, hits = [], []
    for grade in (0, 3):
        labels = {**a["grades"], pair["event_id"]: grade}
        if not any(labels.values()):
            return True  # A positive denominator itself needs review.
        values = [metrics(labels, [h["event_id"] for h in c["ranking"]]) for c in (a, b)]
        delta.append({k: values[1][k] - values[0][k] for k in values[0]})
        hits.append(bool(values[0]["HitRate@10"] and not values[1]["HitRate@10"]))
    if hits[0] != hits[1]:
        return True
    old = {
        k: comparison["v5"]["per_case"][a["case_id"]][k] - v
        for k, v in comparison["v3"]["per_case"][a["case_id"]].items()
    }
    cohort = [r for r in cases[0].values() if r["excluded"] is None]
    for gate in comparison["gates"]:
        name = gate["gate"]
        if name in ("Recall@10", "MRR@10", "nDCG@10"):
            n, metric, tolerance = len(cohort), name, 0.02 if name == "Recall@10" else 0.03
        elif name in (f"language:{a['language']}:Recall@10", f"category:{a['category']}:Recall@10"):
            field, value, metric = name.split(":")
            n, tolerance = sum(r[field] == value for r in cohort), 0.05
        else:
            continue
        passes = [
            gate["delta"] + (d[metric] - old[metric]) / n >= -tolerance - 1e-12 for d in delta
        ]
        if passes[0] != passes[1]:
            return True
    return False


def evaluate(root, work, sealed, destination):
    # This MUST precede imports/reads of operator mapping or historical retrieval files.
    seal = verify_seal(work, sealed)
    require(not destination.exists(), "new_analysis_directory_required")
    from uranus_research_service.blind_expansion import coverage, load
    from uranus_research_service.controlled_evaluation import compare, summarize
    from uranus_research_service.machine_prepare import verify_historical

    pins = verify_historical(root)
    _, _, _, _, original_runs = load(root)
    plan = read(work / "blind/plan.json")
    require(plan["historical_inputs_sha256"] == digest(pins), "historical_binding")
    bundle = read(root / "benchmark/annotation/phase2d/blind-mapping.json")
    require(digest(bundle) == plan["package_sha256"], "mapping_binding")
    mapping = {m["annotation_id"]: m for m in bundle["mapping"]}
    historical = read(root / "benchmark/results/v3-v5-comparison-20261006_8cpu_001.json")
    modes, all_conflicts, agreements, all_runs = {}, {}, {}, {}
    for mode in ("strict", "majority"):
        labels = read_lines(sealed / f"{mode}.jsonl")
        runs = []
        for source in original_runs:
            run = copy.deepcopy(source)
            run["cases"], conflicts = expanded_cases(source["cases"], labels, mapping)
            run["judgment_source_hash"] = digest(
                {
                    "historical": source["judgment_source_hash"],
                    "expansion": labels,
                    "seal": digest(seal),
                }
            )
            require(
                [c["ranking"] for c in run["cases"]] == [c["ranking"] for c in source["cases"]],
                "stored_rankings_changed",
            )
            runs.append(run)
        result = compare(*runs)  # Unchanged metric implementation and gate thresholds.
        result["caveat"] = CAVEAT
        result["evaluation_kind"] = f"exploratory-machine-consensus-{mode}"
        result["verdict"] = (
            "passes under exploratory machine-consensus judgments"
            if all(g["pass"] for g in result["gates"])
            else "fails under exploratory machine-consensus judgments"
        )
        result["machine_seal_sha256"] = digest(seal)
        result["subsets"] = {}
        for subset in ("diagnostic", "balanced", "full-selected"):
            selected = {
                c["case_id"]
                for c in bundle["selection"]["cases"]
                if subset == "full-selected" or c["subset"] == subset
            }
            result["subsets"][subset] = {
                name: summarize([c for c in run["cases"] if c["case_id"] in selected])
                for name, run in zip(("v3", "v5"), runs, strict=True)
            }
        modes[mode], all_conflicts[mode], all_runs[mode] = result, conflicts, runs
        agreements[mode] = historical_agreement(labels, mapping, original_runs[0]["cases"])
    coverages = {"historical": coverage(original_runs, bundle)}
    for mode, runs in all_runs.items():
        coverages[mode] = coverage(
            original_runs, bundle, {c["case_id"]: c["grades"] for c in runs[0]["cases"]}
        )
    issues = {r["annotation_id"]: r for r in read_lines(sealed / "disagreements.jsonl")}
    current = [{c["case_id"]: c for c in run["cases"]} for run in all_runs["majority"]]
    cases = {c["case_id"]: c for c in original_runs[0]["cases"]}
    triage = []
    for aid, m in mapping.items():
        row, c = issues[aid], cases[m["case_id"]]
        sensitive = gate_sensitive(m, current, modes["majority"])
        total_loss = m["case_id"] in bundle["sampling"]["total_loss"]
        failed_category = c["category"] in bundle["sampling"]["failed_categories"]
        priority = (
            1
            if row["classification"] == "material_disagreement"
            else 2
            if row["classification"] == "unresolved"
            else 3
            if sensitive
            else 4
            if total_loss
            else 5
            if failed_category
            else 6
            if row["confidence"]["min"] < 0.8
            else 7
        )
        selected = (
            priority <= 3
            or ((total_loss or failed_category) and row["classification"] != "strong_consensus")
            or row["confidence"]["min"] < 0.8
        )
        triage.append(
            {
                **m,
                "priority": priority,
                "review_selected": selected,
                "gate_sensitive_endpoint_screen": sensitive,
                "classification": row["classification"],
            }
        )
    triage.sort(key=lambda r: (r["priority"], r["annotation_id"]))
    packet = read_lines(work / "blind/blind-candidates.jsonl")
    selected_ids = {r["annotation_id"] for r in triage if r["review_selected"]}
    blind_triage = sorted(
        [p for p in packet if p["annotation_id"] in selected_ids],
        key=lambda p: digest(["phase2dm-triage-blind-v1", p["annotation_id"]]),
    )
    totals = []
    for cid in bundle["sampling"]["total_loss"]:
        positive = sorted(e for e, g in cases[cid]["grades"].items() if g > 0)
        top10 = {
            h["event_id"]
            for h in next(c for c in original_runs[1]["cases"] if c["case_id"] == cid)["ranking"][
                :10
            ]
        }
        row = {
            "case_id": cid,
            "historical_positives": positive,
            "historical_v5_Recall@10": historical["v5"]["per_case"][cid]["Recall@10"],
            "unresolved_candidates": sum(
                issues[aid]["classification"] == "unresolved"
                for aid, m in mapping.items()
                if m["case_id"] == cid
            ),
        }
        for mode in modes:
            labels = read_lines(sealed / f"{mode}.jsonl")
            row[mode] = {
                "v5_Recall@10": modes[mode]["v5"]["per_case"][cid]["Recall@10"],
                "machine_positive_top10": [
                    mapping[r["annotation_id"]]["event_id"]
                    for r in labels
                    if mapping[r["annotation_id"]]["case_id"] == cid
                    and mapping[r["annotation_id"]]["event_id"] in top10
                    and r["grade"] > 0
                ],
                "known_positive_loss_remains": cid in modes[mode]["lost_all_relevant"],
            }
        totals.append(row)
    destination.mkdir(parents=True)
    for mode, result in modes.items():
        atomic_new(destination / f"v3-v5-{mode}-comparison.json", result)
    atomic_new(destination / "historical-conflicts.json", all_conflicts)
    atomic_new(
        destination / "historical-vs-machine.json",
        {
            "caveat": CAVEAT,
            "agreement_with_historical_draft": agreements,
            "historical_gates": historical["gates"],
        },
    )
    atomic_new(destination / "coverage.json", {"caveat": CAVEAT, **coverages})
    atomic_new(destination / "total-loss-reassessment.json", {"caveat": CAVEAT, "cases": totals})
    atomic_new(
        destination / "category-reassessment.json",
        {
            "caveat": CAVEAT,
            "categories": {
                cat: {
                    mode: {name: report[name]["by"]["category"][cat] for name in ("v3", "v5")}
                    for mode, report in {"historical": historical, **modes}.items()
                }
                for cat in bundle["sampling"]["failed_categories"]
            },
        },
    )
    atomic_new(destination / "human-triage.jsonl", triage, jsonl=True)
    atomic_new(destination / "blind-triage-candidates.jsonl", blind_triage, jsonl=True)
    atomic_new(
        destination / "triage-package.json",
        {
            "schema_version": "phase2d-blind-package-v1",
            "package_sha256": plan["package_sha256"],
            "packet_sha256": digest(blind_triage),
            "count": len(blind_triage),
        },
    )
    atomic_new(
        destination / "artifact-sha256.json",
        {
            "caveat": CAVEAT,
            "machine_seal_sha256": digest(seal),
            "files": {p.name: sha(p.read_bytes()) for p in sorted(destination.iterdir())},
            "triage_count": len(blind_triage),
            "triage_by_priority": dict(
                Counter(r["priority"] for r in triage if r["review_selected"])
            ),
        },
    )
    return {"status": "exploratory-machine-only", "triage_count": len(blind_triage)}
