"""Offline derivation only, after blind adjudication has been persisted and validated."""

from collections import Counter
from pathlib import Path

from uranus_research_service.machine_blind_adjudication import BASE, IDS, validate
from uranus_research_service.machine_blind_contracts import load_packet, read, require, sha
from uranus_research_service.semantic_manifest import digest

CONSENSUS_SHA = "13f332d43cd8a32ab0639f3079fcb30ba9af923ca3a4faa9a0820431b20a2385"
LABEL = "machine-only exploratory reevaluation with model adjudication"
VERDICT = "v5 provisionally fails one or more gates"


def original():
    path = BASE / "machine-consensus-v1.json"
    require(sha(path.read_bytes()) == CONSENSUS_SHA, "historical_consensus_changed")
    return read(path)


def combine(directory):
    records = validate(directory)
    old = original()
    require(
        {j["annotation_id"] for j in old["judgments"] if j["status"] != "machine_agreed"} == IDS,
        "conflict_set_changed",
    )
    rows = {r["annotation_id"]: r for r in records}
    judgments = []
    for old_j in old["judgments"]:
        aid = old_j["annotation_id"]
        if aid not in rows:
            judgments.append(
                {"annotation_id": aid, "status": "machine_agreed", "grade": old_j["grade"]}
            )
        else:
            r = rows[aid]
            judgments.append(
                {
                    "annotation_id": aid,
                    "status": r["status"],
                    "grade": r["answer"]["grade"] if r["answer"] else None,
                }
            )
    return {
        "schema_version": "machine-consensus-plus-adjudication-v1",
        "provenance": "machine_proposed",
        "original_consensus_sha256": CONSENSUS_SHA,
        "adjudicated_records": records,
        "adjudicated_records_sha256": digest(records),
        "judgments": judgments,
        "counts": dict(Counter(j["status"] for j in judgments)),
    }


def validate_combined(value, packet):
    require(
        value["schema_version"] == "machine-consensus-plus-adjudication-v1"
        and value["provenance"] == "machine_proposed",
        "combined_schema",
    )
    require(value["original_consensus_sha256"] == CONSENSUS_SHA, "combined_source")
    records = value["adjudicated_records"]
    require(value["adjudicated_records_sha256"] == digest(records), "records_digest")
    require(len(records) == 7 and {r["annotation_id"] for r in records} == IDS, "records_ids")
    from uranus_research_service.machine_blind_adjudication import (
        PROMPT,
        configuration,
        validate_record,
    )

    prompt = PROMPT.read_text()
    config = configuration(prompt)
    mapping = {p["annotation_id"]: p for p in packet}
    for r in records:
        validate_record(r, mapping[r["annotation_id"]], config, prompt)
    judgments = value["judgments"]
    require(
        len(judgments) == 77 and {j["annotation_id"] for j in judgments} == set(mapping),
        "combined_ids",
    )
    old = {j["annotation_id"]: j for j in original()["judgments"]}
    amended = {r["annotation_id"]: r for r in records}
    for j in judgments:
        aid = j["annotation_id"]
        require(set(j) == {"annotation_id", "status", "grade"}, "combined_fields")
        if aid not in IDS:
            require(j == {k: old[aid][k] for k in j}, "agreed_changed")
        else:
            r = amended[aid]
            require(
                j["status"] == r["status"]
                and j["grade"] == (r["answer"]["grade"] if r["answer"] else None),
                "adjudication_changed",
            )
    require(value["counts"] == dict(Counter(j["status"] for j in judgments)), "combined_counts")


def reevaluate(value):
    package = BASE.parent
    packet, _ = load_packet(package)
    validate_combined(value, packet)  # Validate sealed machine provenance before ranking reads.
    from uranus_research_service.lost_all_review import CASES, checked, measure

    plan, packet2, runs = checked(Path("."), package)
    require(packet == packet2, "packet_changed")
    mapping = {p["annotation_id"]: p for p in packet}
    sets = {name: {cid: {} for cid in CASES} for name in ("consensus_only", "adjudicated")}
    unresolved = Counter()
    for j in value["judgments"]:
        p = mapping[j["annotation_id"]]
        cid, eid = p["query_id"], p["event_id"]
        if j["grade"] is None:
            unresolved[cid] += 1
            continue
        sets["adjudicated"][cid][eid] = j["grade"]
        if j["status"] == "machine_agreed":
            sets["consensus_only"][cid][eid] = j["grade"]
    results = []
    for model, run in zip(("v3", "v5"), runs, strict=True):
        for case in run["cases"]:
            cid = case["case_id"]
            if cid not in CASES:
                continue
            ranked = [h["event_id"] for h in case["ranking"]]
            variants = {
                "historical": case["grades"],
                **{name: by_case[cid] for name, by_case in sets.items()},
            }
            result = {
                "case_id": cid,
                "model": model,
                "unresolved_count": unresolved[cid],
                "variants": {},
            }
            for name, grades in variants.items():
                positive = [eid for eid in ranked[:10] if grades.get(eid, 0) > 0]
                result["variants"][name] = {
                    "metrics": measure(grades, ranked),
                    "positive_top10_ids": positive,
                    "best_positive_rank": next(
                        (i + 1 for i, eid in enumerate(ranked) if grades.get(eid, 0) > 0), None
                    ),
                    "coverage": {
                        str(k): sum(eid in grades for eid in ranked[:k]) / k for k in (10, 20)
                    },
                }
            results.append(result)
    losses = {
        name: [
            cid
            for cid in CASES
            if next(r for r in results if r["case_id"] == cid and r["model"] == "v3")["variants"][
                name
            ]["positive_top10_ids"]
            and not next(r for r in results if r["case_id"] == cid and r["model"] == "v5")[
                "variants"
            ][name]["positive_top10_ids"]
        ]
        for name in ("historical", "consensus_only", "adjudicated")
    }
    return {
        "schema_version": "machine-adjudicated-reevaluation-v1",
        "label": LABEL,
        "historical_verdict": VERDICT,
        "combined_sha256": digest(value),
        "plan_sha256": digest(plan),
        "policy": (
            "grade>=1; unresolved and outside-pool candidates remain unknown, not zero labels; "
            "pooled zero-gain metrics; no global gate recomputation"
        ),
        "cases": results,
        "known_positive_loss_cases": losses,
        "each_adjudicated_v5_top10_has_machine_positive": all(
            r["variants"]["adjudicated"]["positive_top10_ids"]
            for r in results
            if r["model"] == "v5"
        ),
    }
