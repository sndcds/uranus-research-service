"""Explicit environment/file configuration, following the Encoder convention."""

import os
from pathlib import Path
from typing import Literal, Self
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator
from sqlalchemy.engine import make_url

PlannerContract = Literal["v9", "v10", "v11", "v12", "v13"]


def read_secret(name: str, *, required: bool = False) -> SecretStr | None:
    """A configured file takes precedence; never fall back after a file error."""
    file = os.environ.get(name + "_FILE")
    try:
        if file:
            path = Path(file)
            if not path.is_absolute():
                raise ValueError
            with path.open("rb") as stream:
                raw = stream.read(4098)
            value = raw.removesuffix(b"\n").removesuffix(b"\r").decode("ascii")
        else:
            value = os.environ.get(name)
        if required and value is None:
            raise ValueError
        return SecretStr(value) if value is not None else None
    except (OSError, UnicodeError, ValueError):
        raise ValueError("invalid_secret_configuration") from None


class Settings(BaseModel):
    model_config = ConfigDict(
        extra="forbid", frozen=True, allow_inf_nan=False, hide_input_in_errors=True
    )
    api_key: SecretStr
    planner_url: str = "http://127.0.0.1:6334"
    planner_api_key: SecretStr | None = None
    planner_contract: PlannerContract = "v13"
    database_url: SecretStr | None = None
    area_database_url: SecretStr | None = None
    event_timezone: str = "Europe/Berlin"
    uranus_timestamp_timezone: str = "UTC"
    uranus_api_url: str = "https://api.kulturbytes.de"
    db_timeout_seconds: int = Field(default=10, ge=1, le=120)
    db_pool_size: int = Field(default=4, ge=1, le=16)
    research_geocoder_url: str = "http://127.0.0.1:6337"
    research_geocoder_api_key: SecretStr | None = None
    research_geocoder_timeout_seconds: float = Field(default=5, gt=0, le=10)
    research_administrative_catalog_path: Path | None = None
    encoder_url: str = "http://127.0.0.1:6335"
    encoder_api_key: SecretStr | None = None
    dependency_timeout_seconds: float = Field(default=5, gt=0, le=30)
    max_response_bytes: int = Field(default=65536, ge=1024, le=1048576)
    max_concurrent_requests: int = Field(default=4, ge=1, le=32)
    body_timeout_seconds: float = Field(default=5, gt=0, le=10)
    request_timeout_seconds: float = Field(default=25, gt=0, le=120)

    @field_validator("api_key", "planner_api_key", "encoder_api_key", "research_geocoder_api_key")
    @classmethod
    def valid_key(cls, value: SecretStr | None) -> SecretStr | None:
        if value is not None:
            key = value.get_secret_value()
            if not 32 <= len(key) <= 4096 or any(not 33 <= ord(c) <= 126 for c in key):
                raise ValueError("invalid_service_key")
        return value

    @field_validator("planner_url", "encoder_url", "research_geocoder_url")
    @classmethod
    def fixed_origin(cls, value: str) -> str:
        try:
            parts = urlsplit(value)
            if (
                not parts.hostname
                or parts.username is not None
                or parts.password is not None
                or parts.path
                or parts.query
                or parts.fragment
                or any(ord(c) < 33 or ord(c) == 127 or c in "*\\%?#" for c in value)
                or (
                    parts.scheme != "https"
                    and not (
                        parts.scheme == "http"
                        and parts.hostname in {"127.0.0.1", "::1", "localhost"}
                    )
                )
            ):
                raise ValueError
            if parts.netloc.startswith("["):
                suffix = parts.netloc.partition("]")[2]
                if suffix and not suffix.startswith(":"):
                    raise ValueError
            if parts.netloc.endswith(":"):
                raise ValueError
            _ = parts.port
        except ValueError:
            raise ValueError("fixed_internal_origin_required") from None
        return value

    @field_validator("database_url", "area_database_url")
    @classmethod
    def database_origin(cls, value):
        if value is not None:
            try:
                url = make_url(value.get_secret_value())
                if url.drivername != "postgresql+asyncpg" or not url.host or not url.database:
                    raise ValueError
                if any(k not in {"ssl"} for k in url.query):
                    raise ValueError
            except Exception:
                raise ValueError("invalid_database_configuration") from None
        return value

    @field_validator("event_timezone", "uranus_timestamp_timezone")
    @classmethod
    def timezone_exists(cls, value):
        try:
            ZoneInfo(value)
        except (ValueError, KeyError):
            raise ValueError("invalid_timezone") from None
        return value

    @classmethod
    def from_env(cls) -> Self:
        return cls(
            database_url=read_secret("RESEARCH_DATABASE_URL"),
            area_database_url=read_secret("RESEARCH_AREA_DATABASE_URL"),
            event_timezone=os.environ.get("EVENT_TIMEZONE", "Europe/Berlin"),
            uranus_timestamp_timezone=os.environ.get("URANUS_TIMESTAMP_TIMEZONE", "UTC"),
            db_timeout_seconds=os.environ.get("DB_TIMEOUT_SECONDS", "10"),
            db_pool_size=os.environ.get("DB_POOL_SIZE", "4"),
            research_geocoder_url=os.environ.get("RESEARCH_GEOCODER_URL", "http://127.0.0.1:6337"),
            research_geocoder_api_key=read_secret("RESEARCH_GEOCODER_API_KEY"),
            research_geocoder_timeout_seconds=os.environ.get(
                "RESEARCH_GEOCODER_TIMEOUT_SECONDS", "5"
            ),
            research_administrative_catalog_path=os.environ.get(
                "RESEARCH_ADMINISTRATIVE_CATALOG_PATH"
            ),
            api_key=read_secret("RESEARCH_API_KEY", required=True),
            planner_api_key=read_secret("PLANNER_API_KEY"),
            encoder_api_key=read_secret("ENCODER_API_KEY"),
            planner_url=os.environ.get("PLANNER_URL", "http://127.0.0.1:6334"),
            encoder_url=os.environ.get("ENCODER_URL", "http://127.0.0.1:6335"),
            planner_contract=os.environ.get("PLANNER_CONTRACT", "v13"),
            dependency_timeout_seconds=os.environ.get("DEPENDENCY_TIMEOUT_SECONDS", "5"),
            max_response_bytes=os.environ.get("MAX_RESPONSE_BYTES", "65536"),
            max_concurrent_requests=os.environ.get("MAX_CONCURRENT_REQUESTS", "4"),
            body_timeout_seconds=os.environ.get("BODY_TIMEOUT_SECONDS", "5"),
            request_timeout_seconds=os.environ.get("REQUEST_TIMEOUT_SECONDS", "25"),
        )
