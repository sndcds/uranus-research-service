"""Real disposable PostGIS + Qdrant; synthetic Encoder over the real HTTP contract."""

import os
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

import httpx
import pytest
from pydantic import SecretStr

from tests.semantic_fixtures import encoder_handler
from uranus_research_service.database import ResearchDatabase
from uranus_research_service.encoder import EncoderClient
from uranus_research_service.errors import DependencyError
from uranus_research_service.indexing import build
from uranus_research_service.qdrant import QdrantMaintenance
from uranus_research_service.repositories.semantic_source import SemanticSource
from uranus_research_service.schemas.research_execution import ExecutionSemanticFilters
from uranus_research_service.semantic import retrieve
from uranus_research_service.semantic_manifest import MANIFEST_ID

pytestmark = pytest.mark.integration
NOW = datetime(2026, 10, 5, tzinfo=UTC)


@pytest.fixture
async def qdrant(settings):
    url = os.environ.get("TEST_QDRANT_URL")
    if not url:
        pytest.skip("TEST_QDRANT_URL required; isolated loopback nondefault port only")
    configured = settings.model_copy(
        update={
            "qdrant_url": url,
            "qdrant_api_key": SecretStr("synthetic-service-key-for-tests-0123456789"),
        }
    )
    client = QdrantMaintenance(
        configured, build_id="test_" + uuid4().hex, isolated=True, test_recovery=True
    )
    try:
        yield client
    finally:
        # Only this fixture's unique collection; never external collection names.
        await client.inactive()
        await client.call("DELETE", "", missing_ok=True)
        await client.close()


async def test_full_build_reuse_evidence_rehydration(
    db_settings, qdrant, tmp_path, root_connection
):
    db, areas = ResearchDatabase(db_settings), ResearchDatabase(db_settings, "area")
    source = SemanticSource(db, areas, db_settings)

    def no_open_snapshot(request):
        assert db.engine.pool.checkedout() == areas.engine.pool.checkedout() == 0
        return encoder_handler(request)

    encoder = EncoderClient(db_settings, transport=httpx.MockTransport(no_open_snapshot))
    try:
        report = await build(source, encoder, qdrant, report_path=tmp_path / "build.json", now=NOW)
        assert report["document_count"] == 2 and report["chunk_count"] >= 2
        assert len(report["smoke"]) == 3
        assert (await qdrant.validate()).chunk_count == report["chunk_count"]
        repeated = await build(
            source, encoder, qdrant, report_path=tmp_path / "repeat.json", now=NOW
        )
        assert (
            repeated["new"]
            == repeated["updated"]
            == repeated["metadata_updated"]
            == repeated["deleted"]
            == 0
        )
        assert repeated["unchanged"] == report["chunk_count"]
        filters = ExecutionSemanticFilters(q="Musik", venue_id=UUID(int=20))
        assert (await qdrant.get_manifest()).chunk_count == repeated["chunk_count"]
        assert (await qdrant.info())["points_count"] == repeated["chunk_count"] + 1
        with patch.object(
            qdrant, "points", AsyncMock(side_effect=AssertionError("full scan in query path"))
        ):
            result = await retrieve(source, encoder, qdrant, filters, now=NOW)
        assert [i.entity_key for i in result.items] == [UUID(int=30)]
        # Modify authoritative public source; self-consistent old payload must not win.
        await root_connection.execute(
            "UPDATE uranus.event SET title='Neue Ausstellung' WHERE uuid=$1", UUID(int=30)
        )
        stale = await retrieve(source, encoder, qdrant, filters, now=NOW)
        assert not any(i.semantic.matched_aspect == "content" for i in stale.items)
        changed = await build(
            source, encoder, qdrant, report_path=tmp_path / "changed.json", now=NOW
        )
        assert changed["new"] >= 1 and changed["deleted"] >= 1
        fresh = await retrieve(source, encoder, qdrant, filters, now=NOW)
        assert fresh.items
        # Public status/date eligibility always comes from PostgreSQL.
        await root_connection.execute(
            "UPDATE uranus.event SET release_status='draft' WHERE uuid=$1", UUID(int=30)
        )
        assert not (await retrieve(source, encoder, qdrant, filters, now=NOW)).items
        await qdrant.delete([MANIFEST_ID])
        with pytest.raises(ValueError, match="missing_manifest"):
            await qdrant.validate()
        recovered = await build(
            source, encoder, qdrant, report_path=tmp_path / "recovered.json", now=NOW
        )
        assert recovered["document_count"] == 1
    finally:
        await root_connection.execute(
            "UPDATE uranus.event SET title='Jazz im Haus',release_status='released' WHERE uuid=$1",
            UUID(int=30),
        )
        await encoder.close()
        await db.close()
        await areas.close()


async def test_wrong_qdrant_dimensions_and_manifest(qdrant):
    await qdrant.call("PUT", "", {"vectors": {"size": 768, "distance": "Cosine"}})
    with pytest.raises(DependencyError):
        await qdrant.info()


async def test_manifest_detects_tampering(db_settings, qdrant, tmp_path):
    from tests.semantic_fixtures import VECTOR
    from tests.test_semantic_v5 import prepared
    from uranus_research_service.research.semantic_contracts import OWNER
    from uranus_research_service.semantic_manifest import Manifest, digest
    from uranus_research_service.version import EMBEDDING_VERSION

    d, c, plan = prepared()
    identity = next(iter(plan.desired))
    payload = plan.desired[identity][1]
    await qdrant.create()
    await qdrant.upsert([{"id": identity, "vector": VECTOR, "payload": payload}])
    m = Manifest.create(
        entity_type="event",
        document_schema_version="event-public-v4",
        build_id=qdrant.build_id,
        created_at=NOW.isoformat(),
        source_snapshot_hash="a" * 64,
        corpus_hash=digest({identity: payload}),
        document_count=1,
        chunk_count=1,
    )
    await qdrant.write_manifest(m)
    await qdrant.validate()
    qdrant.test_recovery = False
    with pytest.raises(ValueError, match="sealed_generation"):
        await qdrant.delete([MANIFEST_ID])
    qdrant.test_recovery = True  # Explicit fixture-only tampering/recovery below.
    for key, value in [
        ("index_owner", "foreign"),
        ("entity_type", "venue"),
        ("embedding_version", "v3"),
        ("content_hash", "0" * 64),
        ("chunk_text", "stale"),
    ]:
        await qdrant.call(
            "PUT",
            "/points/payload?wait=true",
            {"points": [identity], "payload": {**payload, key: value}},
        )
        with pytest.raises(ValueError):
            await qdrant.validate()
        await qdrant.payload(identity, payload)
    assert payload["index_owner"] == OWNER and payload["embedding_version"] == EMBEDDING_VERSION
    await qdrant.validate()
