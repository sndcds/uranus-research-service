# Future database boundary

Phase 1 creates no engines, accepts no database DSN, grants no privileges, and sends
no SQL. This document specifies the later extraction from Admin commit recorded in
`extraction-inventory.json`. PostgreSQL/PostGIS remains authoritative.

## Reader contracts

A dedicated source role will need SELECT on the public-research projection of:

- `uranus.event`, `event_date`, `organization`, `venue`, `space`;
- `uranus.event_type_link`, `event_type`, `genre_type`, `event_category`;
- public image references `uranus.pluto_image_link`, `pluto_image` for existing thumbnails.

Prefer explicit views/column grants where operations need only public fields. Do
not grant access to source users, password/token columns, private contacts or Admin
workflow tables just because canonical shared search definitions mention them.
Confirm the deployed DDL and the exact SQL projections before provisioning. Public
release/date override gates, effective venue/space inheritance and temporal joins
must remain identical to the extracted repositories.

Administrative geography currently lives in **`admin.research_area`**. Research
needs its ID/type/country/region/OSM classification, municipality key, name/display
name, geometry/centroid, retrieval/update provenance and population value/date/source/
name/file hash/import timestamp. It does not need account or workflow state.
Either provide a read-only projection/view with those fields or a separate metadata
reader limited to SELECT on this single table. Keep imports, geometry validation,
population updates and migrations in Admin/operator tooling. No broad Admin runtime
account may be reused by the service.

## Transactions and privilege checks

Reuse async SQLAlchemy/asyncpg only when execution is actually extracted. Set UTC,
`default_transaction_read_only=on`, `hide_parameters=True`, finite connection/pool/
command deadlines and a statement timeout (Admin baseline 10 seconds). Each coherent
source read uses `REPEATABLE READ, READ ONLY`. Bound counts/pages/eligibility probes
and reject overflow instead of silently truncating an authoritative candidate set.

Verify effective inherited privileges, schema CREATE, role ownership, superuser,
role-creation and table/column DML, not merely the account name. Source writes,
TRUNCATE, trigger creation, source DDL, extension creation and runtime grants are
forbidden. Transactions alone do not compensate for excessive role privileges.
The metadata reader must also lack access to unrelated Admin tables.

Resolution/eligibility snapshots end before external embedding or vector calls;
final authoritative rehydration obtains a fresh bounded snapshot. SQL and identifiers
remain code-owned and allowlisted; all user-derived values are bound parameters.
No model-generated SQL, model-chosen tables, runtime ORM reflection or auto-migrations.

## Validation before phase-2 rollout

Use a disposable PostgreSQL/PostGIS database ending `_test`, following Admin's
empty-schema guard. Check count/records/grouped/aggregate/comparison/spatial/temporal
semantics, readonly enforcement, timeout/overflow and denied write privileges.
Never use a production reader as a test fixture setup/teardown account. No database
integration test or live schema verification is claimed by phase 1.
