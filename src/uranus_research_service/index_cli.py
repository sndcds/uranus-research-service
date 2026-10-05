"""Explicit isolated maintenance CLI; no live-write override exists in this phase."""

import argparse
import asyncio
import fcntl
import os
from datetime import datetime
from pathlib import Path
from time import perf_counter

from uranus_research_service.benchmark import compare, load_cases, run_benchmark
from uranus_research_service.config import Settings
from uranus_research_service.database import ResearchDatabase
from uranus_research_service.encoder import EncoderClient
from uranus_research_service.indexing import build, save_report
from uranus_research_service.json_codec import decode
from uranus_research_service.qdrant import QdrantClient, QdrantMaintenance
from uranus_research_service.repositories.semantic_source import SemanticSource


async def run(args):
    if args.command == "compare":
        reports = []
        for path in (args.v3, args.v5):
            if path is None or path.stat().st_size > 16 * 1024 * 1024:
                raise ValueError("bounded_benchmark_reports_required")
            reports.append(decode(path.read_bytes()))
        save_report(args.output, compare(load_cases(args.cases), *reports))
        return
    settings = Settings.from_env()
    source_db, area_db = ResearchDatabase(settings), ResearchDatabase(settings, "area")
    source = SemanticSource(source_db, area_db, settings)
    encoder = EncoderClient(settings)
    qdrant = (
        QdrantMaintenance(settings, build_id=args.build_id, isolated=args.isolated)
        if args.command == "build"
        else QdrantClient(settings, build_id=args.build_id)
    )
    try:
        if args.command in {"plan", "build"}:
            await build(
                source, encoder, qdrant, report_path=args.output, plan_only=args.command == "plan"
            )
        elif args.command == "validate":
            started = perf_counter()
            manifest = await qdrant.validate()
            generation = qdrant.generation_verifier.generation
            save_report(
                args.output,
                {
                    "status": "validated",
                    "collection": generation.collection_name,
                    "build_id": generation.build_id,
                    "manifest_digest": generation.manifest_digest,
                    "documents": manifest.document_count,
                    "chunks": manifest.chunk_count,
                    "point_count": generation.point_count,
                    "validation_duration": perf_counter() - started,
                },
            )
        elif args.command == "benchmark":
            if args.reference_time is None or args.build_report is None:
                raise ValueError("benchmark_reference_and_build_report_required")
            now = datetime.fromisoformat(args.reference_time)
            if now.tzinfo is None:
                raise ValueError("aware_reference_required")
            report = await run_benchmark(load_cases(args.cases), source, encoder, qdrant, now=now)
            artifact = decode(args.build_report.read_bytes())
            if artifact["source_snapshot_hash"] != report["source_snapshot_hash"]:
                raise ValueError("build_report_mismatch")
            report.update({k: artifact[k] for k in ("documents", "average_tokens", "max_tokens")})
            save_report(args.output, report)
    finally:
        await encoder.close()
        await qdrant.close()
        await source_db.close()
        await area_db.close()


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("plan", "build", "validate", "benchmark", "compare"))
    parser.add_argument("--build-id")
    parser.add_argument("--isolated", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cases", type=Path)
    parser.add_argument("--v3", type=Path)
    parser.add_argument("--v5", type=Path)
    parser.add_argument("--build-report", type=Path)
    parser.add_argument("--reference-time")
    args = parser.parse_args(argv)
    if args.command != "compare" and args.build_id is None:
        parser.error("--build-id required")
    if args.command in {"benchmark", "compare"} and args.cases is None:
        parser.error("--cases required")
    os.umask(0o077)
    try:
        with os.fdopen(
            os.open(
                "/tmp/uranus-service-index.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600
            ),
            "w",
        ) as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            asyncio.run(run(args))
    except Exception:
        # No provider replies, DSNs, SQL binds, query text or exception repr.
        raise SystemExit("index_operation_failed") from None
