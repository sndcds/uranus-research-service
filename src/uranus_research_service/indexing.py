"""Operator-only complete event builds. No source transaction crosses an HTTP call."""

import asyncio
import json
import resource
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter, process_time

from uranus_research_service.research.semantic_contracts import COLLECTIONS
from uranus_research_service.research.vector_models import V5
from uranus_research_service.research.vector_sync import payloads_equal, plan_changes
from uranus_research_service.semantic_manifest import MANIFEST_ID, Manifest, digest
from uranus_research_service.version import CHUNK_VERSION, EMBEDDING_VERSION, MODEL, MODEL_REVISION


def save_report(path: Path, report):
    path.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive create: a prior report is never overwritten, even on retries.
    with path.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


async def _build(source, encoder, qdrant, *, report_path, plan_only=False, now=None):
    if qdrant.entity != "event":
        raise ValueError("event_build_only_phase2b1")
    started, cpu = perf_counter(), process_time()
    timestamp = datetime.now(UTC)
    reference = now or timestamp
    documents, total = await source.snapshot(now=reference)
    if total != len(documents) or len({d.entity_id for d in documents}) != total:
        raise ValueError("complete_unique_snapshot_required")
    chunks = await encoder.prepare(documents)
    exists = await qdrant.info() is not None
    existing = await qdrant.points() if exists else {}
    old_manifest = existing.pop(MANIFEST_ID, None)
    if old_manifest is not None:
        Manifest.model_validate(old_manifest).verify(
            entity=qdrant.entity, build_id=qdrant.build_id, points=existing
        )
    # Incomplete interrupted builds may resume only if every point is owned v5 data.
    for payload in existing.values():
        qdrant.validate_payload(payload)
    plan = plan_changes(documents, chunks, existing, V5, complete=True, entity="event")
    payloads = {i: payload for i, (_, payload) in plan.desired.items()}
    manifest = Manifest.create(
        entity_type="event",
        document_schema_version=COLLECTIONS["event"].document_version,
        build_id=qdrant.build_id,
        created_at=timestamp.isoformat(),
        source_snapshot_hash=digest([d.model_dump(mode="json") for d in documents]),
        corpus_hash=digest(payloads),
        document_count=len(documents),
        chunk_count=len(payloads),
    )
    token_counts = [c.token_count for values in chunks.values() for c in values]
    report = {
        "build_id": qdrant.build_id,
        "started_at": timestamp.isoformat(),
        "reference_time": reference.isoformat(),
        "model": MODEL,
        "revision": MODEL_REVISION,
        "embedding_version": EMBEDDING_VERSION,
        "chunk_version": CHUNK_VERSION,
        "entity_type": "event",
        "collection": qdrant.collection,
        "manifest": manifest.model_dump(),
        "document_count": len(documents),
        "chunk_count": len(payloads),
        **plan.counts(),
        "source_snapshot_hash": manifest.source_snapshot_hash,
        "documents": [
            {
                "entity_id": str(d.entity_id),
                "document_hash": digest([s.model_dump(mode="json") for s in d.sections]),
                "chunk_hashes": [c.content_hash for c in chunks[str(d.entity_id)]],
                "chunk_count": len(chunks[str(d.entity_id)]),
            }
            for d in documents
        ],
        "average_tokens": sum(token_counts) / len(token_counts) if token_counts else 0,
        "max_tokens": max(token_counts, default=0),
        "raw_vector_bytes": len(payloads) * 4096,
        "payload_bytes": len(json.dumps(payloads).encode()),
        "plan_only": plan_only,
        "embedding_time": 0.0,
        "qdrant_time": 0.0,
    }
    if not plan_only:
        if await asyncio.to_thread(Path(report_path).exists):
            raise ValueError("immutable_report_exists")
        before = perf_counter()
        if not exists:
            await qdrant.create()
        # Remove completion marker before any mutation. Failed builds cannot be ready.
        if old_manifest is not None:
            await qdrant.delete([MANIFEST_ID])
        report["qdrant_time"] += perf_counter() - before
        for offset in range(0, len(plan.embed), 2):
            ids = plan.embed[offset : offset + 2]
            before = perf_counter()
            vectors = await encoder.embed([plan.desired[i][0].text for i in ids], kind="passage")
            report["embedding_time"] += perf_counter() - before
            before = perf_counter()
            await qdrant.upsert(
                [
                    {"id": i, "vector": v, "payload": payloads[i]}
                    for i, v in zip(ids, vectors, strict=True)
                ]
            )
            report["qdrant_time"] += perf_counter() - before
        before = perf_counter()
        for i in plan.metadata:
            await qdrant.payload(i, payloads[i])
        await qdrant.delete(plan.delete)
        stored = await qdrant.points()
        if stored.keys() != payloads.keys() or any(
            not payloads_equal(payloads[i], stored[i]) for i in stored
        ):
            raise ValueError("build_payload_verification_failed")
        # Hash persisted JSON after verifying the sole allowed float round-trip tolerance.
        manifest = manifest.model_copy(update={"corpus_hash": digest(stored)})
        report["manifest"] = manifest.model_dump()
        await qdrant.write_manifest(manifest)
        await qdrant.validate()
        report["qdrant_time"] += perf_counter() - before
        # Fixed multilingual smoke, not a quality gate. No global search bypass.
        from uranus_research_service.schemas.research_execution import ExecutionSemanticFilters
        from uranus_research_service.semantic import retrieve

        report["smoke"] = []
        try:
            for query in ("Kultur und Musik", "Kultur og musik", "Culture and music"):
                result = await retrieve(
                    source, encoder, qdrant, ExecutionSemanticFilters(q=query), now=reference
                )
                report["smoke"].append(
                    {"returned_count": result.returned_count, "latency": result.latency}
                )
        except Exception:
            await qdrant.delete([MANIFEST_ID])
            raise
    report.update(
        completed_at=datetime.now(UTC).isoformat(),
        wall_time=perf_counter() - started,
        cpu_time=process_time() - cpu,
        peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
    )
    report["chunks_per_second"] = len(plan.embed) / report["wall_time"] if not plan_only else 0
    await asyncio.to_thread(save_report, Path(report_path), report)
    return report


async def build(source, encoder, qdrant, *, report_path, plan_only=False, now=None):
    try:
        return await _build(
            source, encoder, qdrant, report_path=report_path, plan_only=plan_only, now=now
        )
    except Exception:
        if not await asyncio.to_thread(Path(report_path).exists):
            await asyncio.to_thread(
                save_report,
                Path(report_path),
                {
                    "build_id": qdrant.build_id,
                    "collection": qdrant.collection,
                    "completed_at": datetime.now(UTC).isoformat(),
                    "status": "failed",
                    "error": "index_operation_failed",
                    "plan_only": plan_only,
                },
            )
        raise
