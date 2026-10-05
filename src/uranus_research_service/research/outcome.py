"""Execution output without the transport envelope; assembled into HTTP at the API edge."""

from dataclasses import dataclass, field
from datetime import datetime

from uranus_research_service.schemas.research_administrative_result import AdministrativeResult
from uranus_research_service.schemas.research_execution import (
    ExecutionDiagnostics,
    ExecutionProvenance,
    ExecutionResult,
    ResolvedField,
)
from uranus_research_service.schemas.research_sql import ResearchSqlStatement


@dataclass(frozen=True, slots=True)
class ResearchExecutionOutcome:
    resolution: list[ResolvedField]
    result: ExecutionResult
    execution: ExecutionProvenance
    observed_at: datetime
    diagnostics: ExecutionDiagnostics
    administrative: AdministrativeResult | None = None
    sql_provenance: list[ResearchSqlStatement] = field(default_factory=list)
