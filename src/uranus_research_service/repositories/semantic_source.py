"""Read-only public source snapshot; HTTP calls occur after these contexts close."""

from datetime import UTC, date, datetime, time

from uranus_research_service.repositories.research import rehydrate_semantic_events
from uranus_research_service.repositories.research_execution import eligible_event_ids


def is_upcoming_start(row: dict[str, object], local: "datetime") -> bool:
    """Activity/quality start semantics: untimed/all-day today remains upcoming all day."""
    start_date, start_time = row["start_date"], row["start_time"]
    return bool(
        isinstance(start_date, date)
        and (
            start_date > local.date()
            or (
                start_date == local.date()
                and (
                    row["all_day"]
                    or start_time is None
                    or isinstance(start_time, time)
                    and start_time >= local.time().replace(tzinfo=None)
                )
            )
        )
    )


class SemanticSource:
    def __init__(self, database, areas, settings):
        self.database, self.areas, self.settings = database, areas, settings

    async def snapshot(self, *, now=None, limit=None):
        from uranus_research_service.repositories.vector_events import extract_events

        async with self.database.connection() as source, self.areas.connection() as areas:
            return await extract_events(
                source, areas, self.settings, now or datetime.now(UTC), limit, semantic=True
            )

    async def eligible(self, filters, area=None):
        async with self.database.connection() as source:
            return await eligible_event_ids(source, self.settings, filters, area)

    async def rehydrate(self, filters, candidates, *, now=None, area=None):
        from uranus_research_service.repositories.vector_events import extract_events

        async with self.database.connection() as source, self.areas.connection() as areas:
            observed = now or datetime.now(UTC)
            page = await rehydrate_semantic_events(
                source, self.settings, filters, candidates, observed, area
            )
            documents, _ = await extract_events(
                source, areas, self.settings, observed, semantic=True
            )
            return page, {d.entity_id: d for d in documents if d.entity_id in candidates}
