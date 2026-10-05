"""Closed internal requests and versioned structured execution responses."""

from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from uranus_research_service.config import PlannerContract
from uranus_research_service.version import (
    CHUNK_VERSION,
    CONTRACT_VERSION,
    DIMENSIONS,
    EMBEDDING_VERSION,
    ENCODER_CONTRACT,
    MODEL,
    MODEL_REVISION,
    SERVICE_VERSION,
)


class Closed(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


class LocationContext(Closed):
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    display_name: str | None = Field(default=None, min_length=1, max_length=160)
    source: Literal["browser_geolocation", "nominatim_reverse", "manual"]

    @field_validator("display_name")
    @classmethod
    def valid_name(cls, value):
        if value is not None:
            if not value.strip():
                raise ValueError("blank_location")
            value.encode("utf-8")
        return value

    @model_validator(mode="after")
    def usable(self):
        if (self.latitude is None) != (self.longitude is None) or (
            self.latitude is None and self.display_name is None
        ):
            raise ValueError("incomplete_location")
        return self


class QueryRequest(Closed):
    query: str = Field(min_length=1, max_length=2000)
    timezone: str = Field(default="Europe/Berlin", min_length=1, max_length=64)
    language: Literal["de", "da", "en", "auto"] = "auto"
    conversation_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]{43}$")
    location_context: LocationContext | None = None

    @field_validator("query")
    @classmethod
    def valid_query(cls, value):
        if not value.strip():
            raise ValueError("blank_query")
        value.encode("utf-8")
        return value

    @field_validator("timezone")
    @classmethod
    def timezone_exists(cls, value):
        try:
            ZoneInfo(value)
        except (ValueError, ZoneInfoNotFoundError):
            raise ValueError("unknown_timezone") from None
        return value


class HealthResponse(Closed):
    status: Literal["ok"] = "ok"


class RuntimeCapabilities(Closed):
    structured_query: bool = False
    semantic_query: Literal[False] = False
    conversation: bool = False
    spatial: bool = False
    named_place_resolution: bool = False
    administrative_grouping: bool = False


class ReadyResponse(Closed):
    status: Literal["ready"] = "ready"
    query_enabled: bool = False
    capabilities: RuntimeCapabilities = Field(default_factory=lambda: RuntimeCapabilities())


class VersionResponse(Closed):
    service_version: str = SERVICE_VERSION
    contract_version: str = CONTRACT_VERSION
    planner_contract: PlannerContract
    encoder_contract: str = ENCODER_CONTRACT
    embedding_model: str = MODEL
    embedding_revision: str = MODEL_REVISION
    embedding_version: str = EMBEDDING_VERSION
    dimensions: int = DIMENSIONS
    chunk_version: str = CHUNK_VERSION
    query_enabled: bool = False
    capabilities: RuntimeCapabilities = Field(default_factory=lambda: RuntimeCapabilities())


from uranus_research_service.schemas.research_response import (  # noqa: E402
    ConversationResponse,
    ResearchExecutionResponse,
)


class QueryResponse(Closed):
    schema_version: Literal["uranus-research-service-v1"] = CONTRACT_VERSION
    response: ConversationResponse | ResearchExecutionResponse
