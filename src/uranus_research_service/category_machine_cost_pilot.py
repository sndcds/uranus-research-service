"""Twenty requests for usage calibration only. All judgment content is discarded."""

import argparse
import asyncio
import fcntl
import math
import os
import time
from collections import Counter
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Literal

from pydantic import Field, StrictBool, StrictInt

from uranus_research_service import category_machine_execution as ab
from uranus_research_service.machine_blind_review import parse
from uranus_research_service.machine_judge import (
    APIError,
    Closed,
    atomic_new,
    digest,
    encoded,
    read,
    require,
    safe_id,
    sha,
    usage_of,
)

BASELINE = "29c5063f81bacabc884fba7f7a4bcd0941d66ed5"
DEST = Path("benchmark/review/category-coverage-cost-pilot-v1")
PURPOSE = "cost-calibration-pilot"
SEED = "category-coverage-cost-pilot-v1"
COUNT = 20
CATEGORIES = ("accessibility", "outdoor", "theatre", "venue")
BOUNDS = (0, 301, 602, 1129, 1430, 1506)
REPORT_SHA = "c224cfb23ff0aa5769c569c4d0113da32dc03a2457ca00deb8debd8ec6b79f00"


class PilotApproval(Closed):
    schema_version: Literal["category-cost-pilot-approval-v1"]
    purpose: Literal["cost-calibration-pilot"]
    approved: StrictBool
    pilot_only: StrictBool
    approval_reference: str = Field(min_length=1, max_length=1000)
    model: Literal[ab.MODEL]
    request_count: Literal[20]
    selection_sha256: str
    packet_sha256: str
    prompt_sha256: str
    code_sha256: str
    max_input_tokens: StrictInt = Field(gt=0)
    max_output_tokens: StrictInt = Field(gt=0)
    execution_root: str


class Prices(Closed):
    currency: Literal["USD"]
    input_per_million: str = Field(pattern=r"^\d+(\.\d+)?$")
    cached_input_per_million: str = Field(pattern=r"^\d+(\.\d+)?$")
    output_per_million: str = Field(pattern=r"^\d+(\.\d+)?$")


def now():
    return datetime.now(UTC).isoformat()


def code_hash():
    return digest({**ab.code_hashes(), "pilot": sha(Path(__file__).read_bytes())})


def select(shapes, categories):
    """Only ID, payload size/hash and category enter selection; never evidence or grades."""
    require(len(shapes) == ab.COUNT and len(categories) == ab.COUNT, "population_count")
    ordered = sorted(shapes, key=lambda r: (r["payload_bytes"], r["annotation_id"]))
    universe, selected = [], []
    for band, (lo, hi) in enumerate(zip(BOUNDS[:-1], BOUNDS[1:], strict=True)):
        rows = [
            {**r, "category": categories[r["annotation_id"]], "stratum": band}
            for r in ordered[lo:hi]
        ]
        universe.extend(rows)
        # First four bands: one of each category. Largest band: two accessibility,
        # one theatre, one venue. Fixed before any API response, no grade-dependent choice.
        quota = CATEGORIES if band < 4 else ("accessibility", "accessibility", "theatre", "venue")
        used = set()
        for category in quota:
            options = [
                r for r in rows if r["category"] == category and r["annotation_id"] not in used
            ]
            require(options, "stratum_category_unavailable")
            row = min(options, key=lambda r: digest([SEED, "select", r["annotation_id"]]))
            selected.append(row)
            used.add(row["annotation_id"])
    selected.sort(key=lambda r: digest([SEED, "order", r["annotation_id"]]))
    require(len({r["annotation_id"] for r in selected}) == COUNT, "selection_count")
    return universe, selected


def selection_for(package):
    contract, _, _, _, shapes = ab.load_execution(package, ab.DEST, ab.MODEL)
    plan_path, report_path = package / "review-plan.json", package / "selection-report.json"
    require(sha(plan_path.read_bytes()) == ab.PLAN_SHA, "operator_plan_changed")
    require(sha(report_path.read_bytes()) == REPORT_SHA, "category_membership_changed")
    cats = {r["case_id"]: r["category"] for r in read(report_path)["cases"]}
    mapping = {r["annotation_id"]: cats[r["case_id"]] for r in read(plan_path)["mapping"]}
    require(len(cats) == 20 and set(cats.values()) == set(CATEGORIES), "categories")
    universe, selected = select(shapes, mapping)
    return {
        "schema_version": "category-cost-pilot-selection-v1",
        "purpose": PURPOSE,
        "baseline_main": BASELINE,
        "model": ab.MODEL,
        "packet_sha256": ab.PACKET_SHA,
        "prompt_sha256": contract["prompt_sha256"],
        "contract_sha256": sha((ab.DEST / "execution-contract.json").read_bytes()),
        "conservative_cost_report_sha256": sha((ab.DEST / "cost-report.json").read_bytes()),
        "code_sha256": code_hash(),
        "seed": SEED,
        "algorithm": "size-strata-fixed-category-quotas-sha256-v1",
        "stratum_rank_boundaries": list(BOUNDS),
        "request_count": COUNT,
        "max_attempts_per_request": 1,
        "judgment_use": "operationally_discarded",
        "population": universe,
        "selected": selected,
        "category_counts": dict(sorted(Counter(r["category"] for r in selected).items())),
        "payload_bytes": ab.distribution([r["payload_bytes"] for r in selected]),
        "max_input_tokens": sum(r["estimated_input_tokens"] for r in selected),
        "max_output_tokens": COUNT * ab.OUTPUT_CAP,
    }


def prepare(package, output):
    require(not output.exists(), "output_exists")
    # Sibling directory: both older packages have sealed exact-directory contracts.
    require(not output.resolve().is_relative_to(package.resolve()), "frozen_pool_output")
    require(not output.resolve().is_relative_to(ab.DEST.resolve()), "frozen_contract_output")
    s = selection_for(package)
    atomic_new(output / "pilot-selection.json", s)
    atomic_new(output / "pilot-approval-schema.json", PilotApproval.model_json_schema())
    return s


def load_selection(pilot, package):
    s = read(pilot / "pilot-selection.json")
    require(s == selection_for(package), "pilot_selection_changed")
    return s


def authorize(raw, selection, selection_sha, output, model):
    a = PilotApproval.model_validate(raw).model_dump()
    require(a["approved"] is True and a["pilot_only"] is True, "pilot_approval_required")
    require(type(raw["request_count"]) is int, "request_count")
    require(a["approval_reference"].strip(), "approval_reference")
    require(model == a["model"] == selection["model"] == ab.MODEL, "model_binding")
    for key in ("packet_sha256", "prompt_sha256", "code_sha256"):
        require(a[key] == selection[key], "approval_binding")
    require(a["selection_sha256"] == selection_sha, "selection_binding")
    for key in ("max_input_tokens", "max_output_tokens"):
        require(a[key] >= selection[key], "budget_insufficient")
    root = Path(a["execution_root"])
    require(root.is_absolute() and output.resolve() == root.resolve(), "execution_root")
    require(not output.resolve().is_relative_to(Path("benchmark").resolve()), "external_run_only")
    return a


def usage(body):
    values = usage_of(body)
    require(set(values) == {"input_tokens", "output_tokens", "total_tokens"}, "usage_missing")
    require(values["total_tokens"] == values["input_tokens"] + values["output_tokens"], "usage_sum")
    for field, parent, child, ceiling in (
        ("cached_input_tokens", "input_tokens_details", "cached_tokens", "input_tokens"),
        ("reasoning_tokens", "output_tokens_details", "reasoning_tokens", "output_tokens"),
    ):
        value = body["usage"].get(parent, {}).get(child)
        require(
            value is None or type(value) is int and 0 <= value <= values[ceiling], "usage_details"
        )
        values[field] = value
    return values


async def run(pilot, package, approval, output, model, client, *, resume=False):
    s = load_selection(pilot, package)
    selection_sha = sha((pilot / "pilot-selection.json").read_bytes())
    a = authorize(read(approval), s, selection_sha, output, model)
    packet, _ = ab.load_packet(package)
    candidates = {r["annotation_id"]: r for r in packet}
    prompt = ab.PROMPT.read_text()
    config = {
        "purpose": PURPOSE,
        "run_id": SEED + "-" + selection_sha[:16],
        "selection_sha256": selection_sha,
        "approval_sha256": sha(approval.read_bytes()),
        "model": model,
        "code_sha256": code_hash(),
        "parameters": {
            k: v
            for k, v in ab.request_for(packet[0], model, prompt).items()
            if k not in ("input", "instructions", "text")
        },
        "request_limit": COUNT,
        "judgment_use": "operationally_discarded",
    }
    require(resume == output.exists(), "explicit_resume_or_new_directory_required")
    output.mkdir(parents=True, exist_ok=True)
    with (output / ".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        manifest = output / "pilot-run.json"
        if manifest.exists():
            require(read(manifest)["configuration"] == config, "resume_binding")
        else:
            require(not resume, "missing_resume_manifest")
            atomic_new(manifest, {"configuration": config, "started_at": now()})
        spent_input = spent_output = 0
        for ordinal, row in enumerate(s["selected"], 1):
            aid = row["annotation_id"]
            record_path = output / "records" / f"{ordinal:02}.json"
            reservation_path = output / "reservations" / f"{ordinal:02}.json"
            reservation = {
                "ordinal": ordinal,
                "annotation_id": aid,
                "configuration_sha256": digest(config),
                "payload_sha256": row["payload_sha256"],
            }
            spent_input += row["estimated_input_tokens"]
            spent_output += ab.OUTPUT_CAP
            require(
                spent_input <= a["max_input_tokens"] and spent_output <= a["max_output_tokens"],
                "budget_exceeded",
            )
            if reservation_path.exists():
                require(read(reservation_path) == reservation, "reservation_binding")
                # Even an interrupted send consumes its slot. Never resend on resume.
                require(record_path.exists(), "interrupted_attempt_requires_operator_audit")
                require(read(record_path)["reservation"] == reservation, "record_binding")
                require(
                    read(record_path)["status"] == "schema_validated_content_discarded",
                    "previous_failure_terminal",
                )
                continue
            require(not record_path.exists(), "orphan_record")
            candidate = candidates[aid]
            payload = ab.request_for(candidate, model, prompt)
            require(sha(ab.wire(payload)) == row["payload_sha256"], "payload_changed")
            atomic_new(reservation_path, reservation)
            start = time.monotonic()
            record = {
                "reservation": reservation,
                "purpose": PURPOSE,
                "timestamp": now(),
                "retries": 0,
                "status": "failed",
                "usage": None,
            }
            try:
                body, request_id = await client.request(
                    "POST", "responses", payload, f"{config['run_id']}-{ordinal:02}"
                )
                record.update(
                    request_id=safe_id(request_id),
                    response_id=safe_id(body.get("id")),
                    model=model if body.get("model") == model else None,
                    usage=usage(body),
                    service_tier=body.get("service_tier")
                    if body.get("service_tier") in ("default", "flex", "priority", "scale")
                    else None,
                )
                require(record["response_id"], "response_id_missing")
                # Validate precisely the A/B schema, but never persist its answer or raw body.
                parse(body, candidate, model)
                require(
                    record["usage"]["input_tokens"] <= row["estimated_input_tokens"]
                    and record["usage"]["output_tokens"] <= ab.OUTPUT_CAP,
                    "usage_exceeded",
                )
                record["status"] = "schema_validated_content_discarded"
            except APIError as exc:
                record["error_category"] = exc.category
            except (ValueError, TypeError, KeyError):
                record["error_category"] = "response_contract"
            record["latency_ms"] = round((time.monotonic() - start) * 1000, 3)
            atomic_new(record_path, record)
            print(f"pilot {ordinal}/{COUNT}: {record['status']}", flush=True)
            if record["status"] == "failed":
                # No retry, repair, fallback, or continuation after a provider/contract failure.
                return
        publish_usage(output, s)


def validate_records(output, selection):
    config = read(output / "pilot-run.json")["configuration"]
    require(
        config["purpose"] == PURPOSE and config["request_limit"] == COUNT, "pilot_configuration"
    )
    require(
        config["model"] == selection["model"] and config["code_sha256"] == selection["code_sha256"],
        "pilot_code_model",
    )
    require(config["selection_sha256"] == sha(encoded(selection) + b"\n"), "run_selection")
    require(
        {f.name for f in (output / "reservations").iterdir()}
        == {f"{i:02}.json" for i in range(1, COUNT + 1)},
        "reservation_count",
    )
    records = [read(output / "records" / f"{i:02}.json") for i in range(1, COUNT + 1)]
    require(all(r["status"] == "schema_validated_content_discarded" for r in records), "incomplete")
    require(len({r["response_id"] for r in records}) == COUNT, "duplicate_response")
    for ordinal, (record, selected) in enumerate(
        zip(records, selection["selected"], strict=True), 1
    ):
        reservation = {
            "ordinal": ordinal,
            "annotation_id": selected["annotation_id"],
            "configuration_sha256": digest(config),
            "payload_sha256": selected["payload_sha256"],
        }
        require(
            record["reservation"]
            == read(output / "reservations" / f"{ordinal:02}.json")
            == reservation,
            "record_reservation",
        )
        require(
            record["purpose"] == PURPOSE
            and record["model"] == selection["model"]
            and record["retries"] == 0,
            "record_identity",
        )
        u = record["usage"]
        restored = {
            "usage": {
                **{k: u[k] for k in ("input_tokens", "output_tokens", "total_tokens")},
                "input_tokens_details": {"cached_tokens": u["cached_input_tokens"]},
                "output_tokens_details": {"reasoning_tokens": u["reasoning_tokens"]},
            }
        }
        require(usage(restored) == u, "record_usage")
        require(
            u["input_tokens"] <= selected["estimated_input_tokens"]
            and u["output_tokens"] <= ab.OUTPUT_CAP,
            "record_budget",
        )
    return records


def publish_usage(output, selection):
    records = validate_records(output, selection)
    result = {
        "purpose": PURPOSE,
        "judgment_use": "operationally_discarded",
        "count": COUNT,
        "records": records,
        "selection_sha256": sha(encoded(selection) + b"\n"),
        "totals": {
            k: sum(r["usage"][k] for r in records)
            if all(r["usage"][k] is not None for r in records)
            else None
            for k in records[0]["usage"]
        },
    }
    for name, value, jsonl in (
        ("pilot-usage.json", result, False),
        ("pilot-request-ledger.jsonl", records, True),
    ):
        path = output / name
        if path.exists():
            from uranus_research_service.machine_judge import read_lines

            require((read_lines(path) if jsonl else read(path)) == value, "published_usage_changed")
        else:
            atomic_new(path, value, jsonl=jsonl)
    return result


def price(input_tokens, output_tokens, cached_tokens, prices):
    return (
        (Decimal(str(input_tokens)) - Decimal(str(cached_tokens)))
        * Decimal(prices["input_per_million"])
        + Decimal(str(cached_tokens)) * Decimal(prices["cached_input_per_million"])
        + Decimal(str(output_tokens)) * Decimal(prices["output_per_million"])
    ) / Decimal(1000000)


def analyze(selection, usage_report, cost, prices):
    prices = Prices.model_validate(prices).model_dump()
    require(usage_report["purpose"] == PURPOSE and usage_report["count"] == COUNT, "pilot_only")
    require(usage_report["selection_sha256"] == sha(encoded(selection) + b"\n"), "usage_selection")
    rows = usage_report["records"]
    require(len(rows) == COUNT and len({r["response_id"] for r in rows}) == COUNT, "usage_count")
    by_id = {r["reservation"]["annotation_id"]: r for r in rows}
    require(set(by_id) == {r["annotation_id"] for r in selection["selected"]}, "usage_ids")
    cells = {}
    request_costs = []
    for s in selection["selected"]:
        r = by_id[s["annotation_id"]]
        require(r["status"] == "schema_validated_content_discarded", "pilot_incomplete")
        require(
            r.get("service_tier") in (None, "default"), "nonstandard_tier_needs_separate_prices"
        )
        u = r["usage"]
        require(r["reservation"]["payload_sha256"] == s["payload_sha256"], "usage_payload")
        for key in ((s["stratum"], s["category"]), (s["stratum"], None)):
            cells.setdefault(key, []).append((u, s["payload_bytes"]))
        request_costs.append(
            {
                "annotation_id": s["annotation_id"],
                "amount_usd": str(
                    price(
                        u["input_tokens"], u["output_tokens"], u["cached_input_tokens"] or 0, prices
                    )
                ),
            }
        )
    projections = {}
    for scenario in ("lower", "central", "upper"):
        inputs = outputs = cached = 0.0
        fallback = []
        for row in selection["population"]:
            key = (row["stratum"], row["category"])
            if key not in cells:
                key = (row["stratum"], None)
                fallback.append(row["annotation_id"])
            observations = cells[key]
            ratios = [u["input_tokens"] / size for u, size in observations]
            lengths = [u["output_tokens"] for u, _ in observations]
            cache_rates = [
                (u["cached_input_tokens"] or 0) / u["input_tokens"] for u, _ in observations
            ]
            aggregate = (
                min
                if scenario == "lower"
                else max
                if scenario == "upper"
                else lambda v: sum(v) / len(v)
            )
            count = aggregate(ratios) * row["payload_bytes"]
            inputs += 2 * count
            outputs += 2 * aggregate(lengths)
            cached += (
                2
                * count
                * (
                    max(cache_rates)
                    if scenario == "lower"
                    else 0
                    if scenario == "upper"
                    else sum(cache_rates) / len(cache_rates)
                )
            )
        projections[scenario] = {
            "projected_input_tokens": math.ceil(inputs),
            "projected_output_tokens": math.ceil(outputs),
            "projected_cached_tokens": math.floor(cached),
            "amount_usd": str(
                price(math.ceil(inputs), math.ceil(outputs), math.floor(cached), prices)
            ),
            "amount_without_cache_usd": str(
                price(math.ceil(inputs), math.ceil(outputs), 0, prices)
            ),
            "fallback_to_size_stratum_ids": fallback,
        }
    amounts = [Decimal(r["amount_usd"]) for r in request_costs]
    ceiling = price(
        cost["estimated_input_tokens"], cost["estimated_output_token_ceiling"], 0, prices
    )
    return {
        "purpose": PURPOSE,
        "prices": prices,
        "request_costs": request_costs,
        "pilot_amount_usd": str(sum(amounts)),
        "mean_amount_usd": str(sum(amounts) / COUNT),
        "median_amount_usd": str((sorted(amounts)[9] + sorted(amounts)[10]) / 2),
        "p95_amount_usd": str(sorted(amounts)[18]),
        "usage_totals": usage_report["totals"],
        "input_token_distribution": ab.distribution([r["usage"]["input_tokens"] for r in rows]),
        "output_token_distribution": ab.distribution([r["usage"]["output_tokens"] for r in rows]),
        "token_per_byte_ratios": {
            s["annotation_id"]: by_id[s["annotation_id"]]["usage"]["input_tokens"]
            / s["payload_bytes"]
            for s in selection["selected"]
        },
        "projection_requests": 3012,
        "projection_method": (
            "size-stratum/category token-per-byte and output mean; empty cell uses size stratum"
        ),
        "empirical": projections,
        "conservative_contract": {
            "cost_report_sha256": selection["conservative_cost_report_sha256"],
            "input_tokens": cost["estimated_input_tokens"],
            "output_tokens": cost["estimated_output_token_ceiling"],
            "amount_usd": str(ceiling),
        },
        "central_to_ceiling_ratio": str(Decimal(projections["central"]["amount_usd"]) / ceiling)
        if ceiling
        else None,
        "limits": [
            "20/1506, category quotas and large accessibility payloads; not a confidence interval",
            "lower/upper: observed cell extrema, not bounds; many cells have one observation",
            "cached discount may not recur; no-cache central reported separately",
            "output and prices may change; costs are tariff calculations, not invoices",
            "original byte-based contract ceiling remains a separate planning safety estimate",
            "no retries projected; missing cache detail priced as uncached",
        ],
        "judgment_use": "operationally_discarded",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("prepare")
    p.add_argument("--package", type=Path, default=ab.PACKAGE)
    p.add_argument("--output", type=Path, required=True)
    r = sub.add_parser("run")
    r.add_argument("--package", type=Path, default=ab.PACKAGE)
    r.add_argument("--pilot", type=Path, required=True)
    r.add_argument("--approval", type=Path, required=True)
    r.add_argument("--model", required=True, choices=[ab.MODEL])
    r.add_argument("--output", type=Path, required=True)
    r.add_argument("--resume", action="store_true")
    a = sub.add_parser("analyze")
    a.add_argument("--pilot", type=Path, required=True)
    a.add_argument("--pilot-run", type=Path, required=True)
    a.add_argument("--input-price-per-million", required=True)
    a.add_argument("--cached-input-price-per-million", required=True)
    a.add_argument("--output-price-per-million", required=True)
    a.add_argument("--output", type=Path, required=True)
    v = sub.add_parser("validate")
    v.add_argument("--pilot", type=Path, required=True)
    v.add_argument("--pilot-run", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "prepare":
        prepare(args.package, args.output)
    elif args.command == "validate":
        s = load_selection(args.pilot, ab.PACKAGE)
        validate_records(args.pilot_run, s)
        print("20 pilot usage records validated; no judgments retained")
    elif args.command == "analyze":
        s = load_selection(args.pilot, ab.PACKAGE)
        validate_records(args.pilot_run, s)
        result = analyze(
            s,
            read(args.pilot_run / "pilot-usage.json"),
            read(ab.DEST / "cost-report.json"),
            {
                "currency": "USD",
                "input_per_million": args.input_price_per_million,
                "cached_input_per_million": args.cached_input_price_per_million,
                "output_per_million": args.output_price_per_million,
            },
        )
        atomic_new(args.output, result)
    else:
        # Validate approval before constructing any network client or reading the key.
        s = load_selection(args.pilot, args.package)
        authorize(
            read(args.approval),
            s,
            sha((args.pilot / "pilot-selection.json").read_bytes()),
            args.output,
            args.model,
        )

        async def execute():
            client = ab.CategoryJudge(os.environ.get("OPENAI_API_KEY", ""))
            try:
                await run(
                    args.pilot,
                    args.package,
                    args.approval,
                    args.output,
                    args.model,
                    client,
                    resume=args.resume,
                )
            finally:
                await client.close()

        asyncio.run(execute())


if __name__ == "__main__":
    main()
