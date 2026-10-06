"""Offline reconstruction only: immutable completed reports, no services or models."""

import argparse
import hashlib
import json
from pathlib import Path

from uranus_research_service.controlled_evaluation import CAVEAT, compare, metrics

BUILD = "20261006_8cpu_001"
LOSSES = ("historical-q29", "wheelchair-da", "dance-en", "concerts-en")
CATEGORIES = ("atmosphere", "outdoor", "theatre", "venue")
CONTROLS = ("historical-q02", "quiet-da", "creative-da", "nordic-en", "songwriters-en")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def coverage(case):
    grades = case["grades"]
    top = case["ranking"][:10]
    return {
        "judged": sum(h["event_id"] in grades for h in top),
        "known_positive": sum(grades.get(h["event_id"], 0) > 0 for h in top),
        "known_zero": sum(grades.get(h["event_id"]) == 0 for h in top),
        "unjudged": sum(h["event_id"] not in grades for h in top),
    }


def analyze(root):
    base = root / "benchmark/results"
    sources = read(base / "artifact-sha256.json")["files"]
    for name, expected in sources.items():
        if sha(base / name) != expected:
            raise ValueError("completed_artifact_changed")
    for name, expected in read(root / "benchmark/contracts/phase2b2c-input-sha256.json").items():
        if sha(root / name) != expected:
            raise ValueError("frozen_input_changed")
    runs = {m: read(base / f"{m}-{BUILD}.json") for m in ("v3", "v5")}
    comparison = compare(runs["v3"], runs["v5"])
    if comparison != read(base / f"v3-v5-comparison-{BUILD}.json"):
        raise ValueError("comparison_changed")
    chunks = {m: read(base / f"chunks-{m}-{BUILD}.json") for m in runs}
    events = {
        x["event"]["id"]: x["event"]
        for x in map(
            json.loads,
            (root / "benchmark/snapshots/public-events-20261005/events.jsonl")
            .read_text()
            .splitlines(),
        )
    }
    queries = {
        x["id"]: x
        for x in map(
            json.loads, (root / "benchmark/ground-truth-v1.jsonl").read_text().splitlines()
        )
    }
    cases = {m: {c["case_id"]: c for c in run["cases"]} for m, run in runs.items()}

    def hit(m, c, rank):
        h = c["ranking"][rank - 1]
        chunk = chunks[m][h["point_id"]]["chunk"]
        eid = h["event_id"]
        if chunks[m][h["point_id"]]["entity_id"] != eid:
            raise ValueError("point_identity")
        grade = c["grades"].get(eid)
        score = h["score"]
        return {
            **h,
            "rank": rank,
            "title": events[eid]["title"],
            "grade": grade,
            "judgment": "unjudged" if grade is None else "positive" if grade else "zero",
            "gap_to_top10_boundary": c["ranking"][9]["score"] - score,
            "exact_score_tie_ranks": [
                i + 1 for i, v in enumerate(c["ranking"]) if v["score"] == score
            ],
            "chunk": chunk,
        }

    selected = {}
    for cid, c in cases["v3"].items():
        if cid not in (*LOSSES, *CONTROLS) and c["category"] not in CATEGORIES:
            continue
        positives = sorted(e for e, g in c["grades"].items() if g > 0)
        row = {
            "case_id": cid,
            "query": queries[cid]["query"],
            "language": c["language"],
            "category": c["category"],
            "eligibility": queries[cid]["eligibility"],
            "eligibility_hash": c["eligibility_hash"],
            "excluded": c["excluded"],
            "positive_ids": positives,
            "relevant_occurrences": {
                eid: [
                    o for o in events[eid]["occurrences"] if o["id"] in c["eligible_occurrence_ids"]
                ]
                for eid in positives
            },
            "occurrence_limit": "Event labels do not approve occurrences; contexts are evidence.",
        }
        for m in runs:
            mc = cases[m][cid]
            ranks = {h["event_id"]: i + 1 for i, h in enumerate(mc["ranking"])}
            selected_ranks = {ranks[e] for e in positives}
            neighbors = sorted(
                {
                    r
                    for p in selected_ranks
                    for r in range(max(1, p - 2), min(len(ranks), p + 2) + 1)
                }
            )
            row[m] = {
                "metrics": metrics(mc["grades"], list(ranks)) if positives else None,
                "coverage_top10": coverage(mc),
                "top10": [hit(m, mc, i) for i in range(1, 11)],
                "relevant": [hit(m, mc, ranks[e]) for e in positives],
                "neighbors": [hit(m, mc, i) for i in neighbors] if cid in LOSSES else [],
                "strongest_judged_zero": next(
                    (
                        hit(m, mc, i + 1)
                        for i, h in enumerate(mc["ranking"])
                        if mc["grades"].get(h["event_id"]) == 0
                    ),
                    None,
                ),
                "all_relevant_document_chunks": {
                    e: [
                        {"point_id": pid, **p["chunk"]}
                        for pid, p in chunks[m].items()
                        if p["entity_id"] == e
                    ]
                    for e in positives
                }
                if cid in LOSSES
                else {},
            }
        row["same_uuid_language_controls"] = []
        for peer_id, peer in cases["v3"].items():
            if peer["query_group"] != c["query_group"] or peer_id == cid:
                continue
            peer_ranks = {
                m: {h["event_id"]: i + 1 for i, h in enumerate(cases[m][peer_id]["ranking"])}
                for m in runs
            }
            row["same_uuid_language_controls"].append(
                {
                    "case_id": peer_id,
                    "query": queries[peer_id]["query"],
                    "ranks": {eid: {m: peer_ranks[m].get(eid) for m in runs} for eid in positives},
                    "note": "Original-case positives, not transferred peer judgments.",
                }
            )
        selected[cid] = row
    return {
        "schema": "regression-reconstruction-v1",
        "status": "exploratory; no new labels or gates",
        "caveat": CAVEAT,
        "benchmark_build": BUILD,
        "source_artifact_sha256": sources,
        "analysis_code_sha256": sha(Path(__file__)),
        "cases": selected,
        "category_gates": [
            g for g in comparison["gates"] if any(cat in g["gate"] for cat in CATEGORIES)
        ],
        "limits": [
            "Rankings save the winning chunk per event, not all chunk scores or embeddings.",
            "Unjudged competitors are not established false positives.",
            "Cross-model cosine magnitudes are not calibrated against each other.",
            "Language judgment pools differ; compare the same UUIDs across languages.",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = analyze(args.root)
    with args.output.open("x") as f:
        f.write(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n")


if __name__ == "__main__":
    main()
