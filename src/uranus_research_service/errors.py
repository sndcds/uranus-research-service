"""Fixed safe errors; never contain provider bodies, credentials or input values."""

from typing import Literal

from pydantic import BaseModel, ConfigDict
from starlette.responses import JSONResponse

ErrorCode = Literal[
    "research_inventory_invalid",
    "research_area_unavailable",
    "research_area_invalid_boundary",
    "research_execution_too_broad",
    "research_area_level_mismatch",
    "research_area_no_match",
    "research_area_ambiguous",
    "research_area_boundary_unavailable",
    "research_planner_unavailable",
    "research_planner_invalid_response",
    "research_execution_unavailable",
    "research_execution_invalid_plan",
    "research_execution_unsupported",
    "research_plan_unsupported",
    "invalid_principal",
    "invalid_input",
    "geocoder_unavailable",
    "research_inventory_unavailable",
    "research_area_not_found",
    "source_timezone_unconfigured",
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
    "research_inventory_invalid": "Research constraint could not be resolved.",
    "research_area_unavailable": "Research constraint could not be resolved.",
    "research_area_invalid_boundary": "Research constraint could not be resolved.",
    "research_execution_too_broad": "Research constraint could not be resolved.",
    "research_area_level_mismatch": "Research constraint could not be resolved.",
    "research_area_no_match": "Research constraint could not be resolved.",
    "research_area_ambiguous": "Research constraint could not be resolved.",
    "research_area_boundary_unavailable": "Research constraint could not be resolved.",
    "research_planner_unavailable": "Research planner unavailable.",
    "research_planner_invalid_response": "Research planner response invalid.",
    "research_execution_unavailable": "Research execution temporarily unavailable.",
    "research_execution_invalid_plan": "Research execution plan invalid.",
    "research_execution_unsupported": "Research operation unsupported.",
    "research_plan_unsupported": "Research plan unsupported.",
    "invalid_principal": "Internal principal required.",
    "invalid_input": "Invalid input.",
    "geocoder_unavailable": "Location resolution unavailable.",
    "research_inventory_unavailable": "Complete geographic inventory required.",
    "research_area_not_found": "Research area not found.",
    "source_timezone_unconfigured": "Source timezone unavailable.",
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


class APIError(Exception):
    """Ported domain error; HTTP boundary emits only centrally allowlisted messages."""

    def __init__(self, status: int, code: str, message: str):
        self.status, self.code, self.message = status, code, message
        super().__init__(code)
