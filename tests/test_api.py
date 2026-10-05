import asyncio
import logging
from unittest.mock import AsyncMock

import httpx
import pytest

from tests.conftest import KEY
from uranus_research_service.app import create_app
from uranus_research_service.errors import DependencyError
from uranus_research_service.logging import SafeFormatter, logger
from uranus_research_service.version import CONTRACT_VERSION, MODEL_REVISION


@pytest.fixture
async def api(settings):
    planner, encoder = AsyncMock(), AsyncMock()
    app = create_app(settings, planner=planner, encoder=encoder)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
            headers={"Authorization": "Bearer " + KEY},
        ) as client,
    ):
        yield client, planner, encoder


async def test_health_version_and_disabled_query(api):
    client, planner, encoder = api
    result = await client.get("/health", headers={"Authorization": ""})
    assert result.status_code == 200 and result.content == b'{"status":"ok"}'
    planner.ready.assert_not_awaited()
    encoder.ready.assert_not_awaited()
    metadata = (await client.get("/version")).json()
    assert (
        metadata["contract_version"] == CONTRACT_VERSION
        and metadata["embedding_revision"] == MODEL_REVISION
    )
    assert metadata["dimensions"] == 1024 and metadata["query_enabled"] is False
    assert KEY not in str(metadata) and "url" not in str(metadata)
    result = await client.post("/query", json={"query": "Welche Events?"})
    assert result.status_code == 501 and result.json()["error"]["code"] == "query_not_enabled"
    planner.ready.assert_not_awaited()
    encoder.ready.assert_not_awaited()
    assert (await client.get("/health/")).status_code == 404
    assert (await client.get("/docs")).status_code == 404


async def test_ready_and_dependency_failures(api):
    client, planner, encoder = api
    assert (await client.get("/ready")).json() == {"status": "ready", "query_enabled": False}
    planner.ready.side_effect = DependencyError("planner", "unavailable")
    encoder.ready.reset_mock()
    result = await client.get("/ready")
    assert result.status_code == 503 and result.json()["error"]["code"] == "not_ready"
    encoder.ready.assert_not_awaited()
    planner.ready.side_effect = None
    encoder.ready.side_effect = DependencyError("encoder", "incompatible")
    assert (await client.get("/ready")).status_code == 503


@pytest.mark.parametrize("path", ["/version", "/ready", "/query"])
async def test_auth_required_before_dependencies(api, path):
    client, planner, encoder = api
    result = await client.request(
        "POST" if path == "/query" else "GET",
        path,
        headers={"Authorization": ""},
        content=b"private",
    )
    assert result.status_code == 401
    planner.ready.assert_not_awaited()
    encoder.ready.assert_not_awaited()


@pytest.mark.parametrize(
    "headers",
    [
        [("Authorization", "Bearer " + KEY), ("Authorization", "Bearer " + KEY)],
        [("Cookie", "admin_session=private")],
        [("Origin", "https://browser.invalid")],
    ],
)
async def test_duplicates_and_browser_credentials_rejected(api, headers):
    client, planner, encoder = api
    response = await client.get("/ready", headers=headers)
    assert response.status_code in {401, 422}
    planner.ready.assert_not_awaited()


async def test_body_limit_json_and_secrets_not_reflected(api):
    client, planner, encoder = api

    async def large():
        for _ in range(10):
            yield b"x" * 4000

    assert (
        await client.post("/query", content=large(), headers={"Content-Type": "application/json"})
    ).status_code == 413
    for raw in [b'{"query":"private", "query":"other"}', b'{"query":NaN}', b"not-json"]:
        response = await client.post(
            "/query", content=raw, headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 422 and "private" not in response.text
    result = await client.post("/query", json={"query": "private", "model": "private-model"})
    assert result.status_code == 422 and "private" not in result.text
    planner.ready.assert_not_awaited()


async def test_concurrency_limit(settings):
    settings = settings.model_copy(update={"max_concurrent_requests": 1})
    entered = asyncio.Event()
    release = asyncio.Event()

    async def blocked():
        entered.set()
        await release.wait()

    planner = AsyncMock()
    planner.ready.side_effect = blocked
    app = create_app(settings, planner=planner, encoder=AsyncMock())
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
            headers={"Authorization": "Bearer " + KEY},
        ) as client,
    ):
        first = asyncio.create_task(client.get("/ready"))
        await entered.wait()
        try:
            assert (await client.get("/ready")).status_code == 503
        finally:
            release.set()
        assert (await first).status_code == 200


async def test_request_logs_do_not_contain_input(api, caplog):
    client, planner, encoder = api
    logger.addHandler(caplog.handler)
    try:
        await client.post("/query", json={"query": "private-query-example"})
        assert "private-query-example" not in caplog.text and KEY not in caplog.text
        assert all(not hasattr(r, "query") and not r.exc_info for r in caplog.records)
    finally:
        logger.removeHandler(caplog.handler)


def test_log_formatter_drops_unapproved_fields_and_exception_text():
    record = logging.LogRecord("x", 40, "secret/path", 1, "private provider reply", (), None)
    record.authorization = KEY
    record.query = "private query"
    record.status_code = 503
    formatted = SafeFormatter().format(record)
    assert KEY not in formatted and "private" not in formatted and "503" in formatted


async def test_slow_request_body_and_total_timeout(settings):
    configured = settings.model_copy(
        update={"body_timeout_seconds": 0.01, "request_timeout_seconds": 0.01}
    )
    planner = AsyncMock()
    planner.ready.side_effect = lambda: None

    async def slow_ready():
        await asyncio.sleep(0.05)

    planner.ready.side_effect = slow_ready
    app = create_app(configured, planner=planner, encoder=AsyncMock())

    async def slow_body():
        yield b"{"
        await asyncio.sleep(0.05)
        yield b"}"

    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
            headers={"Authorization": "Bearer " + KEY},
        ) as client,
    ):
        result = await client.post(
            "/query", content=slow_body(), headers={"Content-Type": "application/json"}
        )
        assert result.status_code == 503 and result.json()["error"]["code"] == "request_timeout"
        planner.ready.assert_not_awaited()
        assert (await client.get("/ready")).status_code == 503
        assert (await client.get("/health")).json() == {"status": "ok"}


async def test_provider_error_is_not_reflected_or_logged(settings, caplog):
    from uranus_research_service.planner import PlannerClient

    secret = "provider-private-body-token-example"
    planner = PlannerClient(
        settings,
        transport=httpx.MockTransport(lambda r: httpx.Response(500, json={"secret": secret})),
    )
    app = create_app(settings, planner=planner, encoder=AsyncMock())
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
            headers={"Authorization": "Bearer " + KEY},
        ) as client,
    ):
        logger.addHandler(caplog.handler)
        try:
            result = await client.get("/ready")
            assert result.status_code == 503 and secret not in result.text
            assert secret not in caplog.text and KEY not in caplog.text
        finally:
            logger.removeHandler(caplog.handler)
