"""Test-only bridge, executed with pinned Admin's Python. No service runtime imports.

Input arrives on stdin from the guarded integration harness, including disposable
reader DSNs. Only the metadata connection boundary is adapted: Admin's write-oriented
role preflight cannot be applied to the intentionally restricted area-only reader.
"""

import asyncio
import json
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace


async def main():
    data = json.load(sys.stdin)
    backend = Path(data["admin"]) / "backend"
    sys.path.insert(0, str(backend))
    import httpx
    from app.clients.research_geocoder import ResearchGeocoderClient
    from app.config import Settings
    from app.database import create_engine
    from app.repositories import research_resolution
    from app.research.conversation_state import ConversationStore
    from app.schemas.research_location import ResearchQueryRequest
    from app.services.research_conversational import execute_conversation
    from app.services.research_planner import ResearchPlannerClient
    from fastapi import Request
    from pydantic import SecretStr
    from sqlalchemy.engine import make_url

    for name in ("source", "area"):
        url = make_url(data[name])
        if not url.database.endswith("_test") or url.host not in {"127.0.0.1", "localhost", "::1"}:
            raise SystemExit("Disposable loopback _test reader required")
    key = "parity-only-synthetic-credential-0123456789"
    settings = Settings(
        _env_file=None,
        app_env="test",
        dev_auth_enabled=True,
        dev_admin_token=SecretStr(key),
        database_url=SecretStr(data["source"]),
        uranus_timestamp_timezone="UTC",
        uranus_api_url="https://api.kulturbytes.de",
        research_planner_url="http://127.0.0.1:6334",
        research_planner_api_key=SecretStr(key),
        research_planner_contract="v13",
        research_geocoder_api_key=SecretStr(key),
        research_administrative_catalog_path=Path(data["catalog"]),
    )
    source = create_engine(settings)
    area = create_engine(settings.model_copy(update={"database_url": SecretStr(data["area"])}))

    @asynccontextmanager
    async def connect_area(request):
        async with area.connect() as connection:
            yield connection

    research_resolution.connect_admin = connect_area
    current = [None]

    def plan_reply(request):
        assert request.url.path == "/v13/plan"
        return httpx.Response(200, json=current[0])

    def geo_reply(request):
        payload = json.loads(request.content)
        if request.url.path == "/lookup":
            return httpx.Response(
                200, json=next(p for p in data["places"] if p["osm_id"] == payload["osm_id"])
            )
        if request.url.path == "/search":
            return httpx.Response(
                200,
                json={
                    "query": payload["query"],
                    "items": [p for p in data["places"] if p["name"] == payload["query"]],
                },
            )
        raise AssertionError("Unexpected geocoder path")

    planner = ResearchPlannerClient(settings, transport=httpx.MockTransport(plan_reply))
    geocoder = ResearchGeocoderClient(settings, transport=httpx.MockTransport(geo_reply))
    store = ConversationStore()
    state = SimpleNamespace(engine=source, research_conversations=store, research_geocoder=geocoder)
    request = Request(
        {
            "type": "http",
            "headers": [(b"authorization", ("Bearer " + key).encode())],
            "app": SimpleNamespace(state=state),
        }
    )
    results = []
    token = None
    try:
        for case in data["cases"]:
            current[0] = case["envelope"]
            body = {"query": case["query"]}
            if case["plan"]["interaction"]["research_mode"] != "new":
                body["conversation_id"] = token
            response = await execute_conversation(
                request, settings, ResearchQueryRequest(**body), planner
            )
            token = response.conversation_id
            memory = store.entries[token]
            results.append(
                {
                    "id": case["id"],
                    "response": response.model_dump(mode="json"),
                    "facts": memory.facts.model_dump(mode="json") if memory.facts else None,
                    "pending": memory.pending.model_dump(mode="json") if memory.pending else None,
                    "summaries": [s.model_dump(mode="json") for s in memory.summaries],
                }
            )
    finally:
        await planner.close()
        await geocoder.close()
        await source.dispose()
        await area.dispose()
    print(json.dumps(results))


if __name__ == "__main__":
    asyncio.run(main())
