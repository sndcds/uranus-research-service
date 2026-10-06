"""Separate machine-only operator workflow; no service request-path integration."""

import argparse
import asyncio
import os
from pathlib import Path

from uranus_research_service.machine_judge import (
    PASSES,
    APIError,
    OpenAIJudge,
    atomic_new,
    digest,
    load_blind,
    read,
    read_lines,
    require,
    run_pass,
)


async def execute(args):
    plan, _ = load_blind(args.work / "blind")
    require(args.model == plan["model"], "explicit_model_must_match_plan")
    approval = None
    if args.purpose == "full":
        require(args.approval is not None, "full_run_cost_approval_required")
        approval = read(args.approval)
        report = read(args.work / "dry-run.json")
        require(
            approval.get("dry_report_sha256") == digest(report), "cost_approval_report_mismatch"
        )
        require(report["plan_sha256"] == digest(plan), "cost_report_plan_mismatch")
    key = os.environ.get("OPENAI_API_KEY")
    require(key, "OPENAI_API_KEY_required")
    client = OpenAIJudge(key)
    try:
        names = PASSES if args.pass_name == "all" else (args.pass_name,)
        for name in names:
            run_id = plan["run_ids"][name] + ("-pilot" if args.purpose == "dry-run" else "")
            rows = await run_pass(
                args.work / "blind",
                args.work / args.purpose / name,
                name,
                run_id,
                args.purpose,
                client,
                approval=approval,
            )
            print(f"{name}: {len(rows)} completed {args.purpose} judgments")
    finally:
        await client.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "run", "cost", "seal", "evaluate"))
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--model")
    parser.add_argument("--build-id")
    parser.add_argument("--purpose", choices=("dry-run", "full"), default="dry-run")
    parser.add_argument("--pass-name", choices=(*PASSES, "all"), default="all")
    parser.add_argument("--approval", type=Path)
    parser.add_argument("--pricing", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "prepare":
            from uranus_research_service.machine_prepare import prepare

            require(args.model and args.build_id, "explicit_model_and_build_id_required")
            plan = prepare(args.root, args.work, args.model, args.build_id)
            print(f"Prepared {plan['pair_count']} blind pairs; full run is not approved.")
        elif args.command == "run":
            asyncio.run(execute(args))
        elif args.command == "cost":
            from uranus_research_service.machine_prepare import dry_report

            plan, _ = load_blind(args.work / "blind")
            rows, attempts = [], []
            for name in PASSES:
                path = args.work / "dry-run" / name
                rows.extend(read_lines(path / f"{name}.jsonl"))
                attempts.extend(read(p) for p in sorted((path / "attempts").glob("*.result.json")))
            report = dry_report(plan, rows, attempts, read(args.pricing) if args.pricing else None)
            atomic_new(args.work / "dry-run.json", report)
            print("Pilot cost report saved. STOP: explicit full-run cost approval is required.")
        elif args.command == "seal":
            from uranus_research_service.machine_consensus import seal

            require(args.output, "new_output_directory_required")
            seal(args.work, args.output)
            print("Machine-only consensus sealed; no human approval asserted.")
        else:
            from uranus_research_service.machine_analysis import evaluate

            require(args.output, "new_output_directory_required")
            result = evaluate(args.root, args.work, args.work / "consensus", args.output)
            print(f"Exploratory-only evaluation; {result['triage_count']} blind review pairs.")
    except (ValueError, APIError, KeyError, FileNotFoundError, FileExistsError, BlockingIOError):
        # Provider bodies / validation inputs must never reach console logs.
        parser.exit(
            2,
            "Operation stopped: input, approval, provider or resume validation failed. "
            "Inspect safe per-attempt metadata; no fallback was used.\n",
        )


if __name__ == "__main__":
    main()
