"""Offline annotation operators. No inference, Qdrant, live writes or automatic labels."""

import argparse
import hashlib
from datetime import date
from pathlib import Path

from uranus_research_service.ground_truth import (
    GroundTruthCase,
    QueryProposal,
    annotation_csv,
    coverage,
    coverage_markdown,
    evidence_markdown,
    import_annotations,
    prepare_pool,
    validate_cases,
)
from uranus_research_service.ground_truth_snapshot import (
    MAX_BYTES,
    SnapshotManifest,
    canonical_bytes,
    load_snapshot,
    project_event,
    serialize_events,
)
from uranus_research_service.json_codec import decode
from uranus_research_service.semantic_manifest import digest


def read(path):
    path = Path(path)
    if path.stat().st_size > MAX_BYTES:
        raise ValueError("artifact_limit")
    return path.read_bytes()


def write(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as f:
        f.write(data)


def load_cases(path):
    return [GroundTruthCase.model_validate(decode(line)) for line in read(path).splitlines()]


def run(args):
    if args.command == "snapshot-from-export":
        raw = decode(read(args.input))
        events = [project_event(e, date(1900, 1, 1), date(2100, 12, 31)) for e in raw["events"]]
        if len(events) != raw["public_event_count"]:
            raise ValueError("snapshot_count_mismatch")
        rows, data = serialize_events(events)
        manifest = SnapshotManifest(
            schema_version="public-annotation-snapshot-v1",
            snapshot_id=args.snapshot_id,
            captured_at=raw["captured_at"],
            reference_time=raw["reference_time"],
            timezone="Europe/Berlin",
            source="uranus_reader_public_select",
            source_row_count=raw["source_row_count"],
            public_event_count=len(events),
            source_snapshot_hash=digest([r.model_dump(mode="json") for r in rows]),
            file_sha256=hashlib.sha256(data).hexdigest(),
            window_start="1900-01-01",
            window_end="2100-12-31",
            capture_rule="repeatable_read_read_only",
            exporter_sha256=hashlib.sha256(read(args.exporter)).hexdigest(),
            source_code_revision="340df4684611dbc4b8ec73a7702f1fad2ae1973c",
        )
        args.output.mkdir(parents=True, exist_ok=False)
        write(args.output / "events.jsonl", data)
        write(
            args.output / "manifest.json", canonical_bytes(manifest.model_dump(mode="json")) + b"\n"
        )
        return
    manifest, rows = load_snapshot(args.snapshot, args.manifest)
    if args.command == "prepare-pool":
        proposals = [QueryProposal.model_validate(v) for v in decode(read(args.queries))]
        history = decode(read(args.historical)) if args.historical else {}
        manual = decode(read(args.manual)) if args.manual else {}
        cases, audit = prepare_pool(proposals, manifest, rows, history, manual, size=args.pool_size)
        args.output.mkdir(parents=True, exist_ok=False)
        write(
            args.output / "ground-truth-v1.jsonl",
            b"".join(canonical_bytes(c.model_dump(mode="json")) + b"\n" for c in cases),
        )
        write(args.output / "annotation.csv", annotation_csv(cases, rows).encode())
        write(args.output / "evidence.md", evidence_markdown(rows).encode())
        write(args.output / "pool-audit.json", canonical_bytes(audit) + b"\n")
        write(args.output / "ground-truth-v1-report.json", canonical_bytes(coverage(cases)) + b"\n")
    else:
        cases = validate_cases(load_cases(args.cases), manifest, rows)
        if args.command == "import-annotations":
            imported = import_annotations(cases, rows, read(args.annotation).decode())
            validate_cases(imported, manifest, rows)
            write(
                args.output,
                b"".join(canonical_bytes(c.model_dump(mode="json")) + b"\n" for c in imported),
            )
            return
        report = coverage(cases)
        if args.require_approved and (
            report["dataset_status"] != "approved" or len(cases) != report["approved_queries"]
        ):
            raise ValueError("approved_dataset_required")
        write(args.output, canonical_bytes(report) + b"\n")
        if args.markdown_output:
            write(args.markdown_output, coverage_markdown(report, manifest).encode())


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=(
            "snapshot-from-export",
            "prepare-pool",
            "validate-ground-truth",
            "coverage",
            "import-annotations",
        ),
    )
    for flag in (
        "markdown-output",
        "annotation",
        "input",
        "exporter",
        "snapshot",
        "manifest",
        "queries",
        "historical",
        "manual",
        "cases",
        "output",
    ):
        parser.add_argument("--" + flag, type=Path, required=flag == "output")
    parser.add_argument("--snapshot-id")
    parser.add_argument("--pool-size", type=int, default=20)
    parser.add_argument("--require-approved", action="store_true")
    args = parser.parse_args(argv)
    required = {
        "snapshot-from-export": ("input", "exporter", "snapshot_id"),
        "prepare-pool": ("snapshot", "manifest", "queries"),
        "validate-ground-truth": ("snapshot", "manifest", "cases"),
        "coverage": ("snapshot", "manifest", "cases"),
        "import-annotations": ("snapshot", "manifest", "cases", "annotation"),
    }
    if any(getattr(args, f) is None for f in required[args.command]):
        parser.error("required artifact argument missing")
    try:
        run(args)
    except Exception:
        raise SystemExit("ground_truth_operation_failed") from None
