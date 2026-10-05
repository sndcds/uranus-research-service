"""Public-only, immutable annotation corpus. No credentials, database writes or models."""

import hashlib
import json
from datetime import date, datetime
from pathlib import Path
from typing import Literal
from uuid import UUID
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, model_validator

from uranus_research_service.json_codec import decode
from uranus_research_service.research.semantic_documents import public_clean
from uranus_research_service.semantic_manifest import digest

PUBLIC = {"released", "cancelled", "deferred", "rescheduled"}
MAX_BYTES = 64 * 1024 * 1024


class Closed(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Occurrence(Closed):
    id: UUID
    status: Literal["released", "cancelled", "deferred", "rescheduled"]
    start_date: date
    start_time: str = Field(max_length=8)
    end_date: date | None = None
    venue_id: UUID | None = None
    venue: str = Field(max_length=2000)
    city: str = Field(max_length=2000)
    space_id: UUID | None = None
    space: str = Field(max_length=2000)
    venue_accessibility: str = Field(max_length=20000)
    space_accessibility: str = Field(max_length=20000)
    accessibility_info: str = Field(max_length=20000)


class EventType(Closed):
    type_id: int
    genre_id: int
    type_name: str = Field(max_length=2000)
    genre_name: str = Field(max_length=2000)


class PublicEvent(Closed):
    id: UUID
    status: Literal["released", "cancelled", "deferred", "rescheduled"]
    title: str = Field(max_length=10000)
    subtitle: str = Field(max_length=10000)
    summary: str = Field(max_length=200000)
    description: str = Field(max_length=200000)
    content_language: str = Field(max_length=20)
    languages: list[str] = Field(max_length=100)
    tags: list[str] = Field(max_length=1000)
    price_type: str = Field(max_length=100)
    event_types: list[EventType] = Field(max_length=100)
    occurrences: list[Occurrence] = Field(max_length=10000)

    @model_validator(mode="after")
    def public_text(self):
        def check(value):
            if isinstance(value, str) and public_clean(value) != value:
                raise ValueError("non_public_text")
            if isinstance(value, dict):
                for k, v in value.items():
                    if k not in {"id", "venue_id", "space_id"}:
                        check(v)
            if isinstance(value, list):
                for v in value:
                    check(v)

        check(self.model_dump(mode="python"))
        ids = [o.id for o in self.occurrences]
        if ids != sorted(set(ids), key=str):
            raise ValueError("occurrences_not_unique_sorted")
        return self


class SnapshotRow(Closed):
    document_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    event: PublicEvent

    @model_validator(mode="after")
    def hash_matches(self):
        if digest(self.event.model_dump(mode="json")) != self.document_hash:
            raise ValueError("document_hash_mismatch")
        return self


class SnapshotManifest(Closed):
    schema_version: Literal["public-annotation-snapshot-v1"]
    snapshot_id: str = Field(pattern=r"^[a-z0-9_-]{1,80}$")
    captured_at: datetime
    reference_time: datetime
    timezone: str
    source: Literal["uranus_reader_public_select"]
    exporter_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_code_revision: Literal["340df4684611dbc4b8ec73a7702f1fad2ae1973c"]
    source_row_count: int = Field(ge=1, le=10000)
    public_event_count: int = Field(ge=1, le=10000)
    source_snapshot_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    file_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    window_start: date
    window_end: date
    capture_rule: Literal["repeatable_read_read_only"]

    @model_validator(mode="after")
    def consistent(self):
        if self.captured_at.tzinfo is None or self.reference_time.tzinfo is None:
            raise ValueError("aware_snapshot_time_required")
        ZoneInfo(self.timezone)
        if self.window_start > self.window_end or self.public_event_count > self.source_row_count:
            raise ValueError("invalid_snapshot_counts_or_window")
        return self


def canonical_bytes(value):
    return json.dumps(
        value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False
    ).encode()


def serialize_events(events):
    values = sorted(events, key=lambda e: str(e.id))
    if len({e.id for e in values}) != len(values) or not 1 <= len(values) <= 10000:
        raise ValueError("snapshot_event_identity")
    rows = [SnapshotRow(event=e, document_hash=digest(e.model_dump(mode="json"))) for e in values]
    data = b"".join(canonical_bytes(r.model_dump(mode="json")) + b"\n" for r in rows)
    if len(data) > MAX_BYTES:
        raise ValueError("snapshot_size_limit")
    return rows, data


def load_snapshot(path, manifest_path):
    if Path(path).stat().st_size > MAX_BYTES or Path(manifest_path).stat().st_size > 16384:
        raise ValueError("snapshot_size_limit")
    manifest = SnapshotManifest.model_validate(decode(Path(manifest_path).read_bytes()))
    data = Path(path).read_bytes()
    if hashlib.sha256(data).hexdigest() != manifest.file_sha256:
        raise ValueError("snapshot_file_hash_mismatch")
    rows = [SnapshotRow.model_validate(decode(line)) for line in data.splitlines()]
    canonical, encoded = serialize_events([r.event for r in rows])
    if encoded != data or len(rows) != manifest.public_event_count:
        raise ValueError("noncanonical_snapshot")
    if digest([r.model_dump(mode="json") for r in canonical]) != manifest.source_snapshot_hash:
        raise ValueError("source_snapshot_hash_mismatch")
    return manifest, {r.event.id: r for r in rows}


def project_event(raw, start, end):
    if raw.get("release_status") not in PUBLIC:
        raise ValueError("non_public_event")
    event_id = UUID(raw["uuid"])
    occurrences = []
    dates = [raw["date"]] if raw.get("date") else []
    dates += raw.get("further_dates") or []
    for d in dates:
        if d.get("release_status") not in PUBLIC:
            continue
        if UUID(d["event_uuid"]) != event_id:
            raise ValueError("occurrence_event_mismatch")
        day = date.fromisoformat(d["start_date"])
        if not start <= day <= end:
            raise ValueError("snapshot_date_outside_window")
        occurrences.append(
            Occurrence(
                id=d["uuid"],
                status=d["release_status"],
                start_date=day,
                start_time=d.get("start_time") or "",
                end_date=d.get("end_date") or None,
                venue_id=d.get("venue_uuid"),
                venue=public_clean(d.get("venue_name")),
                city=public_clean(d.get("venue_city")),
                space_id=d.get("space_uuid"),
                space=public_clean(d.get("space_name")),
                venue_accessibility=public_clean(d.get("venue_accessibility")),
                space_accessibility=public_clean(d.get("space_accessibility")),
                accessibility_info=public_clean(d.get("accessibility_info")),
            )
        )
    fields = {
        k: public_clean(raw.get(k))
        for k in ("title", "subtitle", "summary", "description", "content_language", "price_type")
    }
    return PublicEvent(
        id=event_id,
        status=raw["release_status"],
        **fields,
        languages=sorted({public_clean(x) for x in raw.get("languages") or []}),
        tags=sorted({public_clean(x) for x in raw.get("tags") or []}),
        event_types=[
            EventType(
                type_id=t["type_id"],
                genre_id=t["genre_id"],
                type_name=public_clean(t.get("type_name")),
                genre_name=public_clean(t.get("genre_name")),
            )
            for t in sorted(
                raw.get("event_types") or [], key=lambda t: (t["type_id"], t["genre_id"])
            )
        ],
        occurrences=sorted(occurrences, key=lambda o: str(o.id)),
    )
