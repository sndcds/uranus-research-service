"""Dedicated read-only engines. No DDL, migrations, ownership or Admin workflow access."""

import asyncio
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from typing import Literal, Protocol

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine

from uranus_research_service.errors import APIError

SOURCE_TABLES = (
    "uranus.event",
    "uranus.event_date",
    "uranus.venue",
    "uranus.organization",
    "uranus.space",
    "uranus.event_type",
    "uranus.event_type_link",
    "uranus.genre_type",
    "uranus.event_category",
    "uranus.pluto_image",
    "uranus.pluto_image_link",
)
AREA_TABLES = ("admin.research_area",)
# Adapted from Admin vector_index.SOURCE_BOUNDARY. MEMBER also catches ownership
# accessible through SET ROLE even when NOINHERIT currently hides privileges.
UNSAFE = """SELECT
 EXISTS(SELECT 1 FROM pg_roles r WHERE pg_has_role(current_user,r.oid,'MEMBER')
   AND (r.rolsuper OR r.rolcreaterole OR r.rolcreatedb OR r.rolreplication OR r.rolbypassrls))
 OR has_database_privilege(current_user,current_database(),'CREATE,TEMP')
 OR EXISTS(SELECT 1 FROM pg_namespace n WHERE n.nspname NOT LIKE 'pg_%'
   AND n.nspname<>'information_schema' AND
   (has_schema_privilege(current_user,n.oid,'CREATE')
    OR pg_has_role(current_user,n.nspowner,'MEMBER')))
 OR EXISTS(SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
   WHERE n.nspname NOT LIKE 'pg_%' AND n.nspname<>'information_schema'
   AND c.relkind IN ('r','p','v','m','f') AND (
    has_table_privilege(current_user,c.oid,'INSERT,UPDATE,DELETE,TRUNCATE,TRIGGER,REFERENCES')
    OR has_any_column_privilege(current_user,c.oid,'INSERT,UPDATE,REFERENCES')
    OR pg_has_role(current_user,c.relowner,'MEMBER')))
 OR EXISTS(SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
   WHERE n.nspname NOT LIKE 'pg_%' AND n.nspname<>'information_schema' AND c.relkind='S'
   AND (has_sequence_privilege(current_user,c.oid,'USAGE,UPDATE')
        OR pg_has_role(current_user,c.relowner,'MEMBER')))
 OR EXISTS(SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
   WHERE n.nspname IN ('uranus','admin') AND c.relkind IN ('r','p','v','m','f')
   AND NOT (n.nspname||'.'||c.relname=ANY(CAST(:allowed AS text[])))
   AND (has_table_privilege(current_user,c.oid,'SELECT')
        OR has_any_column_privilege(current_user,c.oid,'SELECT')))
"""


def unavailable():
    return APIError(503, "research_execution_unavailable", "Research database unavailable.")


class Database(Protocol):
    def connection(self) -> AbstractAsyncContextManager[AsyncConnection]: ...
    async def ready(self) -> None: ...
    async def close(self) -> None: ...


class ResearchDatabase:
    def __init__(self, settings, kind: Literal["source", "area"] = "source"):
        secret = settings.database_url if kind == "source" else settings.area_database_url
        self.tables = SOURCE_TABLES if kind == "source" else AREA_TABLES
        self.timeout = settings.db_timeout_seconds
        self.engine = (
            None
            if secret is None
            else create_async_engine(
                secret.get_secret_value(),
                echo=False,
                hide_parameters=True,
                pool_pre_ping=True,
                pool_size=settings.db_pool_size,
                max_overflow=0,
                pool_timeout=self.timeout,
                connect_args={
                    "timeout": self.timeout,
                    "command_timeout": self.timeout,
                    "server_settings": {
                        "application_name": "uranus-research-service",
                        "timezone": "UTC",
                        "statement_timeout": str(self.timeout * 1000),
                        "lock_timeout": str(self.timeout * 1000),
                        "idle_in_transaction_session_timeout": str(self.timeout * 1000),
                        "default_transaction_read_only": "on",
                    },
                },
            )
        )

    async def close(self):
        if self.engine is not None:
            await self.engine.dispose()

    async def preflight(self, connection):
        if await connection.scalar(text("SHOW transaction_read_only")) != "on":
            raise unavailable()
        if await connection.scalar(text(UNSAFE), {"allowed": list(self.tables)}):
            raise unavailable()
        for schema in {"public", *(name.split(".")[0] for name in self.tables)}:
            if not await connection.scalar(
                text("SELECT has_schema_privilege(current_user,:schema,'USAGE')"),
                {"schema": schema},
            ):
                raise unavailable()
        for name in self.tables:
            oid = await connection.scalar(text("SELECT to_regclass(:name)::oid"), {"name": name})
            if oid is None or not await connection.scalar(
                text("SELECT has_table_privilege(current_user,CAST(:oid AS oid),'SELECT')"),
                {"oid": oid},
            ):
                raise unavailable()
        if not await connection.scalar(
            text("SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname='postgis')")
        ):
            raise unavailable()

    @asynccontextmanager
    async def connection(self):
        if self.engine is None:
            raise unavailable()
        try:
            async with asyncio.timeout(self.timeout):
                async with self.engine.connect() as connection, connection.begin():
                    await connection.execute(
                        text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
                    )
                    await self.preflight(connection)
                    yield connection
        except (SQLAlchemyError, TimeoutError, OSError):
            raise unavailable() from None

    async def ready(self):
        async with self.connection():
            pass
