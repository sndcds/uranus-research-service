"""Transient request/runtime inputs; never persisted or sent to the Planner."""

from dataclasses import dataclass
from datetime import date

from uranus_research_service.schemas.research_location import LocationContext


@dataclass(frozen=True, slots=True)
class ResearchExecutionContext:
    reference_date: date
    timezone: str
    original_query: str
    location_context: LocationContext | None = None
