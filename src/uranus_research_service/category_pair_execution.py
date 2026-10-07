"""Single-attempt transport over the frozen paired Ledger; no independent budget rules."""

import argparse
import asyncio
import os
from collections import Counter
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from time import monotonic

from uranus_research_service import category_pair_budget as budget
from uranus_research_service.machine_blind_analysis import classify
from uranus_research_service.machine_judge import APIError, atomic_new, digest, read, require, sha

BASELINE = "c3612692b01da36e69358c6991c10d4c9d3f44d6"


def binding(approval):
    return {
        "schema_version": "category-pair-execution-v1",
        "baseline_main": BASELINE,
        "approval_sha256": digest(approval),
        "execution_code_sha256": sha(Path(__file__).read_bytes()),
        "analysis_code_sha256": sha(
            Path(__file__).with_name("machine_blind_analysis.py").read_bytes()
        ),
        "purpose": "machine_proposed",
        "max_attempts": 1,
    }


def authorize(output, reference):
    """Explicit operator command; never invoked automatically by run/resume."""
    c, order = budget.load(budget.DEST)
    approval = {
        "schema_version": "category-pair-budget-approval-v1",
        "authorization": "explicit-operator-cost-approval",
        "approval_reference": reference,
        "contract_review_reference": f"PR #17 merged; main {BASELINE}",
        "kind": "initial",
        "contract_sha256": sha((budget.DEST / "execution-contract.json").read_bytes()),
        "order_sha256": sha((budget.DEST / "request-order.json").read_bytes()),
        **{
            k: c[k]
            for k in (
                "packet_sha256",
                "prompt_sha256",
                "model",
                "legacy_contract_sha256",
                "legacy_cost_report_sha256",
                "prices_sha256",
                "pair_count",
                "pass_count",
                "request_count",
                "max_input_tokens",
                "max_output_tokens",
            )
        },
        "passes": {"machine-a": "approved", "machine-b": "approved", "machine-c": "forbidden"},
        "max_amount_usd": "12.00",
        "execution_root": str(output),
    }
    return budget.check_approval(approval, c, order, budget.DEST, output)


async def drive(book, judge):
    """Ledger alone decides admission, dispatch order, settlement and terminal states."""
    while True:
        action = book.resume_action()
        if action == "admit_next_pair":
            book.append({"kind": "admit"})
            continue
        if action == "reconcile_saved_response_offline":
            name = next(k for k, v in book.state["current"]["passes"].items() if v == "in_flight")
            try:
                book.record_response(name, read(book.response_path(name)))
            except (ValueError, KeyError, TypeError):
                book.append({"kind": "fail"})
            continue
        if action not in ("dispatch_machine_a", "dispatch_reserved_machine_b_only"):
            return book.state
        name = "machine-a" if action == "dispatch_machine_a" else "machine-b"
        aid = book.state["current"]["annotation_id"]
        intent = book.request_intent(name)  # fsynced dispatch BEFORE any network activity
        started = monotonic()
        metadata = {
            "annotation_id": aid,
            "pass_name": name,
            "run_id": intent["run_id"],
            "client_request_id": intent["client_request_id"],
            "payload_sha256": sha(budget.legacy.wire(intent["payload"])),
            "started_at": datetime.now(UTC).isoformat(),
            "attempt": 1,
            "retries": 0,
        }
        try:
            body, request_id = await judge.request(
                "POST", "responses", intent["payload"], intent["client_request_id"]
            )
        except APIError as exc:
            metadata.update(status="transport_failure", error_category=exc.category)
            metadata["latency_seconds"] = monotonic() - started
            atomic_new(book.output / name / "attempts" / f"{aid}.json", metadata)
            book.append({"kind": "fail"})
            return book.state
        metadata.update(
            status="response_received", request_id=request_id, latency_seconds=monotonic() - started
        )
        # Receipt must survive a crash even if metadata or settlement fails.
        atomic_new(book.response_path(name), body)
        atomic_new(book.output / name / "attempts" / f"{aid}.json", metadata)
        try:
            book.record_response(name, body)  # identical receipt verified, then settle
        except (ValueError, KeyError, TypeError):
            book.append({"kind": "fail"})
            return book.state
        if name == "machine-b" and book.state["completed_pairs"] % 10 == 0:
            print(
                f"pairs={book.state['completed_pairs']} settled_usd={book.state['actual_usd']}",
                flush=True,
            )


async def execute(output, approval_path, *, resume=False):
    approval = read(approval_path)
    with budget.Ledger(budget.DEST, output) as book:
        checked = budget.check_approval(approval, book.contract, book.order, budget.DEST, output)
        manifest = binding(checked)
        if book.state is None:
            require(not resume, "no_run_to_resume")
            atomic_new(output / "execution.json", manifest)
            book.append({"kind": "initialize", "approval": checked})
        else:
            require(resume, "explicit_resume_required")
            require(read(output / "execution.json") == manifest, "execution_binding")
            require(book.state["approval_sha256"] == digest(checked), "approval_binding")
        judge = budget.legacy.CategoryJudge(os.environ.get("OPENAI_API_KEY", ""))
        try:
            return await drive(book, judge)
        finally:
            await judge.close()


def summarize(book):
    """Measured receipt accounting only; no admission or spending decision here."""
    passes = {}
    for name in budget.PASSES:
        totals = Counter()
        cost = Decimal(0)
        for path in sorted((book.output / name / "responses").glob("*.json")):
            body = read(path)
            try:
                measured = budget.usage(body)
            except (ValueError, KeyError, TypeError):
                totals["unknown_usage_receipts"] += 1
                continue
            for key, value in measured.items():
                if value is not None:
                    totals[key] += value
            cost += budget.price(
                measured["input_tokens"],
                measured["output_tokens"],
                measured["cached_input_tokens"] or 0,
                book.contract["prices"],
            )
            totals["receipts"] += 1
            totals["settled"] += body.get("id") in book.state["response_ids"]
        passes[name] = {**totals, "measured_receipt_cost_usd": str(cost)}
    return {
        "status": book.state["status"],
        "passes": passes,
        "retries": 0,
        "dispatch_intents": book.state["dispatched_requests"],
        "settled_cost_usd": book.state["actual_usd"],
        "outstanding_reservation_usd": book.state["outstanding_usd"],
        "unknown_usage_possible": book.state["status"] in ("in_flight", "request_failed_partial"),
        "prices": book.contract["prices"],
        "no_reevaluation": True,
    }


def consensus(book):
    budget.require_complete(book.state)
    rows, conflicts = [], []
    for pair in book.order["pairs"]:
        aid = pair["annotation_id"]
        candidate = book.packet[aid]
        answers = [
            budget.parse(
                read(book.output / name / "responses" / f"{aid}.json"),
                candidate,
                book.contract["model"],
            )
            for name in budget.PASSES
        ]
        result = {"annotation_id": aid, **classify(*answers)}
        rows.append(result)
        if result["status"] != "machine_agreed":
            conflicts.append(candidate)  # no prior answers, conflict type or grades in blind pool
    return {
        "provenance": "machine_proposed",
        "records": rows,
        "counts": dict(Counter(r["status"] for r in rows)),
    }, conflicts


def export_run(output, destination):
    require(not destination.exists(), "exclusive_export_required")
    with budget.Ledger(budget.DEST, output) as book:
        require(book.state is not None, "missing_run")
        files = {str(p.relative_to(output)): p.read_text() for p in sorted(output.rglob("*.json"))}
        bundle = {
            "schema_version": "category-pair-receipts-v1",
            "files": files,
            "sha256": {k: sha(v.encode()) for k, v in files.items()},
        }
        atomic_new(destination / "run-bundle.json", bundle)
        atomic_new(destination / "usage-cost-report.json", summarize(book))
        if book.state["status"] == "complete":
            agreed, conflicts = consensus(book)  # require_complete enforced inside
            atomic_new(destination / "machine-consensus.json", agreed)
            atomic_new(destination / "conflict-pool.jsonl", conflicts, jsonl=True)
        atomic_new(
            destination / "artifact-sha256.json",
            {p.name: sha(p.read_bytes()) for p in sorted(destination.iterdir()) if p.is_file()},
        )


def validate_bundle(path):
    """Replay original Ledger transitions offline with receipt paths relocated for audit."""
    bundle = read(path)
    require(set(bundle) == {"schema_version", "files", "sha256"}, "bundle_schema")
    require(bundle["schema_version"] == "category-pair-receipts-v1", "bundle_version")
    require(set(bundle["files"]) == set(bundle["sha256"]), "bundle_hash_keys")
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        for name, content in bundle["files"].items():
            rel = Path(name)
            require(not rel.is_absolute() and ".." not in rel.parts, "bundle_path")
            require(sha(content.encode()) == bundle["sha256"][name], "bundle_hash")
            target = root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content)
        approval = read(root / "journal/000000.json")["operation"]["approval"]

        class AuditLedger(budget.Ledger):
            def response_path(self, pass_name):
                return root / super().response_path(pass_name).relative_to(self.output)

        book = AuditLedger(budget.DEST, Path(approval["execution_root"]))
        require(read(root / "execution.json") == binding(approval), "execution_binding")
        for i, file in enumerate(sorted((root / "journal").glob("*.json"))):
            require(file.name == f"{i:06}.json", "journal_gap")
            event = read(file)
            require(
                set(event) == {"previous_sha256", "operation", "state_sha256"}
                and event["previous_sha256"] == book.tail,
                "journal_chain",
            )
            book.state = book.transition(event["operation"])
            require(digest(book.state) == event["state_sha256"], "journal_state")
            book.tail = sha(file.read_bytes())
        require(book.state is not None, "missing_run")
        return book.state


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    auth = commands.add_parser("approve")
    auth.add_argument("--execution-root", type=Path, required=True)
    auth.add_argument("--reference", required=True)
    auth.add_argument("--output", type=Path, required=True)
    run = commands.add_parser("run")
    run.add_argument("--output", type=Path, required=True)
    run.add_argument("--approval", type=Path, required=True)
    run.add_argument("--resume", action="store_true")
    export = commands.add_parser("export")
    export.add_argument("--run", type=Path, required=True)
    export.add_argument("--output", type=Path, required=True)
    check = commands.add_parser("validate")
    check.add_argument("--bundle", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "approve":
        atomic_new(args.output, authorize(args.execution_root, args.reference))
    elif args.command == "run":
        state = asyncio.run(execute(args.output, args.approval, resume=args.resume))
        print(state["status"])
    elif args.command == "export":
        export_run(args.run, args.output)
    else:
        print(validate_bundle(args.bundle)["status"])


if __name__ == "__main__":
    main()
