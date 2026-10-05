import copy
import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock
from uuid import UUID, uuid5

import httpx
import pytest
from pydantic import SecretStr

from scripts.generate_contracts import canonical
from tests.semantic_fixtures import VECTOR, document, encoder_handler
from uranus_research_service.encoder import EncoderClient, validate_vectors
from uranus_research_service.errors import DependencyError
from uranus_research_service.qdrant import QdrantClient, QdrantMaintenance
from uranus_research_service.research.evidence_context import EvidenceContext
from uranus_research_service.research.semantic_evidence import (
    contextualize_event_hit,
    semantic_hits,
)
from uranus_research_service.research.semantic_limits import semantic_relevance_threshold
from uranus_research_service.research.vector_documents import POINT_NAMESPACE, Chunk, content_hash
from uranus_research_service.research.vector_models import V5
from uranus_research_service.research.vector_sync import plan_changes
from uranus_research_service.schemas.research_execution import ExecutionSemanticFilters
from uranus_research_service.semantic import retrieve
from uranus_research_service.semantic_manifest import Manifest, collection_name, digest


def prepared():
    d = document()
    c = Chunk(
        chunk_index=0,
        chunk_kind="content",
        contexts=[EvidenceContext(scope="event")],
        text=d.sections[0].text,
        content_hash=content_hash(d.sections[0].text),
        token_count=20,
    )
    plan = plan_changes([d], {str(d.entity_id): [c]}, {}, V5, complete=True, entity="event")
    return d, c, plan


@pytest.mark.parametrize(
    "bad",
    [
        [],
        [0.0] * 1024,
        [True] + [0.0] * 1023,
        ["1"] + [0.0] * 1023,
        [float("nan")] + [0.0] * 1023,
        [float("inf")] + [0.0] * 1023,
        [1.0] * 1024,
        [1.0] * 1023,
    ],
)
def test_vector_rejects(bad):
    with pytest.raises(ValueError):
        validate_vectors([bad], 1)


def test_vector_valid_and_count():
    validate_vectors([VECTOR], 1)
    with pytest.raises(ValueError):
        validate_vectors([VECTOR], 2)


async def test_embed_and_chunks_contract(settings):
    client = EncoderClient(settings, transport=httpx.MockTransport(encoder_handler))
    try:
        assert await client.embed(["jazz"], kind="query") == [VECTOR]
        assert await client.embed(["jazz"], kind="passage") == [VECTOR]
        chunks = await client.prepare([document()])
        assert chunks[str(UUID(int=30))][0].token_count == 20
    finally:
        await client.close()


@pytest.mark.parametrize(
    "mutation",
    ["version", "count", "bool", "hash", "entity", "index", "tokens", "contexts", "kind", "text"],
)
async def test_inference_failure_boundaries(settings, mutation):
    def handler(request):
        response = encoder_handler(request)
        if request.url.path not in {"/chunks", "/embed"}:
            return response
        data = response.json()
        if mutation == "version":
            data["embedding_version"] = "v3"
        elif request.url.path == "/embed":
            if mutation == "count":
                data["vectors"] = []
            if mutation == "bool":
                data["vectors"][0][0] = True
        else:
            c = data["documents"][0]["chunks"][0]
            if mutation == "hash":
                c["content_hash"] = "a" * 64
            if mutation == "entity":
                data["documents"][0]["entity_id"] = str(UUID(int=999))
            if mutation == "index":
                c["chunk_index"] = 1
            if mutation == "tokens":
                c["token_count"] = 481
            if mutation == "contexts":
                c["contexts"] = [{"scope": "venue", "venue_id": str(UUID(int=3))}]
            if mutation == "kind":
                c["chunk_kind"] = "private"
            if mutation == "text":
                c["text"] = "invented"
                c["content_hash"] = content_hash(c["text"])
        return httpx.Response(200, json=data)

    client = EncoderClient(settings, transport=httpx.MockTransport(handler))
    try:
        with pytest.raises(DependencyError):
            if mutation in {"version", "count", "bool"}:
                await client.embed(["hello"], kind="query")
            else:
                await client.prepare([document()])
    finally:
        await client.close()


@pytest.mark.parametrize(
    "key,value",
    [
        ("embedding_version", "v3"),
        ("model_revision", "bad"),
        ("dimensions", 768),
        ("dimensions", True),
        ("chunk_version", "v3"),
        ("index_owner", "foreign"),
        ("entity_type", "taxonomy"),
        ("distance", "Dot"),
        ("document_schema_version", "event-public-v1"),
        ("complete", False),
    ],
)
def test_manifest_closed(key, value):
    m = manifest({})
    with pytest.raises(ValueError):
        Manifest.model_validate({**m.model_dump(), key: value})


def manifest(points):
    return Manifest.create(
        entity_type="event",
        document_schema_version="event-public-v4",
        build_id="test_one",
        created_at=datetime.now(UTC).isoformat(),
        source_snapshot_hash="a" * 64,
        corpus_hash=digest(points),
        document_count=len({p["entity_id"] for p in points.values()}),
        chunk_count=len(points),
    )


def test_naming_and_stable_ids_sync():
    d, c, plan = prepared()
    identity = next(iter(plan.desired))
    assert identity == str(uuid5(POINT_NAMESPACE, f"event:{d.entity_id}:content:{c.content_hash}"))
    assert collection_name("event", "test_one") == "kulturbytes_events_jina_v5_build_test_one"
    for entity, build in [("foreign", None), ("event", "../v3"), ("event", "a?x")]:
        with pytest.raises(ValueError):
            collection_name(entity, build)
    stored = {i: p for i, (_, p) in plan.desired.items()}
    same = plan_changes([d], {str(d.entity_id): [c]}, stored, V5, complete=True, entity="event")
    assert same.unchanged == 1 and not same.embed
    changed = d.model_copy(
        update={"payload": d.payload.model_copy(update={"source_updated_at": "2026-10-05"})}
    )
    metadata = plan_changes(
        [changed], {str(d.entity_id): [c]}, stored, V5, complete=True, entity="event"
    )
    assert metadata.metadata == [identity] and not metadata.embed
    assert not plan_changes([], {}, stored, V5, complete=False, entity="event").delete
    assert plan_changes([], {}, stored, V5, complete=True, entity="event").delete == [identity]
    for key, value in [
        ("index_owner", "foreign"),
        ("embedding_version", "v3"),
        ("entity_type", "venue"),
    ]:
        bad = copy.deepcopy(stored)
        bad[identity][key] = value
        with pytest.raises(ValueError):
            plan_changes([d], {str(d.entity_id): [c]}, bad, V5, complete=True, entity="event")


@pytest.mark.parametrize(
    "url,build,isolated",
    [
        ("https://production.example", "test_a", True),
        ("http://127.0.0.1:6333", "test_a", True),
        ("http://127.0.0.1:16333", "live", True),
        ("http://127.0.0.1:16333", "test_a", False),
    ],
)
def test_write_guards(settings, url, build, isolated):
    with pytest.raises(ValueError):
        QdrantMaintenance(
            settings.model_copy(update={"qdrant_url": url}), build_id=build, isolated=isolated
        )


@pytest.mark.parametrize("kind", ["timeout", "distance", "dimension", "manifest"])
async def test_qdrant_failure(settings, kind):
    def handler(request):
        if kind == "timeout":
            raise httpx.ReadTimeout("secret")
        if request.url.path.endswith("/scroll"):
            value = {"points": [], "next_page_offset": None}
        else:
            value = {
                "config": {
                    "params": {
                        "vectors": {
                            "size": 768 if kind == "dimension" else 1024,
                            "distance": "Dot" if kind == "distance" else "Cosine",
                        }
                    }
                }
            }
        return httpx.Response(200, json={"status": "ok", "result": value})

    client = QdrantClient(
        settings.model_copy(update={"qdrant_api_key": SecretStr("a" * 32)}),
        build_id="test_one",
        transport=httpx.MockTransport(handler),
    )
    try:
        with pytest.raises((ValueError, DependencyError)) as exc:
            await client.validate()
        assert "secret" not in str(exc.value)
    finally:
        await client.close()


def test_evidence_and_threshold():
    d, c, plan = prepared()
    payload = next(iter(plan.desired.values()))[1]
    hits = semantic_hits([{"score": 0.8, "payload": payload}], {d.entity_id}, V5, entity="event")
    assert len(hits) == 1
    assert contextualize_event_hit(hits[0], venue_id=None, space_id=None, occurrence_id=None)
    assert semantic_relevance_threshold([0.8, 0.1]) == pytest.approx(0.32)
    assert semantic_relevance_threshold([0.01]) == 0.1
    assert semantic_relevance_threshold([]) is None
    for key, value in [
        ("index_owner", "foreign"),
        ("embedding_version", "v3"),
        ("entity_type", "venue"),
    ]:
        assert not semantic_hits(
            [{"score": 0.8, "payload": {**payload, key: value}}], {d.entity_id}, V5, entity="event"
        )
    with pytest.raises(ValueError):
        semantic_hits(
            [{"score": 0.8, "payload": {**payload, "chunk_text": "stale"}}],
            {d.entity_id},
            V5,
            entity="event",
        )


async def test_empty_eligibility_and_db_unavailable():
    source = AsyncMock()
    source.eligible.return_value = []
    encoder = AsyncMock()
    qdrant = AsyncMock()
    qdrant.entity = "event"
    assert not (await retrieve(source, encoder, qdrant, ExecutionSemanticFilters(q="jazz"))).items
    encoder.embed.assert_not_called()
    qdrant.search.assert_not_called()
    source.eligible.side_effect = ValueError("database_unavailable")
    with pytest.raises(ValueError):
        await retrieve(source, encoder, qdrant, ExecutionSemanticFilters(q="jazz"))
    encoder.embed.assert_not_called()


def test_encoder_snapshot_parity():
    from pathlib import Path

    from uranus_research_service import encoder_contracts as c

    for name in (
        "EmbedRequest",
        "EmbedResponse",
        "ChunkRequest",
        "ChunkResponse",
        "Section",
        "Chunk",
        "EvidenceContext",
    ):
        assert canonical(getattr(c, name).model_json_schema()) == json.loads(
            Path(f"contracts/encoder/{name}.json").read_text()
        )


async def test_internal_validated_plan_only(settings):
    from copy import deepcopy

    from tests.structured_fixtures import GOLDENS, envelope
    from uranus_research_service.repositories.research_resolution import Resolution
    from uranus_research_service.research.wire.research_v13_schema import PlanResponseV13
    from uranus_research_service.semantic import retrieve_plan

    case = deepcopy(GOLDENS[0])
    case["plan"]["interaction"]["research_plan"].update(
        intent="search", semantic={"query": "ruhige Kultur", "focus": None}
    )
    response = PlanResponseV13.model_validate_json(json.dumps(envelope(case["plan"])))
    source = AsyncMock()
    source.settings = settings
    source.eligible.return_value = []
    resolver = AsyncMock()
    resolver.resolve.return_value = Resolution()
    qdrant = AsyncMock()
    qdrant.entity = "event"
    result = await retrieve_plan(response, resolver, source, AsyncMock(), qdrant)
    assert result.returned_count == 0
    resolver.resolve.assert_awaited_once()


async def test_semantic_readiness_independent(settings, monkeypatch):
    import uranus_research_service.runtime as module

    encoder = AsyncMock()
    encoder.ready.side_effect = DependencyError("encoder", "incompatible")
    qdrant = AsyncMock()
    qdrant.generation_verifier = Mock(is_verified=True, ready=AsyncMock())
    monkeypatch.setattr(module, "EncoderClient", lambda *a, **kw: encoder)
    monkeypatch.setattr(module, "QdrantClient", lambda *a, **kw: qdrant)
    runtime = module.ResearchRuntime(
        settings.model_copy(update={"semantic_build_id": "test_one"}),
        planner=AsyncMock(),
        database=AsyncMock(),
        areas=AsyncMock(),
    )
    try:
        await runtime.ready()
        assert runtime.capabilities().structured_query
        assert not runtime.capabilities().semantic_index_ready
        assert not runtime.capabilities().semantic_query
        qdrant.validate.assert_not_called()
        encoder.ready.side_effect = None
        await runtime.ready()
        assert runtime.capabilities().semantic_index_ready
        qdrant.generation_verifier.ready.side_effect = ValueError("missing_manifest")
        await runtime.ready()
        assert (
            runtime.capabilities().structured_query
            and not runtime.capabilities().semantic_index_ready
        )
    finally:
        await runtime.close()


def test_internal_schema_snapshots():
    from pathlib import Path

    from uranus_research_service.semantic import RetrievalResult

    for model in (Manifest, RetrievalResult):
        assert canonical(model.model_json_schema()) == json.loads(
            Path(f"contracts/semantic/{model.__name__}.json").read_text()
        )


async def test_encoder_rejects_wrong_service_release(settings, encoder_version):
    encoder_version["service_version"] = "0.1.0"
    client = EncoderClient(
        settings, transport=httpx.MockTransport(lambda r: httpx.Response(200, json=encoder_version))
    )
    try:
        with pytest.raises(DependencyError, match="incompatible"):
            await client.ready()
    finally:
        await client.close()


@pytest.mark.parametrize(
    "field",
    [
        "manifest_owner",
        "index_owner",
        "embedding_model",
        "embedding_version",
        "model_revision",
        "dimensions",
        "distance",
        "chunk_version",
        "complete",
    ],
)
def test_manifest_missing_pins_do_not_default(field):
    value = manifest({}).model_dump()
    del value[field]
    with pytest.raises(ValueError):
        Manifest.model_validate(value)


@pytest.mark.parametrize("field,value", [("dimensions", 1024.0), ("complete", 1)])
def test_manifest_pin_types_are_exact(field, value):
    with pytest.raises(ValueError):
        Manifest.model_validate({**manifest({}).model_dump(), field: value})
