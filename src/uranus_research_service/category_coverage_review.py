"""Offline category pool preparation using existing blind formats, UI and judge contracts."""

import argparse
from collections import Counter
from pathlib import Path

from uranus_research_service.blind_expansion import (
    audit_blind,
    load,
    order_key,
    tie_prefix,
)
from uranus_research_service.blind_review import ReviewBatch, validate_batch
from uranus_research_service.controlled_evaluation import lines, metrics, require
from uranus_research_service.machine_judge import (
    BlindCandidate,
    atomic_new,
    digest,
    read,
    sha,
)

BASELINE = "b86edbffd312fb11e7fe3248d0f2eb593799894a"
PIN = Path("benchmark/contracts/category-coverage-v1-input-sha256.json")
PIN_SHA = "ddd603c072cc52178839294dddc2c39b08604cb65e210b172d0c5f5e7c2dc3b3"
DEST = Path("benchmark/review/category-coverage-v1")
CATEGORIES = ("outdoor", "theatre", "venue", "accessibility")
SEED = "category-coverage-v1-20261007"
RULES = {
    "categories": list(CATEGORIES),
    "top_k": 10,
    "extended_k": 20,
    "jaccard_max": 0.25,
    "positive_rank_gap_min": 10,
    "unjudged_top10_min": 5,
    "absolute_category_delta_contribution_min": 0.02,
    "large_tie_pool_min": 100,
    "positive_basis": "all historical positives; existing machine positives additionally retained",
    "negative_basis": "historical grade-zero in either tie-inclusive Top-20",
    "tie_policy": "exact stored score equality at each chosen prefix cutoff; never truncate",
    "ordering": "SHA256 canonical JSON [seed,presentation,annotation_id] ascending",
}
CHECKS = {
    "outdoor": "Prüfhinweise: Findet die angefragte Aktivität tatsächlich draußen statt? "
    "Garten/Open Air/unter freiem Himmel muss die Veranstaltung betreffen; "
    "eine Außenfläche des Veranstaltungsorts allein reicht nicht.",
    "theatre": "Prüfhinweise: Wenn eine Aufführung verlangt wird, tatsächliche "
    "Theateraufführung/staged performance belegen. Workshop, Basteln oder "
    "Theaterpädagogik dann nur als Teilaspekt bewerten; Venue-Typ Theater allein reicht nicht.",
    "venue": "Prüfhinweise: Den konkret angefragten Ort anhand der zulässigen Occurrence prüfen. "
    "Eine Erwähnung im Beschreibungstext von der tatsächlichen Location unterscheiden. "
    "Bloßer Kunst-/Musikbezug belegt den Ort nicht.",
    "accessibility": "Prüfhinweise: Die konkrete Zugänglichkeitsanforderung anhand "
    "dokumentierter Occurrence-/Space-/Venue-Evidenz prüfen. Einschränkungen "
    "nicht verschweigen oder auf andere Termine übertragen. Barrierearm "
    "belegt nicht automatisch vollständigen Rollstuhlzugang; konservativ bewerten.",
}


def verify():
    require(sha(PIN.read_bytes()) == PIN_SHA, "input_manifest_changed")
    pins = read(PIN)
    require(pins["baseline_main"] == BASELINE, "baseline_changed")
    for name, expected in pins["files"].items():
        require(sha(Path(name).read_bytes()) == expected, f"frozen_input_changed:{name}")
    return pins


def choose(a, b, category_count, extra_positives=()):
    """Symmetric, fixed rules. Explicit reference labels never enter blind evidence."""
    ranked = [{h["event_id"]: i + 1 for i, h in enumerate(r["ranking"])} for r in (a, b)]
    tops = [{h["event_id"] for h in r["ranking"][:10]} for r in (a, b)]
    require(set(a["grades"]) <= set(ranked[0]) == set(ranked[1]), "ranking_population")
    positives = {e for e, grade in a["grades"].items() if grade > 0} | set(extra_positives)
    require(positives <= set(ranked[0]), "positive_eligibility")
    jaccard = len(tops[0] & tops[1]) / len(tops[0] | tops[1]) if any(tops) else 1.0
    gap = max((abs(ranked[0][e] - ranked[1][e]) for e in positives), default=0)
    loss = bool(positives & (tops[0] ^ tops[1]))
    unknown = [len(t - set(a["grades"])) for t in tops]
    measured = [
        metrics(a["grades"], [h["event_id"] for h in r["ranking"]])["Recall@10"] for r in (a, b)
    ]
    contribution = (measured[1] - measured[0]) / category_count
    signals = {
        "low_top10_jaccard": jaccard <= RULES["jaccard_max"],
        "positive_rank_gap": gap >= RULES["positive_rank_gap_min"],
        "positive_top10_loss_either_model": loss,
        "material_category_contribution": abs(contribution)
        >= RULES["absolute_category_delta_contribution_min"],
        "many_unjudged_top10": max(unknown) >= RULES["unjudged_top10_min"],
    }
    k = 20 if any(signals.values()) else 10
    bare = {h["event_id"] for r in (a, b) for h in r["ranking"][:k]}
    with_ties = {h["event_id"] for r in (a, b) for h in tie_prefix(r["ranking"], k)}
    negative_window = {h["event_id"] for r in (a, b) for h in tie_prefix(r["ranking"], 20)}
    zeros = {e for e, grade in a["grades"].items() if grade == 0} & negative_window
    top10 = tops[0] | tops[1]
    extra_positive = positives - top10
    extra_negative = zeros - top10 - extra_positive
    extended = bare - top10 - extra_positive - extra_negative
    ties = with_ties - top10 - extra_positive - extra_negative - extended
    pool = top10 | extra_positive | extra_negative | extended | ties
    blocks = []
    for model, r in zip(("v3", "v5"), (a, b), strict=True):
        prefix = tie_prefix(r["ranking"], k)
        if len(prefix) > k:
            blocks.append(
                {
                    "model": model,
                    "cutoff": k,
                    "end_rank": len(prefix),
                    "score": prefix[-1]["score"],
                    "added_ids": [h["event_id"] for h in prefix[k:]],
                }
            )
    return {
        "ids": sorted(pool),
        "k": k,
        "signals": signals,
        "jaccard": jaccard,
        "max_positive_rank_gap": gap,
        "unjudged_top10": unknown,
        "category_delta_contribution": contribution,
        "tie_blocks": blocks,
        "large_tie_pool": bool(blocks) and len(pool) > RULES["large_tie_pool_min"],
        "groups": {
            "only_v3_top10": sorted(tops[0] - tops[1]),
            "only_v5_top10": sorted(tops[1] - tops[0]),
            "shared_top10": sorted(tops[0] & tops[1]),
            "additional_positives": sorted(extra_positive),
            "additional_negatives": sorted(extra_negative),
            "top20_extension": sorted(extended),
            "tie_extension": sorted(ties),
        },
    }


def coverage(runs, selection):
    sides = [{r["case_id"]: r for r in run["cases"]} for run in runs]
    before, target = {}, {}
    for cat in CATEGORIES:
        chosen = [r for r in selection if r["category"] == cat]
        b = {
            "evaluated_queries": len(chosen),
            "selected_queries": len(chosen),
            "pairs": sum(len(c["ids"]) for c in chosen),
            "models": {},
            "status": "selected" if chosen else "no_evaluable_cases",
        }
        t = {
            **b,
            "models": {},
            "condition": (
                "projection only: every selected task receives a valid grade; "
                "uncertain remains unknown"
            ),
        }
        for i, model in enumerate(("v3", "v5")):
            b["models"][model], t["models"][model] = {}, {}
            for k in (10, 20):
                values, projected = [], []
                for s in chosen:
                    r = sides[i][s["case_id"]]
                    ids = [h["event_id"] for h in r["ranking"][:k]]
                    known = set(r["grades"])
                    values.append(len(set(ids) & known) / len(ids))
                    projected.append(len(set(ids) & (known | set(s["ids"]))) / len(ids))
                b["models"][model][str(k)] = sum(values) / len(values) if values else None
                t["models"][model][str(k)] = sum(projected) / len(projected) if projected else None
        before[cat], target[cat] = b, t
    return before, target


def build():
    pins = verify()
    _, identity, cases, events, runs = load(Path("."))
    queries = {c["id"]: c for c in lines("benchmark/ground-truth-v1.jsonl")}
    rubrics = read("benchmark/annotation/machine-rubrics-v1.json")
    # Reuse the sealed source only for operator-side known-positive retention.
    from uranus_research_service.category_reassessment import load as reviewed_source

    _, judgments, existing_mapping, _, _ = reviewed_source()
    extra = {}
    for j in judgments:
        if j["grade"] > 0:
            m = existing_mapping[j["annotation_id"]]
            extra.setdefault(m["case_id"], set()).add(m["event_id"])
    targets = [c for c in cases if c["category"] in CATEGORIES and c["excluded"] is None]
    counts = Counter(c["category"] for c in targets)
    sides = [{c["case_id"]: c for c in run["cases"]} for run in runs]
    event_rows = {str(eid): row.model_dump(mode="json") for eid, row in events.items()}
    packet, mapping, selection, provenance = [], [], [], []
    for case in sorted(targets, key=lambda c: c["case_id"]):
        cid, cat = case["case_id"], case["category"]
        a, b = (s[cid] for s in sides)
        chosen = choose(a, b, counts[cat], extra.get(cid, ()))
        selection.append({"case_id": cid, "category": cat, "language": case["language"], **chosen})
        ranking = [
            {
                h["event_id"]: {"rank": i + 1, "score": h["score"]}
                for i, h in enumerate(r["ranking"])
            }
            for r in (a, b)
        ]
        for eid in chosen["ids"]:
            aid = order_key(SEED, "annotation", cid, eid)[:32]
            q, event = queries[cid], event_rows[eid]
            eligible = sorted(
                o["id"]
                for o in event["event"]["occurrences"]
                if o["id"] in case["eligible_occurrence_ids"]
            )
            require(eligible, "no_eligible_occurrence")
            mapping.append(
                {
                    "annotation_id": aid,
                    "case_id": cid,
                    "event_id": eid,
                    "document_hash": event["document_hash"],
                    "occurrence_sensitive": True,
                }
            )
            packet.append(
                {
                    "annotation_id": aid,
                    "query": q["query"],
                    "language": q["language"],
                    "reference_time": q["reference_time"],
                    "eligibility": q["eligibility"],
                    "event": {k: v for k, v in event["event"].items() if k != "id"},
                    "eligible_occurrence_ids": eligible,
                    "rubric": rubrics["rules"][rubrics["case_rubrics"][cid]] + " " + CHECKS[cat],
                    "scale": rubrics["scale"],
                }
            )
            provenance.append(
                {
                    "annotation_id": aid,
                    "case_id": cid,
                    "event_id": eid,
                    "category": cat,
                    "v3": ranking[0][eid],
                    "v5": ranking[1][eid],
                    "previous_grade": a["grades"].get(eid),
                    "existing_machine_positive": eid in extra.get(cid, ()),
                    "selection_reason": [
                        name for name, ids in chosen["groups"].items() if eid in ids
                    ],
                    "tie_block_reason": [
                        {k: v for k, v in block.items() if k != "added_ids"}
                        for block in chosen["tie_blocks"]
                        if eid in block["added_ids"]
                    ],
                    "source_artifacts": [
                        f"benchmark/results/{model}-20261006_8cpu_001.json"
                        for model in ("v3", "v5")
                    ],
                }
            )
    packet.sort(key=lambda r: order_key(SEED, "presentation", r["annotation_id"]))
    audit_blind(packet)
    for row in packet:
        BlindCandidate.model_validate(row)
    require(len(mapping) == len({(m["case_id"], m["event_id"]) for m in mapping}), "duplicate_pair")
    before, target = coverage(runs, selection)
    plan = {
        "schema_version": "category-coverage-review-v1",
        "status": "prepared-unjudged",
        "baseline_main": BASELINE,
        "input_manifest_sha256": PIN_SHA,
        "source_snapshot_hash": identity["source_snapshot_hash"],
        "source_hashes": pins["files"],
        "seed": SEED,
        "sampling": RULES,
        "mapping": mapping,
        "rubric_questions": [],
        "annotation_order": [p["annotation_id"] for p in packet],
        "packet_sha256": digest(packet),
        "case_ids": [c["case_id"] for c in targets],
        "atmosphere_overlap": [],
        "intent_checks": CHECKS,
    }
    report = {
        "status": "prepared-unjudged",
        "cases": selection,
        "pair_count": len(packet),
        "case_count": len(selection),
        "by_category": {
            cat: sum(len(c["ids"]) for c in selection if c["category"] == cat) for cat in CATEGORIES
        },
        "languages": dict(Counter(p["language"] for p in packet)),
        "top20_cases": sum(c["k"] == 20 for c in selection),
        "tie_cases": sum(bool(c["tie_blocks"]) for c in selection),
        "large_tie_cases": [c["case_id"] for c in selection if c["large_tie_pool"]],
        "group_totals": dict(
            sum(
                (Counter({k: len(v) for k, v in c["groups"].items()}) for c in selection), Counter()
            )
        ),
    }
    return plan, packet, provenance, report, before, target


def prepare(output):
    require(not output.exists(), "new_destination_required")
    plan, packet, provenance, report, before, target = build()
    for name, value in (
        ("review-plan.json", plan),
        ("provenance.json", provenance),
        ("selection-report.json", report),
        ("coverage-before.json", before),
        ("coverage-target.json", target),
        ("annotation-schema.json", ReviewBatch.model_json_schema()),
    ):
        atomic_new(output / name, value)
    atomic_new(output / "reviewer/blind-candidates.jsonl", packet, jsonl=True)
    atomic_new(
        output / "reviewer/annotation-package.json",
        {
            "schema_version": "phase2d-blind-package-v1",
            "package_sha256": digest(plan),
            "packet_sha256": digest(packet),
            "count": len(packet),
        },
    )
    with (output / "reviewer/review.html").open("xb") as stream:
        stream.write(Path("benchmark/annotation/phase2d/review.html").read_bytes())
    atomic_new(
        output / "artifact-sha256.json",
        {
            "code_sha256": sha(Path(__file__).read_bytes()),
            "files": {
                str(p.relative_to(output)): sha(p.read_bytes())
                for p in sorted(output.rglob("*"))
                if p.is_file()
            },
        },
    )


def checked(package):
    verify()
    index = read(package / "artifact-sha256.json")
    require(index["code_sha256"] == sha(Path(__file__).read_bytes()), "export_code_changed")
    actual = {
        str(p.relative_to(package)): sha(p.read_bytes())
        for p in package.rglob("*")
        if p.is_file() and p != package / "artifact-sha256.json"
    }
    require(index["files"] == actual, "package_changed")
    plan, packet = (
        read(package / "review-plan.json"),
        lines(package / "reviewer/blind-candidates.jsonl"),
    )
    require(digest(packet) == plan["packet_sha256"], "packet_changed")
    require(
        read(package / "reviewer/annotation-package.json")
        == {
            "schema_version": "phase2d-blind-package-v1",
            "package_sha256": digest(plan),
            "packet_sha256": digest(packet),
            "count": len(packet),
        },
        "package_binding",
    )
    require(
        set(p.name for p in (package / "reviewer").iterdir())
        == {"review.html", "blind-candidates.jsonl", "annotation-package.json"},
        "reviewer_file_leak",
    )
    expected = build()
    for name, value in zip(
        (
            "review-plan.json",
            "provenance.json",
            "selection-report.json",
            "coverage-before.json",
            "coverage-target.json",
        ),
        (expected[0], expected[2], expected[3], expected[4], expected[5]),
        strict=True,
    ):
        require(read(package / name) == value, "reproduction_mismatch")
    require(packet == expected[1], "evidence_reproduction_mismatch")
    require(
        read(package / "annotation-schema.json") == ReviewBatch.model_json_schema(), "answer_schema"
    )
    require(
        (package / "reviewer/review.html").read_bytes()
        == Path("benchmark/annotation/phase2d/review.html").read_bytes(),
        "review_ui_changed",
    )
    audit_blind(packet)
    return plan, packet


def prepare_machine(package, output, model, build_id):
    """Package existing generic worker inputs byte-for-byte; never calls a provider."""
    import re

    from uranus_research_service.machine_judge import PASSES, load_blind
    from uranus_research_service.machine_prepare import pilot_sample, schema

    require(re.fullmatch(r"[a-z0-9][a-z0-9.-]{1,99}", model), "explicit_model")
    require(re.fullmatch(r"[a-z0-9_-]{1,60}", build_id), "build_id")
    require(not output.exists(), "new_destination_required")
    bundle, packet = checked(package)
    blind = output / "blind"
    blind.mkdir(parents=True)
    source = Path("benchmark/annotation/phase2dm")
    for name in ("blind-candidates.jsonl", "annotation-package.json"):
        with (blind / name).open("xb") as f:
            f.write((package / "reviewer" / name).read_bytes())
    for name in ("judge-v1.txt", "pass-a.txt", "pass-b.txt", "pass-c.txt"):
        with (blind / name).open("xb") as f:
            f.write((source / "prompt" / name).read_bytes())
    policy = read(source / "policy-v1.json")
    atomic_new(blind / "policy-v1.json", policy)
    atomic_new(blind / "judge-v1.schema.json", schema())
    ids, strata = pilot_sample(packet, policy["dry_seed"])
    plan = {
        "schema_version": "phase2dm-plan-v1",
        "worker_sha256": sha(Path(__file__).with_name("machine_judge.py").read_bytes()),
        "model": model,
        "build_id": build_id,
        "package_sha256": digest(bundle),
        "blind_files": {p.name: sha(p.read_bytes()) for p in sorted(blind.iterdir())},
        "historical_inputs_sha256": PIN_SHA,
        "pair_count": len(packet),
        "judgment_count": len(packet) * 3,
        "dry_annotation_ids": ids,
        "pilot_strata": strata,
        "run_ids": {name: f"{build_id}-{name}" for name in PASSES},
        "settings": {
            k: policy[k]
            for k in ("temperature", "reasoning_effort", "max_output_tokens", "max_attempts")
        },
        "status": "prepared-not-authorized",
        "provenance": "machine-only-not-human",
        "planned_passes": ["machine-a", "machine-b"],
        "legacy_budget_note": (
            "existing worker retains three-pass cost approval envelope; "
            "only A/B are planned; no approval created"
        ),
    }
    atomic_new(blind / "plan.json", plan)
    load_blind(blind)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command", choices=("prepare", "validate", "validate-review", "prepare-machine")
    )
    parser.add_argument("--package", type=Path, default=DEST)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--input", type=Path)
    parser.add_argument("--model")
    parser.add_argument("--build-id")
    args = parser.parse_args()
    if args.command == "prepare":
        prepare(args.output or DEST)
    elif args.command == "prepare-machine":
        require(args.output and args.model and args.build_id, "machine_preparation_arguments")
        prepare_machine(args.package, args.output, args.model, args.build_id)
    else:
        plan, packet = checked(args.package)
        if args.command == "validate-review":
            require(args.input, "review_input_required")
            batch = validate_batch(read(args.input), plan, packet)
            print(f"Valid human-declared batch: {len(batch.answers)}/{len(packet)} entries")
        else:
            print(f"Valid blind package: {len(packet)} pairs")


if __name__ == "__main__":
    main()
