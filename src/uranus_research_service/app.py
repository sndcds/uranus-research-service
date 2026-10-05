"""Authenticated structured Research API; no Admin identity or semantic runtime."""

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header
from fastapi.exceptions import RequestValidationError
from fastapi.security import HTTPBearer
from starlette.exceptions import HTTPException

from uranus_research_service.auth import RequestBoundary
from uranus_research_service.config import Settings
from uranus_research_service.contracts import (
    HealthResponse,
    QueryRequest,
    QueryResponse,
    ReadyResponse,
    VersionResponse,
)
from uranus_research_service.errors import (
    MESSAGES,
    APIError,
    DependencyError,
    ErrorResponse,
    error_response,
)
from uranus_research_service.logging import configure_logging, logger
from uranus_research_service.runtime import ResearchRuntime
from uranus_research_service.semantic_manifest import collection_name
from uranus_research_service.version import SERVICE_VERSION


def create_app(
    settings: Settings | None = None,
    *,
    runtime=None,
    planner=None,
    database=None,
    areas=None,
    geocoder=None,
):
    settings = settings or Settings.from_env()
    runtime = (
        runtime
        if runtime is not None
        else ResearchRuntime(
            settings, planner=planner, database=database, areas=areas, geocoder=geocoder
        )
    )

    @asynccontextmanager
    async def lifespan(app):
        configure_logging()
        try:
            yield
        finally:
            await runtime.close()

    app = FastAPI(
        title="Uranus Research Service",
        version=SERVICE_VERSION,
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        redirect_slashes=False,
    )
    app.add_middleware(RequestBoundary, settings=settings)
    authenticated = [Depends(HTTPBearer(auto_error=False))]

    @app.exception_handler(APIError)
    async def domain_error(request, exc):
        code = (
            exc.code
            if exc.code in MESSAGES
            else ("research_execution_unsupported" if exc.status == 422 else "internal_error")
        )
        logger.warning("dependency_failed", extra={"error_type": code})
        return error_response(code, exc.status)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        return error_response("invalid_request", 422)

    @app.exception_handler(HTTPException)
    async def http_error(request, exc):
        return error_response("not_found", exc.status_code)

    @app.get("/health", response_model=HealthResponse)
    async def health():
        return HealthResponse()

    @app.get("/version", response_model=VersionResponse, dependencies=authenticated)
    async def version():
        return VersionResponse(
            planner_contract=settings.planner_contract,
            semantic_collection_names=[collection_name("event", settings.semantic_build_id)]
            if settings.semantic_build_id
            else [],
            query_enabled=runtime.verified,
            capabilities=runtime.capabilities(),
        )

    @app.get(
        "/ready",
        dependencies=authenticated,
        response_model=ReadyResponse,
        responses={401: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
    )
    async def ready():
        try:
            await runtime.ready()
        except (DependencyError, APIError) as exc:
            logger.warning(
                "dependency_failed",
                extra={
                    "dependency": getattr(exc, "dependency", "database"),
                    "error_type": getattr(exc, "category", "unavailable"),
                },
            )
            return error_response("not_ready", 503)
        return ReadyResponse(query_enabled=runtime.verified, capabilities=runtime.capabilities())

    @app.post(
        "/query",
        dependencies=authenticated,
        response_model=QueryResponse,
        responses={
            401: {"model": ErrorResponse},
            413: {"model": ErrorResponse},
            422: {"model": ErrorResponse},
            502: {"model": ErrorResponse},
            503: {"model": ErrorResponse},
        },
    )
    async def query(body: QueryRequest, principal: str = Header(alias="X-Research-Principal")):
        return await runtime.query(body, principal)

    return app
