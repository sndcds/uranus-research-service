"""Trust and operation-count regressions; no network, model or quality evaluation."""

import asyncio
import copy
import json
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID

import httpx
import pytest
from pydantic import SecretStr

from tests.semantic_fixtures import VECTOR
from tests.test_semantic_v5 import prepared
from uranus_research_service.errors import DependencyError
from uranus_research_service.qdrant import QdrantClient, QdrantMaintenance
from uranus_research_service.runtime import ResearchRuntime
from uranus_research_service.schemas.research import ResearchRecord
from uranus_research_service.schemas.research_execution import ExecutionSemanticFilters
from uranus_research_service.semantic import retrieve
from uranus_research_service.semantic_generation import VALIDATION_TTL_SECONDS
from uranus_research_service.semantic_manifest import MANIFEST_ID, Manifest, digest


class Collection:
    def __init__(self):
        self.document, _, plan = prepared()
        self.identity, (_, self.payload) = next(iter(plan.desired.items()))
        self.manifest = Manifest.create(
            entity_type="event",
            document_schema_version="event-public-v4",
            build_id="test_one",
            created_at=datetime.now(UTC).isoformat(),
            source_snapshot_hash="a" * 64,
            corpus_hash=digest({self.identity: self.payload}),
            document_count=1,
            chunk_count=1,
        ).model_dump(mode="json")
        self.info = {
            "config": {"params": {"vectors": {"size": 1024, "distance": "Cosine"}}},
            "points_count": 2,
        }
        self.manifest_id = MANIFEST_ID
        self.hit = {"id": self.identity, "payload": self.payload, "score": 0.8}
        self.requests = []

    def handler(self, request):
        self.requests.append((request.method, request.url.path))
        path = request.url.path
        marker = [{"id": self.manifest_id, "payload": self.manifest}] if self.manifest else []
        if path.endswith("/scroll"):
            value = {
                "points": [{"id": self.identity, "payload": self.payload}] + marker,
                "next_page_offset": None,
            }
        elif path.endswith("/query"):
            value = {"points": [self.hit]}
        elif path.endswith("/points") and request.method == "POST":
            assert json.loads(request.content) == {
                "ids": [MANIFEST_ID],
                "with_payload": True,
                "with_vector": False,
            }
            value = marker
        elif path == "/aliases":
            value = {"aliases": []}
        elif request.method == "GET":
            if self.info is None:
                return httpx.Response(404, json={"status": "error"})
            value = self.info
        else:
            raise AssertionError("unexpected write or request")
        return httpx.Response(200, json={"status": "ok", "result": copy.deepcopy(value)})


@pytest.fixture
async def generation(settings):
    data = Collection()
    client = QdrantClient(
        settings.model_copy(update={"qdrant_api_key": SecretStr("a" * 32)}),
        build_id="test_one",
        transport=httpx.MockTransport(data.handler),
    )
    clock = [0.0]
    client.generation_verifier.clock = lambda: clock[0]
    try:
        yield data, client, clock
    finally:
        await client.close()


async def test_full_validation_creates_immutable_state_and_direct_fetch(generation):
    data, client, _ = generation
    verifier = client.generation_verifier
    assert not verifier.is_verified
    assert (await client.get_manifest()).model_dump(mode="json") == data.manifest
    assert not any(p.endswith("/scroll") for _, p in data.requests)
    manifest = await client.validate()
    state = verifier.generation
    assert state.manifest_digest == digest(manifest.model_dump(mode="json"))
    assert state.point_count == manifest.chunk_count + 1 == 2
    assert state.source_snapshot_hash == manifest.source_snapshot_hash
    assert state.validated_at.tzinfo is not None
    assert state.collection_name == client.collection
    with pytest.raises(FrozenInstanceError):
        state.build_id = "changed"
    # Canonical JSON SHA256: independent of input key order or Python object hash.
    assert digest({"b": 2, "a": "ä"}) == digest({"a": "ä", "b": 2})
    assert digest({"a": 1}) == "015abd7f5cc57a2dd94b7590f04ad8084273905ee33ec5cebeae62276a97f862"


async def test_one_full_validation_100_retrieves_no_scroll(generation):
    data, client, _ = generation
    await client.validate()
    client.points = AsyncMock(side_effect=AssertionError("full scan in query path"))
    source, encoder = AsyncMock(), AsyncMock()
    source.eligible.return_value = [data.document.entity_id]
    source.rehydrate.return_value = (
        SimpleNamespace(
            items=[
                ResearchRecord(
                    entity_type="event",
                    entity_key=data.document.entity_id,
                    name=data.document.display_name,
                )
            ],
            occurrence_ids={},
        ),
        {data.document.entity_id: data.document},
    )
    encoder.embed.return_value = [VECTOR]
    before = client.generation_verifier.manifest_check_count
    for _ in range(100):
        result = await retrieve(source, encoder, client, ExecutionSemanticFilters(q="Musik"))
        assert result.returned_count == 1
    client.points.assert_not_called()
    assert client.generation_verifier.full_validation_count == 1
    assert client.generation_verifier.manifest_check_count - before == 100
    assert sum(p.endswith("/scroll") for _, p in data.requests) == 1
    assert sum(p.endswith("/query") for _, p in data.requests) == 100
    # Current-document freshness is still independent of manifest/hash validity.
    source.rehydrate.return_value[1][data.document.entity_id] = data.document.model_copy(
        update={"sections": []}
    )
    assert not (await retrieve(source, encoder, client, ExecutionSemanticFilters(q="Musik"))).items


@pytest.mark.parametrize(
    "mutation",
    [
        "missing_collection",
        "dimension",
        "distance",
        "count",
        "bool_count",
        "missing_manifest",
        "manifest_id",
        "build_id",
        "embedding_version",
        "document_schema_version",
        "digest",
        "extra",
    ],
)
async def test_mismatch_invalidates_runtime_without_scan(settings, generation, mutation):
    data, client, _ = generation
    runtime = ResearchRuntime(
        settings, planner=AsyncMock(), database=AsyncMock(), areas=AsyncMock()
    )
    runtime.semantic_qdrant = client
    runtime.semantic_encoder = AsyncMock()
    await runtime.ready()
    assert runtime.semantic_generation is not None
    assert runtime.capabilities().semantic_index_ready
    client.points = AsyncMock(side_effect=AssertionError("full scan in query path"))
    if mutation == "missing_collection":
        data.info = None
    elif mutation in {"dimension", "distance"}:
        data.info["config"]["params"]["vectors"].update(
            {"size": 768} if mutation == "dimension" else {"distance": "Dot"}
        )
    elif mutation in {"count", "bool_count"}:
        data.info["points_count"] = 3 if mutation == "count" else True
    elif mutation == "missing_manifest":
        data.manifest = None
    elif mutation == "manifest_id":
        data.manifest_id = str(UUID(int=99))
    else:
        data.manifest[mutation if mutation != "digest" else "source_snapshot_hash"] = (
            "b" * 64 if mutation == "digest" else "wrong"
        )
    with pytest.raises((ValueError, DependencyError)):
        await client.search(VECTOR, entity_ids=[data.document.entity_id])
    assert not runtime.capabilities().semantic_index_ready
    assert runtime.capabilities().structured_query
    assert runtime.capabilities().semantic_query is False
    assert runtime.semantic_generation is None
    client.points.assert_not_called()
    assert not any(p.endswith("/query") for _, p in data.requests)
    await runtime.close()


async def test_ttl_queries_fail_closed_readiness_revalidates(generation):
    data, client, clock = generation
    verifier = client.generation_verifier
    await verifier.ready()
    initial = verifier.generation
    await verifier.ready()
    assert verifier.full_validation_count == 1
    clock[0] = VALIDATION_TTL_SECONDS
    assert not verifier.is_verified
    with pytest.raises(ValueError, match="verification_required"):
        await client.search(VECTOR, entity_ids=[data.document.entity_id])
    assert verifier.full_validation_count == 1 and verifier.generation is None
    await verifier.ready()
    assert verifier.full_validation_count == 2 and verifier.generation is not initial
    # Restart cannot inherit the first client's process-local trust.
    from uranus_research_service.semantic_generation import SemanticGenerationVerifier

    fresh = SemanticGenerationVerifier(client)
    assert fresh.generation is None
    await fresh.ready()
    assert fresh.full_validation_count == 1


async def test_concurrent_readiness_single_full_scan(generation):
    _, client, _ = generation
    original = client.points
    entered, release = asyncio.Event(), asyncio.Event()

    async def slow_scan():
        entered.set()
        await release.wait()
        return await original()

    client.points = AsyncMock(side_effect=slow_scan)
    tasks = [asyncio.create_task(client.generation_verifier.ready()) for _ in range(10)]
    await entered.wait()
    release.set()
    states = await asyncio.gather(*tasks)
    assert all(s is states[0] for s in states)
    client.points.assert_awaited_once()


async def test_failed_full_validation_clears_old_state(generation):
    data, client, _ = generation
    await client.validate()
    data.payload["index_owner"] = "foreign"
    with pytest.raises(ValueError):
        await client.validate()
    assert client.generation_verifier.generation is None


@pytest.mark.parametrize(
    "field,value",
    [
        ("id", "invalid"),
        ("id", str(UUID(int=99))),
        ("index_owner", "foreign"),
        ("entity_type", "venue"),
        ("entity_id", str(UUID(int=31))),
        ("embedding_model", "jina-v3"),
        ("embedding_version", "v3"),
        ("document_schema_version", "event-public-v1"),
        ("chunk_kind", "invalid"),
        ("chunk_index", -1),
        ("chunk_index", True),
        ("chunk_text", "stale"),
        ("content_hash", "0" * 64),
        ("evidence_contexts", []),
    ],
)
async def test_each_hit_validated_after_cheap_check(generation, field, value):
    data, client, _ = generation
    await client.validate()
    data.hit = copy.deepcopy(data.hit)
    if field == "id":
        data.hit[field] = value
    else:
        data.hit["payload"][field] = value
    with pytest.raises(ValueError, match="invalid_search_hit"):
        await client.search(VECTOR, entity_ids=[data.document.entity_id])
    assert not client.generation_verifier.is_verified


@pytest.mark.parametrize("validated_here", [False, True])
@pytest.mark.parametrize("operation", ["upsert", "payload", "delete", "write_manifest"])
async def test_sealed_generation_blocks_all_maintenance(settings, operation, validated_here):
    data = Collection()
    client = QdrantMaintenance(
        settings.model_copy(
            update={"qdrant_url": "http://127.0.0.1:16333", "qdrant_api_key": SecretStr("a" * 32)}
        ),
        build_id="test_one",
        isolated=True,
        transport=httpx.MockTransport(data.handler),
    )
    if validated_here:
        await client.validate()
    args = {
        "upsert": ([{"id": data.identity, "payload": data.payload, "vector": VECTOR}],),
        "payload": (data.identity, data.payload),
        "delete": ([MANIFEST_ID],),
        "write_manifest": (Manifest.model_validate(data.manifest),),
    }
    try:
        with pytest.raises(ValueError, match="sealed_generation"):
            await getattr(client, operation)(*args[operation])
    finally:
        await client.close()


async def test_readiness_mismatch_fails_then_explicitly_revalidates(generation):
    data, client, _ = generation
    verifier = client.generation_verifier
    await verifier.ready()
    data.manifest["created_at"] = "2026-10-06T00:00:00+00:00"
    with pytest.raises(ValueError, match="generation_changed"):
        await verifier.ready()
    assert verifier.full_validation_count == 1
    assert not verifier.is_verified
    await verifier.ready()
    assert verifier.full_validation_count == 2
    assert verifier.is_verified


async def test_unverified_request_does_not_bootstrap_trust(generation):
    data, client, _ = generation
    with pytest.raises(ValueError, match="verification_required"):
        await client.search(VECTOR, entity_ids=[data.document.entity_id])
    assert data.requests == []


async def test_change_during_full_scan_prevents_state_publication(generation):
    data, client, _ = generation
    original = client.points

    async def changing_scan():
        points = await original()
        data.manifest["created_at"] = "2026-10-06T00:00:00+00:00"
        return points

    client.points = changing_scan
    with pytest.raises(ValueError, match="generation_changed"):
        await client.validate()
    assert client.generation_verifier.generation is None


async def test_cancelled_full_validation_clears_trust_and_releases_lock(generation):
    _, client, _ = generation
    await client.validate()
    original = client.points
    entered = asyncio.Event()

    async def blocked_scan():
        entered.set()
        await asyncio.Event().wait()

    client.points = blocked_scan
    task = asyncio.create_task(client.validate())
    await entered.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert not client.generation_verifier.is_verified
    client.points = original
    await client.generation_verifier.ready()
    assert client.generation_verifier.is_verified
