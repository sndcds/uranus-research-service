# Uranus Research Service

Internal deterministic Research execution for Kulturbytes/Uranus. **Phase 2B.1** retains
structured Planner-v13 queries and grounded conversation responses. Admin still runs
its existing Research path; this repository does not switch any consumer or deployment.

```text
Today: Browser → Admin → existing Admin Research execution

Isolated service / future Admin adapter:
Admin identity → internal Bearer + opaque principal → Research Service
    ├─ Planner v13: language → closed, validated plan
    ├─ deterministic resolution + execution → read-only PostgreSQL/PostGIS
    ├─ separate metadata reader → admin.research_area only
    ├─ optional Research Geocoder + reviewed complete area inventory
    └─ bounded conversation state → safe AnswerFacts → deterministic answer

Semantic plans → unsupported_constraint, before resolution or SQL
Encoder / Qdrant: isolated internal semantic path; optional separate readiness capability
```

This service owns execution, not Admin identity/workflows, language inference, model
weights, a vector database or the authoritative source data. PostgreSQL remains the
facts source. No free-form SQL, model-generated answers or autonomous tools are accepted.

## Run and contracts

Python 3.13, uv, FastAPI, Pydantic, httpx, SQLAlchemy async and asyncpg:

```sh
uv sync --locked
# Supply protected key/reader files and fixed service origins; see .env.example.
uv run uranus-research-service
```

No `.env` is loaded implicitly. Secret files take precedence over environment secrets;
file errors fail startup without fallback. No credentials or model weights belong in
Git or the image. The executable listens on 6338; expose it only internally/loopback.

| Endpoint | Behavior |
| --- | --- |
| GET /health | Unauthenticated process liveness, exactly `{"status":"ok"}`; no dependencies |
| GET /version | Authenticated service 0.2.0 / contract v1, expected pins, last readiness capabilities |
| GET /ready | Planner readiness/v13 route, both read-only DB boundaries, required tables/PostGIS |
| POST /query | Validated v13 planning → conversation or deterministic structured execution |

`/query` requires both `Authorization: Bearer …` and `X-Research-Principal` (64 lowercase
hex characters). The latter is an opaque pseudonym minted by the trusted caller, not
an Admin cookie or session token. A future Admin adapter must derive it server-side
using a dedicated, domain-separated HMAC key. No Admin adapter is activated here.

```json
{"query":"Welche Veranstaltungen gibt es am Wochenende?","timezone":"Europe/Berlin","language":"auto","conversation_id":null,"location_context":null}
```

Successful responses use `{"schema_version":"uranus-research-service-v1","response":…}`.
The inner ResearchExecutionResponse / ConversationResponse preserves Admin semantics.
Semantic requests produce a bounded conversation `unsupported_constraint`, never
partial structured execution. Caller-selected SQL/model/collection/backend fields fail.
See [query contract](docs/query-contract.md) for mappings and errors.

## Readiness and capabilities

Every Planner response passes the actual closed v13 Pydantic validators, including
original query, nested plan, timezone, prompt, model/diagnostic and interaction identity.
Readiness itself uses GET /ready and OPTIONS /v13/plan without inference.

`query_enabled` and `capabilities.structured_query` start false and become true after
a successful explicit readiness probe. `/version` reports that last probe, not a new
external check. Failed readiness/server-side execution invalidates it. Every structured
resolution rechecks both reader boundaries, and every SQL snapshot rechecks its role.
Conversation-only acts can return without touching either database.

Capabilities distinguish structured execution, conversation, SQL spatial operations,
optional named-place resolution, complete administrative grouping and disabled semantic
retrieval. Missing optional Geocoder/inventory does not block basic SQL readiness; its
capability is false and affected requests fail explicitly. Encoder/Qdrant availability
never blocks structured readiness. Encoder metadata in /version remains an **expected consumer pin**; the separate
semantic_index_ready capability reports the last configured compatibility check.

## Isolated semantic indexing

The Jina-v5 HTTP consumer, fixed-role Qdrant client, manifest verification, operator-only
complete event builds and internal SQL → evidence → rehydration path are implemented.
`POST /query` still rejects semantic plans before resolution/SQL. No live writes or
Admin/Planner/Encoder code changes accompany this phase.

Use `uranus-research-service index plan|build|validate|benchmark|compare` with explicit
build IDs and immutable report destinations. Writes require a disposable loopback
Qdrant on a nondefault port, `test_` build ID and `--isolated`; no live override exists.
See [operator guide](docs/phase2b1-semantic-index.md), [reindex plan](docs/v5-reindex-plan.md),
[benchmark](docs/retrieval-benchmark.md), and [live read-only inventory](docs/live-semantic-preflight.md).

Set `SEMANTIC_BUILD_ID` to probe a configured event build separately during `/ready`.
`semantic_index_ready` can become true; `semantic_query` stays false.

## Validation

```sh
uv run --no-sync ruff check .
uv run --no-sync ruff format --check .
uv run --no-sync pytest -q -m 'not integration'
# Empty disposable LOOPBACK PostgreSQL/PostGIS DB ending _test, synthetic credentials:
TEST_DATABASE_URL=... ADMIN_PARITY_ROOT=/path/to/pinned/uranus-admin \
  uv run --no-sync pytest -q
```

The integration fixture refuses populated source/admin schemas, creates synthetic
rows and restricted roles, and removes only its own schemas/roles. Differential tests
execute untouched pinned Admin code with its own Python environment on the identical
dataset/plans/reference date. No live Planner inference is claimed by these fixtures.
CI runs both unit tests and disposable PostGIS/Admin parity, plus an offline image build.
Actual results and limitations: [validation](docs/validation.md).

## Container

```sh
uv run --no-sync python scripts/build_wheelhouse.py
docker build --network=none -f deploy/Dockerfile -t uranus-research-service:phase2a .
```

Prepare locked, hash-checked wheels using Python 3.13 Linux for the target architecture.
The ignored wheelhouse must be rebuilt after code/lock changes. The image installs
without package networking and runs as UID 10001 with read-only root support. See
`deploy/compose.example.yml`; it is an example, not a deployment command or role grant.

## Extraction and ownership

[Phase-2A implementation](docs/phase2-structured-execution.md),
[extraction audit](docs/extraction-audit.md),
[per-module source/target manifest](docs/phase2-port-manifest.json),
[database boundary](docs/database-boundary.md),
[Qdrant boundary](docs/qdrant-boundary.md), and
[v5 consumer migration](docs/jina-v5-consumer-migration.md).

Code was selectively ported from the pinned AGPL Uranus Admin reference. Contracts
are local JSON snapshots and validators, not runtime imports from sibling repositories.
Admin auth, sessions, CSRF, UI, learning and workflow tables remain in Admin.

Service code: AGPL-3.0-only (LICENSE). No model weights are included. The separate
future Jina-v5 encoder uses CC-BY-NC-4.0 weights; review their terms before commercial
use. This is not a legal assessment and the model is not loaded by this service.
