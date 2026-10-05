"""Explicit environment/file configuration, following the Encoder convention."""

import os
from pathlib import Path
from typing import Literal, Self
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator

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
    encoder_url: str = "http://127.0.0.1:6335"
    encoder_api_key: SecretStr | None = None
    dependency_timeout_seconds: float = Field(default=5, gt=0, le=30)
    max_response_bytes: int = Field(default=65536, ge=1024, le=1048576)
    max_concurrent_requests: int = Field(default=4, ge=1, le=32)
    body_timeout_seconds: float = Field(default=5, gt=0, le=10)
    request_timeout_seconds: float = Field(default=25, gt=0, le=120)

    @field_validator("api_key", "planner_api_key", "encoder_api_key")
    @classmethod
    def valid_key(cls, value: SecretStr | None) -> SecretStr | None:
        if value is not None:
            key = value.get_secret_value()
            if not 32 <= len(key) <= 4096 or any(not 33 <= ord(c) <= 126 for c in key):
                raise ValueError("invalid_service_key")
        return value

    @field_validator("planner_url", "encoder_url")
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

    @classmethod
    def from_env(cls) -> Self:
        return cls(
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
