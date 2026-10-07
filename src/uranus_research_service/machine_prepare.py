"""Offline operator preparation; never imported by the blind API worker."""

import shutil
from collections import defaultdict
from datetime import date

from uranus_research_service.machine_judge import (
    PASSES,
    Judgment,
    atomic_new,
    digest,
    encoded,
    read,
    read_lines,
    require,
    sha,
)

ROOT_PATH = "benchmark/annotation/phase2dm"
PINS = "benchmark/contracts/phase2dm-input-sha256.json"


def verify_historical(root):
    pins = read(root / PINS)
    for path, checksum in pins["files"].items():
        require((root / path).resolve().is_relative_to(root.resolve()), "input_path")
        require(sha((root / path).read_bytes()) == checksum, "historical_input_changed")
    return pins


def schema():
    result = Judgment.model_json_schema()
    from uranus_research_service.machine_judge import SUPPORT

    result["properties"]["supporting_fields"]["items"] = {"type": "string", "enum": list(SUPPORT)}
    return result


def pilot_sample(packet, seed):
    by_language = defaultdict(list)
    for p in packet:
        by_language[p["language"]].append(p)
    selected, strata = [], {}
    for language, values in sorted(by_language.items()):
        values.sort(key=lambda p: (len(encoded(p)), p["annotation_id"]))
        buckets = defaultdict(list)
        for index, p in enumerate(values):
            bucket = f"{language}-length-q{min(3, index * 4 // len(values)) + 1}"
            buckets[bucket].append(p)
            strata[p["annotation_id"]] = bucket
        for values in buckets.values():
            selected.append(
                min(values, key=lambda p: digest([seed, p["annotation_id"]]))["annotation_id"]
            )
    return sorted(selected), strata


def prepare(root, destination, model, build_id):
    import re

    require(re.fullmatch(r"[a-z0-9][a-z0-9.-]{1,99}", model), "explicit_model_required")
    require(re.fullmatch(r"[a-z0-9_-]{1,60}", build_id), "build_id")
    require(not destination.exists(), "new_preparation_directory_required")
    pins = verify_historical(root)
    source = root / "benchmark/annotation/phase2d"
    packet = read_lines(source / "blind-candidates.jsonl")
    policy = read(root / ROOT_PATH / "policy-v1.json")
    ids, strata = pilot_sample(packet, policy["dry_seed"])
    destination.mkdir(parents=True)
    blind = destination / "blind"
    blind.mkdir()
    for name in ("blind-candidates.jsonl", "annotation-package.json"):
        shutil.copyfile(source / name, blind / name)
    for name in ("judge-v1.txt", "pass-a.txt", "pass-b.txt", "pass-c.txt"):
        shutil.copyfile(root / ROOT_PATH / "prompt" / name, blind / name)
    shutil.copyfile(root / ROOT_PATH / "policy-v1.json", blind / "policy-v1.json")
    atomic_new(blind / "judge-v1.schema.json", schema())
    files = {p.name: sha(p.read_bytes()) for p in sorted(blind.iterdir())}
    plan = {
        "schema_version": "phase2dm-plan-v1",
        "worker_sha256": sha((root / "src/uranus_research_service/machine_judge.py").read_bytes()),
        "model": model,
        "build_id": build_id,
        "package_sha256": read(source / "annotation-package.json")["package_sha256"],
        "blind_files": files,
        "historical_inputs_sha256": digest(pins),
        "pair_count": len(packet),
        "judgment_count": len(packet) * 3,
        "dry_annotation_ids": ids,
        "pilot_strata": strata,
        "run_ids": {name: f"{build_id}-{name}" for name in PASSES},
        "settings": {
            k: policy[k]
            for k in ("temperature", "reasoning_effort", "max_output_tokens", "max_attempts")
        },
        "status": "prepared-not-cost-approved",
        "provenance": "machine-only-not-human",
    }
    # Model-free categories for pre-deblinding bias reports. Never given to the API worker.
    mapping = read(source / "blind-mapping.json")
    cases = {c["case_id"]: c for c in mapping["selection"]["cases"]}
    public = {p["annotation_id"]: p for p in packet}
    annotations = {}
    for row in mapping["mapping"]:
        c, p = cases[row["case_id"]], public[row["annotation_id"]]
        size = len(encoded(p["event"]))
        annotations[row["annotation_id"]] = {
            "language": c["language"],
            "category": c["category"],
            "text_length_bin": "short" if size < 2000 else "medium" if size < 8000 else "long",
        }
    plan["bias_strata_sha256"] = digest(annotations)
    atomic_new(blind / "plan.json", plan)
    atomic_new(destination / "bias-strata.json", annotations)
    return plan


def dry_report(plan, rows, attempts, pricing=None):
    expected = {(p, aid) for p in PASSES for aid in plan["dry_annotation_ids"]}
    require(
        {(r["pass_name"], r["annotation_id"]) for r in rows} == expected
        and len(rows) == len(expected),
        "incomplete_pilot",
    )
    require(
        all(r["purpose"] == "dry-run" and r["plan_sha256"] == digest(plan) for r in rows),
        "pilot_identity",
    )
    counts = defaultdict(int)
    for bucket in plan["pilot_strata"].values():
        counts[bucket] += 1
    projected = {
        k: sum(r["usage"][k] * counts[plan["pilot_strata"][r["annotation_id"]]] for r in rows)
        for k in ("input_tokens", "output_tokens")
    }
    result = {
        "schema_version": "phase2dm-dry-report-v1",
        "status": "pilot-only-awaiting-cost-approval",
        "model": plan["model"],
        "plan_sha256": digest(plan),
        "candidates": len(plan["dry_annotation_ids"]),
        "requests_succeeded": len(rows),
        "judgments_sha256": digest(rows),
        "attempts_sha256": digest(attempts),
        "failed_attempts": sum(r["status"] != "success" for r in attempts),
        "mean_input_tokens": sum(r["usage"]["input_tokens"] for r in rows) / len(rows),
        "mean_output_tokens": sum(r["usage"]["output_tokens"] for r in rows) / len(rows),
        "projected_full_tokens_no_retries": projected,
        "projection_method": "population-weighted language/length strata; "
        "one sample per stratum per pass",
        "full_judgments": plan["judgment_count"],
        "estimated_usd": None,
        "limit": "Small pilot; no calibrated uncertainty interval. Retries may cost extra; "
        "caches/tax excluded. Pilot judgments are not full-run labels.",
    }
    if pricing:
        require(pricing["model"] == plan["model"], "pricing_model")
        require(pricing["currency"] == "USD" and pricing["tier"] == "standard", "pricing_tier")
        require(
            0 <= (date.today() - date.fromisoformat(pricing["verified_on"])).days <= 7,
            "pricing_stale",
        )
        require(
            all(
                type(pricing[k]) in (int, float) and pricing[k] >= 0
                for k in ("input_usd_per_million", "output_usd_per_million")
            ),
            "pricing_rates",
        )
        result["pricing"] = pricing
        result["estimated_usd"] = sum(
            projected[k] * pricing[f"{k.removesuffix('_tokens')}_usd_per_million"] / 1e6
            for k in projected
        )
        result["retry_stress_estimate_usd"] = result["estimated_usd"] * 3
    return result
