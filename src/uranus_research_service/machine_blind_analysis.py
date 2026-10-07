"""Offline machine agreement/consensus; rankings loaded only by explicit reevaluation."""

import math
import re
from collections import Counter
from datetime import datetime

from uranus_research_service.machine_blind_contracts import (
    META_SHA,
    PACKET_SHA,
    PARAMETERS,
    PROMPT,
    load_packet,
    read,
    require,
    sha,
    validate_answer,
)
from uranus_research_service.machine_judge import atomic_new
from uranus_research_service.semantic_manifest import digest

CAVEAT = (
    "machine-only exploratory reevaluation; not human-reviewed, "
    "not ground truth or production approval"
)


def validate_run(raw, packet):
    require(set(raw) == {"manifest", "completed_at", "records", "summary"}, "run_schema")
    require(set(raw["manifest"]) == {"configuration", "started_at"}, "manifest_schema")
    c = raw["manifest"]["configuration"]
    require(
        set(c)
        == {
            "schema_version",
            "provenance",
            "provider",
            "model",
            "pass_id",
            "run_id",
            "parameters",
            "prompt_version",
            "prompt_sha256",
            "packet_sha256",
            "package_file_sha256",
            "expected_count",
            "code_sha256",
        },
        "configuration_schema",
    )
    require(
        c["schema_version"] == "blind-machine-pass-v1" and c["provenance"] == "machine_proposed",
        "machine_only",
    )
    require(c["provider"] == "openai" and c["pass_id"] in ("a", "b"), "provider_pass")
    require(
        c["packet_sha256"] == PACKET_SHA and c["package_file_sha256"] == META_SHA, "run_input_hash"
    )
    require(c["parameters"] == PARAMETERS and c["expected_count"] == 77, "run_parameters")
    require(
        c["prompt_version"] == "focused-judge-v1"
        and c["prompt_sha256"] == sha(PROMPT.read_bytes()),
        "prompt_changed",
    )
    require(re.fullmatch(r"[a-z0-9][a-z0-9.-]{1,99}", c["model"]), "model_id")
    require(re.fullmatch(r"[a-z0-9_-]{1,100}", c["run_id"]), "run_id")
    require(
        set(c["code_sha256"])
        == {"machine_blind_contracts.py", "machine_judge.py", "machine_blind_review.py"},
        "code_provenance",
    )
    require(all(re.fullmatch(r"[a-f0-9]{64}", h) for h in c["code_sha256"].values()), "code_hash")
    for stamp in (raw["manifest"]["started_at"], raw["completed_at"]):
        require(datetime.fromisoformat(stamp).tzinfo is not None, "aware_timestamp")
    summary = raw["summary"]
    require(
        set(summary)
        == {"count", "failed_cases", "failed_attempts", "retry_count", "unknown_attempts", "usage"},
        "summary_schema",
    )
    require(
        all(type(summary[k]) is int and summary[k] >= 0 for k in summary if k != "usage"),
        "summary_counts",
    )
    require(summary["count"] == 77 and summary["failed_cases"] == 0, "incomplete_summary")
    by_id = {p["annotation_id"]: p for p in packet}
    answers = {}
    for row in raw["records"]:
        require(
            set(row)
            == {
                "answer",
                "configuration_sha256",
                "request_id",
                "response_id",
                "attempt",
                "completed_at",
                "latency_ms",
                "usage",
            },
            "record_schema",
        )
        require(row["configuration_sha256"] == digest(c), "record_identity")
        require(type(row["attempt"]) is int and 1 <= row["attempt"] <= 3, "attempt")
        require(
            type(row["latency_ms"]) in (int, float)
            and math.isfinite(row["latency_ms"])
            and row["latency_ms"] >= 0,
            "latency",
        )
        require(datetime.fromisoformat(row["completed_at"]).tzinfo is not None, "record_time")
        for field in ("request_id", "response_id"):
            require(
                row[field] is None or re.fullmatch(r"[A-Za-z0-9_-]{1,200}", row[field]),
                "provider_id",
            )
        require(
            set(row["usage"]) == {"input_tokens", "output_tokens", "total_tokens"}, "usage_schema"
        )
        require(all(type(v) is int and v >= 0 for v in row["usage"].values()), "usage_counts")
        aid = row["answer"]["annotation_id"]
        require(aid in by_id and aid not in answers, "unknown_or_duplicate_id")
        answers[aid] = validate_answer(row["answer"], by_id[aid])
    require(set(answers) == set(by_id) and len(answers) == 77, "incomplete_run")
    require(
        set(summary["usage"]) == {"input_tokens", "output_tokens", "total_tokens"}, "summary_usage"
    )
    for k, v in summary["usage"].items():
        require(
            type(v) is int and v >= sum(r["usage"][k] for r in raw["records"]),
            "summary_usage_count",
        )
    return answers


def classify(a, b):
    status = (
        "machine_uncertain"
        if a["uncertain"] or b["uncertain"]
        else "machine_agreed"
        if a["grade"] == b["grade"]
        else "machine_conflict"
    )
    difference = (
        abs(a["grade"] - b["grade"]) if a["grade"] is not None and b["grade"] is not None else None
    )
    return {
        "status": status,
        "grade": a["grade"] if status == "machine_agreed" else None,
        "absolute_grade_difference": difference,
        "extreme_0_3": status == "machine_conflict" and {a["grade"], b["grade"]} == {0, 3},
    }


def compare(a, b, packet):
    aa, bb = validate_run(a, packet), validate_run(b, packet)
    ca, cb = [r["manifest"]["configuration"] for r in (a, b)]
    require(
        ca["pass_id"] == "a" and cb["pass_id"] == "b" and ca["run_id"] != cb["run_id"],
        "separate_passes",
    )
    require(ca["prompt_sha256"] == cb["prompt_sha256"], "same_rubric_prompt")
    ids = [{r["response_id"] for r in run["records"] if r["response_id"]} for run in (a, b)]
    require(not ids[0] & ids[1], "reused_response")
    rows = [
        {
            "annotation_id": p["annotation_id"],
            "a": aa[p["annotation_id"]],
            "b": bb[p["annotation_id"]],
            **classify(aa[p["annotation_id"]], bb[p["annotation_id"]]),
        }
        for p in packet
    ]
    counts = Counter(r["status"] for r in rows)
    pairs = Counter(
        "-".join(map(str, sorted((r["a"]["grade"], r["b"]["grade"]))))
        for r in rows
        if r["status"] == "machine_conflict"
    )
    return {
        "schema_version": "two-pass-machine-agreement-v1",
        "provenance": "machine_proposed",
        "packet_sha256": PACKET_SHA,
        "prompt_sha256": ca["prompt_sha256"],
        "pass_a_sha256": digest(a),
        "pass_b_sha256": digest(b),
        "configurations": [ca, cb],
        "summary": {
            **{k: counts[k] for k in ("machine_agreed", "machine_conflict", "machine_uncertain")},
            "extreme_0_3": sum(r["extreme_0_3"] for r in rows),
            "conflict_grade_pairs": dict(sorted(pairs.items())),
        },
        "rows": rows,
        "limitation": (
            "Two stateless machine passes, not statistically independent humans; "
            "no majority or adjudication."
        ),
    }


def consensus(report, packet):
    require(
        report["schema_version"] == "two-pass-machine-agreement-v1"
        and report["provenance"] == "machine_proposed",
        "agreement_schema",
    )
    require(report["packet_sha256"] == PACKET_SHA, "agreement_hash")
    by_id = {p["annotation_id"]: p for p in packet}
    rows, seen = [], set()
    for row in report["rows"]:
        aid = row["annotation_id"]
        require(aid in by_id and aid not in seen, "agreement_ids")
        seen.add(aid)
        a, b = (validate_answer(row[k], by_id[aid]) for k in ("a", "b"))
        classification = classify(a, b)
        require(all(row[k] == v for k, v in classification.items()), "agreement_changed")
        rows.append({"annotation_id": aid, **classification})
    require(seen == set(by_id), "agreement_incomplete")
    return {
        "schema_version": "blind-machine-consensus-v1",
        "provenance": "machine_proposed",
        "packet_sha256": PACKET_SHA,
        "agreement_sha256": digest(report),
        "judgments": rows,
        "policy": (
            "Two equal non-uncertain grades only; no majority; conflicts/uncertainty remain null."
        ),
    }


def follow_up(report, packet):
    cs = consensus(report, packet)
    statuses = {r["annotation_id"]: r["status"] for r in cs["judgments"]}
    return [
        {**p, "status": statuses[p["annotation_id"]]}
        for p in packet
        if statuses[p["annotation_id"]] != "machine_agreed"
    ]


def reevaluate(report, root, package):
    packet, _ = load_packet(package)
    cs = consensus(report, packet)  # seal/validate blind consensus before any ranking read
    from uranus_research_service.lost_all_review import CASES, checked, measure

    plan, original, runs = checked(root, package)
    require(original == packet, "review_packet_changed")
    mapping = {p["annotation_id"]: p for p in packet}
    judged = {cid: {} for cid in CASES}
    unresolved = Counter()
    for j in cs["judgments"]:
        p = mapping[j["annotation_id"]]
        if j["status"] == "machine_agreed":
            judged[p["query_id"]][p["event_id"]] = j["grade"]
        else:
            unresolved[p["query_id"]] += 1
    result = []
    for model, run in zip(("v3", "v5"), runs, strict=True):
        for c in run["cases"]:
            cid = c["case_id"]
            if cid not in judged:
                continue
            ranks = [h["event_id"] for h in c["ranking"]]
            result.append(
                {
                    "case_id": cid,
                    "model": model,
                    "historical_metrics": measure(c["grades"], ranks),
                    "machine_consensus_metrics": measure(judged[cid], ranks),
                    "unresolved_count": unresolved[cid],
                    "coverage": {
                        str(k): {
                            "historical": sum(e in c["grades"] for e in ranks[:k]) / k,
                            "machine_consensus": sum(e in judged[cid] for e in ranks[:k]) / k,
                        }
                        for k in (10, 20)
                    },
                }
            )
    return {
        "schema_version": "blind-machine-reevaluation-v1",
        "label": CAVEAT,
        "consensus_sha256": digest(cs),
        "plan_sha256": digest(plan),
        "historical_verdict": "v5 provisionally fails one or more gates",
        "policy": (
            "grade>=1; only agreed machine grades; unjudged/conflict/uncertain absent, "
            "never zero labels; provisional pooled zero-gain metrics, no gate recomputation"
        ),
        "cases": result,
    }


def dispatch(args):
    packet, _ = load_packet(args.package)
    if args.command == "import":
        raw = read(args.input)
        validate_run(raw, packet)
        atomic_new(args.output, raw)
    elif args.command == "compare":
        atomic_new(args.output, compare(read(args.a), read(args.b), packet))
    elif args.command == "consensus":
        report = read(args.input)
        require(not args.output.exists(), "new_consensus_directory_required")
        result = consensus(report, packet)
        atomic_new(args.output / "machine-consensus-v1.json", result)
        atomic_new(
            args.output / "machine-review-needed.jsonl", follow_up(report, packet), jsonl=True
        )
    else:
        atomic_new(args.output, reevaluate(read(args.input), args.root, args.package))
