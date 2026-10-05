"""Independent pinned snapshots, provenance and intentional request extensions."""

import hashlib
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from scripts.generate_contracts import canonical
from uranus_research_service.app import create_app
from uranus_research_service.contracts import (
    HealthResponse,
    QueryRequest,
    QueryResponse,
    ReadyResponse,
    VersionResponse,
)
from uranus_research_service.errors import ErrorResponse
from uranus_research_service.version import ENCODER_EXPECTED

ROOT = Path("contracts")


def read(path):
    return json.loads((ROOT / path).read_text())


@pytest.mark.parametrize("number", range(9, 14))
def test_planner_admin_response_parity(number):
    planner = read(f"planner/v{number}-response.json")
    admin = read(f"admin/planner-v{number}-response.json")
    assert planner == admin
    Draft202012Validator.check_schema(planner)
    digest = hashlib.sha256(
        json.dumps(canonical(planner), sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    assert digest == read("planner/pins.json")[f"v{number}"]["response_schema_sha256"]


@pytest.mark.parametrize(
    "model",
    [HealthResponse, QueryRequest, QueryResponse, ReadyResponse, VersionResponse, ErrorResponse],
)
def test_generated_service_schema_exact(model):
    assert canonical(model.model_json_schema()) == read(f"service/{model.__name__}.json")


async def test_generated_openapi_matches_and_structured_query(settings):
    from unittest.mock import AsyncMock

    app = create_app(settings, planner=AsyncMock(), database=AsyncMock(), areas=AsyncMock())
    spec = canonical(app.openapi())
    assert spec == read("service/openapi.json")
    assert set(spec["paths"]) == {"/health", "/ready", "/version", "/query"}
    assert "200" in spec["paths"]["/query"]["post"]["responses"]
    assert spec["paths"]["/query"]["post"]["security"]
    assert not spec["paths"]["/health"]["get"].get("security")


def test_upstream_snapshot_hashes_and_encoder_identity():
    manifest = read("sources.json")
    for file, digest in manifest["snapshots"].items():
        assert hashlib.sha256((ROOT / file).read_bytes()).hexdigest() == digest
    expected = read("encoder/expected-version.json")
    assert all(expected[k] == v for k, v in ENCODER_EXPECTED.items())
    assert read("encoder/EmbedRequest.json")["properties"]["model"]["const"] == "jina-v5"
    assert read("encoder/EmbedRequest.json")["properties"]["kind"]["enum"] == ["passage", "query"]


def test_admin_request_mapping_is_explicit():
    admin = read("admin/query-request.json")
    service = canonical(QueryRequest.model_json_schema())
    assert service["properties"]["query"] == admin["properties"]["query"]
    assert service["properties"]["conversation_id"] == admin["properties"]["conversation_id"]
    assert (
        service["$defs"]["LocationContext"]["properties"]
        == admin["$defs"]["LocationContext"]["properties"]
    )
    assert set(service["properties"]) - set(admin["properties"]) == {"timezone", "language"}
    assert set(admin["properties"]) - set(service["properties"]) == {"conversation_context"}


def test_ported_runtime_contracts_match_admin():
    from uranus_research_service.research.wire.research_v13_schema import PlanResponseV13
    from uranus_research_service.schemas.research_response import (
        ConversationResponse,
        ResearchExecutionResponse,
    )

    assert canonical(PlanResponseV13.model_json_schema()) == read("planner/v13-response.json")
    assert canonical(ResearchExecutionResponse.model_json_schema()) == read(
        "admin/execution-response.json"
    )
    assert canonical(ConversationResponse.model_json_schema()) == read(
        "admin/conversation-response.json"
    )
