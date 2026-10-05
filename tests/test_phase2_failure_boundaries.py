import asyncio
from copy import deepcopy
from unittest.mock import AsyncMock

import httpx
import pytest

from tests.structured_fixtures import GOLDENS, SOCIAL, envelope
from tests.test_structured_runtime import HEADERS
from uranus_research_service.app import create_app
from uranus_research_service.config import Settings
from uranus_research_service.errors import APIError
from uranus_research_service.geocoder import ResearchGeocoderClient
from uranus_research_service.planner import PlannerClient
from uranus_research_service.runtime import ResearchRuntime


@pytest.mark.parametrize(
    "failure,status",
    [
        ("timeout", 503),
        ("auth", 503),
        ("unavailable", 503),
        ("redirect", 502),
        ("html", 502),
        ("huge", 502),
        ("duplicate", 502),
        ("invalid_json", 502),
        ("wrong_contract", 502),
        ("error_body", 502),
    ],
)
async def test_planner_failure_http_mapping_no_reflection(settings, failure, status, caplog):
    secret = "private-upstream-value"

    def reply(request):
        if failure == "timeout":
            raise httpx.ReadTimeout(secret)
        if failure == "auth":
            return httpx.Response(401, text=secret)
        if failure == "unavailable":
            return httpx.Response(503, text=secret)
        if failure == "redirect":
            return httpx.Response(307, headers={"location": "https://untrusted.invalid"})
        if failure == "html":
            return httpx.Response(200, text=secret, headers={"content-type": "text/html"})
        if failure == "huge":
            return httpx.Response(
                200, content=b"x" * 32769, headers={"content-type": "application/json"}
            )
        if failure == "duplicate":
            return httpx.Response(
                200, content=b'{"x":1,"x":2}', headers={"content-type": "application/json"}
            )
        if failure == "invalid_json":
            return httpx.Response(200, content=b"{", headers={"content-type": "application/json"})
        if failure == "error_body":
            return httpx.Response(422, json={"error": {"message": secret}})
        return httpx.Response(
            200, json={"schema_version": "research-query-plan-v12", "private": secret}
        )

    planner = PlannerClient(settings, transport=httpx.MockTransport(reply))
    executor = AsyncMock()
    db = AsyncMock()
    runtime = ResearchRuntime(settings, planner=planner, database=db, areas=db, executor=executor)
    app = create_app(settings, runtime=runtime)
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post("/query", headers=HEADERS, json={"query": "private query"})
        assert response.status_code == status, response.text
        assert secret not in response.text and secret not in caplog.text
        executor.execute.assert_not_awaited()
        db.connection.assert_not_called()
    finally:
        await runtime.close()


@pytest.mark.parametrize(
    "code,status",
    [
        ("research_execution_unavailable", 503),
        ("research_execution_invalid_plan", 502),
        ("research_execution_unsupported", 422),
    ],
)
async def test_execution_failure_http_mapping(settings, code, status):
    planner = PlannerClient(
        settings,
        transport=httpx.MockTransport(
            lambda r: httpx.Response(200, json=envelope(GOLDENS[0]["plan"]))
        ),
    )
    executor = AsyncMock()
    executor.execute.side_effect = APIError(status, code, "PRIVATE-SQL-VALUES")
    runtime = ResearchRuntime(
        settings, planner=planner, database=AsyncMock(), areas=AsyncMock(), executor=executor
    )
    app = create_app(settings, runtime=runtime)
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            r = await client.post("/query", headers=HEADERS, json={"query": GOLDENS[0]["query"]})
        assert r.status_code == status and "PRIVATE" not in r.text
    finally:
        await runtime.close()


async def test_same_conversation_concurrency_and_ownership(settings):
    current = deepcopy(SOCIAL[0]["plan"])
    entered = asyncio.Event()
    release = asyncio.Event()
    block = [False]

    async def reply(request):
        if block[0]:
            entered.set()
            await release.wait()
        return httpx.Response(200, json=envelope(current))

    planner = PlannerClient(settings, transport=httpx.MockTransport(reply))
    runtime = ResearchRuntime(
        settings, planner=planner, database=AsyncMock(), areas=AsyncMock(), executor=AsyncMock()
    )
    app = create_app(settings, runtime=runtime)
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            body = {"query": current["original_query"]}
            first = await client.post("/query", headers=HEADERS, json=body)
            token = first.json()["response"]["conversation_id"]
            body["conversation_id"] = token
            block[0] = True
            task = asyncio.create_task(client.post("/query", headers=HEADERS, json=body))
            await entered.wait()
            try:
                busy = await client.post("/query", headers=HEADERS, json=body)
                assert busy.status_code == 503
            finally:
                release.set()
            assert (await task).status_code == 200
            other = await client.post(
                "/query", headers=HEADERS | {"X-Research-Principal": "b" * 64}, json=body
            )
            assert other.status_code == 200
            response = other.json()["response"]
            assert response["conversation_id"] != token
            assert response["interaction"]["conversation"]["reason"] == "needs_context"
    finally:
        await runtime.close()


@pytest.mark.parametrize("failure", ["timeout", "redirect", "type", "huge", "invalid"])
async def test_geocoder_transport_safe_failures(settings, failure):
    def reply(r):
        if failure == "timeout":
            raise httpx.ReadTimeout("private")
        if failure == "redirect":
            return httpx.Response(302, headers={"location": "https://other.invalid"})
        if failure == "type":
            return httpx.Response(200, text="private", headers={"content-type": "text/html"})
        if failure == "huge":
            return httpx.Response(
                200, content=b"x" * 262145, headers={"content-type": "application/json"}
            )
        return httpx.Response(200, json={"private": "invalid"})

    configured = settings.model_copy(update={"research_geocoder_api_key": settings.api_key})
    client = ResearchGeocoderClient(configured, transport=httpx.MockTransport(reply))
    try:
        with pytest.raises(APIError) as caught:
            await client.search("Flensburg")
        assert caught.value.status == 503 and "private" not in caught.value.message
    finally:
        await client.close()


async def test_encoder_never_blocks_structured_readiness(settings):
    runtime = ResearchRuntime(
        settings.model_copy(update={"encoder_api_key": None}),
        planner=AsyncMock(),
        database=AsyncMock(),
        areas=AsyncMock(),
    )
    try:
        assert runtime.capabilities().structured_query is False
        await runtime.ready()
        assert runtime.capabilities().structured_query is True
        assert runtime.capabilities().semantic_query is False
        runtime.areas.ready.side_effect = APIError(503, "research_execution_unavailable", "private")
        with pytest.raises(APIError):
            await runtime.ready()
        assert runtime.capabilities().structured_query is False
    finally:
        await runtime.close()


def test_database_secret_file_preferred_and_sanitized(monkeypatch, tmp_path):
    key = "synthetic-key-for-testing-0123456789"
    file = tmp_path / "reader"
    file.write_text("postgresql+asyncpg://reader:synthetic@127.0.0.1/db\n")
    monkeypatch.setenv("RESEARCH_API_KEY", key)
    monkeypatch.setenv("RESEARCH_DATABASE_URL_FILE", str(file))
    monkeypatch.setenv("RESEARCH_DATABASE_URL", "invalid-fallback")
    settings = Settings.from_env()
    assert settings.database_url.get_secret_value().startswith("postgresql+asyncpg://reader:")
    assert "synthetic@" not in str(settings)
    file.unlink()
    with pytest.raises(ValueError, match="invalid_secret_configuration"):
        Settings.from_env()


def test_execution_has_no_admin_or_vector_service_locator():
    import ast
    from pathlib import Path

    root = Path("src/uranus_research_service")
    for folder in ("research", "repositories", "services"):
        for path in (root / folder).rglob("*.py"):
            source = path.read_text()
            assert "request.app.state" not in source
            for node in ast.walk(ast.parse(source)):
                if isinstance(node, ast.ImportFrom) and node.module:
                    assert not node.module.startswith("app.")
                    assert not any(
                        part in node.module
                        for part in (
                            "encoder",
                            "vector_transport",
                            "semantic_search",
                            "admin_database",
                            "auth.",
                        )
                    )


def test_descendant_sqlalchemy_logs_are_suppressed(caplog):
    import logging

    from uranus_research_service.logging import configure_logging

    configure_logging()
    logging.getLogger("sqlalchemy.engine.Engine").error("PRIVATE_BIND_VALUES")
    logging.getLogger("sqlalchemy.pool.impl.QueuePool").error("PRIVATE_DSN")
    assert "PRIVATE" not in caplog.text
