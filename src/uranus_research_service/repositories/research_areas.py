"""Persisted areas are resolved once; no provider access in a Research request."""

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from uranus_research_service.errors import APIError
from uranus_research_service.research.area_selection import normalize_area_ids
from uranus_research_service.schemas.research_areas import (
    AreaGeometry,
    ResearchArea,
)

AREA_COLUMNS = """id,area_type,country_code,region_code,name,display_name,
    osm_type,osm_id::text,osm_admin_level,source,retrieved_at,updated_at,
    CASE WHEN population_count IS NULL THEN NULL ELSE jsonb_build_object(
        'value',population_count,'as_of',population_date,'source',population_source,
        'municipality_name',population_name,'file_sha256',population_file_sha256,
        'imported_at',population_imported_at) END population,
    jsonb_build_object('longitude',ST_X(centroid),'latitude',ST_Y(centroid)) centroid,
    ARRAY[ST_XMin(geometry),ST_YMin(geometry),ST_XMax(geometry),ST_YMax(geometry)] bbox"""


@dataclass(frozen=True)
class ResolvedResearchArea:
    area: ResearchArea
    ewkb: bytes
    geometry: AreaGeometry | None = None
    municipality_key: str | None = None


@dataclass(frozen=True)
class ResolvedResearchAreas:
    area_ids: tuple[UUID, ...]
    ewkb: bytes


async def resolve_areas(admin: AsyncConnection, identifiers: list[UUID]) -> ResolvedResearchAreas:
    """Resolve all selected boundaries in one snapshot; their union means OR."""
    selected = normalize_area_ids(area_ids=identifiers)
    assert selected is not None
    row = (
        (
            await admin.execute(
                text("""SELECT count(*) area_count, ST_AsEWKB(ST_Union(geometry)) ewkb
                FROM admin.research_area WHERE id=ANY(CAST(:ids AS uuid[]))"""),
                {"ids": selected},
            )
        )
        .mappings()
        .one()
    )
    if row["area_count"] != len(selected):
        raise APIError(404, "research_area_not_found", "Research area was not found.")
    return ResolvedResearchAreas(tuple(selected), bytes(row["ewkb"]))


async def resolve_area(
    admin: AsyncConnection, identifier: UUID, *, boundary: bool = False
) -> ResolvedResearchArea:
    geometry = ",ST_AsGeoJSON(geometry)::jsonb boundary" if boundary else ""
    row = (
        (
            await admin.execute(
                text(
                    f"SELECT {AREA_COLUMNS},municipality_key,ST_AsEWKB(geometry) ewkb {geometry} "
                    "FROM admin.research_area WHERE id=:id"
                ),
                {"id": identifier},
            )
        )
        .mappings()
        .first()
    )
    if row is None:
        raise APIError(404, "research_area_not_found", "Research area was not found.")
    return ResolvedResearchArea(
        ResearchArea.model_validate(row),
        bytes(row["ewkb"]),
        AreaGeometry.model_validate(row["boundary"]) if boundary else None,
        row["municipality_key"],
    )
