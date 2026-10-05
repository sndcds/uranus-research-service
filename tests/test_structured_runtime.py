"""Actual v13 HTTP transport -> closed validators -> routing; SQL is isolated here."""

import json
from copy import deepcopy
from datetime import date
from unittest.mock import AsyncMock

import httpx
import pytest

from tests.conftest import KEY
from tests.structured_fixtures import GOLDENS, SOCIAL, envelope
from uranus_research_service.app import create_app
from uranus_research_service.contracts import QueryRequest
from uranus_research_service.errors import APIError
from uranus_research_service.planner import PlannerClient
from uranus_research_service.research.capabilities import require_supported
from uranus_research_service.research.context import ResearchExecutionContext
from uranus_research_service.research.normalize_v12 import normalize_v12
from uranus_research_service.research.plan import (
    InternalResearchPlan,
    SemanticSelection,
    TemporalSelection,
)
from uranus_research_service.research.sql_provenance import (
    LOCATION_REDACTED,
    VALUE_REDACTED,
    safe_value,
)
from uranus_research_service.research.wire.research_v13_schema import PlanResponseV13
from uranus_research_service.runtime import ResearchRuntime
from uranus_research_service.services.research_plan_execution import (
    ResearchPlanExecutor,
    temporal_bounds,
)

HEADERS = {"Authorization": "Bearer " + KEY, "X-Research-Principal": "a" * 64}


@pytest.mark.parametrize("case", SOCIAL, ids=lambda c: c["request"]["query"])
async def test_conversation_returns_before_any_database_or_resolver(settings, case):
    calls = []

    def handler(request):
        calls.append(request)
        assert request.url.path == "/v13/plan" and request.method == "POST"
        assert request.headers["Authorization"] == "Bearer " + KEY
        return httpx.Response(200, json=envelope(case["plan"]))

    planner = PlannerClient(settings, transport=httpx.MockTransport(handler))
    database = AsyncMock()
    executor = AsyncMock()
    runtime = ResearchRuntime(
        settings, planner=planner, database=database, areas=database, executor=executor
    )
    app = create_app(settings, runtime=runtime)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        result = await client.post(
            "/query", headers=HEADERS, json={"query": case["request"]["query"]}
        )
    await runtime.close()
    assert result.status_code == 200, result.text
    assert result.json()["response"]["kind"] == "conversation"
    assert len(calls) == 1
    executor.execute.assert_not_awaited()
    database.ready.assert_not_awaited()
    database.connection.assert_not_called()


@pytest.mark.parametrize(
    "change",
    ["query", "nested_query", "timezone", "prompt", "schema", "model", "extra", "coercion", "kind"],
)
async def test_invalid_planner_contract_never_executes(settings, change):
    value = deepcopy(envelope(GOLDENS[0]["plan"]))
    if change == "query":
        value["plan"]["original_query"] = "other"
    if change == "nested_query":
        value["plan"]["interaction"]["research_plan"]["original_query"] = "other"
    if change == "timezone":
        value["timezone"] = "UTC"
    if change == "prompt":
        value["prompt_version"] = "research-planner-v18"
    if change == "schema":
        value["schema_version"] = "research-query-plan-v12"
    if change == "model":
        value["diagnostics"]["planner_model"] = "different"
    if change == "extra":
        value["sql"] = "SELECT private"
    if change == "coercion":
        value["plan"]["interaction"]["research_plan"]["limit"] = "20"
    if change == "kind":
        value["diagnostics"]["interaction_kind"] = "help"
    planner = PlannerClient(
        settings, transport=httpx.MockTransport(lambda r: httpx.Response(200, json=value))
    )
    executor = AsyncMock()
    db = AsyncMock()
    runtime = ResearchRuntime(settings, planner=planner, database=db, areas=db, executor=executor)
    try:
        with pytest.raises(APIError) as error:
            await runtime.query(QueryRequest(query=GOLDENS[0]["query"]), "a" * 64)
        assert error.value.status == 502
        executor.execute.assert_not_awaited()
        db.connection.assert_not_called()
    finally:
        await runtime.close()


async def test_semantic_rejected_even_with_clarification_before_sql(settings):
    case = deepcopy(GOLDENS[0])
    wire = case["plan"]["interaction"]["research_plan"]
    wire.update(intent="search", semantic={"query": "ruhige Kultur", "focus": None})
    planner = PlannerClient(
        settings,
        transport=httpx.MockTransport(lambda r: httpx.Response(200, json=envelope(case["plan"]))),
    )
    executor = AsyncMock()
    db = AsyncMock()
    runtime = ResearchRuntime(settings, planner=planner, database=db, areas=db, executor=executor)
    try:
        result = await runtime.query(QueryRequest(query=case["query"]), "a" * 64)
        assert result.response.interaction.conversation.reason == "unsupported_constraint"
        executor.execute.assert_not_awaited()
        db.connection.assert_not_called()
        state = next(iter(runtime.conversations.entries.values()))
        assert not state.summaries and state.pending is None and state.facts is None
    finally:
        await runtime.close()
    internal = InternalResearchPlan(
        intent="search", entity_type="event", semantic=SemanticSelection("ruhig", None)
    )
    with pytest.raises(APIError):
        require_supported(internal)
    resolver = AsyncMock()
    with pytest.raises(APIError):
        await ResearchPlanExecutor(db, resolver, settings).execute(
            internal,
            ResearchExecutionContext(
                reference_date=date(2026, 10, 4), timezone="Europe/Berlin", original_query="x"
            ),
            planner_ms=0,
        )
    resolver.resolve.assert_not_awaited()


@pytest.mark.parametrize(
    "period,start,end",
    [
        ("today", date(2026, 10, 4), date(2026, 10, 4)),
        ("tomorrow", date(2026, 10, 5), date(2026, 10, 5)),
        ("this_weekend", date(2026, 10, 3), date(2026, 10, 4)),
        ("this_month", date(2026, 10, 1), date(2026, 10, 31)),
        ("next_week", date(2026, 10, 5), date(2026, 10, 11)),
    ],
)
def test_temporal_bounds_unchanged(period, start, end):
    context = ResearchExecutionContext(
        reference_date=date(2026, 10, 4), timezone="Europe/Berlin", original_query="x"
    )
    plan = InternalResearchPlan(
        intent="list", entity_type="event", temporal=TemporalSelection(period=period)
    )
    assert temporal_bounds(plan, context) == (start, end)


@pytest.mark.parametrize("case", GOLDENS, ids=lambda c: c["id"])
def test_all_structured_goldens_validate_and_normalize(case):
    e = PlanResponseV13.model_validate_json(json.dumps(envelope(case["plan"])))
    if case["expected"]["kind"] == "conversation":
        assert e.plan.interaction.research_plan.clarification != "none"
        return
    plan = normalize_v12(e.plan.interaction.research_plan)
    assert plan.semantic is None
    require_supported(plan)


def test_sql_provenance_allowlist_preserved():
    assert safe_value("place_latitude", 54.8) == LOCATION_REDACTED
    assert safe_value("constraints", [{"coordinates": [9.4, 54.8]}]) == LOCATION_REDACTED
    assert safe_value("credential", "private") == VALUE_REDACTED
    assert safe_value("event_type_ids", [1, 2]) == [1, 2]


@pytest.mark.parametrize(
    "principal", [None, "", "x" * 64, "a" * 63, "a" * 65, "admin:123", "Bearer " + KEY]
)
async def test_principal_required_before_planner(settings, principal):
    planner = AsyncMock()
    app = create_app(settings, planner=planner, database=AsyncMock(), areas=AsyncMock())
    headers = {"Authorization": "Bearer " + KEY}
    if principal is not None:
        headers["X-Research-Principal"] = principal
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post("/query", headers=headers, json={"query": "x"})
    assert response.status_code == 422
    planner.plan_natural.assert_not_awaited()


@pytest.mark.parametrize(
    "reference,period,start,end",
    [
        (date(2024, 2, 20), "this_month", date(2024, 2, 1), date(2024, 2, 29)),
        (date(2026, 3, 29), "this_weekend", date(2026, 3, 28), date(2026, 3, 29)),
        (date(2026, 10, 25), "this_weekend", date(2026, 10, 24), date(2026, 10, 25)),
    ],
)
def test_leap_year_and_dst_calendar_semantics(reference, period, start, end):
    context = ResearchExecutionContext(
        reference_date=reference, timezone="Europe/Berlin", original_query="x"
    )
    plan = InternalResearchPlan(
        intent="list", entity_type="event", temporal=TemporalSelection(period=period)
    )
    assert temporal_bounds(plan, context) == (start, end)
