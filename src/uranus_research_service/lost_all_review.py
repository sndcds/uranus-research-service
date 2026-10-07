"""Small human follow-up using the existing blind packet, UI and Answer contract.

No provider, encoder, vector store or runtime imports. Historical files are read-only.
"""

import hashlib
import json
import os
import tempfile
from collections import Counter
from pathlib import Path

from uranus_research_service.blind_expansion import audit_blind, export, order_key, read
from uranus_research_service.blind_review import ReviewBatch, validate_batch
from uranus_research_service.controlled_evaluation import lines, metrics, require
from uranus_research_service.ground_truth_snapshot import canonical_bytes
from uranus_research_service.semantic_manifest import digest

CASES = ("historical-q29", "wheelchair-da", "dance-en", "concerts-en")
SET_ID = "focused-human-review-v1"
SEED = "focused-human-review-v1-20261007"
PIN = "benchmark/contracts/lost-all-input-sha256.json"
DEST = "benchmark/review/lost-all-v1"
CHECKS = {
    "historical-q29": [
        "Kunst/kreative Gestaltung",
        "aktive Beteiligung/Workshop",
        "Jugendliche/junge Menschen",
    ],
    "wheelchair-da": [
        "Kulturangebot",
        "dokumentierter Rollstuhlzugang je zulässigem Termin",
        "Zugang und Toiletten/Einschränkungen getrennt",
    ],
    "dance-en": [
        "selbst tanzen statt nur Tanzaufführung",
        "lebhafte Atmosphäre",
        "Abend statt Nachmittag",
    ],
    "concerts-en": [
        "Konzert/Live-Musik",
        "mehrere belegte Genres innerhalb eines einzelnen Konzertprogramms",
    ],
}
EXTRA = {"query_id", "event_id", "category", "intent_checks"}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def atomic_new(path, value, *, jsonl=False):
    """Publish a complete fsynced file exclusively; never replace prior work."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = (
        b"".join(canonical_bytes(r) + b"\n" for r in value)
        if jsonl
        else canonical_bytes(value) + b"\n"
    )
    fd, name = tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.link(name, path)
    finally:
        os.unlink(name)


def verify(root):
    pins = read(root / PIN)
    for name, expected in pins["files"].items():
        path = root / name
        require(path.resolve().is_relative_to(root.resolve()), "input_path_escape")
        require(sha(path) == expected, f"frozen_input_changed:{name}")
    return pins


def pool(a, b):
    """Event UUID union; all historical positives retained, including beyond Top 20."""
    tops = [{h["event_id"] for h in r["ranking"][:10]} for r in (a, b)]
    positives = {e for e, g in a["grades"].items() if g > 0}
    ids = set.union(*tops, positives)
    counts = {
        "only_v3_top10": len(tops[0] - tops[1]),
        "only_v5_top10": len(tops[1] - tops[0]),
        "both_top10": len(tops[0] & tops[1]),
        "additional_known_positive": len(positives - set.union(*tops)),
        "total": len(ids),
    }
    return ids, counts


def audit(packet):
    audit_blind([{k: v for k, v in r.items() if k not in EXTRA} for r in packet])
    for r in packet:
        require(EXTRA <= r.keys(), "review_identity_missing")
        require(r["query_id"] in CASES, "unexpected_query")
        require(r["intent_checks"] == CHECKS[r["query_id"]], "intent_check_changed")


def build(root):
    pins = verify(root)
    original, original_packet, runs = export(root)
    evidence = {r["annotation_id"]: r for r in original_packet}
    by_pair = {(r["case_id"], r["event_id"]): r for r in original["mapping"]}
    sides = [{c["case_id"]: c for c in r["cases"]} for r in runs]
    mapping, packet, provenance, counts = [], [], [], {}
    for cid in CASES:
        a, b = [r[cid] for r in sides]
        ids, counts[cid] = pool(a, b)
        ranked = [
            {h["event_id"]: (i + 1, h["score"]) for i, h in enumerate(r["ranking"])} for r in (a, b)
        ]
        for eid in sorted(ids):
            source = by_pair[cid, eid]
            aid = order_key(SEED, "review", cid, eid)[:32]
            m = {**source, "annotation_id": aid, "occurrence_sensitive": True}
            mapping.append(m)
            p = {
                **evidence[source["annotation_id"]],
                "annotation_id": aid,
                "query_id": cid,
                "event_id": eid,
                "category": a["category"],
                "intent_checks": CHECKS[cid],
            }
            # Existing UI renders rubric; full original rubric is preserved verbatim first.
            p["rubric"] += " Prüfhinweise (keine neue Skala): " + "; ".join(CHECKS[cid]) + "."
            packet.append(p)
            provenance.append(
                {
                    "annotation_id": aid,
                    "case_id": cid,
                    "event_id": eid,
                    "previous_grade": a["grades"].get(eid),
                    **{
                        model: {"rank": ranked[i][eid][0], "score": ranked[i][eid][1]}
                        for i, model in enumerate(("v3", "v5"))
                    },
                }
            )
    packet.sort(key=lambda r: order_key(SEED, "presentation", r["annotation_id"]))
    audit(packet)
    plan = {
        "schema_version": "focused-human-review-plan-v1",
        "review_set_id": SET_ID,
        "status": "awaiting-human-review",
        "seed": SEED,
        "selection": (
            "union(v3-top10,v5-top10,all-existing-positive-events); UUID dedup; no tie extension"
        ),
        "ordering": "SHA256 canonical JSON [seed,presentation,annotation_id] ascending",
        "input_manifest_sha256": sha(root / PIN),
        "source_hashes": pins["files"],
        "case_ids": list(CASES),
        "counts": counts,
        "mapping": mapping,
        "packet_sha256": digest(packet),
        "annotation_order": [r["annotation_id"] for r in packet],
    }
    return plan, packet, provenance, runs


def prepare(root, output):
    require(not output.exists(), "destination_must_be_new")
    plan, packet, provenance, _ = build(root)
    atomic_new(output / "review-plan.json", plan)
    atomic_new(output / "provenance.json", provenance)
    atomic_new(output / "reviewer/blind-candidates.jsonl", packet, jsonl=True)
    atomic_new(
        output / "reviewer/annotation-package.json",
        {
            "schema_version": "phase2d-blind-package-v1",
            "review_set_id": SET_ID,
            "package_sha256": digest(plan),
            "packet_sha256": digest(packet),
            "count": len(packet),
        },
    )
    atomic_new(output / "annotation-schema.json", ReviewBatch.model_json_schema())
    # Reuse the reviewed offline UI byte-for-byte, no second frontend implementation.
    data = (root / "benchmark/annotation/phase2d/review.html").read_bytes()
    with (output / "reviewer/review.html").open("xb") as f:
        f.write(data)
    atomic_new(
        output / "artifact-sha256.json",
        {str(p.relative_to(output)): sha(p) for p in sorted(output.rglob("*")) if p.is_file()},
    )
    return plan


def checked(root, directory):
    plan, packet, provenance, runs = build(root)
    require(read(directory / "review-plan.json") == plan, "review_plan_changed")
    require(
        lines(directory / "reviewer/blind-candidates.jsonl") == packet, "review_evidence_changed"
    )
    require(read(directory / "provenance.json") == provenance, "provenance_changed")
    meta = read(directory / "reviewer/annotation-package.json")
    require(
        meta["package_sha256"] == digest(plan)
        and meta["packet_sha256"] == digest(packet)
        and meta["count"] == len(packet),
        "review_package_changed",
    )
    for name, expected in read(directory / "artifact-sha256.json").items():
        path = directory / name
        require(path.resolve().is_relative_to(directory.resolve()), "artifact_path_escape")
        require(sha(path) == expected, "review_artifact_changed")
    require(
        (directory / "reviewer/review.html").read_bytes()
        == (root / "benchmark/annotation/phase2d/review.html").read_bytes(),
        "review_ui_changed",
    )
    return plan, packet, runs


def completion(batch, plan):
    answers = {a.annotation_id: a for a in batch.answers}
    missing = [
        r["annotation_id"]
        for r in plan["mapping"]
        if r["annotation_id"] not in answers or answers[r["annotation_id"]].state == "pending"
    ]
    return {
        "complete": not missing,
        "missing": missing,
        "states": dict(Counter(a.state for a in batch.answers)),
        "uncertain_is_zero": False,
    }


def validate(raw, plan, packet):
    batch = validate_batch(raw, plan, packet)
    return batch, completion(batch, plan)


def imported(raw, plan, packet):
    batch, status = validate(raw, plan, packet)
    require(status["complete"], "review_incomplete")
    answers = {a.annotation_id: a for a in batch.answers}
    return {
        "schema_version": "focused-human-judgments-v1",
        "status": "human-review-follow-up-not-production-approval",
        "review_set_id": SET_ID,
        "plan_sha256": digest(plan),
        "source_hashes": plan["source_hashes"],
        "review_sha256": digest(batch.model_dump(mode="json")),
        "review": batch.model_dump(mode="json"),
        "judgments": [
            {**r, **answers[r["annotation_id"]].model_dump(mode="json")} for r in plan["mapping"]
        ],
    }


def measure(grades, ranking):
    if any(g > 0 for g in grades.values()):
        return metrics(grades, ranking)
    return {
        "Recall@5": None,
        "Recall@10": None,
        "HitRate@5": 0.0,
        "HitRate@10": 0.0,
        "MRR@10": 0.0,
        "nDCG@10": None,
    }


def evaluate(derived, plan, packet, runs):
    # Re-derive from the source human submission; tampered derived labels fail closed.
    require(derived == imported(derived["review"], plan, packet), "derived_judgments_changed")
    sides = [{c["case_id"]: c for c in r["cases"]} for r in runs]
    results = []
    for cid in CASES:
        old = sides[0][cid]["grades"]
        reviewed = [r for r in derived["judgments"] if r["case_id"] == cid]
        human = {r["event_id"]: r["grade"] for r in reviewed if r["state"] == "graded"}
        unresolved = {r["event_id"] for r in reviewed if r["state"] != "graded"}
        # Null removes a previous draft grade for this follow-up; it is never zero.
        expanded = {e: g for e, g in old.items() if e not in unresolved}
        expanded.update(human)
        models = {}
        for model, side in zip(("v3", "v5"), sides, strict=True):
            ranking = [h["event_id"] for h in side[cid]["ranking"]]

            def best(grades, ranked=ranking):
                return next((i + 1 for i, e in enumerate(ranked) if grades.get(e, 0) > 0), None)

            models[model] = {
                "historical_metrics": measure(old, ranking),
                "expanded_metrics": measure(expanded, ranking),
                "human_only_metrics": measure(human, ranking),
                "old_best_known_relevant_rank": best(old),
                "new_best_human_relevant_rank": best(human),
                "human_positive_top10": [e for e in ranking[:10] if human.get(e, 0) > 0],
                "expanded_positive_top10": [e for e in ranking[:10] if expanded.get(e, 0) > 0],
                "coverage": {
                    str(k): {
                        "before": sum(e in old for e in ranking[:k]) / k,
                        "after": sum(e in expanded for e in ranking[:k]) / k,
                        "human": sum(e in human for e in ranking[:k]) / k,
                    }
                    for k in (10, 20)
                },
            }
        new_top = models["v5"]["human_positive_top10"]
        conflicts = [
            {"event_id": e, "old_grade": old[e], "human_grade": g}
            for e, g in human.items()
            if e in old and g != old[e]
        ]
        remains = (
            bool(models["v3"]["expanded_positive_top10"])
            and not models["v5"]["expanded_positive_top10"]
        )
        results.append(
            {
                "case_id": cid,
                "models": models,
                "old_known_positive_ids": sorted(e for e, g in old.items() if g > 0),
                "human_positive_ids": sorted(e for e, g in human.items() if g > 0),
                "conflicts_with_draft": conflicts,
                "newly_judged": {e: g for e, g in human.items() if e not in old},
                "unresolved": sorted(unresolved),
                "historical_known_positive_loss_remains": remains if not unresolved else None,
                "disappears_solely_by_missing_judgments": bool(new_top)
                and all(e not in old for e in new_top)
                and not conflicts
                and not unresolved,
                "interpretation": "incomplete-review"
                if unresolved
                else "four-query-human-follow-up",
            }
        )
    aggregate = {}
    for model in ("v3", "v5"):
        aggregate[model] = {}
        for variant in ("historical_metrics", "expanded_metrics", "human_only_metrics"):
            values = [r["models"][model][variant] for r in results]
            aggregate[model][variant] = {
                key: {
                    "mean": sum(v[key] for v in values if v[key] is not None)
                    / sum(v[key] is not None for v in values)
                    if any(v[key] is not None for v in values)
                    else None,
                    "defined_cases": sum(v[key] is not None for v in values),
                }
                for key in values[0]
            }
    return {
        "schema_version": "focused-human-reevaluation-v1",
        "plan_sha256": digest(plan),
        "judgments_sha256": digest(derived),
        "historical_verdict": "v5 provisionally fails one or more gates",
        "expanded_review_verdict": (
            "four-query follow-up only; no global gate or production decision"
        ),
        "policy": (
            "grade>=1; unchanged stored rankings and original metrics; reviewed grades "
            "override draft only in derived follow-up; unresolved remains unknown; "
            "pooled zero gain is not an irrelevance judgment"
        ),
        "cases": results,
        "aggregate": aggregate,
    }


def command(args):
    root = args.root
    if args.command == "prepare-lost-all-review":
        plan = prepare(root, args.output)
        print(
            json.dumps(
                {
                    "pairs": len(plan["mapping"]),
                    "counts": plan["counts"],
                    "plan_sha256": digest(plan),
                }
            )
        )
        return
    require(args.package is not None, "package_required")
    plan, packet, runs = checked(root, args.package)
    if args.command == "check-lost-all-review":
        result = {"status": "valid", "pairs": len(packet), "plan_sha256": digest(plan)}
    else:
        require(args.a is not None, "review_input_required")
        raw = read(args.a)
        if args.command == "validate-lost-all-review":
            _, result = validate(raw, plan, packet)
        elif args.command == "import-lost-all-review":
            result = imported(raw, plan, packet)
        else:
            result = evaluate(raw, plan, packet, runs)
    atomic_new(args.output, result)


def main():
    """Keep the hash-pinned Phase-2D CLI unchanged; reuse its argument conventions."""
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=(
            "prepare-lost-all-review",
            "check-lost-all-review",
            "validate-lost-all-review",
            "import-lost-all-review",
            "reevaluate-lost-all",
        ),
    )
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--package", type=Path)
    parser.add_argument("--a", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    command(parser.parse_args())


if __name__ == "__main__":
    main()
