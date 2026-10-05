import pytest
from sqlalchemy import text

from uranus_research_service.database import ResearchDatabase
from uranus_research_service.errors import APIError

pytestmark = pytest.mark.integration


async def test_reader_preflight_and_database_enforced_readonly(db_settings):
    db = ResearchDatabase(db_settings)
    areas = ResearchDatabase(db_settings, "area")
    try:
        await db.ready()
        await areas.ready()
        async with db.connection() as conn:
            assert await conn.scalar(text("SHOW transaction_isolation")) == "repeatable read"
            assert await conn.scalar(text("SHOW transaction_read_only")) == "on"
            assert await conn.scalar(text("SELECT count(*) FROM uranus.event")) == 3
        with pytest.raises(APIError):
            async with db.connection() as conn:
                await conn.execute(text("UPDATE uranus.event SET title='forbidden'"))
        with pytest.raises(APIError):
            async with areas.connection() as conn:
                await conn.execute(text("SELECT private_value FROM admin.workflow_private"))
    finally:
        await db.close()
        await areas.close()


@pytest.mark.parametrize(
    "privilege",
    ["INSERT", "UPDATE", "DELETE", "TRUNCATE", "TRIGGER", "REFERENCES", "UPDATE(title)"],
)
async def test_effective_write_grants_rejected(db_settings, root_connection, postgres, privilege):
    role = postgres["source_role"]
    await root_connection.execute(f"GRANT {privilege} ON uranus.event TO {role}")
    db = ResearchDatabase(db_settings)
    try:
        with pytest.raises(APIError):
            await db.ready()
    finally:
        await db.close()
        await root_connection.execute(f"REVOKE {privilege} ON uranus.event FROM {role}")


@pytest.mark.parametrize(
    "scenario",
    [
        "schema_create",
        "inherited_owner",
        "superuser",
        "createrole",
        "workflow_read",
        "missing_table",
        "missing_usage",
    ],
)
async def test_unsafe_boundary_fails_closed(db_settings, root_connection, postgres, scenario):
    role = postgres["source_role"]
    admin = postgres["area_role"]
    changes = {
        "missing_usage": (
            f"REVOKE USAGE ON SCHEMA uranus FROM {role}",
            f"GRANT USAGE ON SCHEMA uranus TO {role}",
        ),
        "schema_create": (
            f"GRANT CREATE ON SCHEMA uranus TO {role}",
            f"REVOKE CREATE ON SCHEMA uranus FROM {role}",
        ),
        "inherited_owner": (f"GRANT postgres TO {role}", f"REVOKE postgres FROM {role}"),
        "superuser": (f"ALTER ROLE {role} SUPERUSER", f"ALTER ROLE {role} NOSUPERUSER"),
        "createrole": (f"ALTER ROLE {role} CREATEROLE", f"ALTER ROLE {role} NOCREATEROLE"),
        "workflow_read": (
            f"GRANT SELECT ON admin.workflow_private TO {admin}",
            f"REVOKE SELECT ON admin.workflow_private FROM {admin}",
        ),
        "missing_table": (
            "ALTER TABLE uranus.event_type RENAME TO hidden_event_type",
            "ALTER TABLE uranus.hidden_event_type RENAME TO event_type",
        ),
    }
    change, undo = changes[scenario]
    await root_connection.execute(change)
    db = ResearchDatabase(db_settings, "area" if scenario == "workflow_read" else "source")
    try:
        with pytest.raises(APIError):
            await db.ready()
    finally:
        await db.close()
        await root_connection.execute(undo)


async def test_noinherit_nonsuperuser_table_ownership_is_rejected(
    db_settings, postgres, root_connection
):
    role = postgres["source_role"]
    owner = role + "_owner"
    await root_connection.execute(f"CREATE ROLE {owner}; ALTER TABLE uranus.event OWNER TO {owner}")
    await root_connection.execute(f"GRANT {owner} TO {role} WITH INHERIT FALSE")
    db = ResearchDatabase(db_settings)
    try:
        with pytest.raises(APIError):
            await db.ready()
    finally:
        await db.close()
        await root_connection.execute(
            f"REVOKE {owner} FROM {role}; "
            f"ALTER TABLE uranus.event OWNER TO postgres; DROP ROLE {owner}"
        )
