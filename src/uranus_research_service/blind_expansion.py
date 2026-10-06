"""Offline Phase-2D selection and blind export. Never imported by the query runtime."""

import hashlib
from collections import defaultdict
from pathlib import Path

from uranus_research_service.controlled_evaluation import inputs, lines, metrics, require
from uranus_research_service.ground_truth_snapshot import canonical_bytes
from uranus_research_service.json_codec import decode
from uranus_research_service.semantic_manifest import digest

BUILD = "20261006_8cpu_001"
PIN_PATH = "benchmark/contracts/phase2d-input-sha256.json"
CONFIG_PATH = "benchmark/annotation/phase2d/sampling-plan.json"


def read(path):
    return decode(Path(path).read_bytes())


def write_new(path, value, *, jsonl=False):
    """Exclusive creation: never replace historical artifacts or human work."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = (
        b"".join(canonical_bytes(row) + b"\n" for row in value)
        if jsonl
        else canonical_bytes(value) + b"\n"
    )
    with path.open("xb") as stream:
        stream.write(data)


def verify_inputs(root):
    pins = read(root / PIN_PATH)
    require(pins["schema_version"] == "phase2d-input-sha256-v1", "input_manifest_schema")
    for name, sha in pins["files"].items():
        path = root / name
        require(path.resolve().is_relative_to(root.resolve()), "input_path_escape")
        require(hashlib.sha256(path.read_bytes()).hexdigest() == sha, f"input_changed:{name}")
    return pins


def load(root):
    pins = verify_inputs(root)
    identity, cases, events = inputs(root)
    runs = [read(root / f"benchmark/results/{model}-{BUILD}.json") for model in ("v3", "v5")]
    for run in runs:
        for key, value in identity.items():
            require(run[key] == value, f"historical_identity:{key}")
        require(len(run["cases"]) == len(cases), "case_count")
        by_id = {r["case_id"]: r for r in run["cases"]}
        require(len(by_id) == len(cases), "duplicate_case")
        for c in cases:
            r = by_id[c["case_id"]]
            for key in ("grades", "eligible_ids", "eligible_occurrence_ids", "excluded"):
                require(r[key] == c[key], f"historical_case:{key}")
            ranked = [h["event_id"] for h in r["ranking"]]
            require(len(set(ranked)) == len(ranked), "duplicate_ranking")
            require(set(ranked) == set(c["eligible_ids"]), "incomplete_stored_ranking")
            require(
                r["ranking"] == sorted(r["ranking"], key=lambda h: (-h["score"], h["event_id"])),
                "ranking_order",
            )
    return pins, identity, cases, events, runs


def tie_prefix(ranking, k):
    end = min(k, len(ranking))
    while end and end < len(ranking) and ranking[end]["score"] == ranking[end - 1]["score"]:
        end += 1
    return ranking[:end]


def order_key(seed, *parts):
    return digest([seed, *parts])


def disagreement(a, b, config):
    ranks = [{h["event_id"]: i + 1 for i, h in enumerate(r["ranking"])} for r in (a, b)]
    tops = [set(list(r)[:10]) for r in ranks]
    jaccard = len(tops[0] & tops[1]) / len(tops[0] | tops[1]) if any(tops) else 1.0
    positives = [e for e, g in a["grades"].items() if g > 0]
    gap = max((abs(ranks[0][e] - ranks[1][e]) for e in positives), default=0)
    top5_gap = any(
        rank <= 5 and ranks[1 - i][e] >= config["top5_other_rank_min"]
        for i, side in enumerate(ranks)
        for e, rank in side.items()
    )
    unknown = [len(top - set(a["grades"])) for top in tops]
    strong = jaccard <= config["top10_jaccard_max"] or gap >= config["known_positive_rank_gap_min"]
    return {
        "strong": strong,
        "material": strong or top5_gap or max(unknown) >= config["unjudged_top10_min"],
        "top10_jaccard": jaccard,
        "known_positive_rank_gap": gap,
        "top5_other_far": top5_gap,
        "unjudged_top10": unknown,
    }


def select(cases, runs, config):
    sides = [{c["case_id"]: c for c in run["cases"]} for run in runs]
    records = {}
    controls = defaultdict(list)
    material = defaultdict(list)
    for c in cases:
        cid = c["case_id"]
        a, b = (side[cid] for side in sides)
        d = disagreement(a, b, config)
        row = {"case_id": cid, "language": c["language"], "category": c["category"], **d}
        if cid in config["total_loss"]:
            records[cid] = {**row, "priority": 1, "k": config["priority1_k"]}
        elif c["category"] in config["failed_categories"]:
            records[cid] = {
                **row,
                "priority": 2,
                "k": config["strong_disagreement_k"] if d["strong"] else config["priority2_k"],
            }
        elif c["excluded"] is None and d["material"]:
            material[c["language"]].append(row)
    for rows in material.values():
        chosen = sorted(rows, key=lambda r: order_key(config["seed"], "p3", r["case_id"]))
        for row in chosen[: config["priority3_per_language"]]:
            records[row["case_id"]] = {**row, "priority": 3, "k": config["strong_disagreement_k"]}
    for c in cases:
        cid = c["case_id"]
        if cid in records or c["excluded"] is not None:
            continue
        values = [
            metrics(c["grades"], [h["event_id"] for h in side[cid]["ranking"]]) for side in sides
        ]
        delta = values[1]["Recall@10"] - values[0]["Recall@10"]
        direction = (
            "neutral"
            if abs(delta) <= config["neutral_recall_delta_max"]
            else "v5_improvement"
            if delta > 0
            else "v3_improvement"
        )
        controls[c["language"], direction].append(c)
    strata = []
    for lang in ("de", "da", "en"):
        for direction in ("v3_improvement", "neutral", "v5_improvement"):
            chosen = sorted(
                controls[lang, direction],
                key=lambda c: order_key(config["seed"], "control", c["case_id"]),
            )[: config["control_per_language_direction"]]
            strata.append({"language": lang, "direction": direction, "selected": len(chosen)})
            for c in chosen:
                records[c["case_id"]] = {
                    "case_id": c["case_id"],
                    "language": lang,
                    "category": c["category"],
                    "priority": 4,
                    "k": config["control_k"],
                    "control_direction": direction,
                }
    pool = []
    for cid, row in sorted(records.items()):
        row["subset"] = "balanced" if row["priority"] == 4 else "diagnostic"
        a, b = (side[cid] for side in sides)
        eids = {h["event_id"] for r in (a, b) for h in tie_prefix(r["ranking"], row["k"])}
        eids.update(e for e, grade in a["grades"].items() if grade > 0)
        pool.extend({"case_id": cid, "event_id": eid} for eid in sorted(eids))
    return {
        "cases": [records[cid] for cid in sorted(records)],
        "control_strata": strata,
        "pool_before_shuffle": pool,
    }


def export(root):
    pins, identity, cases, events, runs = load(root)
    config = read(root / CONFIG_PATH)
    selection = select(cases, runs, config)
    queries = {c["id"]: c for c in lines(root / "benchmark/ground-truth-v1.jsonl")}
    eligible = {c["case_id"]: set(c["eligible_occurrence_ids"]) for c in cases}
    event_rows = {str(eid): row.model_dump(mode="json") for eid, row in events.items()}
    rubrics = read(root / "benchmark/annotation/machine-rubrics-v1.json")
    mapping, packet = [], []
    for pair in selection["pool_before_shuffle"]:
        cid, eid = pair["case_id"], pair["event_id"]
        blind_id = order_key(config["seed"], "blind", cid, eid)[:32]
        q, event = queries[cid], event_rows[eid]
        mapping.append(
            {
                "annotation_id": blind_id,
                **pair,
                "document_hash": event["document_hash"],
                "occurrence_sensitive": q["category"]
                in {"accessibility", "venue", "location", "outdoor"}
                or rubrics["case_rubrics"][cid]
                in {"meeting", "stepfree", "wheelchair", "access", "access_registration"}
                or any(
                    q["eligibility"][key]
                    for key in ("date_from", "date_to", "weekdays", "city", "venue_id")
                ),
            }
        )
        packet.append(
            {
                "annotation_id": blind_id,
                "query": q["query"],
                "language": q["language"],
                "reference_time": q["reference_time"],
                "eligibility": q["eligibility"],
                "event": {k: v for k, v in event["event"].items() if k != "id"},
                "eligible_occurrence_ids": sorted(
                    o["id"] for o in event["event"]["occurrences"] if o["id"] in eligible[cid]
                ),
                "rubric": rubrics["rules"][rubrics["case_rubrics"][cid]]
                + (
                    " Verbindlich für diese Runde menschlich bestätigt: mehrere Genres im "
                    "einzelnen Konzertprogramm, keine Vielfalt über die Ergebnisliste."
                    if rubrics["case_rubrics"][cid] == "concerts"
                    and config.get("rubric_clarifications")
                    else ""
                ),
                "scale": rubrics["scale"],
            }
        )
    packet.sort(key=lambda r: order_key(config["seed"], "presentation", r["annotation_id"]))
    audit_blind(packet)
    bundle = {
        "schema_version": "phase2d-package-v1",
        "status": "draft",
        "input_manifest_sha256": digest(pins),
        "source_snapshot_hash": identity["source_snapshot_hash"],
        "sampling": config,
        "selection": selection,
        "mapping": mapping,
        "annotation_order": [r["annotation_id"] for r in packet],
        "packet_sha256": digest(packet),
        "rubric_questions": []
        if config.get("rubric_clarifications", {}).get("concerts", {}).get("decision")
        == "confirm-existing-single-event-rubric"
        else ["concerts-single-event-versus-result-set"],
    }
    return bundle, packet, runs


def audit_blind(packet):
    """Allowlisted metadata, never substring-match public evidence text."""
    top = {
        "annotation_id",
        "query",
        "language",
        "reference_time",
        "eligibility",
        "event",
        "eligible_occurrence_ids",
        "rubric",
        "scale",
    }
    from uranus_research_service.ground_truth import Eligibility
    from uranus_research_service.ground_truth_snapshot import PublicEvent

    ids = []
    for row in packet:
        require(set(row) == top, "blind_metadata_leak")
        require(set(row["scale"]) == {"0", "1", "2", "3"}, "blind_scale")
        Eligibility.model_validate(row["eligibility"])
        require("id" not in row["event"], "event_identity_in_packet")
        PublicEvent.model_validate({"id": "00000000-0000-0000-0000-000000000001", **row["event"]})
        ids.append(row["annotation_id"])
    require(len(ids) == len(set(ids)), "duplicate_blind_id")


def response_template(packet):
    return [
        {
            "annotation_id": p["annotation_id"],
            "state": "pending",
            "grade": None,
            "reason": "",
            "supporting_fields": [],
            "occurrence_ids": [],
        }
        for p in packet
    ]


def coverage(runs, bundle, expanded=None):
    subsets = {r["case_id"]: r["subset"] for r in bundle["selection"]["cases"]}
    rows = []
    for model, run in zip(("v3", "v5"), runs, strict=True):
        for c in run["cases"]:
            grades = c["grades"] if expanded is None else expanded[c["case_id"]]
            for k in (10, 20):
                ids = [h["event_id"] for h in c["ranking"][:k]]
                positive = sum(grades.get(e, 0) > 0 for e in ids)
                zero = sum(e in grades and grades[e] == 0 for e in ids)
                rows.append(
                    {
                        "case_id": c["case_id"],
                        "language": c["language"],
                        "category": c["category"],
                        "subset": subsets.get(c["case_id"], "unselected"),
                        "model": model,
                        "k": k,
                        "positive": positive,
                        "zero": zero,
                        "unjudged": len(ids) - positive - zero,
                        "returned": len(ids),
                        "judged_coverage": (positive + zero) / len(ids) if ids else None,
                    }
                )
    groups = defaultdict(list)
    for row in rows:
        groups[f"{row['model']}:{row['k']}:all"].append(row)
        if row["case_id"] in bundle["sampling"]["total_loss"]:
            groups[f"{row['model']}:{row['k']}:total_loss"].append(row)
        for field in ("language", "category", "subset"):
            groups[f"{row['model']}:{row['k']}:{field}:{row[field]}"].append(row)
    return {
        "per_case": rows,
        "aggregates": {
            key: {
                "cases": len(values),
                **{
                    f: sum(r[f] for r in values)
                    for f in ("positive", "zero", "unjudged", "returned")
                },
                "mean_coverage": sum(
                    r["judged_coverage"] for r in values if r["judged_coverage"] is not None
                )
                / max(1, sum(r["judged_coverage"] is not None for r in values)),
            }
            for key, values in sorted(groups.items())
        },
    }
