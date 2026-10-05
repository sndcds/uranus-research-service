# Read-only PostgreSQL/PostGIS boundary — Phase 2A

Two explicitly injected SQLAlchemy async/asyncpg engines are used:

- `RESEARCH_DATABASE_URL[_FILE]`: dedicated source reader.
- `RESEARCH_AREA_DATABASE_URL[_FILE]`: separate metadata reader limited to
  `admin.research_area`. No Admin runtime/writer account is accepted.

Files take precedence, contain a `postgresql+asyncpg://` URL, and must be absolute.
No DDL, grants, migrations, writes or source schema discovery/ORM reflection run in
production code. DSNs are SecretStr values and never returned or logged.

## Required SELECT contracts

Source reader needs schema USAGE and SELECT on:
`uranus.event`, `event_date`, `venue`, `organization`, `space`, `event_type`,
`event_type_link`, `genre_type`, `event_category`, `pluto_image`, `pluto_image_link`.
Queries retain explicit public projections, release/date override eligibility,
venue/space inheritance, taxonomy identity and temporal semantics from pinned Admin.
No source user, password, account or workflow table is queried. A future narrower
column/view projection requires a separately reviewed privilege-contract change.

Metadata reader needs only schema USAGE and SELECT on **admin.research_area**. The
existing projection supplies administrative classification, names, OSM identity,
geometry/centroid/bounds, municipality key and population/provenance metadata. It
supplies no account/session/workflow fields. Geometry import/enrichment and population
updates remain Admin/operator responsibilities.

Chosen Phase-2A option: separate narrow reader, preserving existing SQL. A new
projection view would require unprovisioned DDL and is not invented silently. The
service checks required relation/SELECT availability; source column compatibility is
also exercised by real SQL integration tests. Deployed DDL still requires operator
verification before any later rollout.

## Effective privilege preflight

On /ready, before structured resolution, and inside every read snapshot:

- Reject effective or SET ROLE-accessible superuser, createrole, createdb, replication
  and bypass-RLS roles.
- Reject database CREATE/TEMP and application-schema CREATE or ownership.
- Reject INSERT/UPDATE/DELETE/TRUNCATE/TRIGGER/REFERENCES, including column grants,
  application relation ownership and inherited/NOINHERIT owner membership.
- Reject writable sequence rights/ownership.
- Reject SELECT/column SELECT on any other relation in uranus/admin for that reader.
- Require schema USAGE (public and the reader's relation schema), all role-specific
  tables, SELECT grants, PostGIS and transaction_read_only=on.

Checks use PostgreSQL catalogs/effective privileges, not role names. This is stricter
than a transaction-only safeguard: operators must also remove inherited/PUBLIC
CREATE/TEMP where applicable. The runtime never repairs grants. Admin's DML-oriented
`assert_admin_boundary` is intentionally not reused for this narrow metadata reader.

## Transaction model

Connections set default_transaction_read_only=on, UTC, finite connect/pool/statement/
lock/idle-transaction deadlines and hide_parameters=True. Each coherent source/area
read uses REPEATABLE READ, READ ONLY. Pools have bounded size and zero overflow.

Planner inference and Geocoder calls run outside database transactions. Resolution
snapshots close before final execution obtains its own snapshot, matching Admin's
existing semantics. Only application-owned SQL/identifiers and bound user values are
used. SQL provenance instruments explicit Research calls, not global SQLAlchemy hooks;
privilege probes are not mixed into answer provenance.

## Disposable testing

Tests accept only a loopback database name matching `[a-z][a-z0-9_]*_test`, with neither
uranus nor admin schemas already present. Fixture DDL copies the pinned schema-only
Admin snapshot and adds a synthetic area table; all rows/reader credentials are test
material. Fixtures create and remove their own roles/schemas. No production DSN is
used, and no SQLite approximation replaces PostGIS.

Tests verify actual execution plus denied writes, table/column grants, schema CREATE,
superuser/createrole, inherited ownership (including a nonsuperuser NOINHERIT owner),
unrelated workflow SELECT, missing schema USAGE and missing required relations. CI provisions its own
PostGIS container. Role/schema setup here is test infrastructure, not deployment DDL.
