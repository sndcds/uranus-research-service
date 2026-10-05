"""HTTP query pipeline against real disposable PostGIS and controlled v13 responses."""

import json
from uuid import UUID

import httpx
import pytest

from tests.geography_fixtures import CATALOG, geocoder_reply
from tests.structured_fixtures import GOLDENS, envelope
from tests.test_structured_runtime import HEADERS
from uranus_research_service.app import create_app
from uranus_research_service.geocoder import ResearchGeocoderClient
from uranus_research_service.planner import PlannerClient
from uranus_research_service.runtime import ResearchRuntime

pytestmark = pytest.mark.integration


def check_expected(case, response):
    expected = case["expected"]
    result = response if expected["kind"] == "conversation" else response["result"]
    assert result["kind"] == expected["kind"], case["id"]
    if "value" in expected:
        assert result["value"] == expected["value"], case["id"]
    if "values" in expected:
        assert [i["value"] for i in result["items"]] == expected["values"], case["id"]
    if "ids" in expected:
        assert [UUID(i["entity_key"]).int for i in result["items"]] == expected["ids"], case["id"]
    if "names" in expected:
        assert [i["name"] for i in result["items"]] == expected["names"], case["id"]
    assert response["answer_text"]


async def run_cases(settings, catalog):
    configured = settings.model_copy(update={"research_administrative_catalog_path": catalog})
    current = [None]
    requests = []

    def planner_reply(request):
        if request.url.path == "/ready":
            return httpx.Response(200, json={"status": "ready"})
        if request.method == "OPTIONS":
            return httpx.Response(
                405, json={"detail": "Method Not Allowed"}, headers={"Allow": "POST"}
            )
        assert request.url.path == "/v13/plan"
        requests.append(json.loads(request.content))
        return httpx.Response(200, json=envelope(current[0]["plan"]))

    planner = PlannerClient(configured, transport=httpx.MockTransport(planner_reply))
    geocoder_settings = configured.model_copy(
        update={"research_geocoder_api_key": configured.api_key}
    )
    geocoder = ResearchGeocoderClient(
        geocoder_settings, transport=httpx.MockTransport(geocoder_reply)
    )
    runtime = ResearchRuntime(configured, planner=planner, geocoder=geocoder)
    app = create_app(configured, runtime=runtime)
    results = []
    token = None
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test", headers=HEADERS
        ) as client,
    ):
        ready = await client.get("/ready")
        assert ready.status_code == 200, ready.text
        assert ready.json()["capabilities"]["semantic_query"] is False
        for case in GOLDENS:
            current[0] = case
            mode = case["plan"]["interaction"]["research_mode"]
            body = {"query": case["query"]}
            if mode != "new":
                body["conversation_id"] = token
            response = await client.post("/query", json=body)
            assert response.status_code == 200, (case["id"], response.text)
            data = response.json()["response"]
            token = data["conversation_id"]
            check_expected(case, data)
            state = runtime.conversations.entries[token]
            results.append(
                {
                    "id": case["id"],
                    "response": data,
                    "facts": state.facts.model_dump(mode="json") if state.facts else None,
                    "pending": state.pending.model_dump(mode="json") if state.pending else None,
                    "summaries": [s.model_dump(mode="json") for s in state.summaries],
                }
            )
        assert len(requests) == len(GOLDENS)
        assert requests[-1]["conversation_context"] is not None
    return results


async def test_structured_http_goldens(db_settings, tmp_path):
    catalog = tmp_path / "catalog.json"
    catalog.write_text(json.dumps(CATALOG))
    results = await run_cases(db_settings, catalog)
    assert len(results) == len(GOLDENS)
