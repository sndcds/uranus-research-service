"""Phase-1 service: dependency compatibility and a disabled query contract."""

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.security import HTTPBearer
from starlette.exceptions import HTTPException

from uranus_research_service.auth import RequestBoundary
from uranus_research_service.config import Settings
from uranus_research_service.contracts import (
    HealthResponse,
    QueryRequest,
    ReadyResponse,
    VersionResponse,
)
from uranus_research_service.encoder import EncoderClient
from uranus_research_service.errors import DependencyError, ErrorResponse, error_response
from uranus_research_service.logging import configure_logging, logger
from uranus_research_service.planner import PlannerClient
from uranus_research_service.version import SERVICE_VERSION


def create_app(settings: Settings | None = None, *, planner=None, encoder=None):
    settings = settings or Settings.from_env()
    planner_client = planner or PlannerClient(settings)
    encoder_client = encoder or EncoderClient(settings)

    @asynccontextmanager
    async def lifespan(app):
        configure_logging()
        try:
            yield
        finally:
            await planner_client.close()
            await encoder_client.close()

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
        return VersionResponse(planner_contract=settings.planner_contract)

    @app.get(
        "/ready",
        dependencies=authenticated,
        response_model=ReadyResponse,
        responses={401: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
    )
    async def ready():
        try:
            await planner_client.ready()
            await encoder_client.ready()
        except DependencyError as exc:
            logger.warning(
                "dependency_failed",
                extra={"dependency": exc.dependency, "error_type": exc.category},
            )
            return error_response("not_ready", 503)
        return ReadyResponse()

    @app.post(
        "/query",
        dependencies=authenticated,
        status_code=501,
        response_model=ErrorResponse,
        responses={
            401: {"model": ErrorResponse},
            413: {"model": ErrorResponse},
            422: {"model": ErrorResponse},
        },
    )
    async def query(body: QueryRequest):
        return error_response("query_not_enabled", 501)

    return app
