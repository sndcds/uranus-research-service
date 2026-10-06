"""Operator-only frozen benchmark. Fixed loopback endpoints; no production switches."""

import argparse
import asyncio
import json
import os
import re
import time
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid5

from pydantic import SecretStr

from uranus_research_service.clients import InternalClient
from uranus_research_service.controlled_evaluation import (
    aggregate,
    compare,
    distribution,
    inputs,
    require,
    summarize,
    thresholds,
)
from uranus_research_service.encoder import validate_vectors
from uranus_research_service.encoder_contracts import ChunkDocument, ChunkResponse, EmbedResponse
from uranus_research_service.research.vector_documents import content_hash
from uranus_research_service.semantic_manifest import digest
from uranus_research_service.version import ENCODER_EXPECTED

NAMESPACE = UUID("9c17fd27-cbd6-4c31-bedd-c4f51670b1cb")
MANIFEST_ID = str(uuid5(NAMESPACE, "controlled-benchmark-manifest"))
V3 = {
    "service_version": "0.1.0",
    "contract_version": "uranus-research-encoder-v1",
    "model": "jina-v3",
    "model_repository": "jinaai/jina-embeddings-v3-hf",
    "model_revision": "d18862d9a48706220815554fac3ebb4dfa46fc28",
    "dimensions": 1024,
    "chunk_version": "sections-480-overlap64-v2",
    "backend": "onnx-merged",
    "runtime": "onnxruntime-1.30.0-cpu",
    "embedding_version": "d18862d9a48706220815554fac3ebb4dfa46fc28:"
    "native-transformers5.17.0-retrieval-normalized-f32:sections-480-overlap64-v2",
}
V5 = {
    **ENCODER_EXPECTED,
    "service_version": "0.2.0",
    "backend": "torch",
    "runtime": "torch-2.11.0+cpu-transformers-5.17.0-peft-0.21.1-cpu",
}


def collection_name(model, build):
    require(model in {"v3", "v5"} and re.fullmatch(r"[a-z0-9_]{1,60}", build), "benchmark_identity")
    return f"benchmark_events_jina_{model}_{build}"


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as stream:
        json.dump(data, stream, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        stream.write("\n")


def documents(events):
    """Benchmark snapshot projection v1; missing production-only fields are not invented."""
    result = {}
    for eid, row in events.items():
        e = row.event
        sections = []

        def add(kind, text, context, sections=sections):
            if text.strip():
                sections.append({"kind": kind, "text": text, "context": context})

        content = [e.title, e.subtitle, e.summary, e.description]
        types = sorted({v for t in e.event_types for v in (t.type_name, t.genre_name) if v})
        content += ["Veranstaltungsarten / Genres: " + ", ".join(types)] if types else []
        content += ["Schlagworte: " + ", ".join(e.tags)] if e.tags else []
        add("content", "\n\n".join(x for x in content if x), {"scope": "event"})
        price = {
            "free": "kostenlos",
            "regular_price": "regulärer Eintritt",
            "donation": "Spende",
            "tiered_prices": "gestaffelte Preise",
        }.get(e.price_type)
        if price:
            add("tickets", "Preisart: " + price, {"scope": "event"})
        for o in e.occurrences:
            context = {
                "scope": "occurrence",
                "occurrence_id": str(o.id),
                "venue_id": str(o.venue_id) if o.venue_id else None,
                "space_id": str(o.space_id) if o.space_id else None,
            }
            add(
                "location_context",
                "\n".join(
                    f"{label}: {value}"
                    for label, value in (("Ort", o.venue), ("Raum", o.space), ("Stadt", o.city))
                    if value
                ),
                context,
            )
            # These are the captured effective public values for this occurrence ONLY.
            add(
                "accessibility",
                "\n\n".join(
                    v
                    for v in (o.venue_accessibility, o.space_accessibility, o.accessibility_info)
                    if v
                ),
                context,
            )
        doc = ChunkDocument.model_validate({"entity_id": str(eid), "sections": sections})
        result[str(eid)] = doc.model_dump(mode="json")
    return result


class BenchHTTP(InternalClient):
    def __init__(self, dependency, model):
        port = 16633 if dependency == "qdrant" else {"v3": 16635, "v5": 16636}[model]
        key = os.environ.get("CONTROLLED_BENCHMARK_KEY", "")
        require(len(key) >= 32, "benchmark_key_required")
        super().__init__(
            SimpleNamespace(
                **{
                    dependency + "_url": f"http://127.0.0.1:{port}",
                    dependency + "_api_key": SecretStr(key),
                    "dependency_timeout_seconds": 240,
                    "max_response_bytes": 32 * 1024 * 1024,
                }
            ),
            dependency,
        )


async def compatible(client, expected):
    metadata = await client.get("/version")
    require(
        all(type(metadata.get(k)) is type(v) and metadata[k] == v for k, v in expected.items()),
        "encoder_contract_mismatch",
    )
    ready = await client.get("/ready")
    require(ready.get("status") == "ready", "encoder_not_ready")
    require(
        all(
            ready.get(k) == v
            for k, v in expected.items()
            if k not in {"service_version", "model_repository", "chunk_version"}
        ),
        "encoder_ready_mismatch",
    )
    return metadata


async def embed(client, expected, texts, kind):
    raw = await client._request(
        "POST", "/embed", {"model": expected["model"], "kind": kind, "texts": texts}
    )
    require(raw.get("embedding_version") == expected["embedding_version"], "embedding_mismatch")
    validate_vectors(raw["vectors"], len(texts))
    response = EmbedResponse.model_validate(raw)
    return response.vectors


def validate_chunk(doc, chunk, index):
    require(type(chunk.chunk_index) is int and chunk.chunk_index == index, "chunk_order")
    require(content_hash(chunk.text) == chunk.content_hash, "chunk_hash")
    matching = [
        s for s in doc["sections"] if s["kind"] == chunk.chunk_kind and chunk.text in s["text"]
    ]
    require(matching and chunk.contexts, "chunk_source_evidence")
    # Normalize absent optional IDs through the same closed context contract.
    from uranus_research_service.encoder_contracts import EvidenceContext

    allowed = {
        digest(EvidenceContext.model_validate(s["context"]).model_dump(mode="json"))
        for s in matching
    }
    require(
        all(digest(c.model_dump(mode="json")) in allowed for c in chunk.contexts), "chunk_context"
    )


async def full_validate(qdrant, path, manifest, points):
    info = (await qdrant._request("GET", path))["result"]
    require(
        all(
            info["config"]["params"]["vectors"].get(k) == v
            for k, v in {"size": 1024, "distance": "Cosine"}.items()
        ),
        "vector_contract",
    )
    require(info["points_count"] == len(points) + 1, "point_count")
    found = set()
    offset = None
    while True:
        page = (
            await qdrant._request(
                "POST",
                path + "/points/scroll",
                {
                    "limit": 64,
                    "offset": offset,
                    "with_payload": True,
                    "with_vector": True,
                },
            )
        )["result"]
        for point in page["points"]:
            pid = point["id"]
            require(pid not in found, "duplicate_point")
            found.add(pid)
            if pid == MANIFEST_ID:
                require(
                    point["payload"] == {"kind": "manifest", "manifest": manifest},
                    "manifest_mismatch",
                )
            else:
                require(
                    pid in points and point["payload"] == points[pid]["payload"],
                    "foreign_or_stale_point",
                )
                validate_vectors([point["vector"]], 1)
                require(
                    max(
                        abs(a - b)
                        for a, b in zip(point["vector"], points[pid]["vector"], strict=True)
                    )
                    < 1e-5,
                    "stored_vector_mismatch",
                )
        offset = page["next_page_offset"]
        if offset is None:
            break
    require(found == set(points) | {MANIFEST_ID}, "collection_incomplete")


async def run(root, model, build):
    identity, cases, events = inputs(root)
    profile = os.environ.get("CONTROLLED_BENCHMARK_PROFILE", "2cpu-original-threads")
    require(profile in {"2cpu-original-threads", "8cpu-8threads"}, "execution_profile")
    identity["execution_profile"] = profile
    docs = documents(events)
    expected = V3 if model == "v3" else V5
    collection = collection_name(model, build)
    output = root / f"benchmark/results/{model}-{build}.json"
    require(not output.exists(), "immutable_report_exists")
    encoder, qdrant = BenchHTTP("encoder", model), BenchHTTP("qdrant", model)
    path = "/collections/" + collection
    started = time.perf_counter()
    try:
        metadata = await compatible(encoder, expected)
        require(
            await qdrant._request("GET", path, missing_ok=True) is None,
            "build_exists_no_inplace_writes",
        )
        points, mapping, chunk_times, embed_times = {}, {}, [], []
        for eid, doc in docs.items():
            begin = time.perf_counter()
            raw = await encoder._request(
                "POST", "/chunks", {"model": expected["model"], "documents": [doc]}
            )
            result = ChunkResponse.model_validate(raw)
            require(
                result.embedding_version == expected["embedding_version"]
                and len(result.documents) == 1
                and str(result.documents[0].entity_id) == eid,
                "chunk_contract",
            )
            chunks = result.documents[0].chunks
            chunk_times.append(time.perf_counter() - begin)
            mapping[eid] = {
                "document_hash": events[UUID(eid)].document_hash,
                "semantic_document_hash": digest(doc),
                "chunks": [],
            }
            for index, chunk in enumerate(chunks):
                validate_chunk(doc, chunk, index)
                value = chunk.model_dump(mode="json")
                pid = str(uuid5(NAMESPACE, model + ":" + eid + ":" + digest(value)))
                require(pid not in points, "duplicate_chunk_identity")
                payload = {
                    "entity_id": eid,
                    "kind": "chunk",
                    "model": expected["model"],
                    "embedding_version": expected["embedding_version"],
                    "document_hash": events[UUID(eid)].document_hash,
                    "chunk": value,
                }
                points[pid] = {"id": pid, "payload": payload}
                mapping[eid]["chunks"].append(
                    {
                        "point_id": pid,
                        "content_hash": chunk.content_hash,
                        "tokens": chunk.token_count,
                        "characters": len(chunk.text),
                    }
                )
            for start in range(0, len(chunks), 8):
                batch = chunks[start : start + 8]
                begin = time.perf_counter()
                vectors = await embed(encoder, expected, [c.text for c in batch], "passage")
                embed_times.append(time.perf_counter() - begin)
                for i, vector in enumerate(vectors, start):
                    points[mapping[eid]["chunks"][i]["point_id"]]["vector"] = vector
            if len(mapping) % 25 == 0:
                print(
                    json.dumps(
                        {
                            "phase": "embed",
                            "model": model,
                            "documents": len(mapping),
                            "chunks": len(points),
                        }
                    ),
                    flush=True,
                )
        await qdrant._request("PUT", path, {"vectors": {"size": 1024, "distance": "Cosine"}})
        ordered = list(points.values())
        for start in range(0, len(ordered), 32):
            await qdrant._request(
                "PUT", path + "/points?wait=true", {"points": ordered[start : start + 32]}
            )
        tokens = [c["tokens"] for d in mapping.values() for c in d["chunks"]]
        manifest = {
            **identity,
            "build_id": build,
            "model": expected,
            "collection_name": collection,
            "document_schema_version": "benchmark-public-snapshot-sections-v1",
            "index_owner": "controlled-retrieval-benchmark-v1",
            "distance": "Cosine",
            "dimensions": 1024,
            "document_count": len(docs),
            "chunk_count": len(points),
            "corpus_hash": digest([p["payload"] for p in ordered]),
            "complete": True,
        }
        await qdrant._request(
            "PUT",
            path + "/points?wait=true",
            {
                "points": [
                    {
                        "id": MANIFEST_ID,
                        "vector": [1.0] + [0.0] * 1023,
                        "payload": {"kind": "manifest", "manifest": manifest},
                    }
                ]
            },
        )
        begin = time.perf_counter()
        await full_validate(qdrant, path, manifest, points)
        validation_time = time.perf_counter() - begin
        build_seconds = time.perf_counter() - started
        # Immutable chunks are explicit benchmark evidence; vectors remain only in isolated Qdrant.
        write(
            root / f"benchmark/results/chunks-{model}-{build}.json",
            {pid: p["payload"] for pid, p in points.items()},
        )
        results = []
        for case in cases:
            begin = time.perf_counter()
            query_start = begin
            vector = (await embed(encoder, expected, [case["query"]], "query"))[0]
            query_ms = (time.perf_counter() - query_start) * 1000
            begin_search = time.perf_counter()
            response = (
                (
                    await qdrant._request(
                        "POST",
                        path + "/points/query",
                        {
                            "query": vector,
                            "filter": {
                                "must": [
                                    {"key": "kind", "match": {"value": "chunk"}},
                                    {"key": "entity_id", "match": {"any": case["eligible_ids"]}},
                                ]
                            },
                            "limit": len(points),
                            "with_payload": False,
                            "with_vector": False,
                            "params": {"exact": True},
                        },
                    )
                )["result"]["points"]
                if case["eligible_ids"]
                else []
            )
            search_ms = (time.perf_counter() - begin_search) * 1000
            begin_aggregation = time.perf_counter()
            hits = []
            for hit in response:
                require(hit["id"] in points, "foreign_query_hit")
                payload = points[hit["id"]]["payload"]
                require(payload["entity_id"] in case["eligible_ids"], "ineligible_query_hit")
                if not any(
                    c["scope"] == "event" or c["occurrence_id"] in case["eligible_occurrence_ids"]
                    for c in payload["chunk"]["contexts"]
                ):
                    continue
                hits.append(
                    {"event_id": payload["entity_id"], "point_id": hit["id"], "score": hit["score"]}
                )
            ranking = aggregate(hits)
            aggregation_ms = (time.perf_counter() - begin_aggregation) * 1000
            results.append(
                {k: v for k, v in case.items() if k != "query"}
                | {
                    "ranking": ranking,
                    "candidate_chunks": len(hits),
                    "best_relevant_rank": next(
                        (
                            i + 1
                            for i, h in enumerate(ranking)
                            if case["grades"].get(h["event_id"], 0) > 0
                        ),
                        None,
                    ),
                    "judged_scores": [
                        {
                            "event_id": h["event_id"],
                            "score": h["score"],
                            "grade": case["grades"][h["event_id"]],
                        }
                        for h in ranking
                        if h["event_id"] in case["grades"]
                    ],
                    "latency_ms": {
                        "embedding": query_ms,
                        "qdrant": search_ms,
                        "aggregation": aggregation_ms,
                        "total": (time.perf_counter() - begin) * 1000,
                    },
                }
            )
        await compatible(encoder, expected)
        inputs(root)  # Frozen input integrity again after inference.
        report = {
            **identity,
            "build_id": build,
            "model": metadata,
            "manifest": manifest,
            "manifest_digest": digest(manifest),
            "documents": {eid: digest(doc) for eid, doc in docs.items()},
            "chunk_mapping": mapping,
            "chunk_statistics": {
                "chunks_per_document": distribution([len(d["chunks"]) for d in mapping.values()]),
                "tokens": distribution(tokens),
                "characters": distribution(
                    [c["characters"] for d in mapping.values() for c in d["chunks"]]
                ),
                "max_tokens": 480,
                "overlap_tokens": 64,
            },
            "build_performance": {
                "seconds": build_seconds,
                "embedding_seconds": sum(embed_times),
                "chunking_seconds": sum(chunk_times),
                "full_validation_seconds": validation_time,
                "passage_chunks_per_second": len(points) / sum(embed_times),
            },
            "cases": results,
            "metrics": summarize(results),
            "threshold_analysis": thresholds(results),
        }
        write(output, report)
        print(
            json.dumps(
                {"status": "complete", "model": model, "cases": len(results), "chunks": len(points)}
            ),
            flush=True,
        )
    finally:
        await encoder.close()
        await qdrant.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["run", "compare"])
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--model", choices=["v3", "v5"])
    parser.add_argument("--build", required=True)
    args = parser.parse_args()
    if args.command == "run":
        require(args.model is not None, "model_required")
        asyncio.run(run(args.root, args.model, args.build))
    else:
        base = args.root / "benchmark/results"
        identity, _, _ = inputs(args.root)
        v3, v5 = (
            json.loads((base / f"{model}-{args.build}.json").read_text()) for model in ("v3", "v5")
        )
        for report, expected in ((v3, V3), (v5, V5)):
            require(all(report[k] == value for k, value in identity.items()), "run_input_mismatch")
            require(
                all(report["model"].get(k) == value for k, value in expected.items()),
                "run_encoder_mismatch",
            )
        write(base / f"v3-v5-comparison-{args.build}.json", compare(v3, v5))


if __name__ == "__main__":
    main()
