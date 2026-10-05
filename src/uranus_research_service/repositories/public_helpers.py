"""Pure public projection helpers extracted from Admin; no identity/workflow access."""

import math
from dataclasses import dataclass, field
from urllib.parse import urlencode
from uuid import UUID

from pydantic import BaseModel

from uranus_research_service.config import Settings
from uranus_research_service.errors import APIError

PUBLIC_API = "https://api.kulturbytes.de"


class Pagination(BaseModel):
    page: int
    page_size: int
    total: int
    pages: int


def pagination(page: int, size: int, total: int) -> Pagination:
    return Pagination(page=page, page_size=size, total=total, pages=(total + size - 1) // size)


def image_url(image_uuid: UUID | str | None, api_url: str) -> str | None:
    """Public Pluto thumbnail; never expose private origins or stored URL strings."""
    if image_uuid is None or api_url.rstrip("/") != PUBLIC_API:
        return None
    try:
        identifier = UUID(str(image_uuid))
    except ValueError:
        return None
    query = urlencode({"width": 320, "type": "png"})
    return f"{PUBLIC_API}/api/image/{identifier}?{query}"


def location(latitude: float | None, longitude: float | None) -> dict[str, float] | None:
    if (
        latitude is None
        or longitude is None
        or not math.isfinite(latitude)
        or not math.isfinite(longitude)
        or not -90 <= latitude <= 90
        or not -180 <= longitude <= 180
    ):
        return None
    return {"latitude": latitude, "longitude": longitude}


def require_timezone(settings: Settings) -> str:
    if settings.uranus_timestamp_timezone is None:
        raise APIError(503, "source_timezone_unconfigured", "Source timezone must be configured.")
    return settings.uranus_timestamp_timezone


def escape_search(value: str) -> str:
    """Treat PostgreSQL LIKE metacharacters as literal user input."""
    return value.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


@dataclass(frozen=True)
class SearchDefinition:
    source: str
    fields: tuple[str, ...]  # UUID fields are identified by field_names, including related UUIDs.
    label: str
    subtitle: str
    field_names: tuple[str, ...] = field(kw_only=True)
    created_at: str = field(kw_only=True)
    organization: str = "NULL::uuid"
    status: str = "NULL::text"
    entity_key: str | None = field(default=None, kw_only=True)
    # Only event dates need a distinct, joined parent target; never a database href.
    action_key: str = field(default="NULL::text", kw_only=True)
    venue_scope: str = field(default="NULL::text", kw_only=True)

    def projection(self) -> str:
        fields = ",".join(f"{field} search_{i}" for i, field in enumerate(self.fields))
        return (
            f"SELECT {self.entity_key or self.fields[0]} entity_key,"
            f"{self.label} label,{self.subtitle} subtitle,{self.action_key} action_key,"
            f"{self.created_at} created_at,{self.organization} organization_id,"
            f"{self.status} status,{self.venue_scope} venue_scope,{fields} FROM {self.source}"
        )

    def rank(self) -> str:
        uuid_matches = " OR ".join(
            f"search_{i} ILIKE :exact" for i, name in enumerate(self.field_names) if name == "uuid"
        )
        return (
            f"CASE WHEN {uuid_matches} THEN 0 "
            f"WHEN {self.matches('exact')} THEN 1 "
            f"WHEN {self.matches('prefix')} THEN 2 ELSE 3 END"
        )

    def matched_fields(self) -> str:
        fields = ",".join(
            "CASE WHEN "
            + " OR ".join(
                f"search_{i} ILIKE :q"
                for i, field_name in enumerate(self.field_names)
                if field_name == name
            )
            + f" THEN '{name}' END"
            for name in dict.fromkeys(self.field_names)
        )
        return f"array_remove(ARRAY[{fields}],NULL)"

    def matches(self, parameter: str = "q") -> str:
        return " OR ".join(f"search_{i} ILIKE :{parameter}" for i in range(len(self.fields)))


SEARCH_DEFINITIONS = {
    "organization": SearchDefinition(
        "uranus.organization o",
        ("o.uuid::text", "o.name", "o.contact_email", "o.city", "o.postal_code"),
        "o.name",
        "COALESCE(NULLIF(concat_ws(' · ',NULLIF(o.city,''),NULLIF(o.postal_code,'')),''),"
        "NULLIF(o.contact_email,''))",
        "o.uuid",
        field_names=("uuid", "name", "contact_email", "city", "postal_code"),
        created_at="o.created_at",
    ),
    "venue": SearchDefinition(
        "uranus.venue v LEFT JOIN uranus.organization o ON o.uuid=v.org_uuid",
        (
            "v.uuid::text",
            "v.name",
            "v.contact_email",
            "v.street",
            "v.house_number",
            "v.postal_code",
            "v.city",
        ),
        "v.name",
        "COALESCE(NULLIF(concat_ws(' · ',"
        "NULLIF(concat_ws(' ',NULLIF(v.street,''),NULLIF(v.house_number,'')),''),"
        "NULLIF(concat_ws(' ',NULLIF(v.postal_code,''),NULLIF(v.city,'')),'')),''),o.name)",
        "v.org_uuid",
        field_names=(
            "uuid",
            "name",
            "contact_email",
            "street",
            "house_number",
            "postal_code",
            "city",
        ),
        created_at="v.created_at",
        venue_scope="v.scope",
    ),
    "event": SearchDefinition(
        "uranus.event e LEFT JOIN uranus.organization o ON o.uuid=e.org_uuid",
        ("e.uuid::text", "e.title", "e.subtitle", "e.external_id"),
        "e.title",
        "COALESCE(NULLIF(e.subtitle,''),NULLIF(o.name,''),e.release_status::text,e.external_id)",
        "e.org_uuid",
        "e.release_status::text",
        field_names=("uuid", "title", "subtitle", "external_id"),
        created_at="e.created_at",
    ),
}
