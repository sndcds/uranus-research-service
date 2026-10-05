"""Test-only execution of pinned Admin source extraction, not a runtime dependency."""

import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path


async def main():
    data = json.load(sys.stdin)
    sys.path.insert(0, str(Path(data["admin"]) / "backend"))
    from app.config import Settings
    from app.repositories.vector_events import extract_events
    from pydantic import SecretStr
    from sqlalchemy import text
    from sqlalchemy.engine import make_url
    from sqlalchemy.ext.asyncio import create_async_engine

    for key in ("source", "area"):
        url = make_url(data[key])
        if url.host not in {"127.0.0.1", "localhost", "::1"} or not url.database.endswith("_test"):
            raise ValueError("guarded_test_database_required")
    settings = Settings(
        _env_file=None,
        app_env="test",
        dev_auth_enabled=True,
        dev_admin_token=SecretStr("synthetic-admin-parity-key-0123456789"),
        database_url=SecretStr(data["source"]),
        uranus_timestamp_timezone="UTC",
    )
    source, area = (create_async_engine(data[k], hide_parameters=True) for k in ("source", "area"))
    try:
        async with source.connect() as s, s.begin(), area.connect() as a, a.begin():
            await s.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"))
            await a.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"))
            docs, total = await extract_events(
                s, a, settings, datetime.fromisoformat(data["now"]), semantic=True
            )
            print(
                json.dumps({"total": total, "documents": [d.model_dump(mode="json") for d in docs]})
            )
    finally:
        await source.dispose()
        await area.dispose()


if __name__ == "__main__":
    asyncio.run(main())
