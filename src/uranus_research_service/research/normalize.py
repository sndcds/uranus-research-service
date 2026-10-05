"""Shared unsupported guard extracted from Admin; no legacy planner dispatch."""

from uranus_research_service.errors import APIError


def unsupported() -> APIError:
    return APIError(422, "research_execution_unsupported", "This combination is not supported.")
