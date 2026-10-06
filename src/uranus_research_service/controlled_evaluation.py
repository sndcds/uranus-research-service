"""Frozen draft evaluation only; never imported by the service request runtime."""

import hashlib
import math
from collections import Counter
from pathlib import Path

from uranus_research_service.ground_truth import GroundTruthCase
from uranus_research_service.ground_truth_snapshot import load_snapshot
from uranus_research_service.json_codec import decode
from uranus_research_service.semantic_manifest import digest

EVALUATOR = "controlled-draft-retrieval-v1"
CAVEAT = (
    "This benchmark uses a frozen draft relevance dataset containing machine proposals plus "
    "manually calibrated scoring policy. It is suitable for provisional comparative evaluation, "
    "not final production approval."
)
NO_HIT = {f"{q}-{lang}" for q in ("koreanopera", "harpsichord") for lang in ("de", "da", "en")}
POLICY = {
    "k": [5, 10],
    "binary_relevant": "grade>=1",
    "aggregation": "max-eligible-chunk-cosine;ties=event-uuid-ascending",
    "unjudged": "unknown;zero-gain-for-provisional-pooled-ranking-only;excluded-from-thresholds",
    "threshold": "none-for-ranking;exploratory-unsplit-curves-only",
    "gates": {"Recall@10": 0.02, "MRR@10": 0.03, "nDCG@10": 0.03, "subgroup_Recall@10": 0.05},
}


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def lines(path):
    return [decode(line) for line in Path(path).read_bytes().splitlines()]


def inputs(root):
    pins = decode((root / "benchmark/contracts/phase2b2c-input-sha256.json").read_bytes())
    for name, sha in pins.items():
        require(
            hashlib.sha256((root / name).read_bytes()).hexdigest() == sha, "frozen_input_changed"
        )
    base = root / "benchmark/snapshots/public-events-20261005"
    manifest, events = load_snapshot(base / "events.jsonl", base / "manifest.json")
    cases = [
        GroundTruthCase.model_validate(c) for c in lines(root / "benchmark/ground-truth-v1.jsonl")
    ]
    proposals = lines(root / "benchmark/annotation/machine-proposals-v1.jsonl")
    labels = {}
    for p in proposals:
        key = p["case_id"], p["event_id"]
        require(key not in labels, "duplicate_proposal")
        require(type(p["proposed_relevance"]) is int and 0 <= p["proposed_relevance"] <= 3, "grade")
        labels[key] = p["proposed_relevance"]
    pool = {(c.id, str(j.event_id)) for c in cases for j in c.judgments}
    require(set(labels) == pool, "judgment_pool_mismatch")
    records = []
    for c in cases:
        require(c.source_snapshot_hash == manifest.source_snapshot_hash, "case_snapshot_mismatch")
        require(c.reference_time == manifest.reference_time, "case_reference_time_mismatch")
        eligible = sorted(str(eid) for eid, r in events.items() if c.eligibility.accepts(r.event))
        eligible_occurrences = sorted(
            str(o.id)
            for row in events.values()
            for o in row.event.occurrences
            if c.eligibility.accepts(row.event.model_copy(update={"occurrences": [o]}))
        )
        grades = {str(j.event_id): labels[c.id, str(j.event_id)] for j in c.judgments}
        require(set(grades) <= set(eligible), "judgment_eligibility_mismatch")
        reason = (
            "unresolved_no_hit"
            if c.id in NO_HIT
            else ("no_judged_positive_not_confirmed_negative" if not any(grades.values()) else None)
        )
        records.append(
            {
                "case_id": c.id,
                "language": c.language,
                "category": c.category,
                "query": c.query,
                "query_group": c.query_group,
                "eligible_ids": eligible,
                "eligible_occurrence_ids": eligible_occurrences,
                "eligibility_hash": digest(eligible),
                "grades": grades,
                "excluded": reason,
            }
        )
    identity = {
        "benchmark_schema_version": "controlled-retrieval-v1",
        "evaluator_version": EVALUATOR,
        "source_snapshot_hash": manifest.source_snapshot_hash,
        "query_set_hash": pins["benchmark/ground-truth-v1.jsonl"],
        "judgment_source_hash": pins["benchmark/annotation/machine-proposals-v1.jsonl"],
        "reference_time": manifest.reference_time.isoformat(),
        "input_sha256": pins,
        "policy": POLICY,
        "caveat": CAVEAT,
    }
    return identity, records, events


def aggregate(chunks):
    scores = {}
    for hit in chunks:
        require(type(hit["score"]) in (float, int) and math.isfinite(hit["score"]), "invalid_score")
        eid = hit["event_id"]
        current = scores.get(eid)
        if current is None or (-hit["score"], hit["point_id"]) < (
            -current["score"],
            current["point_id"],
        ):
            scores[eid] = hit
    return sorted(scores.values(), key=lambda h: (-h["score"], h["event_id"]))


def metrics(grades, ranked, minimum=1):
    require(len(set(ranked)) == len(ranked), "duplicate_event")
    relevant = {eid for eid, grade in grades.items() if grade >= minimum}
    require(relevant, "no_judged_positive")
    result = {}
    for k in POLICY["k"]:
        n = len(relevant.intersection(ranked[:k]))
        result[f"Recall@{k}"] = n / len(relevant)
        result[f"HitRate@{k}"] = float(n > 0)
    result["MRR@10"] = next(
        (1 / (i + 1) for i, eid in enumerate(ranked[:10]) if eid in relevant), 0.0
    )

    def gain(eid):
        return 2 ** grades.get(eid, 0) - 1 if grades.get(eid, 0) >= minimum else 0

    dcg = sum(gain(eid) / math.log2(i + 2) for i, eid in enumerate(ranked[:10]))
    ideal = sum(
        (2**grade - 1) / math.log2(i + 2)
        for i, grade in enumerate(
            sorted((grade for grade in grades.values() if grade >= minimum), reverse=True)[:10]
        )
    )
    result["nDCG@10"] = dcg / ideal
    return result


def distribution(values):
    ordered = sorted(values)
    if not ordered:
        return {"count": 0, "mean": None, "p50": None, "p95": None, "max": None, "min": None}

    def quantile(q):
        x = q * (len(ordered) - 1)
        lo, hi = math.floor(x), math.ceil(x)
        return ordered[lo] + (ordered[hi] - ordered[lo]) * (x - lo)

    return {
        "count": len(values),
        "mean": math.fsum(values) / len(values),
        "p50": quantile(0.5),
        "p95": quantile(0.95),
        "max": ordered[-1],
        "min": ordered[0],
    }


def macro(rows):
    return {name: math.fsum(r[name] for r in rows) / len(rows) for name in rows[0]} if rows else {}


def summarize(runs):
    included = [r for r in runs if r["excluded"] is None]
    evaluated = {
        r["case_id"]: metrics(r["grades"], [x["event_id"] for x in r["ranking"]]) for r in included
    }
    by = {}
    for field in ("language", "category"):
        by[field] = {
            v: macro([evaluated[r["case_id"]] for r in included if r[field] == v])
            for v in sorted({r[field] for r in included})
        }
    return {
        "included": len(included),
        "excluded": {r["case_id"]: r["excluded"] for r in runs if r["excluded"]},
        "overall": macro(list(evaluated.values())),
        "per_case": evaluated,
        "by": by,
        "zero_relevant_top10": sum(v["HitRate@10"] == 0 for v in evaluated.values()),
        "zero_returned": sum(not r["ranking"] for r in runs),
        "mean_returned_count": distribution([len(r["ranking"]) for r in runs]),
        "best_relevant_rank": distribution(
            [r["best_relevant_rank"] for r in included if r["best_relevant_rank"] is not None]
        ),
        "top_score": distribution([r["ranking"][0]["score"] for r in included if r["ranking"]]),
        "relevant_scores": distribution(
            [s["score"] for r in included for s in r["judged_scores"] if s["grade"] > 0]
        ),
        "irrelevant_judged_scores": distribution(
            [s["score"] for r in included for s in r["judged_scores"] if s["grade"] == 0]
        ),
        "unjudged_top10": sum(
            sum(x["event_id"] not in r["grades"] for x in r["ranking"][:10]) for r in included
        ),
        "latency_ms": {
            k: distribution([r["latency_ms"][k] for r in runs]) for k in runs[0]["latency_ms"]
        },
    }


def thresholds(runs):
    included = [r for r in runs if not r["excluded"]]

    def curve(rows):
        result = []
        for t in [-1.0, *[i / 20 for i in range(21)]]:
            counts = Counter()
            for r in rows:
                for s in r["judged_scores"]:
                    positive, selected = s["grade"] > 0, s["score"] >= t
                    key = ("tp" if selected else "fn") if positive else ("fp" if selected else "tn")
                    counts[key] += 1
            tp, fp, fn, tn = (counts[x] for x in ("tp", "fp", "fn", "tn"))
            precision = tp / (tp + fp) if tp + fp else 0.0
            recall = tp / (tp + fn) if tp + fn else 0.0
            result.append(
                {
                    "threshold": t,
                    "precision": precision,
                    "recall": recall,
                    "F1": 2 * precision * recall / (precision + recall)
                    if precision + recall
                    else 0.0,
                    "false_positive_rate": fp / (fp + tn) if fp + tn else None,
                    "tp": tp,
                    "fp": fp,
                    "fn": fn,
                    "tn": tn,
                }
            )
        return result

    return {
        "status": "exploratory-unsplit-judged-pairs-only",
        "overall": curve(included),
        "by": {
            field: {
                v: curve([r for r in included if r[field] == v])
                for v in sorted({r[field] for r in included})
            }
            for field in ("language", "category")
        },
        "unresolved_no_hit_exploratory": {
            r["case_id"]: {
                str(t): sum(s["score"] >= t for s in r["ranking"])
                for t in [0.0, 0.25, 0.5, 0.75, 1.0]
            }
            for r in runs
            if r["excluded"] == "unresolved_no_hit"
        },
    }


def compare(v3, v5):
    for key in (
        "benchmark_schema_version",
        "evaluator_version",
        "source_snapshot_hash",
        "query_set_hash",
        "judgment_source_hash",
        "reference_time",
        "input_sha256",
        "policy",
        "documents",
    ):
        require(v3[key] == v5[key], f"comparison_mismatch_{key}")
    require(v3["model"]["model"] == "jina-v3" and v5["model"]["model"] == "jina-v5", "model_order")
    left, right = ({r["case_id"]: r for r in run["cases"]} for run in (v3, v5))
    require(
        len(left) == len(v3["cases"])
        and len(right) == len(v5["cases"])
        and set(left) == set(right),
        "case_set_mismatch",
    )
    for cid, a in left.items():
        for key in (
            "eligible_ids",
            "eligible_occurrence_ids",
            "eligibility_hash",
            "grades",
            "excluded",
            "language",
            "category",
            "query_group",
        ):
            require(a[key] == right[cid][key], f"comparison_mismatch_{key}")
        require(a["eligibility_hash"] == digest(a["eligible_ids"]), "eligibility_hash_invalid")
    summaries = [summarize(run["cases"]) for run in (v3, v5)]
    require(
        all(set(s["by"]["language"]) == {"de", "da", "en"} for s in summaries),
        "missing_language_coverage",
    )
    gates = []

    def gate(name, a, b, drop):
        gates.append(
            {"gate": name, "v3": a, "v5": b, "delta": b - a, "pass": b - a >= -drop - 1e-12}
        )

    for metric, drop in POLICY["gates"].items():
        if metric.startswith("subgroup"):
            continue
        gate(metric, *(s["overall"][metric] for s in summaries), drop)
    for field in ("language", "category"):
        for value in summaries[0]["by"][field]:
            gate(
                f"{field}:{value}:Recall@10",
                *(s["by"][field][value]["Recall@10"] for s in summaries),
                0.05,
            )
    lost = [
        cid
        for cid, m in summaries[0]["per_case"].items()
        if m["HitRate@10"] and not summaries[1]["per_case"][cid]["HitRate@10"]
    ]
    gates.append(
        {
            "gate": "lost-all-relevant cases",
            "v3": 0,
            "v5": len(lost),
            "delta": len(lost),
            "pass": not lost,
        }
    )
    cases = []
    for cid, a in left.items():
        b = right[cid]
        delta = {
            k: summaries[1]["per_case"][cid][k] - v
            for k, v in summaries[0]["per_case"].get(cid, {}).items()
        }
        cases.append(
            {
                "case_id": cid,
                "language": a["language"],
                "category": a["category"],
                "excluded": a["excluded"],
                "judged_relevant_ids": sorted(e for e, g in a["grades"].items() if g > 0),
                "v3": {"top10": a["ranking"][:10], "best_relevant_rank": a["best_relevant_rank"]},
                "v5": {"top10": b["ranking"][:10], "best_relevant_rank": b["best_relevant_rank"]},
                "delta": delta,
                "direction": "exploratory"
                if not delta
                else "regressed"
                if any(v < -1e-12 for v in delta.values())
                else "improved"
                if any(v > 1e-12 for v in delta.values())
                else "unchanged",
            }
        )
    return {
        "caveat": CAVEAT,
        "evaluator_version": EVALUATOR,
        "gates": gates,
        "lost_all_relevant": lost,
        "verdict": "v5 provisionally passes the controlled benchmark gates"
        if all(g["pass"] for g in gates)
        else "v5 provisionally fails one or more gates",
        "v3": summaries[0],
        "v5": summaries[1],
        "cases": cases,
    }
