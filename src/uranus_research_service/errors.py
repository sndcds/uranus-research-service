"""Fixed safe errors; never contain provider bodies, credentials or input values."""

from typing import Literal

from pydantic import BaseModel, ConfigDict
from starlette.responses import JSONResponse

ErrorCode = Literal[
    "unauthorized",
    "invalid_request",
    "request_too_large",
    "not_ready",
    "query_not_enabled",
    "capacity_exceeded",
    "request_timeout",
    "internal_error",
    "not_found",
]
MESSAGES = {
    "unauthorized": "Internal authentication required.",
    "invalid_request": "Invalid internal request.",
    "request_too_large": "Request body exceeds the limit.",
    "not_ready": "Research dependencies are not ready.",
    "query_not_enabled": "Research execution is not enabled in phase 1.",
    "capacity_exceeded": "Request capacity is exhausted.",
    "request_timeout": "Request deadline exceeded.",
    "internal_error": "Research service unavailable.",
    "not_found": "Endpoint unavailable.",
}


class ErrorDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: ErrorCode
    message: str


class ErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    error: ErrorDetail


class DependencyError(Exception):
    def __init__(
        self,
        dependency: Literal["planner", "encoder"],
        category: Literal[
            "unconfigured",
            "unavailable",
            "invalid_response",
            "incompatible",
            "contract_unverifiable",
        ],
    ):
        self.dependency = dependency
        self.category = category
        super().__init__(category)


def error_response(code: ErrorCode, status: int) -> JSONResponse:
    return JSONResponse(
        {"error": {"code": code, "message": MESSAGES[code]}},
        status_code=status,
        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
    )
