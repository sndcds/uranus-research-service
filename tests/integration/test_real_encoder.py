"""Optional local real-weight HTTP evidence, never CI-required or a live probe."""

import os
from urllib.parse import urlsplit

import pytest

from tests.semantic_fixtures import document
from uranus_research_service.encoder import EncoderClient, validate_vectors
from uranus_research_service.version import EMBEDDING_VERSION

pytestmark = [pytest.mark.integration, pytest.mark.real_encoder]


@pytest.fixture
async def real_encoder(settings):
    url = os.environ.get("TEST_ENCODER_URL")
    if not url:
        pytest.skip("TEST_ENCODER_URL required for optional real-weight evidence")
    if urlsplit(url).hostname not in {"127.0.0.1", "::1"} or urlsplit(url).port == 6335:
        pytest.fail("Only isolated local encoder permitted")
    client = EncoderClient(
        settings.model_copy(update={"encoder_url": url, "dependency_timeout_seconds": 30})
    )
    try:
        yield client
    finally:
        await client.close()


async def test_real_query_passage_determinism(real_encoder):
    await real_encoder.ready()
    version = await real_encoder.get("/version")
    assert version["embedding_version"] == EMBEDDING_VERSION
    a = await real_encoder.embed(["Musik für alle"], kind="query")
    b = await real_encoder.embed(["Musik für alle"], kind="query")
    c = await real_encoder.embed(["Titel: Musik für alle"], kind="passage")
    validate_vectors(a, 1)
    validate_vectors(c, 1)
    assert a == b
    chunks = await real_encoder.prepare([document()])
    assert chunks and all(c.token_count <= 480 for batch in chunks.values() for c in batch)


async def test_real_index_and_benchmark(real_encoder, db_settings, root_connection, tmp_path):
    from pathlib import Path
    from uuid import UUID, uuid4

    from pydantic import SecretStr

    from tests.integration.test_semantic_index import NOW
    from uranus_research_service.benchmark import load_cases, run_benchmark
    from uranus_research_service.database import ResearchDatabase
    from uranus_research_service.indexing import build, save_report
    from uranus_research_service.qdrant import QdrantMaintenance
    from uranus_research_service.repositories.semantic_source import SemanticSource

    url = os.environ.get("TEST_QDRANT_URL")
    if not url:
        pytest.skip("TEST_QDRANT_URL required")
    db, areas = ResearchDatabase(db_settings), ResearchDatabase(db_settings, "area")
    source = SemanticSource(db, areas, db_settings)
    client = QdrantMaintenance(
        db_settings.model_copy(
            update={
                "qdrant_url": url,
                "qdrant_api_key": SecretStr("synthetic-service-key-for-tests-0123456789"),
            }
        ),
        build_id="test_real_" + uuid4().hex[:12],
        isolated=True,
    )
    try:
        await root_connection.execute(
            "UPDATE uranus.event SET summary='Jazzmusik in entspannter Atmosphäre' WHERE uuid=$1",
            UUID(int=30),
        )
        await root_connection.execute(
            "UPDATE uranus.venue SET accessibility_summary=$2 WHERE uuid=$1",
            UUID(int=20),
            "Stufenloser Zugang. Rollstuhlgerechter Eingang.",
        )
        report = await build(
            source, real_encoder, client, report_path=tmp_path / "real-build.json", now=NOW
        )
        assert report["document_count"] == 2
        benchmark = await run_benchmark(
            load_cases("tests/fixtures/retrieval_goldens.json"),
            source,
            real_encoder,
            client,
            now=NOW,
        )
        benchmark.update({k: report[k] for k in ("documents", "average_tokens", "max_tokens")})
        save_report(tmp_path / "real-benchmark.json", benchmark)
        if output := os.environ.get("VALIDATION_OUTPUT_DIR"):
            save_report(Path(output) / ("index-build-" + client.build_id + ".json"), report)
            save_report(Path(output) / ("benchmark-" + client.build_id + ".json"), benchmark)
    finally:
        await root_connection.execute(
            "UPDATE uranus.event SET summary=NULL WHERE uuid=$1", UUID(int=30)
        )
        await root_connection.execute(
            "UPDATE uranus.venue SET accessibility_summary=NULL WHERE uuid=$1", UUID(int=20)
        )
        await client.inactive()
        await client.call("DELETE", "", missing_ok=True)
        await client.close()
        await db.close()
        await areas.close()
