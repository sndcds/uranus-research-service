from importlib.metadata import version

import pytest
from pydantic import ValidationError

from tests.conftest import KEY
from uranus_research_service.config import Settings
from uranus_research_service.contracts import QueryRequest
from uranus_research_service.version import SERVICE_VERSION


@pytest.mark.parametrize(
    "key", ["short", "x" * 31, "x" * 4097, "x" * 32 + "\n", "x" * 32 + " ", "é" * 32]
)
def test_invalid_keys(key):
    with pytest.raises(ValidationError):
        Settings(api_key=key)


@pytest.mark.parametrize(
    "origin",
    [
        "http://external.invalid",
        "https://host/path",
        "https://user:pass@host",
        "https://host?key=secret",
        "https://host/#frag",
        "https://host/%0a",
        "https://*.host",
        "https://[::1]junk",
        " https://host",
        "https://host:99999",
        "ftp://host",
    ],
)
def test_fixed_origins(origin):
    with pytest.raises(ValidationError):
        Settings(api_key=KEY, planner_url=origin)


@pytest.mark.parametrize(
    "origin", ["http://127.0.0.1:6334", "http://[::1]:6334", "https://planner.internal.invalid"]
)
def test_valid_origins(origin):
    assert Settings(api_key=KEY, planner_url=origin).planner_url == origin


def test_file_secrets_preferred_and_missing_file_never_falls_back(monkeypatch, tmp_path):
    path = tmp_path / "key"
    path.write_text(KEY + "\n")
    monkeypatch.setenv("RESEARCH_API_KEY_FILE", str(path))
    monkeypatch.setenv("RESEARCH_API_KEY", "invalid environment key")
    settings = Settings.from_env()
    assert settings.api_key.get_secret_value() == KEY and KEY not in repr(settings)
    path.unlink()
    with pytest.raises(ValueError, match="invalid_secret_configuration"):
        Settings.from_env()


@pytest.mark.parametrize(
    "field,value",
    [
        ("language", "fr"),
        ("timezone", "Invalid/Zone"),
        ("query", " "),
        ("query", "x" * 2001),
        ("conversation_id", "private-id"),
        ("query", 42),
    ],
)
def test_invalid_query_contract(field, value):
    with pytest.raises(ValidationError):
        QueryRequest.model_validate({"query": "Welche Events?", field: value})


@pytest.mark.parametrize(
    "field",
    [
        "model",
        "collection",
        "embedding_version",
        "planner_version",
        "sql",
        "backend",
        "repository",
        "provider",
        "principal",
        "conversation_context",
    ],
)
def test_no_routing_selectors(field):
    with pytest.raises(ValidationError):
        QueryRequest.model_validate({"query": "Welche Events?", field: "untrusted"})


def test_request_preserves_text_and_validates_location():
    assert QueryRequest(query="  Jazz?  ").query == "  Jazz?  "
    with pytest.raises(ValidationError):
        QueryRequest(query="Jazz?", location_context={"source": "manual", "latitude": 54.8})
    with pytest.raises(ValidationError):
        QueryRequest(
            query="Jazz?",
            location_context={"source": "manual", "latitude": float("nan"), "longitude": 9.4},
        )
    assert QueryRequest(
        query="Jazz?", location_context={"source": "manual", "display_name": "Flensburg"}
    ).location_context


def test_package_version():
    assert version("uranus-research-service") == SERVICE_VERSION


@pytest.mark.parametrize(
    "field,value",
    [
        ("dependency_timeout_seconds", float("nan")),
        ("dependency_timeout_seconds", float("inf")),
        ("max_response_bytes", 10000000),
        ("max_concurrent_requests", 0),
        ("body_timeout_seconds", 0),
        ("planner_contract", "v8"),
        ("planner_url", "https://host:"),
    ],
)
def test_configuration_limits(field, value):
    with pytest.raises(ValidationError):
        Settings(api_key=KEY, **{field: value})
