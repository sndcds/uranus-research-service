"""Explicit per-app dependencies; no FastAPI Request, Admin state or model runtime."""

import asyncio

from uranus_research_service.contracts import QueryResponse, RuntimeCapabilities
from uranus_research_service.database import ResearchDatabase
from uranus_research_service.encoder import EncoderClient
from uranus_research_service.errors import APIError, DependencyError
from uranus_research_service.geocoder import ResearchGeocoderClient
from uranus_research_service.logging import logger
from uranus_research_service.planner import PlannerClient
from uranus_research_service.qdrant import QdrantClient
from uranus_research_service.repositories.research_resolution import ResearchResolver
from uranus_research_service.research.administrative_catalog import read_catalogs
from uranus_research_service.research.conversation_state import ConversationStore
from uranus_research_service.schemas.research_location import ResearchQueryRequest
from uranus_research_service.services.research_conversational import execute_conversation
from uranus_research_service.services.research_plan_execution import ResearchPlanExecutor


class ResearchRuntime:
    def __init__(
        self,
        settings,
        *,
        planner=None,
        database=None,
        areas=None,
        geocoder=None,
        conversations=None,
        executor=None,
    ):
        self.settings = settings
        self.planner = planner if planner is not None else PlannerClient(settings)
        self.database = database if database is not None else ResearchDatabase(settings)
        self.areas = areas if areas is not None else ResearchDatabase(settings, "area")
        self.geocoder = (
            geocoder
            if geocoder is not None
            else (ResearchGeocoderClient(settings) if settings.research_geocoder_api_key else None)
        )
        self.conversations = conversations if conversations is not None else ConversationStore()
        self.resolver = ResearchResolver(self.database, self.areas, settings, self.geocoder)
        self.executor = (
            executor
            if executor is not None
            else ResearchPlanExecutor(self.database, self.resolver, settings)
        )
        self.semantic_encoder = EncoderClient(settings) if settings.semantic_build_id else None
        self.semantic_qdrant = (
            QdrantClient(settings, build_id=settings.semantic_build_id)
            if settings.semantic_build_id
            else None
        )
        self.semantic_verified = False
        self.verified = False
        self.geocoder_verified = False
        self.inventory_verified = False

    @property
    def semantic_generation(self):
        return (
            self.semantic_qdrant.generation_verifier.generation
            if self.semantic_qdrant is not None
            else None
        )

    def capabilities(self):
        return RuntimeCapabilities(
            structured_query=self.verified,
            semantic_index_ready=bool(
                self.semantic_verified
                and self.semantic_qdrant is not None
                and self.semantic_qdrant.generation_verifier.is_verified
            ),
            conversation=self.verified,
            spatial=self.verified,
            named_place_resolution=self.verified and self.geocoder_verified,
            administrative_grouping=self.verified
            and self.geocoder_verified
            and self.inventory_verified,
        )

    async def ready(self):
        self.verified = False
        if self.settings.planner_contract != "v13":
            raise APIError(503, "not_ready", "Only v13 execution supported.")
        await self.planner.ready()
        await self.database.ready()
        await self.areas.ready()
        self.geocoder_verified = self.geocoder is not None and await self.geocoder.ready()
        self.inventory_verified = False
        if self.settings.research_administrative_catalog_path is not None:
            try:
                await asyncio.to_thread(
                    read_catalogs, self.settings.research_administrative_catalog_path
                )
                self.inventory_verified = True
            except (OSError, ValueError):
                pass  # optional capability stays disabled; query still fails closed
        self.verified = True
        self.semantic_verified = False
        if self.semantic_encoder is not None:
            try:
                async with asyncio.timeout(self.settings.dependency_timeout_seconds):
                    await self.semantic_encoder.ready()
                    await self.semantic_qdrant.generation_verifier.ready()
                self.semantic_verified = True
            except (DependencyError, ValueError, KeyError, TypeError, TimeoutError):
                self.semantic_qdrant.generation_verifier.invalidate()
                # Separate semantic capability cannot block structured readiness.

    async def close(self):
        if self.semantic_encoder is not None:
            await self.semantic_encoder.close()
            await self.semantic_qdrant.close()
        # All dependencies are app-owned, including injected transports.
        try:
            await self.planner.close()
        finally:
            try:
                await self.database.close()
            finally:
                await self.areas.close()
                if self.geocoder is not None:
                    await self.geocoder.close()

    async def query(self, body, principal):
        if body.timezone != self.settings.event_timezone:
            raise APIError(422, "invalid_input", "Event timezone mismatch.")
        if self.settings.planner_contract != "v13":
            raise APIError(503, "not_ready", "Only v13 execution supported.")
        request = ResearchQueryRequest.model_validate_json(
            body.model_dump_json(exclude={"timezone", "language"})
        )
        try:
            response = await execute_conversation(
                principal,
                self.conversations,
                self.executor,
                self.settings,
                request,
                self.planner,
                initial_language=body.language,
            )
        except APIError as exc:
            if exc.status >= 500:
                self.verified = False
            raise
        if hasattr(response, "diagnostics"):
            logger.info("research_execution", extra=response.diagnostics.model_dump())
        return QueryResponse(response=response)
