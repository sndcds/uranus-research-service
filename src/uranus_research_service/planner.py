"""Fixed v13 planning with the original closed Admin validators; no repair or retries."""

import asyncio

import httpx

from uranus_research_service.clients import InternalClient
from uranus_research_service.errors import APIError, DependencyError
from uranus_research_service.json_codec import decode
from uranus_research_service.research.wire.research_v13_schema import PlanResponseV13


class PlannerClient(InternalClient):
    def __init__(self, settings, *, transport=None):
        super().__init__(settings, "planner", transport=transport)
        self.contract = settings.planner_contract
        self.timezone = settings.event_timezone

    async def ready(self):
        if await self.get("/ready") != {"status": "ready"}:
            raise DependencyError("planner", "unavailable")
        # FastAPI returns 405 / Allow: POST for OPTIONS on a known POST route.
        # This cannot invoke plan generation. Unknown routes/redirects fail closed.
        await self.route(self.contract)

    async def plan_natural(
        self, query, context=None, *, language=None, pending=None, previous_answer_available=False
    ):
        if self.contract != "v13" or self.key is None:
            raise APIError(503, "research_planner_unavailable", "Planner unavailable.")
        request = httpx.Request(
            "POST",
            self.origin + "/v13/plan",
            headers={
                "Authorization": "Bearer " + self.key.get_secret_value(),
                "Accept": "application/json",
                "Accept-Encoding": "identity",
            },
            json={
                "query": query,
                "timezone": self.timezone,
                "language": "auto",
                "conversation_language": language,
                "pending_clarification": pending.model_dump(mode="json") if pending else None,
                "previous_answer_available": previous_answer_available,
                **({"conversation_context": context.model_dump(mode="json")} if context else {}),
            },
        )
        try:
            async with asyncio.timeout(self.timeout):
                response = await self.http.send(request, stream=True)
                try:
                    if response.status_code in {401, 403, 503}:
                        raise APIError(503, "research_planner_unavailable", "Planner unavailable.")
                    if (
                        response.status_code != 200
                        or response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
                        != "application/json"
                        or response.headers.get("content-encoding", "identity") != "identity"
                    ):
                        raise invalid_response()
                    body = bytearray()
                    maximum = min(self.max_bytes, 32768)
                    async for part in response.aiter_bytes(chunk_size=maximum + 1):
                        if len(body) + len(part) > maximum:
                            raise invalid_response()
                        body.extend(part)
                    decode(bytes(body))  # reject duplicate keys and nonfinite JSON, without repair
                    envelope = PlanResponseV13.model_validate_json(
                        body, context={"original_query": query}
                    )
                    return validate_response(envelope, query, self.timezone)
                finally:
                    await response.aclose()
        except (httpx.HTTPError, TimeoutError, OSError):
            raise APIError(503, "research_planner_unavailable", "Planner unavailable.") from None
        except (ValueError, TypeError, RecursionError):
            raise invalid_response() from None


def invalid_response():
    return APIError(502, "research_planner_invalid_response", "Planner response invalid.")


def validate_response(response, query, timezone):
    """Also validate injected clients: model_construct/copy can bypass validators."""
    try:
        envelope = PlanResponseV13.model_validate_json(
            response.model_dump_json(), context={"original_query": query}
        )
        if envelope.timezone != timezone:
            raise ValueError
        return envelope
    except (ValueError, TypeError, AttributeError):
        raise invalid_response() from None
