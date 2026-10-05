"""Non-inference route readiness; full plan validation belongs to phase 2."""

from uranus_research_service.clients import InternalClient
from uranus_research_service.errors import DependencyError


class PlannerClient(InternalClient):
    def __init__(self, settings, *, transport=None):
        super().__init__(settings, "planner", transport=transport)
        self.contract = settings.planner_contract

    async def ready(self):
        if await self.get("/ready") != {"status": "ready"}:
            raise DependencyError("planner", "unavailable")
        # FastAPI returns 405 / Allow: POST for OPTIONS on a known POST route.
        # This cannot invoke plan generation. Unknown routes/redirects fail closed.
        await self.route(self.contract)
