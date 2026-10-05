import asyncio

import httpx
import pytest

from uranus_research_service.encoder import EncoderClient
from uranus_research_service.errors import DependencyError
from uranus_research_service.planner import PlannerClient
from uranus_research_service.version import ENCODER_EXPECTED


@pytest.mark.parametrize("contract", ["v9", "v10", "v11", "v12", "v13"])
async def test_planner_ready_checks_exact_route_without_inference(settings, contract):
    calls = []

    def handler(request):
        calls.append((request.method, request.url.path))
        assert request.content == b""
        assert request.headers["Authorization"].startswith("Bearer ")
        if request.url.path == "/ready":
            return httpx.Response(200, json={"status": "ready"})
        assert request.method == "OPTIONS" and request.url.path == f"/{contract}/plan"
        return httpx.Response(405, headers={"Allow": "POST"}, json={"detail": "Method Not Allowed"})

    client = PlannerClient(
        settings.model_copy(update={"planner_contract": contract}),
        transport=httpx.MockTransport(handler),
    )
    try:
        await client.ready()
        assert calls == [("GET", "/ready"), ("OPTIONS", f"/{contract}/plan")]
    finally:
        await client.close()


async def test_encoder_ready_uses_real_metadata_shapes(settings, encoder_version, encoder_ready):
    calls = []

    def handler(request):
        calls.append(request.url.path)
        assert request.method == "GET" and "cookie" not in request.headers
        return httpx.Response(
            200,
            json=encoder_version if request.url.path == "/version" else encoder_ready,
            headers={"Set-Cookie": "untrusted=value"},
        )

    client = EncoderClient(settings, transport=httpx.MockTransport(handler))
    try:
        await client.ready()
        assert calls == ["/version", "/ready"]
    finally:
        await client.close()


@pytest.mark.parametrize(
    "field,stage",
    [
        (field, stage)
        for field in [*ENCODER_EXPECTED, "backend"]
        for stage in ["version", "ready"]
        if not (stage == "ready" and field in {"model_repository", "chunk_version"})
    ],
)
async def test_encoder_identity_is_fail_closed(
    settings, encoder_version, encoder_ready, field, stage
):
    data = encoder_version if stage == "version" else encoder_ready
    data[field] = "wrong-v3-or-foreign-contract"
    client = EncoderClient(
        settings,
        transport=httpx.MockTransport(
            lambda r: httpx.Response(
                200, json=encoder_version if r.url.path == "/version" else encoder_ready
            )
        ),
    )
    try:
        with pytest.raises(DependencyError, match="incompatible"):
            await client.ready()
    finally:
        await client.close()


@pytest.mark.parametrize("value", [True, "1024", 1024.0, None])
async def test_dimension_types_do_not_coerce(settings, encoder_version, value):
    encoder_version["dimensions"] = value
    client = EncoderClient(
        settings, transport=httpx.MockTransport(lambda r: httpx.Response(200, json=encoder_version))
    )
    try:
        with pytest.raises(DependencyError):
            await client.ready()
    finally:
        await client.close()


@pytest.mark.parametrize("kind", ["planner", "encoder"])
@pytest.mark.parametrize(
    "case",
    [
        "timeout",
        "invalid_json",
        "not_object",
        "bad_content_type",
        "oversized",
        "upstream_error",
        "redirect",
        "duplicate_json",
        "nonfinite",
        "compressed",
    ],
)
async def test_provider_failure_boundaries(settings, kind, case):
    calls = []

    def handler(request):
        calls.append(request)
        if case == "timeout":
            raise httpx.ReadTimeout("private provider body and token", request=request)
        if case == "invalid_json":
            return httpx.Response(
                200, content=b"{secret", headers={"Content-Type": "application/json"}
            )
        if case == "not_object":
            return httpx.Response(200, json=[])
        if case == "bad_content_type":
            return httpx.Response(200, text="private html")
        if case == "oversized":
            return httpx.Response(
                200, content=b" " * 65537, headers={"Content-Type": "application/json"}
            )
        if case == "upstream_error":
            return httpx.Response(500, json={"secret": "provider-private"})
        if case == "redirect":
            return httpx.Response(307, headers={"Location": "https://evil.invalid"})
        if case == "duplicate_json":
            return httpx.Response(
                200,
                content=b'{"status":"ready","status":"bad"}',
                headers={"Content-Type": "application/json"},
            )
        if case == "nonfinite":
            return httpx.Response(
                200, content=b'{"value":NaN}', headers={"Content-Type": "application/json"}
            )
        return httpx.Response(
            200,
            content=b"compressed",
            headers={"Content-Type": "application/json", "Content-Encoding": "gzip"},
        )

    client = (PlannerClient if kind == "planner" else EncoderClient)(
        settings, transport=httpx.MockTransport(handler)
    )
    try:
        with pytest.raises(DependencyError) as error:
            await client.ready()
        assert "private" not in str(error.value)
        assert len(calls) == 1
        assert not client.http.follow_redirects and not client.http._trust_env
    finally:
        await client.close()


@pytest.mark.parametrize(
    "status,allow",
    [(404, "POST"), (200, "POST"), (405, "GET"), (405, "POST, GET"), (503, "POST"), (401, "POST")],
)
async def test_planner_wrong_route_or_version_never_falls_back(settings, status, allow):
    calls = []

    def handler(r):
        calls.append(r.url.path)
        if r.url.path == "/ready":
            return httpx.Response(200, json={"status": "ready"})
        return httpx.Response(status, headers={"Allow": allow}, json={"detail": "private"})

    client = PlannerClient(settings, transport=httpx.MockTransport(handler))
    try:
        with pytest.raises(DependencyError):
            await client.ready()
        assert calls == ["/ready", "/v13/plan"]
    finally:
        await client.close()


class SlowStream(httpx.AsyncByteStream):
    async def __aiter__(self):
        yield b"{"
        await asyncio.sleep(0.05)
        yield b"}"


async def test_total_deadline_bounds_slow_stream(settings):
    client = PlannerClient(
        settings.model_copy(update={"dependency_timeout_seconds": 0.01}),
        transport=httpx.MockTransport(
            lambda r: httpx.Response(
                200, stream=SlowStream(), headers={"Content-Type": "application/json"}
            )
        ),
    )
    try:
        with pytest.raises(DependencyError, match="unavailable"):
            await client.ready()
    finally:
        await client.close()


async def test_missing_keys_fail_before_transport(settings):
    client = PlannerClient(
        settings.model_copy(update={"planner_api_key": None}),
        transport=httpx.MockTransport(
            lambda r: pytest.fail("unconfigured provider must not be called")
        ),
    )
    try:
        with pytest.raises(DependencyError, match="unconfigured"):
            await client.ready()
    finally:
        await client.close()


async def test_environment_proxies_and_inference_paths_are_disabled(settings, monkeypatch):
    monkeypatch.setenv("HTTPS_PROXY", "http://private-proxy.invalid:9999")
    monkeypatch.setenv("HTTP_PROXY", "http://private-proxy.invalid:9999")
    client = EncoderClient(
        settings, transport=httpx.MockTransport(lambda r: pytest.fail("No call allowed"))
    )
    try:
        assert not client.http._trust_env and not client.http._mounts
        with pytest.raises(ValueError):
            await client.get("/embed")
        with pytest.raises(ValueError):
            await client.route("v13")
    finally:
        await client.close()
