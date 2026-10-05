"""Run with the pinned Admin's Python over SSH stdin; SELECT-only, JSON stdout.

Example remote environment: PYTHONDONTWRITEBYTECODE=1 python -B - < this-script.
No files are created remotely. Credentials remain in the existing server env file.
This is an operator export adapter, never imported by the service runtime.
"""

import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ADMIN_ROOT = Path("/var/lib/uranus-admin/releases/340df4684611dbc4b8ec73a7702f1fad2ae1973c/backend")
ENV_FILE = Path("/etc/uranus-admin/runtime.env")
REFERENCE_TIME = "2026-10-05T00:00:00+02:00"


async def export():
    sys.path.insert(0, str(ADMIN_ROOT))
    from app.repositories.vector_events import (
        DATE_STATUS,
        DATES_SQL,
        EVENT_SQL,
        PUBLIC_EVENT,
        TYPES_SQL,
    )
    from app.research.semantic_documents import public_clean
    from app.research.vector_index import SOURCE_BOUNDARY
    from dotenv import dotenv_values
    from sqlalchemy import text
    from sqlalchemy.engine import make_url
    from sqlalchemy.ext.asyncio import create_async_engine

    config = dotenv_values(ENV_FILE)
    if make_url(config["DATABASE_URL"]).username != "uranus_reader":
        raise ValueError("explicit_reader_required")
    engine = create_async_engine(
        config["DATABASE_URL"],
        echo=False,
        hide_parameters=True,
        connect_args={
            "server_settings": {
                "default_transaction_read_only": "on",
                "statement_timeout": "10000",
                "lock_timeout": "2000",
            }
        },
    )
    try:
        async with engine.connect() as c, c.begin():
            await c.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"))
            if await c.scalar(text("SHOW transaction_read_only")) != "on" or await c.scalar(
                text(SOURCE_BOUNDARY)
            ):
                raise ValueError("unsafe_source_role")
            source_count = await c.scalar(text("SELECT count(*) FROM uranus.event"))
            total = await c.scalar(
                text("SELECT count(*) FROM uranus.event e WHERE " + PUBLIC_EVENT)
            )
            if not 1 <= total <= 10000:
                raise ValueError("snapshot_limit")
            rows = list(
                (
                    await c.execute(
                        text(EVENT_SQL),
                        {"limit": 10000, "source_tz": config["URANUS_TIMESTAMP_TIMEZONE"]},
                    )
                ).mappings()
            )
            if len(rows) != total:
                raise ValueError("incomplete_snapshot")
            ids = [r["entity_id"] for r in rows]
            date_sql = DATES_SQL.replace(
                "SELECT d.uuid occurrence_id,",
                "SELECT "
                + DATE_STATUS
                + "::text occurrence_status,v.city venue_city,d.uuid occurrence_id,",
            )
            if date_sql == DATES_SQL:
                raise ValueError("source_projection_changed")
            dates = list((await c.execute(text(date_sql), {"ids": ids})).mappings())
            types = list((await c.execute(text(TYPES_SQL), {"ids": ids})).mappings())
            if len(dates) > 100000 or len(types) > 100000:
                raise ValueError("context_limit")
            events = []
            for r in rows:
                e = {
                    "uuid": str(r["entity_id"]),
                    "release_status": r["status"],
                    **{
                        k: public_clean(r.get(k))
                        for k in ("title", "subtitle", "summary", "description", "price_type")
                    },
                    "content_language": public_clean(r["language"]),
                    "languages": [public_clean(x) for x in r["languages"] or []],
                    "tags": [public_clean(x) for x in r["tags"] or []],
                    "event_types": [
                        {
                            "type_id": t["type_id"],
                            "genre_id": t["genre_id"],
                            "type_name": public_clean(t["type_name"]),
                            "genre_name": public_clean(t["genre_name"]),
                        }
                        for t in types
                        if t["event_uuid"] == r["entity_id"]
                    ],
                    "further_dates": [],
                }
                for d in dates:
                    if d["event_uuid"] != r["entity_id"]:
                        continue
                    e["further_dates"].append(
                        {
                            "uuid": str(d["occurrence_id"]),
                            "event_uuid": e["uuid"],
                            "release_status": d["occurrence_status"],
                            "venue_city": public_clean(d["venue_city"]),
                            "start_date": d["start_date"].isoformat(),
                            "start_time": d["start_time"].isoformat() if d["start_time"] else "",
                            "end_date": d["end_date"].isoformat() if d["end_date"] else None,
                            "venue_uuid": str(d["venue_id"]) if d["venue_id"] else None,
                            "venue_name": public_clean(d["venue_name"]),
                            "space_uuid": str(d["space_id"]) if d["space_id"] else None,
                            "space_name": public_clean(d["space_name"]),
                            "venue_accessibility": public_clean(d["venue_accessibility"]),
                            "space_accessibility": public_clean(d["space_accessibility"]),
                            "accessibility_info": public_clean(d["date_accessibility"]),
                        }
                    )
                events.append(e)
            result = {
                "captured_at": datetime.now(UTC).isoformat(),
                "reference_time": REFERENCE_TIME,
                "source_row_count": source_count,
                "public_event_count": total,
                "events": events,
            }
    finally:
        await engine.dispose()
    value = json.dumps(result, ensure_ascii=False, sort_keys=True, default=str)
    if len(value.encode()) > 64 * 1024 * 1024:
        raise ValueError("snapshot_size_limit")
    print(value)


if __name__ == "__main__":
    try:
        asyncio.run(export())
    except Exception:
        print("public_snapshot_export_failed", file=sys.stderr)
        raise SystemExit(1) from None
