# Research extraction boundary audit

Audit completed 2026-10-05, **before code extraction**. Source: freshly fetched
`sndcds/uranus-admin` main `340df4684611dbc4b8ec73a7702f1fad2ae1973c`.
The machine-readable inventory records source hashes and internal imports for every
Research module, repository, schema and service inspected. This is an extraction
plan, not a claim that the new service or production rollout already exists.

## Existing repositories and architecture

At the start of this audit, no `uranus-research-service` existed in the inspected
local workspaces or the GitHub repository listing. `uranus-research-knowledge` answers evidence-backed project
knowledge questions; `uranus-research-geocoder` resolves geography. Neither owns
Research execution and neither should be repurposed. Create a separate service.

```text
Before: Browser → Admin auth/routes → Planner
                              ├── ResearchPlanExecutor → Uranus/PostGIS
                              ├── semantic_search → Encoder + Qdrant → SQL rehydration
                              ├── process-local ConversationStore
                              └── Admin DB (area reads + separate suggestion writes)
After:  Browser → Admin auth/thin client → Research Service → Planner (plans only)
                                                 ├── reader → Uranus/PostGIS
                                                 ├── area-only reader → admin.research_area
                                                 ├── Encoder v5 + Qdrant v5
                                                 └── semantic ConversationStore
        Admin retains identity, sessions, workflows, area imports and learning.
```

## Boundary decisions

| Capability | Decision | Adaptation |
| --- | --- | --- |
| Planner client and normalization v9–v13 | MOVE | Preserve closed version-specific validation and errors; no response repair/fallback. |
| ResearchPlanExecutor | MOVE | Replace FastAPI Request with explicitly constructed database/resolver/semantic dependencies. |
| SQL/PostGIS count, records, aggregate, grouped, comparison, taxonomy, spatial, temporal | MOVE | Preserve SQL, parameter binding, ordering, eligibility limits, repeatable-read/read-only UTC transactions. |
| Entity/name/geography resolution | MOVE | Inject source reader, restricted area reader and Geocoder client; fail closed on ambiguity. |
| Semantic retrieval | MOVE | SQL eligibility precedes vectors; authoritative rehydration/context selection follows. |
| Encoder transport | MOVE | Validate exact v5 `/version` contract before embedding/chunking. |
| Qdrant transport | MOVE | Separate v5 collections; validate embedding manifest in addition to size/distance. |
| Vector indexing/sync/documents | MOVE | Keep deterministic IDs/hashes, complete-snapshot deletion, metadata reuse and bounded batches; separate operator CLI. |
| Taxonomy retrieval/index/policy | MOVE | v5 identity invalidates old calibration; no automatic v3 policy reuse. |
| Evidence | MOVE | Preserve ownership/version/hash/SQL eligibility/context checks. Add current-document freshness checks where needed. |
| Answer facts/rendering | MOVE | Deterministic facts projection and safe response rendering, no LLM answer generation. |
| SQL provenance | MOVE | Preserve context-local capture and exact redaction/parameter allowlist. |
| Conversation semantics/store | MOVE | Preserve TTL/capacity/turn locks, summaries and answer facts; no transcripts/rows/vectors/coordinates. |
| Admin session binding | KEEP_IN_ADMIN | Derive an opaque, service-specific principal server-side; never forward session material or cookies. |
| Research Areas | MOVE / KEEP_IN_ADMIN | Read-only boundary/population contract moves; imports, enrichment and ownership remain Admin. |
| Suggestions and learning | KEEP_IN_ADMIN | Best-effort after validated response; preserve sensitive-location/v13 exclusion. |
| Browser-facing schemas | SHARED_CONTRACT | Existing response shape stays; internal versioned envelope unwraps in Admin. |
| Query/plan/semantic routes | REPLACE_WITH_HTTP_CLIENT | Explicit rollout setting; no per-request fallback on service failure. |
| Admin SQL console, login, workflows, frontend | KEEP_IN_ADMIN | Unrelated to research execution. |
| v4 project-knowledge route and candidate-only legacy gateway | DEFER | Not used by normal v13 execution; no second vector fallback in new service. |

## Admin database and privacy audit

`research_resolution`, `research_areas`, `vector_events` read only
`admin.research_area`: geometry/EWKB, centroid/bbox, OSM/administrative identifiers,
municipality key, names, provenance timestamps and population metadata. No account,
session, finding or review data is needed. A separately provisioned metadata reader
is allowed SELECT on this table only; no broad Admin runtime role or migrations.
Both engines must reject effective write/ownership/schema-CREATE privileges. Area
absence fails the affected operation; it must not broaden a spatial query.

`research_learning` and `repositories/research_suggestions` write Admin suggestion
state and remain in Admin. `research/areas`, `population`, administrative import
commands mutate Admin's geographic cache and remain operator workflows in Admin.
Do not copy `admin_database.assert_admin_boundary`: that check expects Admin DML
rights and is inappropriate for the new reader.

The existing v13 coordinator hashes the browser credential to bind ConversationStore
ownership. Replace that coupling with a fixed-format, keyed, domain-separated opaque
principal minted by Admin. The internal bearer key authenticates Admin itself; the
principal is never chosen by browser request JSON. Conversation state stores only
this pseudonym, bounded semantic summaries, pending clarification and safe answer
facts. Existing ownership isolation, expiry and busy rejection remain.

## Coupling and compatibility risks

* Executor, resolver, semantic pipeline and conversation coordinator currently use
  Request/app.state. Remove this from extracted execution code; retain Request only
  at the new HTTP boundary. No fake Request or copied Admin service locator.
* `repositories/research` imports generic pagination, public image/location helpers
  and the canonical entity search definitions. Extract only the required pure
  helpers/definitions and prove parity; do not import Admin activity/workflows.
* Existing Qdrant.info validates only size/Cosine; add a fail-closed collection
  manifest including model/version/document schema/owner. Never adopt a pre-existing
  unmarked collection or overwrite a v3 collection.
* Existing evidence hashes prove payload self-consistency; they do not alone prove
  equality to the current source text. Preserve current rehydration/context checks
  and verify current document content before accepting stale text as evidence.
* Taxonomy thresholds and semantic relevance thresholds were calibrated for the old
  embedding space. Preserve the algorithm, disclose lack of v5 quality calibration,
  and gate rollout on an identical-corpus benchmark. No quality improvement claim.
* New encoder identity is pinned: jina-v5, 1024 dimensions, revision
  dd76d535f5447ca3897a9c893fb1e612ead98192, contract uranus-research-encoder-v1,
  chunk sections-480-overlap64-v2. Exact embedding_version comes from the merged
  encoder 0.2.0 version.py; ONNX is not used.
* New tokenizer/prefix counts can change chunk boundaries despite identical v2
  chunk algorithm. Record corpus/document and chunk hashes separately in reports.
* Existing uncommitted Planner retrieval work belongs to an earlier task. Preserve
  it separately; do not transfer its replacement execution design into this service.
  The committed Planner stays language-only. Encoder remains unchanged.

## Phase-1 scope and subsequent extraction sequence

This audit now accompanies the deliberately smaller phase-1 skeleton. No executor,
SQL repository, indexer, semantic runtime or conversation store is copied into the
active service. Earlier isolated extraction experiments were set aside outside this
repository; they are not validated deliverables or production changes.

Phase 1 implements authenticated health/version/readiness, metadata clients, a
closed disabled query contract and pinned JSON snapshots. Per user decision,
Planner readiness checks `/ready` and OPTIONS on the exact configured version route
(405 + Allow: POST). This is route availability, **not full schema attestation**;
future real responses must undergo the original closed semantic validation.

Phase 2 ports the tested executor/normalizers with explicit database/resolver/semantic
parameters, then the read-only area projection, semantic evidence, and conversation
principal binding. Preserve Admin rollback through an explicit deployment setting;
no automatic request fallback or dual writes. Only after synthetic and isolated
PostGIS/contract tests should an optional Admin client be activated in development.

Subsequent controlled jobs build four separate v5 collections, validate manifests,
counts and smoke retrieval, then run reviewed same-corpus goldens. Production alias
cutover and eventual v3 cleanup require separate explicit authorization.

Source tests listed below are **coverage inventory**, not phase-1 test results.
Imports and SQL-name references are static evidence; transitive dependencies and
operator-only statements must be reviewed before granting any database permission.
No grant may be generated blindly from this inventory.

## Complete component inventory

### `backend/app/api/research.py`

- Classification: **REPLACE_WITH_HTTP_CLIENT** (later extraction).
- Responsibility: Research routes with source read-only access and admin-only suggestion learning.
- Proposed target: `Admin internal HTTP adapter (future)`.
- Imports: `app.admin_database`, `app.auth.dependencies`, `app.config`, `app.database`, `app.errors`, `app.repositories`, `app.repositories.research`, `app.repositories.research_areas`, `app.research.answer`, `app.research.context`, `app.research.conversation`, `app.research.geography`, `app.research.normalize`, `app.research.public_result`, `app.schemas.research`, `app.schemas.research_administrative_result`, `app.schemas.research_areas`, `app.schemas.research_location`, `app.schemas.research_planner`, `app.schemas.research_response`, `app.schemas.research_suggestions`, `app.schemas.research_unified`, `app.services.research_administrative`, `app.services.research_conversational`, `app.services.research_learning`, `app.services.research_legacy_conversation`, `app.services.research_plan_execution`, `app.services.research_planner`, `app.services.research_unified`, `app.services.semantic_search`.
- Direct database references: None; see imported repositories for transitive access.
- Admin coupling: app.admin_database, app.auth.dependencies, Admin Request/app.state dependency to remove.
- External services: Planner HTTP.
- Existing tests: `backend/tests/test_research_sql_provenance.py`, `backend/tests/test_vector_metadata.py`, `backend/tests/test_research_calendar.py`, `backend/tests/test_research_internal_plan.py`, `backend/tests/test_admin_auth.py`, `backend/tests/test_research_area_migration.py`, `backend/tests/test_research_v13.py`, `backend/tests/test_review_benchmark.py`, `backend/tests/test_research_population.py`, `backend/tests/test_research_administrative.py`, `backend/tests/test_research_resolution.py`, `backend/tests/test_research_administrative_areas_batch.py`, `backend/tests/test_research_geography.py`, `backend/tests/test_project_knowledge.py`, `backend/tests/test_administrative_integration_guards.py`, `backend/tests/test_administrative_geography.py`, `backend/tests/test_research_suggestions.py`, `backend/tests/test_research_areas.py`, `backend/tests/test_research_scope.py`, `backend/tests/test_research_taxonomy.py`, `backend/tests/test_taxonomy_index.py`, `backend/tests/test_research_v12.py`, `backend/tests/test_research_grouping_flow.py`, `backend/tests/test_research_catalog.py`, `backend/tests/test_research_conversation.py`, `backend/tests/test_research_grouping.py`, `backend/tests/test_taxonomy_semantic.py`, `backend/tests/test_search_gateway.py`, `backend/tests/test_admin_upgrade_contracts.py`, `backend/tests/test_admin_roles.py`, `backend/tests/test_research_domain_contract.py`, `backend/tests/test_research_administrative_areas.py`, `backend/tests/test_research_answer.py`, `backend/tests/test_research_operator_config.py`, `backend/tests/test_research_chronology.py`, `backend/tests/test_semantic_search.py`, `backend/tests/test_operator_diagnostics.py`, `backend/tests/test_taxonomy_flow.py`, `backend/tests/test_semantic_genres.py`, `backend/tests/test_research_plan_execution.py`, `backend/tests/test_vector_index.py`, `backend/tests/test_research_ordering_contract.py`, `backend/tests/test_research_planner.py`, `backend/tests/test_research_analytics.py`, `backend/tests/test_research_unified.py`, `backend/tests/test_research_geocoder.py`, `backend/tests/test_semantic_knowledge_index.py`, `backend/tests/test_research_v12_postgis.py`, `backend/tests/test_research_v9_adapter.py`, `backend/tests/test_semantic_relevance.py`, `backend/tests/test_research.py`, `backend/tests/test_research_semantic_eligibility.py`.
- Decision: Query, plan and semantic endpoint dispatch to internal service; Admin authentication/learning and legacy rollout switch stay here.

### `backend/app/repositories/research.py`

- Classification: **MOVE** (later extraction).
- Responsibility: Public research projections over the existing read-only source snapshot.
- Proposed target: `src/uranus_research_service/repositories/research.py`.
- Imports: `app.config`, `app.errors`, `app.repositories.activity_previews`, `app.repositories.created_period`, `app.repositories.entities`, `app.repositories.entity_search`, `app.repositories.location`, `app.repositories.research_areas`, `app.repositories.research_place`, `app.research.sql_provenance`, `app.schemas.research`, `app.services.quality.urls`.
- Direct database references: `uranus.event`, `uranus.event_category`, `uranus.event_date`, `uranus.event_type_link`, `uranus.genre_type`, `uranus.organization`, `uranus.pluto_image`, `uranus.pluto_image_link`, `uranus.space`, `uranus.venue`.
- Admin coupling: No direct auth/workflow dependency.
- External services: None directly; service clients can be transitive.
- Existing tests: `backend/tests/test_research_sql_provenance.py`, `backend/tests/test_vector_metadata.py`, `backend/tests/test_research_calendar.py`, `backend/tests/test_research_internal_plan.py`, `backend/tests/test_admin_auth.py`, `backend/tests/test_research_area_migration.py`, `backend/tests/test_research_v13.py`, `backend/tests/test_review_benchmark.py`, `backend/tests/test_research_population.py`, `backend/tests/test_research_administrative.py`, `backend/tests/test_research_resolution.py`, `backend/tests/test_research_administrative_areas_batch.py`, `backend/tests/test_research_geography.py`, `backend/tests/test_project_knowledge.py`, `backend/tests/test_administrative_integration_guards.py`, `backend/tests/test_administrative_geography.py`, `backend/tests/test_research_suggestions.py`, `backend/tests/test_research_areas.py`, `backend/tests/test_research_scope.py`, `backend/tests/test_research_taxonomy.py`, `backend/tests/test_taxonomy_index.py`, `backend/tests/test_research_v12.py`, `backend/tests/test_research_grouping_flow.py`, `backend/tests/test_research_catalog.py`, `backend/tests/test_research_conversation.py`, `backend/tests/test_research_grouping.py`, `backend/tests/test_taxonomy_semantic.py`, `backend/tests/test_search_gateway.py`, `backend/tests/test_admin_upgrade_contracts.py`, `backend/tests/test_admin_roles.py`, `backend/tests/test_research_domain_contract.py`, `backend/tests/test_research_administrative_areas.py`, `backend/tests/test_research_answer.py`, `backend/tests/test_research_operator_config.py`, `backend/tests/test_research_chronology.py`, `backend/tests/test_semantic_search.py`, `backend/tests/test_operator_diagnostics.py`, `backend/tests/test_taxonomy_flow.py`, `backend/tests/test_semantic_genres.py`, `backend/tests/test_research_plan_execution.py`, `backend/tests/test_vector_index.py`, `backend/tests/test_research_ordering_contract.py`, `backend/tests/test_research_planner.py`, `backend/tests/test_research_analytics.py`, `backend/tests/test_research_unified.py`, `backend/tests/test_research_geocoder.py`, `backend/tests/test_semantic_knowledge_index.py`, `backend/tests/test_research_v12_postgis.py`, `backend/tests/test_research_v9_adapter.py`, `backend/tests/test_semantic_relevance.py`, `backend/tests/test_research.py`, `backend/tests/test_research_semantic_eligibility.py`.
- Decision: Preserve deterministic Research behavior in the execution service.

### `backend/app/repositories/research_administrative.py`

- Classification: **MOVE** (later extraction).
- Responsibility: Assemble resolved identities from the administrative metadata boundary.
- Proposed target: `src/uranus_research_service/repositories/research_administrative.py`.
- Imports: `app.repositories.research_administrative_metadata`, `app.repositories.research_areas`, `app.research.geography`.
- Direct database references: None; see imported repositories for transitive access.
- Admin coupling: No direct auth/workflow dependency.
- External services: None directly; service clients can be transitive.
- Existing tests: `backend/tests/test_research_sql_provenance.py`, `backend/tests/test_research_internal_plan.py`, `backend/tests/test_research_administrative.py`, `backend/tests/test_research_administrative_areas_batch.py`, `backend/tests/test_administrative_integration_guards.py`, `backend/tests/test_administrative_geography.py`, `backend/tests/test_research_v12.py`, `backend/tests/test_research_grouping_flow.py`, `backend/tests/test_research_analytics.py`, `backend/tests/test_research_v9_adapter.py`.
- Decision: Preserve deterministic Research behavior in the execution service.

### `backend/app/repositories/research_administrative_metadata.py`

- Classification: **MOVE** (later extraction).
- Responsibility: TRANSITIONAL metadata adapter for the existing research_area schema.
- Proposed target: `src/uranus_research_service/repositories/research_administrative_metadata.py`.
- Imports: `app.repositories.research_areas`, `app.research.catalog`, `app.research.geography`.
- Direct database references: None; see imported repositories for transitive access.
- Admin coupling: No direct auth/workflow dependency.
- External services: None directly; service clients can be transitive.
- Existing tests: No direct module reference found; needs targeted extraction coverage.
- Decision: Preserve deterministic Research behavior in the execution service.

### `backend/app/repositories/research_areas.py`

- Classification: **MOVE** (later extraction).
- Responsibility: Persisted areas are resolved once; no provider access in a Research request.
- Proposed target: `src/uranus_research_service/repositories/research_areas.py`.
- Imports: `app.admin_database`, `app.errors`, `app.repositories.entities`, `app.repositories.entity_search`, `app.research.area_selection`, `app.schemas.research_areas`.
- Direct database references: `admin.research_area`.
- Admin coupling: app.admin_database.
- External services: None directly; service clients can be transitive.
- Existing tests: `backend/tests/test_research_administrative.py`, `backend/tests/test_research_areas.py`, `backend/tests/test_research_catalog.py`, `backend/tests/test_research_administrative_areas.py`, `backend/tests/test_research_chronology.py`, `backend/tests/test_semantic_search.py`, `backend/tests/test_semantic_genres.py`, `backend/tests/test_research_plan_execution.py`, `backend/tests/test_research_analytics.py`, `backend/tests/test_research_semantic_eligibility.py`.
- Decision: Split: read-only area queries move; Admin area imports and writes remain. Dedicated reader may SELECT only admin.research_area.

### `backend/app/repositories/research_execution.py`

- Classification: **MOVE** (later extraction).
- Responsibility: Exact, bounded SQL metrics using the shared eligible Research population.
- Proposed target: `src/uranus_research_service/repositories/research_execution.py`.
- Imports: `app.config`, `app.errors`, `app.repositories.research`, `app.repositories.research_areas`, `app.repositories.research_resolution`, `app.research.semantic_limits`, `app.research.sql_provenance`, `app.schemas.research`, `app.schemas.research_execution`, `app.schemas.research_sql`.
- Direct database references: `uranus.event_type_link`.
- Admin coupling: No direct auth/workflow dependency.
- External services: None directly; service clients can be transitive.
- Existing tests: `backend/tests/test_research_sql_provenance.py`, `backend/tests/test_research_calendar.py`, `backend/tests/test_research_internal_plan.py`, `backend/tests/test_research_v13.py`, `backend/tests/test_research_administrative.py`, `backend/tests/test_research_resolution.py`, `backend/tests/test_administrative_integration_guards.py`, `backend/tests/test_administrative_geography.py`, `backend/tests/test_research_taxonomy.py`, `backend/tests/test_research_v12.py`, `backend/tests/test_research_grouping.py`, `backend/tests/test_research_answer.py`, `backend/tests/test_research_chronology.py`, `backend/tests/test_taxonomy_flow.py`, `backend/tests/test_research_plan_execution.py`, `backend/tests/test_research_analytics.py`, `backend/tests/test_research_unified.py`, `backend/tests/test_research_v9_adapter.py`, `backend/tests/test_research_semantic_eligibility.py`.
- Decision: Preserve deterministic Research behavior in the execution service.

### `backend/app/repositories/research_grouping.py`

- Classification: **MOVE** (later extraction).
- Responsibility: Ordered cell aggregation on the shared authoritative occurrence selection.
- Proposed target: `src/uranus_research_service/repositories/research_grouping.py`.
- Imports: `app.config`, `app.repositories.administrative_execution`, `app.repositories.research`, `app.repositories.research_areas`, `app.repositories.research_execution`, `app.research.capabilities`, `app.research.plan`, `app.research.sql_provenance`, `app.schemas.research_execution`.
- Direct database references: None; see imported repositories for transitive access.
- Admin coupling: No direct auth/workflow dependency.
- External services: None directly; service clients can be transitive.
- Existing tests: `backend/tests/test_research_calendar.py`, `backend/tests/test_research_v13.py`, `backend/tests/test_research_v12.py`, `backend/tests/test_research_grouping_flow.py`, `backend/tests/test_research_conversation.py`, `backend/tests/test_research_grouping.py`, `backend/tests/test_research_v12_postgis.py`, `backend/tests/test_research_v9_adapter.py`.
- Decision: Preserve deterministic Research behavior in the execution service.

### `backend/app/repositories/research_metrics.py`

- Classification: **DEFER** (outside phase 1).
- Responsibility: Closed exact metrics over the shared public PostgreSQL Research population.
- Proposed target: `backend/app/repositories/research_metrics.py`.
- Imports: `app.config`, `app.errors`, `app.repositories.research`, `app.repositories.research_areas`, `app.research.semantic_documents`, `app.research.sql_provenance`, `app.schemas.research_domain`, `app.schemas.research_execution`, `app.schemas.research_unified`.
- Direct database references: None; see imported repositories for transitive access.
- Admin coupling: No direct auth/workflow dependency.
- External services: None directly; service clients can be transitive.
- Existing tests: `backend/tests/test_research_sql_provenance.py`, `backend/tests/test_research_unified.py`.
- Decision: Legacy v4 metrics path; retain while active v9–v13 extraction is staged.

### `backend/app/repositories/research_place.py`

- Classification: **MOVE** (later extraction).
- Responsibility: Place selection over effective venue data. All SQL identifiers are application-owned.
- Proposed target: `src/uranus_research_service/repositories/research_place.py`.
- Imports: `app.schemas.research_location`.
- Direct database references: None; see imported repositories for transitive access.
- Admin coupling: No direct auth/workflow dependency.
- External services: None directly; service clients can be transitive.
- Existing tests: `backend/tests/test_research_geography.py`.
- Decision: Preserve deterministic Research behavior in the execution service.

### `backend/app/repositories/research_resolution.py`

- Classification: **MOVE** (later extraction).
- Responsibility: Bounded exact-first resolution; optional vectors propose source-revalidated taxonomy.
- Proposed target: `src/uranus_research_service/repositories/research_resolution.py`.
- Imports: `app.admin_database`, `app.clients.research_geocoder`, `app.config`, `app.database`, `app.errors`, `app.repositories.entity_search`, `app.repositories.research`, `app.repositories.research_administrative`, `app.repositories.research_administrative_metadata`, `app.repositories.research_areas`, `app.repositories.research_place`, `app.repositories.research_taxonomy`, `app.research.administrative_catalog`, `app.research.administrative_resolver`, `app.research.capabilities`, `app.research.context`, `app.research.geography`, `app.research.plan`, `app.schemas.research_execution`, `app.schemas.research_location`, `app.services.taxonomy_resolution`.
- Direct database references: `admin.research_area`.
- Admin coupling: app.admin_database, Admin Request/app.state dependency to remove.
- External services: Research Geocoder HTTP.
- Existing tests: `backend/tests/test_research_sql_provenance.py`, `backend/tests/test_research_internal_plan.py`, `backend/tests/test_research_administrative.py`, `backend/tests/test_research_resolution.py`, `backend/tests/test_administrative_geography.py`, `backend/tests/test_research_taxonomy.py`, `backend/tests/test_research_v12.py`, `backend/tests/test_research_grouping_flow.py`, `backend/tests/test_research_grouping.py`, `backend/tests/test_taxonomy_semantic.py`, `backend/tests/test_research_administrative_areas.py`, `backend/tests/test_research_chronology.py`, `backend/tests/test_taxonomy_flow.py`, `backend/tests/test_research_plan_execution.py`, `backend/tests/test_research_analytics.py`, `backend/tests/test_research_v12_postgis.py`, `backend/tests/test_research_v9_adapter.py`, `backend/tests/test_research_semantic_eligibility.py`.
- Decision: Preserve deterministic Research behavior in the execution service.

### `backend/app/repositories/research_suggestions.py`

- Classification: **KEEP_IN_ADMIN** (retained in Admin).
- Responsibility: Admin-only learning transactions and one indexed suggestion retrieval.
- Proposed target: `backend/app/repositories/research_suggestions.py`.
- Imports: `app.admin_tables`, `app.errors`, `app.research.plan`, `app.schemas.research_analytics`, `app.schemas.research_planner`, `app.schemas.research_suggestions`, `app.services`.
- Direct database references: SQLAlchemy tables `admin.research_query_history`, `admin.research_query_suggestion`, `admin.research_query_suggestion_event` (Admin-only reads/writes).
- Admin coupling: app.admin_tables.
- External services: None directly; service clients can be transitive.
- Existing tests: `backend/tests/test_research_suggestions.py`.
- Decision: Admin-owned persistence/import/learning; service receives only read-only geographic projection.

### `backend/app/repositories/research_taxonomy.py`

- Classification: **MOVE** (later extraction).
- Responsibility: Shared authoritative public taxonomy projections, including localized labels.
- Proposed target: `src/uranus_research_service/repositories/research_taxonomy.py`.
- Imports: `app.repositories.research`, `app.repositories.vector_events`, `app.research.taxonomy`.
- Direct database references: `uranus.event`, `uranus.event_type`, `uranus.event_type_link`, `uranus.genre_type`.
- Admin coupling: No direct auth/workflow dependency.
- External services: None directly; service clients can be transitive.
- Existing tests: `backend/tests/test_taxonomy_index.py`, `backend/tests/test_research_grouping.py`, `backend/tests/test_taxonomy_semantic.py`, `backend/tests/test_research_analytics.py`.
- Decision: Preserve deterministic Research behavior in the execution service.

### `backend/app/repositories/vector_entities.py`

- Classification: **MOVE** (later extraction).
- Responsibility: Bounded, read-only venue/organization projections with canonical public event gates.
- Proposed target: `src/uranus_research_service/repositories/vector_entities.py`.
- Imports: `app.config`, `app.repositories.location`, `app.repositories.research`, `app.repositories.vector_events`, `app.research.semantic_contracts`, `app.research.semantic_documents`.
- Direct database references: `uranus.event`, `uranus.event_date`, `uranus.organization`, `uranus.venue`.
- Admin coupling: No direct auth/workflow dependency.
- External services: None directly; service clients can be transitive.
- Existing tests: `backend/tests/test_semantic_knowledge_index.py`.
- Decision: Preserve deterministic Research behavior in the execution service.

### `backend/app/repositories/vector_events.py`

- Classification: **MOVE** (later extraction).
- Responsibility: Bounded public event snapshot. No model calls or source mutations in this module.
- Proposed target: `src/uranus_research_service/repositories/vector_events.py`.
- Imports: `app.config`, `app.repositories.activity_previews`, `app.repositories.location`, `app.repositories.research`, `app.repositories.temporal`, `app.research.semantic_contracts`, `app.research.semantic_documents`, `app.research.vector_documents`.
- Direct database references: `admin.research_area`, `uranus.event`, `uranus.event_date`, `uranus.event_type`, `uranus.event_type_link`, `uranus.organization`, `uranus.space`, `uranus.venue`.
- Admin coupling: No direct auth/workflow dependency.
- External services: None directly; service clients can be transitive.
- Existing tests: `backend/tests/test_semantic_genres.py`, `backend/tests/test_vector_index.py`, `backend/tests/test_semantic_knowledge_index.py`.
- Decision: Preserve deterministic Research behavior in the execution service.

### `backend/app/research/__init__.py`

- Classification: **MOVE** (later extraction).
- Responsibility: Operator tools for persisted Research metadata.
- Proposed target: `src/uranus_research_service/research/__init__.py`.
- Imports: None.
- Direct database references: None; see imported repositories for transitive access.
- Admin coupling: No direct auth/workflow dependency.
- External services: None directly; service clients can be transitive.
- Existing tests: `backend/tests/test_research_sql_provenance.py`, `backend/tests/test_sql_console.py`, `backend/tests/test_timeline.py`, `backend/tests/test_notifications.py`, `backend/tests/test_notification_smtp_security.py`, `backend/tests/test_semantic_knowledge_index.py`.
- Decision: Preserve deterministic Research behavior in the execution service.

### `backend/app/research/administrative_areas.py`

- Classification: **KEEP_IN_ADMIN** (retained in Admin).
- Responsibility: Explicit, atomic operator import of reviewed district/state/region boundaries.
- Proposed target: `backend/app/research/administrative_areas.py`.
- Imports: `app.auth.diagnostics`, `app.clients.research_geocoder`, `app.config`, `app.research.administrative_catalog`, `app.research.administrative_import`, `app.research.administrative_resolver`, `app.research.areas`, `app.services.nominatim`, `app.storage_preflight`.
- Direct database references: `admin.research_area`.
- Admin coupling: app.auth.diagnostics.
- External services: Research Geocoder HTTP.
- Existing tests: `backend/tests/test_research_administrative_areas_batch.py`, `backend/tests/test_research_administrative_areas.py`.
- Decision: Admin-owned persistence/import/learning; service receives only read-only geographic projection.

### `backend/app/research/administrative_areas_batch.py`

- Classification: **KEEP_IN_ADMIN** (retained in Admin).
- Responsibility: Sequential operator import of checked-in DE states/districts and DK regions.
- Proposed target: `backend/app/research/administrative_areas_batch.py`.
- Imports: `app.config`, `app.research.administrative_areas`.
- Direct database references: None; see imported repositories for transitive access.
- Admin coupling: No direct auth/workflow dependency.
- External services: None directly; service clients can be transitive.
- Existing tests: `backend/tests/test_research_administrative_areas_batch.py`.
- Decision: Admin-owned persistence/import/learning; service receives only read-only geographic projection.

### `backend/app/research/administrative_catalog.py`

- Classification: **MOVE** (later extraction).
- Responsibility: Operator-built complete inventories; Nominatim search is never an enumeration API.
- Proposed target: `src/uranus_research_service/research/administrative_catalog.py`.
- Imports: `app.errors`, `app.research.administrative_resolver`, `app.research.geography`, `app.schemas.research_administrative`, `app.schemas.research_values`.
- Direct database references: None; see imported repositories for transitive access.
- Admin coupling: No direct auth/workflow dependency.
- External services: Nominatim (Admin operator import).
- Existing tests: `backend/tests/test_administrative_integration_guards.py`, `backend/tests/test_administrative_geography.py`.
- Decision: Preserve deterministic Research behavior in the execution service.

### `backend/app/research/administrative_import.py`

- Classification: **KEEP_IN_ADMIN** (retained in Admin).
- Responsibility: Build a reviewed inventory through the private Geocoder; never infer completeness.
- Proposed target: `backend/app/research/administrative_import.py`.
- Imports: `app.clients.research_geocoder`, `app.config`, `app.research.administrative_catalog`, `app.research.administrative_resolver`, `app.research.geography`, `app.schemas.research_values`.
- Direct database references: None; see imported repositories for transitive access.
- Admin coupling: No direct auth/workflow dependency.
- External services: Research Geocoder HTTP.
- Existing tests: No direct module reference found; needs targeted extraction coverage.
- Decision: Admin-owned persistence/import/learning; service receives only read-only geographic projection.

### `backend/app/research/administrative_resolver.py`

- Classification: **MOVE** (later extraction).
- Responsibility: Geocoder is authoritative; ambiguity and role mismatches are never auto-corrected.
- Proposed target: `src/uranus_research_service/research/administrative_resolver.py`.
- Imports: `app.clients.research_geocoder`, `app.errors`, `app.research.geography`, `app.schemas.research_administrative`.
- Direct database references: None; see imported repositories for transitive access.
- Admin coupling: No direct auth/workflow dependency.
- External services: Research Geocoder HTTP.
- Existing tests: `backend/tests/test_administrative_integration_guards.py`, `backend/tests/test_administrative_geography.py`.
- Decision: Preserve deterministic Research behavior in the execution service.

### `backend/app/research/answer.py`

- Classification: **MOVE** (later extraction).
- Responsibility: Pure German answer text from the executed selection, never model prose or SQL.
- Proposed target: `src/uranus_research_service/research/answer.py`.
- Imports: `app.research.plan`, `app.schemas.research_execution`.
- Direct database references: None; see imported repositories for transitive access.
- Admin coupling: No direct auth/workflow dependency.
- External services: None directly; service clients can be transitive.
- Existing tests: `backend/tests/test_research_v13.py`, `backend/tests/test_research_answer.py`.
- Decision: Preserve deterministic Research behavior in the execution service.

### `backend/app/research/answer_facts.py`

- Classification: **MOVE** (later extraction).
- Responsibility: Bounded, identity-free factual projection for deterministic conversational rendering.
- Proposed target: `src/uranus_research_service/research/answer_facts.py`.
- Imports: `app.research.plan`, `app.research.wire.research_v13_schema`, `app.schemas.research_execution`, `app.schemas.research_values`.
- Direct database references: None; see imported repositories for transitive access.
- Admin coupling: No direct auth/workflow dependency.
- External services: None directly; service clients can be transitive.
- Existing tests: `backend/tests/test_research_v13.py`.
- Decision: Preserve deterministic Research behavior in the execution service.

### `backend/app/research/area_selection.py`

- Classification: **MOVE** (later extraction).
- Responsibility: Shared bounded selection for semantic area filters.
- Proposed target: `src/uranus_research_service/research/area_selection.py`.
- Imports: None.
- Direct database references: None; see imported repositories for transitive access.
- Admin coupling: No direct auth/workflow dependency.
- External services: None directly; service clients can be transitive.
- Existing tests: `backend/tests/test_semantic_knowledge_index.py`.
- Decision: Preserve deterministic Research behavior in the execution service.

### `backend/app/research/areas.py`

- Classification: **KEEP_IN_ADMIN** (retained in Admin).
- Responsibility: Explicit operator import of OSM municipalities through the configured Nominatim.
- Proposed target: `backend/app/research/areas.py`.
- Imports: `app.auth.diagnostics`, `app.config`, `app.errors`, `app.logging`, `app.research.catalog`, `app.research.danish_catalog`, `app.schemas.geo`, `app.services.nominatim`, `app.storage_preflight`.
- Direct database references: `admin.research_area`.
- Admin coupling: app.auth.diagnostics.
- External services: Nominatim (Admin operator import).
- Existing tests: `backend/tests/test_research_area_migration.py`, `backend/tests/test_research_administrative_areas_batch.py`, `backend/tests/test_research_areas.py`, `backend/tests/test_research_catalog.py`, `backend/tests/test_research_administrative_areas.py`.
- Decision: Admin-owned persistence/import/learning; service receives only read-only geographic projection.

### `backend/app/research/capabilities.py`

- Classification: **MOVE** (later extraction).
- Responsibility: One version-independent capability gate. No natural-language interpretation.
- Proposed target: `src/uranus_research_service/research/capabilities.py`.
- Imports: `app.errors`, `app.research.geography`, `app.research.plan`.
- Direct database references: None; see imported repositories for transitive access.
- Admin coupling: No direct auth/workflow dependency.
- External services: None directly; service clients can be transitive.
- Existing tests: `backend/tests/test_research_internal_plan.py`, `backend/tests/test_research_administrative.py`, `backend/tests/test_administrative_integration_guards.py`, `backend/tests/test_research_grouping.py`, `backend/tests/test_research_v9_adapter.py`.
- Decision: Preserve deterministic Research behavior in the execution service.

### `backend/app/research/catalog.py`

- Classification: **MOVE** (later extraction).
- Responsibility: Offline BKG VG250 municipality names/AGS to bounded Nominatim discovery input.
- Proposed target: `src/uranus_research_service/research/catalog.py`.
- Imports: None.
- Direct database references: None; see imported repositories for transitive access.
- Admin coupling: No direct auth/workflow dependency.
- External services: Nominatim (Admin operator import).
- Existing tests: `backend/tests/test_sql_console.py`, `backend/tests/test_sql_console_integration.py`, `backend/tests/test_source_schema_verify.py`, `backend/tests/test_research_administrative_areas_batch.py`, `backend/tests/test_administrative_integration_guards.py`, `backend/tests/test_administrative_geography.py`, `backend/tests/test_research_areas.py`, `backend/tests/test_research_scope.py`, `backend/tests/test_research_catalog.py`, `backend/tests/test_research_domain_contract.py`, `backend/tests/test_entities.py`, `backend/tests/test_notifications.py`, `backend/tests/test_research_unified.py`.
- Decision: Preserve deterministic Research behavior in the execution service.

### `backend/app/research/chunk_kinds.py`

- Classification: **MOVE** (later extraction).
- Responsibility: Canonical public chunk kinds shared by index and response contracts.
- Proposed target: `src/uranus_research_service/research/chunk_kinds.py`.
- Imports: None.
- Direct database references: None; see imported repositories for transitive access.
- Admin coupling: No direct auth/workflow dependency.
- External services: None directly; service clients can be transitive.
- Existing tests: `backend/tests/test_review_benchmark.py`.
- Decision: Preserve deterministic Research behavior in the execution service.

### `backend/app/research/context.py`

- Classification: **MOVE** (later extraction).
- Responsibility: Transient request/runtime inputs; never persisted or sent to the Planner.
- Proposed target: `src/uranus_research_service/research/context.py`.
- Imports: `app.schemas.research_location`.
- Direct database references: None; see imported repositories for transitive access.
- Admin coupling: No direct auth/workflow dependency.
- External services: None directly; service clients can be transitive.
- Existing tests: `backend/tests/test_health.py`, `backend/tests/test_research_sql_provenance.py`, `backend/tests/test_research_internal_plan.py`, `backend/tests/test_admin_auth.py`, `backend/tests/test_geo_analytics.py`, `backend/tests/test_activity.py`, `backend/tests/test_research_v13.py`, `backend/tests/test_finding_previews.py`, `backend/tests/test_research_administrative.py`, `backend/tests/test_temporal_entities.py`, `backend/tests/test_source_schema_verify.py`, `backend/tests/test_marks.py`, `backend/tests/test_research_geography.py`, `backend/tests/test_administrative_integration_guards.py`, `backend/tests/test_core_rules.py`, `backend/tests/test_live_sql_diagnostics.py`, `backend/tests/test_research_suggestions.py`, `backend/tests/test_quality_v2.py`, `backend/tests/test_entity_periods.py`, `backend/tests/test_logo_rules.py`, `backend/tests/test_research_taxonomy.py`, `backend/tests/test_research_v12.py`, `backend/tests/test_research_grouping_flow.py`, `backend/tests/test_research_conversation.py`, `backend/tests/test_venue_scope.py`, `backend/tests/test_entities.py`, `backend/tests/test_research_answer.py`, `backend/tests/test_entity_search.py`, `backend/tests/test_queues.py`, `backend/tests/test_url_reachability.py`, `backend/tests/test_research_chronology.py`, `backend/tests/test_semantic_search.py`, `backend/tests/test_semantic_genres.py`, `backend/tests/test_notifications.py`, `backend/tests/test_research_plan_execution.py`, `backend/tests/test_sql_diagnostics.py`, `backend/tests/test_vector_index.py`, `backend/tests/test_notification_smtp_security.py`, `backend/tests/test_research_planner.py`, `backend/tests/test_research_analytics.py`, `backend/tests/test_research_unified.py`, `backend/tests/test_research_geocoder.py`, `backend/tests/test_semantic_knowledge_index.py`, `backend/tests/test_event_content.py`, `backend/tests/test_research_v12_postgis.py`, `backend/tests/test_postal_code_rules.py`, `backend/tests/test_research_v9_adapter.py`, `backend/tests/test_semantic_relevance.py`, `backend/tests/test_research_semantic_eligibility.py`.
- Decision: Preserve deterministic Research behavior in the execution service.

### `backend/app/research/conversation.py`

- Classification: **MOVE** (later extraction).
- Responsibility: Deliberate allowlist projection of executed intent, not response serialization.
- Proposed target: `src/uranus_research_service/research/conversation.py`.
- Imports: `app.research.geography`, `app.research.plan`, `app.schemas.research_conversation`, `app.schemas.research_conversation_v12`.
- Direct database references: None; see imported repositories for transitive access.
- Admin coupling: No direct auth/workflow dependency.
- External services: None directly; service clients can be transitive.
- Existing tests: `backend/tests/test_research_v13.py`, `backend/tests/test_research_v12.py`, `backend/tests/test_research_conversation.py`, `backend/tests/test_research_v12_postgis.py`.
- Decision: Preserve deterministic Research behavior in the execution service.

### `backend/app/research/conversation_state.py`

- Classification: **MOVE** (later extraction).
- Responsibility: Bounded process-local, session-bound state. Tokens are random, not encoded semantics.
- Proposed target: `src/uranus_research_service/research/conversation_state.py`.
- Imports: `app.errors`, `app.research.answer_facts`, `app.research.wire.research_v13_schema`, `app.schemas.research_conversation_v12`.
- Direct database references: None; see imported repositories for transitive access.
- Admin coupling: No direct auth/workflow dependency.
- External services: None directly; service clients can be transitive.
- Existing tests: `backend/tests/test_research_v13.py`.
- Decision: Preserve deterministic Research behavior in the execution service.

### `backend/app/research/danish_catalog.py`

- Classification: **KEEP_IN_ADMIN** (retained in Admin).
- Responsibility: Explicit municipality identities; no discovery or public geocoder fallback.
- Proposed target: `backend/app/research/danish_catalog.py`.
- Imports: None.
- Direct database references: None; see imported repositories for transitive access.
- Admin coupling: No direct auth/workflow dependency.
- External services: Nominatim (Admin operator import).
- Existing tests: `backend/tests/test_research_areas.py`.
- Decision: Admin-owned persistence/import/learning; service receives only read-only geographic projection.

### `backend/app/research/evidence_context.py`

- Classification: **MOVE** (later extraction).
- Responsibility: Explicit public source identities; never infer scope from names or prose.
- Proposed target: `src/uranus_research_service/research/evidence_context.py`.
- Imports: None.
- Direct database references: None; see imported repositories for transitive access.
- Admin coupling: No direct auth/workflow dependency.
- External services: None directly; service clients can be transitive.
- Existing tests: `backend/tests/test_semantic_search.py`, `backend/tests/test_vector_index.py`, `backend/tests/test_semantic_knowledge_index.py`.
- Decision: Preserve deterministic Research behavior in the execution service.

### `backend/app/research/geography.py`

- Classification: **MOVE** (later extraction).
- Responsibility: Internal geography: identity and administrative level are separate from names.
- Proposed target: `src/uranus_research_service/research/geography.py`.
- Imports: None.
- Direct database references: None; see imported repositories for transitive access.
- Admin coupling: No direct auth/workflow dependency.
- External services: None directly; service clients can be transitive.
- Existing tests: `backend/tests/test_research_internal_plan.py`, `backend/tests/test_research_administrative.py`, `backend/tests/test_research_geography.py`, `backend/tests/test_administrative_integration_guards.py`, `backend/tests/test_administrative_geography.py`, `backend/tests/test_research_v12.py`, `backend/tests/test_research_conversation.py`, `backend/tests/test_research_grouping.py`, `backend/tests/test_research_analytics.py`, `backend/tests/test_semantic_knowledge_index.py`, `backend/tests/test_research_v12_postgis.py`, `backend/tests/test_research_v9_adapter.py`.
- Decision: Preserve deterministic Research behavior in the execution service.

### `backend/app/research/normalize.py`

- Classification: **MOVE** (later extraction).
- Responsibility: Validated wire -> domain adapters. No lookup, inference or contract repair.
- Proposed target: `src/uranus_research_service/research/normalize.py`.
- Imports: `app.errors`, `app.research.geography`, `app.research.normalize_v10`, `app.research.normalize_v12`, `app.research.normalize_v9`, `app.research.plan`, `app.research.wire.research_v10_schema`, `app.research.wire.research_v11_schema`, `app.research.wire.research_v12_schema`, `app.research.wire.research_v8_schema`, `app.research.wire.research_v8_types`, `app.research.wire.research_v9_schema`, `app.schemas.research_analytics`, `app.schemas.research_analytics_guard`, `app.schemas.research_geography`, `app.schemas.research_planner`.
- Direct database references: None; see imported repositories for transitive access.
- Admin coupling: No direct auth/workflow dependency.
- External services: None directly; service clients can be transitive.
- Existing tests: `backend/tests/test_research_sql_provenance.py`, `backend/tests/test_research_calendar.py`, `backend/tests/test_research_internal_plan.py`, `backend/tests/test_research_administrative.py`, `backend/tests/test_research_resolution.py`, `backend/tests/test_administrative_integration_guards.py`, `backend/tests/test_administrative_geography.py`, `backend/tests/test_research_suggestions.py`, `backend/tests/test_research_v12.py`, `backend/tests/test_research_conversation.py`, `backend/tests/test_research_grouping.py`, `backend/tests/test_notifications.py`, `backend/tests/test_vector_index.py`, `backend/tests/test_geo.py`, `backend/tests/test_research_v12_postgis.py`, `backend/tests/test_research_v9_adapter.py`.
- Decision: Preserve deterministic Research behavior in the execution service.

### `backend/app/research/normalize_grouping.py`

- Classification: **MOVE** (later extraction).
- Responsibility: Compatibility adapter for the frozen scalar v7 representation.
- Proposed target: `src/uranus_research_service/research/normalize_grouping.py`.
- Imports: `app.research.normalize_v9`, `app.research.plan`, `app.research.wire.research_v7_schema`, `app.research.wire.research_v9_schema`.
- Direct database references: None; see imported repositories for transitive access.
- Admin coupling: No direct auth/workflow dependency.
- External services: None directly; service clients can be transitive.
- Existing tests: `backend/tests/test_research_grouping.py`.
- Decision: Preserve deterministic Research behavior in the execution service.

### `backend/app/research/normalize_v10.py`

- Classification: **MOVE** (later extraction).
- Responsibility: Additive wire calendar fields become shared domain predicates; no execution.
- Proposed target: `src/uranus_research_service/research/normalize_v10.py`.
- Imports: `app.research.capabilities`, `app.research.normalize_v9`, `app.research.plan`, `app.research.wire.research_v10_schema`, `app.research.wire.research_v9_schema`.
- Direct database references: None; see imported repositories for transitive access.
- Admin coupling: No direct auth/workflow dependency.
- External services: None directly; service clients can be transitive.
- Existing tests: `backend/tests/test_research_calendar.py`, `backend/tests/test_research_conversation.py`.
- Decision: Preserve deterministic Research behavior in the execution service.

### `backend/app/research/normalize_v12.py`

- Classification: **MOVE** (later extraction).
- Responsibility: Lossless v12 spatial adapter to the shared research plan; no resolver or executor.
- Proposed target: `src/uranus_research_service/research/normalize_v12.py`.
- Imports: `app.research.capabilities`, `app.research.geography`, `app.research.normalize`, `app.research.normalize_v10`, `app.research.normalize_v9`, `app.research.plan`, `app.research.wire.research_v10_schema`, `app.research.wire.research_v12_schema`, `app.research.wire.research_v9_constraints`.
- Direct database references: None; see imported repositories for transitive access.
- Admin coupling: No direct auth/workflow dependency.
- External services: None directly; service clients can be transitive.
- Existing tests: `backend/tests/test_research_v12.py`.
- Decision: Preserve deterministic Research behavior in the execution service.

### `backend/app/research/normalize_v9.py`

- Classification: **MOVE** (later extraction).
- Responsibility: Lossless v9 wire adapter to existing Admin capabilities; no lookup or execution.
- Proposed target: `src/uranus_research_service/research/normalize_v9.py`.
- Imports: `app.research.capabilities`, `app.research.geography`, `app.research.normalize`, `app.research.plan`, `app.research.wire.research_v9_constraints`, `app.research.wire.research_v9_schema`, `app.research.wire.research_v9_types`, `app.schemas.research_execution`.
- Direct database references: None; see imported repositories for transitive access.
- Admin coupling: No direct auth/workflow dependency.
- External services: None directly; service clients can be transitive.
- Existing tests: `backend/tests/test_research_calendar.py`, `backend/tests/test_research_grouping.py`, `backend/tests/test_research_v9_adapter.py`.
- Decision: Preserve deterministic Research behavior in the execution service.

### `backend/app/research/outcome.py`

- Classification: **MOVE** (later extraction).
- Responsibility: Execution output without the transport envelope; assembled into HTTP at the API edge.
- Proposed target: `src/uranus_research_service/research/outcome.py`.
- Imports: `app.schemas.research_administrative_result`, `app.schemas.research_execution`, `app.schemas.research_sql`.
- Direct database references: None; see imported repositories for transitive access.
- Admin coupling: No direct auth/workflow dependency.
- External services: None directly; service clients can be transitive.
- Existing tests: `backend/tests/test_research_sql_provenance.py`, `backend/tests/test_research_internal_plan.py`, `backend/tests/test_research_v13.py`, `backend/tests/test_administrative_integration_guards.py`, `backend/tests/test_notifications.py`, `backend/tests/test_research_plan_execution.py`.
- Decision: Preserve deterministic Research behavior in the execution service.

### `backend/app/research/plan.py`

- Classification: **MOVE** (later extraction).
- Responsibility: Admin-owned execution intent. Not an HTTP model or a Planner schema mirror.
- Proposed target: `src/uranus_research_service/research/plan.py`.
- Imports: `app.research.geography`, `app.schemas.research_execution`.
- Direct database references: None; see imported repositories for transitive access.
- Admin coupling: No direct auth/workflow dependency.
- External services: None directly; service clients can be transitive.
- Existing tests: `backend/tests/test_research_sql_provenance.py`, `backend/tests/test_research_calendar.py`, `backend/tests/test_research_internal_plan.py`, `backend/tests/test_research_v13.py`, `backend/tests/test_research_administrative.py`, `backend/tests/test_administrative_integration_guards.py`, `backend/tests/test_administrative_geography.py`, `backend/tests/test_research_grouping_flow.py`, `backend/tests/test_research_conversation.py`, `backend/tests/test_research_grouping.py`, `backend/tests/test_research_answer.py`.
- Decision: Preserve deterministic Research behavior in the execution service.

### `backend/app/research/population.py`

- Classification: **KEEP_IN_ADMIN** (retained in Admin).
- Responsibility: Offline, AGS-exact BKG population import; never changes boundary geometry.
- Proposed target: `backend/app/research/population.py`.
- Imports: `app.auth.diagnostics`, `app.config`, `app.logging`, `app.research.areas`, `app.research.catalog`, `app.storage_preflight`.
- Direct database references: `admin.research_area`.
- Admin coupling: app.auth.diagnostics.
- External services: None directly; service clients can be transitive.
- Existing tests: `backend/tests/test_research_calendar.py`, `backend/tests/test_research_population.py`, `backend/tests/test_research_administrative.py`, `backend/tests/test_research_areas.py`, `backend/tests/test_research_grouping_flow.py`, `backend/tests/test_research_grouping.py`, `backend/tests/test_research_administrative_areas.py`, `backend/tests/test_research_operator_config.py`, `backend/tests/test_taxonomy_flow.py`, `backend/tests/test_research_plan_execution.py`, `backend/tests/test_research_analytics.py`, `backend/tests/test_research_unified.py`, `backend/tests/test_research_v9_adapter.py`, `backend/tests/test_research_semantic_eligibility.py`.
- Decision: Admin-owned persistence/import/learning; service receives only read-only geographic projection.

### `backend/app/research/public_result.py`

- Classification: **MOVE** (later extraction).
- Responsibility: Mask internal taxonomy choices only at the public response boundary.
- Proposed target: `src/uranus_research_service/research/public_result.py`.
- Imports: `app.schemas.research_execution`.
- Direct database references: None; see imported repositories for transitive access.
- Admin coupling: No direct auth/workflow dependency.
- External services: None directly; service clients can be transitive.
- Existing tests: No direct module reference found; needs targeted extraction coverage.
- Decision: Preserve deterministic Research behavior in the execution service.

### `backend/app/research/scope.py`

- Classification: **KEEP_IN_ADMIN** (retained in Admin).
- Responsibility: Run the municipality importer over the complete German/Danish input inventory.
- Proposed target: `backend/app/research/scope.py`.
- Imports: `app.config`, `app.logging`, `app.research.areas`, `app.research.catalog`, `app.research.danish_catalog`.
- Direct database references: None; see imported repositories for transitive access.
- Admin coupling: No direct auth/workflow dependency.
- External services: None directly; service clients can be transitive.
- Existing tests: No direct module reference found; needs targeted extraction coverage.
- Decision: Admin-owned persistence/import/learning; service receives only read-only geographic projection.

### `backend/app/research/search_gateway.py`

- Classification: **DEFER** (outside phase 1).
- Responsibility: Bounded candidate-only access to the operator-confirmed Jina-v3 event gateway.
- Proposed target: `backend/app/research/search_gateway.py`.
- Imports: `app.errors`.
- Direct database references: None; see imported repositories for transitive access.
- Admin coupling: No direct auth/workflow dependency.
- External services: None directly; service clients can be transitive.
- Existing tests: `backend/tests/test_search_gateway.py`.
- Decision: Historical pilot/project-knowledge path, separate from current v9–v13 execution; keep explicit legacy route during phased rollout.

### `backend/app/research/semantic_contracts.py`

- Classification: **MOVE** (later extraction).
- Responsibility: Internal, closed contracts for the next semantic index; no public API changes.
- Proposed target: `src/uranus_research_service/research/semantic_contracts.py`.
- Imports: `app.research.evidence_context`, `app.research.vector_documents`, `app.schemas.genre`.
- Direct database references: None; see imported repositories for transitive access.
- Admin coupling: No direct auth/workflow dependency.
- External services: None directly; service clients can be transitive.
- Existing tests: `backend/tests/test_vector_metadata.py`, `backend/tests/test_semantic_genres.py`, `backend/tests/test_vector_index.py`, `backend/tests/test_semantic_knowledge_index.py`.
- Decision: Preserve deterministic Research behavior in the execution service.

### `backend/app/research/semantic_documents.py`

- Classification: **MOVE** (later extraction).
- Responsibility: Explicit public field builders, reusing the event section and normalization pipeline.
- Proposed target: `src/uranus_research_service/research/semantic_documents.py`.
- Imports: `app.repositories.activity_previews`, `app.repositories.research`, `app.research.evidence_context`, `app.research.semantic_contracts`, `app.research.vector_documents`.
- Direct database references: None; see imported repositories for transitive access.
- Admin coupling: No direct auth/workflow dependency.
- External services: None directly; service clients can be transitive.
- Existing tests: `backend/tests/test_semantic_knowledge_index.py`.
- Decision: Preserve deterministic Research behavior in the execution service.

### `backend/app/research/semantic_evidence.py`

- Classification: **MOVE** (later extraction).
- Responsibility: Allowlisted evidence, deterministic entity ranking and explicit hard area filters.
- Proposed target: `src/uranus_research_service/research/semantic_evidence.py`.
- Imports: `app.research.area_selection`, `app.research.evidence_context`, `app.research.semantic_contracts`, `app.research.semantic_documents`, `app.research.vector_documents`, `app.research.vector_models`, `app.schemas.genre`.
- Direct database references: None; see imported repositories for transitive access.
- Admin coupling: No direct auth/workflow dependency.
- External services: None directly; service clients can be transitive.
- Existing tests: `backend/tests/test_semantic_search.py`, `backend/tests/test_semantic_genres.py`, `backend/tests/test_semantic_knowledge_index.py`.
- Decision: Preserve deterministic Research behavior in the execution service.

### `backend/app/research/semantic_explanations.py`

- Classification: **MOVE** (later extraction).
- Responsibility: Deterministic presentation of validated evidence; never query-generated prose.
- Proposed target: `src/uranus_research_service/research/semantic_explanations.py`.
- Imports: `app.research.chunk_kinds`, `app.research.semantic_contracts`, `app.schemas.research`.
- Direct database references: None; see imported repositories for transitive access.
- Admin coupling: No direct auth/workflow dependency.
- External services: None directly; service clients can be transitive.
- Existing tests: No direct module reference found; needs targeted extraction coverage.
- Decision: Preserve deterministic Research behavior in the execution service.

### `backend/app/research/semantic_limits.py`

- Classification: **MOVE** (later extraction).
- Responsibility: Internal semantic execution bounds and relevance policy; no public request controls.
- Proposed target: `src/uranus_research_service/research/semantic_limits.py`.
- Imports: None.
- Direct database references: None; see imported repositories for transitive access.
- Admin coupling: No direct auth/workflow dependency.
- External services: None directly; service clients can be transitive.
- Existing tests: `backend/tests/test_semantic_relevance.py`, `backend/tests/test_research_semantic_eligibility.py`.
- Decision: Preserve deterministic Research behavior in the execution service.

### `backend/app/research/sql_provenance.py`

- Classification: **MOVE** (later extraction).
- Responsibility: Opt-in source execution capture, never a SQLAlchemy listener or query logger.
- Proposed target: `src/uranus_research_service/research/sql_provenance.py`.
- Imports: `app.schemas.research_sql`.
- Direct database references: None; see imported repositories for transitive access.
- Admin coupling: No direct auth/workflow dependency.
- External services: None directly; service clients can be transitive.
- Existing tests: `backend/tests/test_research_sql_provenance.py`, `backend/tests/test_research_calendar.py`, `backend/tests/test_research_v12.py`, `backend/tests/test_research_grouping_flow.py`, `backend/tests/test_research_conversation.py`, `backend/tests/test_research_grouping.py`, `backend/tests/test_taxonomy_flow.py`, `backend/tests/test_sql_provenance.py`, `backend/tests/test_research_v12_postgis.py`, `backend/tests/test_research_v9_adapter.py`.
- Decision: Preserve deterministic Research behavior in the execution service.

### `backend/app/research/taxonomy.py`

- Classification: **MOVE** (later extraction).
- Responsibility: Closed, bounded taxonomy index documents. No query aliases or source identities invented.
- Proposed target: `src/uranus_research_service/research/taxonomy.py`.
- Imports: `app.research.vector_models`.
- Direct database references: None; see imported repositories for transitive access.
- Admin coupling: No direct auth/workflow dependency.
- External services: None directly; service clients can be transitive.
- Existing tests: `backend/tests/test_research_sql_provenance.py`, `backend/tests/test_research_calendar.py`, `backend/tests/test_research_internal_plan.py`, `backend/tests/test_research_administrative.py`, `backend/tests/test_research_resolution.py`, `backend/tests/test_research_taxonomy.py`, `backend/tests/test_taxonomy_index.py`, `backend/tests/test_research_grouping.py`, `backend/tests/test_taxonomy_semantic.py`, `backend/tests/test_research_answer.py`, `backend/tests/test_taxonomy_flow.py`, `backend/tests/test_research_plan_execution.py`, `backend/tests/test_research_analytics.py`, `backend/tests/test_research_v9_adapter.py`.
- Decision: Preserve deterministic Research behavior in the execution service.

### `backend/app/research/taxonomy_benchmark.py`

- Classification: **MOVE** (later extraction).
- Responsibility: Measured exact-first, kind-aware calibration; synthetic scores are not live evidence.
- Proposed target: `src/uranus_research_service/research/taxonomy_benchmark.py`.
- Imports: `app.repositories.research_resolution`, `app.research.taxonomy`, `app.research.taxonomy_policy`, `app.research.taxonomy_transport`, `app.research.vector_transport`.
- Direct database references: None; see imported repositories for transitive access.
- Admin coupling: No direct auth/workflow dependency.
- External services: Encoder HTTP, Qdrant HTTP.
- Existing tests: `backend/tests/test_taxonomy_index.py`.
- Decision: Preserve deterministic Research behavior in the execution service.

### `backend/app/research/taxonomy_index.py`

- Classification: **MOVE** (later extraction).
- Responsibility: Operator-only taxonomy snapshot indexing; separate lifecycle from event documents.
- Proposed target: `src/uranus_research_service/research/taxonomy_index.py`.
- Imports: `app.config`, `app.database`, `app.logging`, `app.repositories.research_taxonomy`, `app.research.taxonomy`, `app.research.taxonomy_benchmark`, `app.research.taxonomy_transport`, `app.research.vector_index`, `app.research.vector_transport`.
- Direct database references: None; see imported repositories for transitive access.
- Admin coupling: No direct auth/workflow dependency.
- External services: Encoder HTTP, Qdrant HTTP.
- Existing tests: `backend/tests/test_taxonomy_index.py`.
- Decision: Preserve deterministic Research behavior in the execution service.

### `backend/app/research/taxonomy_policy.py`

- Classification: **MOVE** (later extraction).
- Responsibility: Thresholds are an operator-reviewed benchmark artifact, never guessed defaults.
- Proposed target: `src/uranus_research_service/research/taxonomy_policy.py`.
- Imports: `app.research.taxonomy`.
- Direct database references: None; see imported repositories for transitive access.
- Admin coupling: No direct auth/workflow dependency.
- External services: None directly; service clients can be transitive.
- Existing tests: `backend/tests/test_taxonomy_index.py`, `backend/tests/test_taxonomy_semantic.py`.
- Decision: Preserve deterministic Research behavior in the execution service.

### `backend/app/research/taxonomy_transport.py`

- Classification: **MOVE** (later extraction).
- Responsibility: Dedicated taxonomy collection using the existing authenticated bounded HTTP transport.
- Proposed target: `src/uranus_research_service/research/taxonomy_transport.py`.
- Imports: `app.config`, `app.research.taxonomy`, `app.research.vector_transport`.
- Direct database references: None; see imported repositories for transitive access.
- Admin coupling: No direct auth/workflow dependency.
- External services: Qdrant HTTP.
- Existing tests: `backend/tests/test_taxonomy_index.py`, `backend/tests/test_taxonomy_semantic.py`.
- Decision: Preserve deterministic Research behavior in the execution service.

### `backend/app/research/vector_benchmark.py`

- Classification: **MOVE** (later extraction).
- Responsibility: Reproducible, unlabelled retrieval exports; quality metrics require real judgments.
- Proposed target: `src/uranus_research_service/research/vector_benchmark.py`.
- Imports: `app.research.vector_documents`, `app.research.vector_sync`, `app.research.vector_transport`.
- Direct database references: None; see imported repositories for transitive access.
- Admin coupling: No direct auth/workflow dependency.
- External services: Encoder HTTP, Qdrant HTTP.
- Existing tests: `backend/tests/test_review_benchmark.py`, `backend/tests/test_vector_index.py`.
- Decision: Preserve deterministic Research behavior in the execution service.

### `backend/app/research/vector_diagnostics.py`

- Classification: **MOVE** (later extraction).
- Responsibility: Bounded, value-redacted diagnostics for metadata-only payload differences.
- Proposed target: `src/uranus_research_service/research/vector_diagnostics.py`.
- Imports: `app.research.vector_sync`.
- Direct database references: None; see imported repositories for transitive access.
- Admin coupling: No direct auth/workflow dependency.
- External services: None directly; service clients can be transitive.
- Existing tests: `backend/tests/test_vector_metadata.py`.
- Decision: Preserve deterministic Research behavior in the execution service.

### `backend/app/research/vector_documents.py`

- Classification: **MOVE** (later extraction).
- Responsibility: Allowlisted public prose and tokenizer-bounded, deterministic event chunks.
- Proposed target: `src/uranus_research_service/research/vector_documents.py`.
- Imports: `app.repositories.research`, `app.research.chunk_kinds`, `app.research.evidence_context`.
- Direct database references: None; see imported repositories for transitive access.
- Admin coupling: No direct auth/workflow dependency.
- External services: None directly; service clients can be transitive.
- Existing tests: `backend/tests/test_semantic_search.py`, `backend/tests/test_vector_index.py`, `backend/tests/test_semantic_knowledge_index.py`.
- Decision: Preserve deterministic Research behavior in the execution service.

### `backend/app/research/vector_index.py`

- Classification: **MOVE** (later extraction).
- Responsibility: Explicit operator pilot: public source snapshot -> bounded internal retrieval services.
- Proposed target: `src/uranus_research_service/research/vector_index.py`.
- Imports: `app.admin_database`, `app.config`, `app.database`, `app.logging`, `app.repositories.vector_entities`, `app.repositories.vector_events`, `app.research.semantic_contracts`, `app.research.vector_benchmark`, `app.research.vector_diagnostics`, `app.research.vector_documents`, `app.research.vector_models`, `app.research.vector_sync`, `app.research.vector_transport`.
- Direct database references: `admin.research_area`.
- Admin coupling: app.admin_database.
- External services: Encoder HTTP, Qdrant HTTP.
- Existing tests: `backend/tests/test_vector_metadata.py`, `backend/tests/test_review_benchmark.py`, `backend/tests/test_semantic_genres.py`, `backend/tests/test_vector_index.py`, `backend/tests/test_semantic_knowledge_index.py`.
- Decision: Preserve deterministic Research behavior in the execution service.

### `backend/app/research/vector_models.py`

- Classification: **MOVE** (later extraction).
- Responsibility: Reviewed, pinned retrieval models; no implicit production model or remote input IDs.
- Proposed target: `src/uranus_research_service/research/vector_models.py`.
- Imports: `app.research.vector_documents`.
- Direct database references: None; see imported repositories for transitive access.
- Admin coupling: No direct auth/workflow dependency.
- External services: None directly; service clients can be transitive.
- Existing tests: `backend/tests/test_semantic_search.py`, `backend/tests/test_vector_index.py`, `backend/tests/test_semantic_knowledge_index.py`, `backend/tests/test_research_semantic_eligibility.py`.
- Decision: Preserve deterministic Research behavior in the execution service.

### `backend/app/research/vector_sync.py`

- Classification: **MOVE** (later extraction).
- Responsibility: Incremental embedding reuse and explicit reconciliation against a complete snapshot.
- Proposed target: `src/uranus_research_service/research/vector_sync.py`.
- Imports: `app.research.semantic_contracts`, `app.research.semantic_documents`, `app.research.vector_documents`, `app.research.vector_models`, `app.research.vector_transport`.
- Direct database references: None; see imported repositories for transitive access.
- Admin coupling: No direct auth/workflow dependency.
- External services: Encoder HTTP, Qdrant HTTP.
- Existing tests: `backend/tests/test_vector_metadata.py`, `backend/tests/test_vector_index.py`, `backend/tests/test_semantic_knowledge_index.py`.
- Decision: Preserve deterministic Research behavior in the execution service.

### `backend/app/research/vector_transport.py`

- Classification: **MOVE** (later extraction).
- Responsibility: Fixed-origin, authenticated and bounded internal HTTP; never return provider errors.
- Proposed target: `src/uranus_research_service/research/vector_transport.py`.
- Imports: `app.config`, `app.errors`, `app.research.area_selection`, `app.research.semantic_contracts`, `app.research.semantic_evidence`, `app.research.semantic_limits`, `app.research.vector_documents`, `app.research.vector_models`.
- Direct database references: None; see imported repositories for transitive access.
- Admin coupling: No direct auth/workflow dependency.
- External services: Encoder HTTP, Qdrant HTTP.
- Existing tests: `backend/tests/test_vector_metadata.py`, `backend/tests/test_taxonomy_semantic.py`, `backend/tests/test_semantic_search.py`, `backend/tests/test_semantic_genres.py`, `backend/tests/test_vector_index.py`, `backend/tests/test_semantic_knowledge_index.py`, `backend/tests/test_research_semantic_eligibility.py`.
- Decision: Preserve deterministic Research behavior in the execution service.

### `backend/app/research/wire/__init__.py`

- Classification: **SHARED_CONTRACT** (later extraction).
- Responsibility: Mirrored Planner wire contract; never an execution model.
- Proposed target: `contracts/ snapshots with parity tests; future consumer-side validation`.
- Imports: None.
- Direct database references: None; see imported repositories for transitive access.
- Admin coupling: No direct auth/workflow dependency.
- External services: None directly; service clients can be transitive.
- Existing tests: `backend/tests/test_research_sql_provenance.py`, `backend/tests/test_sql_console.py`, `backend/tests/test_timeline.py`, `backend/tests/test_notifications.py`, `backend/tests/test_notification_smtp_security.py`, `backend/tests/test_semantic_knowledge_index.py`.
- Decision: Retain wire shape; generated schema snapshot and parity checks, no runtime cross-repository import.

### `backend/app/research/wire/research_v10_schema.py`

- Classification: **SHARED_CONTRACT** (later extraction).
- Responsibility: Additive recurring-calendar wire contract; v9 remains frozen.
- Proposed target: `contracts/ snapshots with parity tests; future consumer-side validation`.
- Imports: `app.research.wire.research_v9_constraints`, `app.research.wire.research_v9_schema`, `app.research.wire.research_v9_types`.
- Direct database references: None; see imported repositories for transitive access.
- Admin coupling: No direct auth/workflow dependency.
- External services: None directly; service clients can be transitive.
- Existing tests: `backend/tests/test_research_calendar.py`.
- Decision: Retain wire shape; generated schema snapshot and parity checks, no runtime cross-repository import.

### `backend/app/research/wire/research_v11_schema.py`

- Classification: **SHARED_CONTRACT** (later extraction).
- Responsibility: Additive conversation wire boundary; v10 stays frozen.
- Proposed target: `contracts/ snapshots with parity tests; future consumer-side validation`.
- Imports: `app.research.wire.research_v10_schema`, `app.research.wire.research_v9_types`.
- Direct database references: None; see imported repositories for transitive access.
- Admin coupling: No direct auth/workflow dependency.
- External services: None directly; service clients can be transitive.
- Existing tests: `backend/tests/test_research_conversation.py`.
- Decision: Retain wire shape; generated schema snapshot and parity checks, no runtime cross-repository import.

### `backend/app/research/wire/research_v12_schema.py`

- Classification: **SHARED_CONTRACT** (later extraction).
- Responsibility: Combined modern v12 contract: v11 semantics with bounded administrative geography.
- Proposed target: `contracts/ snapshots with parity tests; future consumer-side validation`.
- Imports: `app.research.wire.research_v10_schema`, `app.research.wire.research_v12_spatial`, `app.research.wire.research_v9_constraints`, `app.research.wire.research_v9_types`.
- Direct database references: None; see imported repositories for transitive access.
- Admin coupling: No direct auth/workflow dependency.
- External services: None directly; service clients can be transitive.
- Existing tests: `backend/tests/test_research_v12.py`.
- Decision: Retain wire shape; generated schema snapshot and parity checks, no runtime cross-repository import.

### `backend/app/research/wire/research_v12_spatial.py`

- Classification: **SHARED_CONTRACT** (later extraction).
- Responsibility: Administrative semantics reuse v8's validated, identity-free spatial vocabulary.
- Proposed target: `contracts/ snapshots with parity tests; future consumer-side validation`.
- Imports: `app.research.wire.research_v8_constraints`.
- Direct database references: None; see imported repositories for transitive access.
- Admin coupling: No direct auth/workflow dependency.
- External services: None directly; service clients can be transitive.
- Existing tests: No direct module reference found; needs targeted extraction coverage.
- Decision: Retain wire shape; generated schema snapshot and parity checks, no runtime cross-repository import.

### `backend/app/research/wire/research_v13_schema.py`

- Classification: **SHARED_CONTRACT** (later extraction).
- Responsibility: Closed conversational envelope around the unchanged v12 research algebra.
- Proposed target: `contracts/ snapshots with parity tests; future consumer-side validation`.
- Imports: `app.research.wire.research_v12_schema`, `app.research.wire.research_v9_types`.
- Direct database references: None; see imported repositories for transitive access.
- Admin coupling: No direct auth/workflow dependency.
- External services: None directly; service clients can be transitive.
- Existing tests: `backend/tests/test_research_v13.py`.
- Decision: Retain wire shape; generated schema snapshot and parity checks, no runtime cross-repository import.

### `backend/app/research/wire/research_v7_constraints.py`

- Classification: **SHARED_CONTRACT** (later extraction).
- Responsibility: Closed v7 temporal, spatial, relation and interpretation constraints; no execution.
- Proposed target: `contracts/ snapshots with parity tests; future consumer-side validation`.
- Imports: `app.research.wire.research_v7_types`.
- Direct database references: None; see imported repositories for transitive access.
- Admin coupling: No direct auth/workflow dependency.
- External services: None directly; service clients can be transitive.
- Existing tests: No direct module reference found; needs targeted extraction coverage.
- Decision: Retain wire shape; generated schema snapshot and parity checks, no runtime cross-repository import.

### `backend/app/research/wire/research_v7_schema.py`

- Classification: **SHARED_CONTRACT** (later extraction).
- Responsibility: Research Query Language v7. Declarative interpretation, never an execution plan.
- Proposed target: `contracts/ snapshots with parity tests; future consumer-side validation`.
- Imports: `app.research.wire.research_v7_constraints`, `app.research.wire.research_v7_types`.
- Direct database references: None; see imported repositories for transitive access.
- Admin coupling: No direct auth/workflow dependency.
- External services: None directly; service clients can be transitive.
- Existing tests: `backend/tests/test_research_grouping.py`.
- Decision: Retain wire shape; generated schema snapshot and parity checks, no runtime cross-repository import.

### `backend/app/research/wire/research_v7_types.py`

- Classification: **SHARED_CONTRACT** (later extraction).
- Responsibility: Independent v7 vocabulary, nonrecursive metrics and typed predicates.
- Proposed target: `contracts/ snapshots with parity tests; future consumer-side validation`.
- Imports: None.
- Direct database references: None; see imported repositories for transitive access.
- Admin coupling: No direct auth/workflow dependency.
- External services: None directly; service clients can be transitive.
- Existing tests: No direct module reference found; needs targeted extraction coverage.
- Decision: Retain wire shape; generated schema snapshot and parity checks, no runtime cross-repository import.

### `backend/app/research/wire/research_v8_constraints.py`

- Classification: **SHARED_CONTRACT** (later extraction).
- Responsibility: Closed v8 temporal, spatial, relation and interpretation constraints; no execution.
- Proposed target: `contracts/ snapshots with parity tests; future consumer-side validation`.
- Imports: `app.research.wire.research_v8_types`.
- Direct database references: None; see imported repositories for transitive access.
- Admin coupling: No direct auth/workflow dependency.
- External services: None directly; service clients can be transitive.
- Existing tests: `backend/tests/test_research_internal_plan.py`.
- Decision: Retain wire shape; generated schema snapshot and parity checks, no runtime cross-repository import.

### `backend/app/research/wire/research_v8_schema.py`

- Classification: **SHARED_CONTRACT** (later extraction).
- Responsibility: Research Query Language v8. Declarative interpretation, never an execution plan.
- Proposed target: `contracts/ snapshots with parity tests; future consumer-side validation`.
- Imports: `app.research.wire.research_v8_constraints`, `app.research.wire.research_v8_types`.
- Direct database references: None; see imported repositories for transitive access.
- Admin coupling: No direct auth/workflow dependency.
- External services: None directly; service clients can be transitive.
- Existing tests: `backend/tests/test_research_internal_plan.py`, `backend/tests/test_administrative_geography.py`, `backend/tests/test_research_v9_adapter.py`.
- Decision: Retain wire shape; generated schema snapshot and parity checks, no runtime cross-repository import.

### `backend/app/research/wire/research_v8_types.py`

- Classification: **SHARED_CONTRACT** (later extraction).
- Responsibility: Independent v8 vocabulary, nonrecursive metrics and typed predicates.
- Proposed target: `contracts/ snapshots with parity tests; future consumer-side validation`.
- Imports: None.
- Direct database references: None; see imported repositories for transitive access.
- Admin coupling: No direct auth/workflow dependency.
- External services: None directly; service clients can be transitive.
- Existing tests: `backend/tests/test_research_internal_plan.py`.
- Decision: Retain wire shape; generated schema snapshot and parity checks, no runtime cross-repository import.

### `backend/app/research/wire/research_v9_constraints.py`

- Classification: **SHARED_CONTRACT** (later extraction).
- Responsibility: Closed v9 temporal, spatial, relation and interpretation constraints; no execution.
- Proposed target: `contracts/ snapshots with parity tests; future consumer-side validation`.
- Imports: `app.research.wire.research_v9_types`.
- Direct database references: None; see imported repositories for transitive access.
- Admin coupling: No direct auth/workflow dependency.
- External services: None directly; service clients can be transitive.
- Existing tests: No direct module reference found; needs targeted extraction coverage.
- Decision: Retain wire shape; generated schema snapshot and parity checks, no runtime cross-repository import.

### `backend/app/research/wire/research_v9_schema.py`

- Classification: **SHARED_CONTRACT** (later extraction).
- Responsibility: Research Query Language v9. Declarative interpretation, never an execution plan.
- Proposed target: `contracts/ snapshots with parity tests; future consumer-side validation`.
- Imports: `app.research.wire.research_v9_constraints`, `app.research.wire.research_v9_types`.
- Direct database references: None; see imported repositories for transitive access.
- Admin coupling: No direct auth/workflow dependency.
- External services: None directly; service clients can be transitive.
- Existing tests: `backend/tests/test_research_grouping_flow.py`, `backend/tests/test_research_grouping.py`, `backend/tests/test_research_v9_adapter.py`.
- Decision: Retain wire shape; generated schema snapshot and parity checks, no runtime cross-repository import.

### `backend/app/research/wire/research_v9_types.py`

- Classification: **SHARED_CONTRACT** (later extraction).
- Responsibility: Independent v9 vocabulary, nonrecursive metrics and typed predicates.
- Proposed target: `contracts/ snapshots with parity tests; future consumer-side validation`.
- Imports: None.
- Direct database references: None; see imported repositories for transitive access.
- Admin coupling: No direct auth/workflow dependency.
- External services: None directly; service clients can be transitive.
- Existing tests: No direct module reference found; needs targeted extraction coverage.
- Decision: Retain wire shape; generated schema snapshot and parity checks, no runtime cross-repository import.

### `backend/app/schemas/research.py`

- Classification: **SHARED_CONTRACT** (later extraction).
- Responsibility: Research-only contracts. No workflow, account, actor or private contact fields.
- Proposed target: `contracts/ snapshots with parity tests; future consumer-side validation`.
- Imports: `app.research.area_selection`, `app.research.chunk_kinds`, `app.schemas.finding`, `app.schemas.genre`.
- Direct database references: None; see imported repositories for transitive access.
- Admin coupling: No direct auth/workflow dependency.
- External services: None directly; service clients can be transitive.
- Existing tests: `backend/tests/test_research_sql_provenance.py`, `backend/tests/test_vector_metadata.py`, `backend/tests/test_research_calendar.py`, `backend/tests/test_research_internal_plan.py`, `backend/tests/test_admin_auth.py`, `backend/tests/test_research_area_migration.py`, `backend/tests/test_research_v13.py`, `backend/tests/test_review_benchmark.py`, `backend/tests/test_research_population.py`, `backend/tests/test_research_administrative.py`, `backend/tests/test_research_resolution.py`, `backend/tests/test_research_administrative_areas_batch.py`, `backend/tests/test_research_geography.py`, `backend/tests/test_project_knowledge.py`, `backend/tests/test_administrative_integration_guards.py`, `backend/tests/test_administrative_geography.py`, `backend/tests/test_research_suggestions.py`, `backend/tests/test_research_areas.py`, `backend/tests/test_research_scope.py`, `backend/tests/test_research_taxonomy.py`, `backend/tests/test_taxonomy_index.py`, `backend/tests/test_research_v12.py`, `backend/tests/test_research_grouping_flow.py`, `backend/tests/test_research_catalog.py`, `backend/tests/test_research_conversation.py`, `backend/tests/test_research_grouping.py`, `backend/tests/test_taxonomy_semantic.py`, `backend/tests/test_search_gateway.py`, `backend/tests/test_admin_upgrade_contracts.py`, `backend/tests/test_admin_roles.py`, `backend/tests/test_research_domain_contract.py`, `backend/tests/test_research_administrative_areas.py`, `backend/tests/test_research_answer.py`, `backend/tests/test_research_operator_config.py`, `backend/tests/test_research_chronology.py`, `backend/tests/test_semantic_search.py`, `backend/tests/test_operator_diagnostics.py`, `backend/tests/test_taxonomy_flow.py`, `backend/tests/test_semantic_genres.py`, `backend/tests/test_research_plan_execution.py`, `backend/tests/test_vector_index.py`, `backend/tests/test_research_ordering_contract.py`, `backend/tests/test_research_planner.py`, `backend/tests/test_research_analytics.py`, `backend/tests/test_research_unified.py`, `backend/tests/test_research_geocoder.py`, `backend/tests/test_semantic_knowledge_index.py`, `backend/tests/test_research_v12_postgis.py`, `backend/tests/test_research_v9_adapter.py`, `backend/tests/test_semantic_relevance.py`, `backend/tests/test_research.py`, `backend/tests/test_research_semantic_eligibility.py`.
- Decision: Retain wire shape; generated schema snapshot and parity checks, no runtime cross-repository import.

### `backend/app/schemas/research_administrative.py`

- Classification: **SHARED_CONTRACT** (later extraction).
- Responsibility: Strict internal geocoder metadata and bounded polygon shapes.
- Proposed target: `contracts/ snapshots with parity tests; future consumer-side validation`.
- Imports: `app.schemas.research_location`, `app.schemas.research_values`.
- Direct database references: None; see imported repositories for transitive access.
- Admin coupling: No direct auth/workflow dependency.
- External services: None directly; service clients can be transitive.
- Existing tests: `backend/tests/test_research_sql_provenance.py`, `backend/tests/test_research_internal_plan.py`, `backend/tests/test_research_administrative.py`, `backend/tests/test_research_administrative_areas_batch.py`, `backend/tests/test_administrative_integration_guards.py`, `backend/tests/test_administrative_geography.py`, `backend/tests/test_research_v12.py`, `backend/tests/test_research_grouping_flow.py`, `backend/tests/test_research_analytics.py`, `backend/tests/test_research_v9_adapter.py`.
- Decision: Retain wire shape; generated schema snapshot and parity checks, no runtime cross-repository import.

### `backend/app/schemas/research_administrative_result.py`

- Classification: **SHARED_CONTRACT** (later extraction).
- Responsibility: Public administrative selection results, independent of internal plan types.
- Proposed target: `contracts/ snapshots with parity tests; future consumer-side validation`.
- Imports: `app.schemas.research`, `app.schemas.research_sql`, `app.schemas.research_values`.
- Direct database references: None; see imported repositories for transitive access.
- Admin coupling: No direct auth/workflow dependency.
- External services: None directly; service clients can be transitive.
- Existing tests: `backend/tests/test_administrative_integration_guards.py`.
- Decision: Retain wire shape; generated schema snapshot and parity checks, no runtime cross-repository import.

### `backend/app/schemas/research_analytics.py`

- Classification: **SHARED_CONTRACT** (later extraction).
- Responsibility: Closed analytical v5/v10 wire contract; legacy v3/v7 stays frozen.
- Proposed target: `contracts/ snapshots with parity tests; future consumer-side validation`.
- Imports: None.
- Direct database references: None; see imported repositories for transitive access.
- Admin coupling: No direct auth/workflow dependency.
- External services: None directly; service clients can be transitive.
- Existing tests: `backend/tests/test_research_internal_plan.py`, `backend/tests/test_research_administrative.py`, `backend/tests/test_research_analytics.py`, `backend/tests/test_research_v9_adapter.py`.
- Decision: Retain wire shape; generated schema snapshot and parity checks, no runtime cross-repository import.

### `backend/app/schemas/research_analytics_guard.py`

- Classification: **SHARED_CONTRACT** (later extraction).
- Responsibility: Conservative multilingual vetoes, never a replacement planner or SQL generator.
- Proposed target: `contracts/ snapshots with parity tests; future consumer-side validation`.
- Imports: None.
- Direct database references: None; see imported repositories for transitive access.
- Admin coupling: No direct auth/workflow dependency.
- External services: None directly; service clients can be transitive.
- Existing tests: `backend/tests/test_research_analytics.py`.
- Decision: Retain wire shape; generated schema snapshot and parity checks, no runtime cross-repository import.

### `backend/app/schemas/research_areas.py`

- Classification: **SHARED_CONTRACT** (later extraction).
- Responsibility: Bounded read-only area projections; polygons are only returned for dossiers.
- Proposed target: `contracts/ snapshots with parity tests; future consumer-side validation`.
- Imports: `app.schemas.finding`, `app.schemas.research`.
- Direct database references: None; see imported repositories for transitive access.
- Admin coupling: No direct auth/workflow dependency.
- External services: None directly; service clients can be transitive.
- Existing tests: `backend/tests/test_research_administrative.py`, `backend/tests/test_research_areas.py`, `backend/tests/test_research_catalog.py`, `backend/tests/test_research_administrative_areas.py`, `backend/tests/test_research_chronology.py`, `backend/tests/test_semantic_search.py`, `backend/tests/test_semantic_genres.py`, `backend/tests/test_research_plan_execution.py`, `backend/tests/test_research_analytics.py`, `backend/tests/test_research_semantic_eligibility.py`.
- Decision: Retain wire shape; generated schema snapshot and parity checks, no runtime cross-repository import.

### `backend/app/schemas/research_conversation.py`

- Classification: **SHARED_CONTRACT** (later extraction).
- Responsibility: Bounded advisory semantics, never executable plans or result data.
- Proposed target: `contracts/ snapshots with parity tests; future consumer-side validation`.
- Imports: None.
- Direct database references: None; see imported repositories for transitive access.
- Admin coupling: No direct auth/workflow dependency.
- External services: None directly; service clients can be transitive.
- Existing tests: `backend/tests/test_research_v13.py`, `backend/tests/test_research_v12.py`, `backend/tests/test_research_conversation.py`.
- Decision: Retain wire shape; generated schema snapshot and parity checks, no runtime cross-repository import.

### `backend/app/schemas/research_conversation_v12.py`

- Classification: **SHARED_CONTRACT** (later extraction).
- Responsibility: V12 summaries retain lexical administrative expectations, never resolved identities.
- Proposed target: `contracts/ snapshots with parity tests; future consumer-side validation`.
- Imports: `app.research.wire.research_v8_types`, `app.schemas.research_conversation`.
- Direct database references: None; see imported repositories for transitive access.
- Admin coupling: No direct auth/workflow dependency.
- External services: None directly; service clients can be transitive.
- Existing tests: `backend/tests/test_research_v13.py`, `backend/tests/test_research_v12.py`.
- Decision: Retain wire shape; generated schema snapshot and parity checks, no runtime cross-repository import.

### `backend/app/schemas/research_domain.py`

- Classification: **SHARED_CONTRACT** (later extraction).
- Responsibility: Public planner v4 mirror; compatible addition beside the existing v3 endpoint.
- Proposed target: `contracts/ snapshots with parity tests; future consumer-side validation`.
- Imports: `app.schemas.research_planner`.
- Direct database references: None; see imported repositories for transitive access.
- Admin coupling: No direct auth/workflow dependency.
- External services: None directly; service clients can be transitive.
- Existing tests: `backend/tests/test_research_sql_provenance.py`, `backend/tests/test_project_knowledge.py`, `backend/tests/test_research_domain_contract.py`, `backend/tests/test_research_unified.py`.
- Decision: Retain wire shape; generated schema snapshot and parity checks, no runtime cross-repository import.

### `backend/app/schemas/research_execution.py`

- Classification: **SHARED_CONTRACT** (later extraction).
- Responsibility: Closed execution results and internal filters; never accepted from a browser.
- Proposed target: `contracts/ snapshots with parity tests; future consumer-side validation`.
- Imports: `app.schemas.genre`, `app.schemas.research`, `app.schemas.research_location`, `app.schemas.research_values`.
- Direct database references: None; see imported repositories for transitive access.
- Admin coupling: No direct auth/workflow dependency.
- External services: None directly; service clients can be transitive.
- Existing tests: `backend/tests/test_research_sql_provenance.py`, `backend/tests/test_research_calendar.py`, `backend/tests/test_research_internal_plan.py`, `backend/tests/test_research_v13.py`, `backend/tests/test_research_administrative.py`, `backend/tests/test_research_resolution.py`, `backend/tests/test_administrative_integration_guards.py`, `backend/tests/test_administrative_geography.py`, `backend/tests/test_research_taxonomy.py`, `backend/tests/test_research_v12.py`, `backend/tests/test_research_grouping.py`, `backend/tests/test_research_answer.py`, `backend/tests/test_research_chronology.py`, `backend/tests/test_taxonomy_flow.py`, `backend/tests/test_research_plan_execution.py`, `backend/tests/test_research_analytics.py`, `backend/tests/test_research_unified.py`, `backend/tests/test_research_v9_adapter.py`, `backend/tests/test_research_semantic_eligibility.py`.
- Decision: Retain wire shape; generated schema snapshot and parity checks, no runtime cross-repository import.

### `backend/app/schemas/research_geography.py`

- Classification: **SHARED_CONTRACT** (later extraction).
- Responsibility: Versioned geographic v6/v11 contract; earlier contracts remain frozen.
- Proposed target: `contracts/ snapshots with parity tests; future consumer-side validation`.
- Imports: `app.schemas.research_analytics`.
- Direct database references: None; see imported repositories for transitive access.
- Admin coupling: No direct auth/workflow dependency.
- External services: None directly; service clients can be transitive.
- Existing tests: `backend/tests/test_research_internal_plan.py`, `backend/tests/test_research_geography.py`, `backend/tests/test_research_v9_adapter.py`.
- Decision: Retain wire shape; generated schema snapshot and parity checks, no runtime cross-repository import.

### `backend/app/schemas/research_location.py`

- Classification: **SHARED_CONTRACT** (later extraction).
- Responsibility: Untrusted browser context and bounded geocoder output; never persisted.
- Proposed target: `contracts/ snapshots with parity tests; future consumer-side validation`.
- Imports: `app.schemas.research_conversation`, `app.schemas.research_conversation_v12`, `app.schemas.research_planner`.
- Direct database references: None; see imported repositories for transitive access.
- Admin coupling: No direct auth/workflow dependency.
- External services: None directly; service clients can be transitive.
- Existing tests: `backend/tests/test_research_sql_provenance.py`, `backend/tests/test_research_geography.py`, `backend/tests/test_research_v12.py`, `backend/tests/test_research_grouping_flow.py`, `backend/tests/test_research_conversation.py`, `backend/tests/test_research_geocoder.py`, `backend/tests/test_research_v9_adapter.py`.
- Decision: Retain wire shape; generated schema snapshot and parity checks, no runtime cross-repository import.

### `backend/app/schemas/research_planner.py`

- Classification: **SHARED_CONTRACT** (later extraction).
- Responsibility: Admin mirror of the planner v3/v7 wire contract, not inference or execution logic.
- Proposed target: `contracts/ snapshots with parity tests; future consumer-side validation`.
- Imports: None.
- Direct database references: None; see imported repositories for transitive access.
- Admin coupling: No direct auth/workflow dependency.
- External services: None directly; service clients can be transitive.
- Existing tests: `backend/tests/test_research_sql_provenance.py`, `backend/tests/test_research_calendar.py`, `backend/tests/test_research_internal_plan.py`, `backend/tests/test_research_v13.py`, `backend/tests/test_research_geography.py`, `backend/tests/test_project_knowledge.py`, `backend/tests/test_administrative_integration_guards.py`, `backend/tests/test_administrative_geography.py`, `backend/tests/test_research_taxonomy.py`, `backend/tests/test_research_v12.py`, `backend/tests/test_research_grouping_flow.py`, `backend/tests/test_research_conversation.py`, `backend/tests/test_research_domain_contract.py`, `backend/tests/test_research_chronology.py`, `backend/tests/test_taxonomy_flow.py`, `backend/tests/test_research_plan_execution.py`, `backend/tests/test_research_ordering_contract.py`, `backend/tests/test_research_planner.py`, `backend/tests/test_research_analytics.py`, `backend/tests/test_research_unified.py`, `backend/tests/test_research_geocoder.py`, `backend/tests/test_research_v12_postgis.py`.
- Decision: Retain wire shape; generated schema snapshot and parity checks, no runtime cross-repository import.

### `backend/app/schemas/research_response.py`

- Classification: **SHARED_CONTRACT** (later extraction).
- Responsibility: HTTP response composition. Planner provenance remains at the API boundary.
- Proposed target: `contracts/ snapshots with parity tests; future consumer-side validation`.
- Imports: `app.research.answer`, `app.research.wire.research_v10_schema`, `app.research.wire.research_v11_schema`, `app.research.wire.research_v12_schema`, `app.research.wire.research_v13_schema`, `app.research.wire.research_v9_schema`, `app.schemas.research_analytics`, `app.schemas.research_conversation`, `app.schemas.research_conversation_v12`, `app.schemas.research_execution`, `app.schemas.research_geography`, `app.schemas.research_planner`, `app.schemas.research_sql`, `app.schemas.research_values`.
- Direct database references: None; see imported repositories for transitive access.
- Admin coupling: No direct auth/workflow dependency.
- External services: None directly; service clients can be transitive.
- Existing tests: `backend/tests/test_research_sql_provenance.py`, `backend/tests/test_research_calendar.py`, `backend/tests/test_research_v12.py`, `backend/tests/test_research_grouping_flow.py`, `backend/tests/test_research_answer.py`.
- Decision: Retain wire shape; generated schema snapshot and parity checks, no runtime cross-repository import.

### `backend/app/schemas/research_sql.py`

- Classification: **SHARED_CONTRACT** (later extraction).
- Responsibility: Bounded, closed, display-only provenance for authoritative Research source SQL.
- Proposed target: `contracts/ snapshots with parity tests; future consumer-side validation`.
- Imports: `app.schemas.research_values`.
- Direct database references: None; see imported repositories for transitive access.
- Admin coupling: No direct auth/workflow dependency.
- External services: None directly; service clients can be transitive.
- Existing tests: `backend/tests/test_research_sql_provenance.py`, `backend/tests/test_research_calendar.py`, `backend/tests/test_research_grouping.py`, `backend/tests/test_semantic_search.py`, `backend/tests/test_research_analytics.py`, `backend/tests/test_research_v9_adapter.py`.
- Decision: Retain wire shape; generated schema snapshot and parity checks, no runtime cross-repository import.

### `backend/app/schemas/research_suggestions.py`

- Classification: **KEEP_IN_ADMIN** (retained in Admin).
- Responsibility: Bounded, identity-free suggestion telemetry.
- Proposed target: `backend/app/schemas/research_suggestions.py`.
- Imports: None.
- Direct database references: None; see imported repositories for transitive access.
- Admin coupling: No direct auth/workflow dependency.
- External services: None directly; service clients can be transitive.
- Existing tests: `backend/tests/test_research_suggestions.py`.
- Decision: Admin-owned persistence/import/learning; service receives only read-only geographic projection.

### `backend/app/schemas/research_unified.py`

- Classification: **DEFER** (outside phase 1).
- Responsibility: Historical pilot/project-knowledge path, separate from current v9–v13 execution; keep explicit legacy route during phased rollout.
- Proposed target: `backend/app/schemas/research_unified.py`.
- Imports: `app.schemas.project_knowledge`, `app.schemas.research_domain`, `app.schemas.research_execution`, `app.schemas.research_sql`.
- Direct database references: None; see imported repositories for transitive access.
- Admin coupling: No direct auth/workflow dependency.
- External services: None directly; service clients can be transitive.
- Existing tests: `backend/tests/test_research_sql_provenance.py`, `backend/tests/test_project_knowledge.py`, `backend/tests/test_research_unified.py`.
- Decision: Historical pilot/project-knowledge path, separate from current v9–v13 execution; keep explicit legacy route during phased rollout.

### `backend/app/schemas/research_values.py`

- Classification: **SHARED_CONTRACT** (later extraction).
- Responsibility: Shared execution response primitives, independent of Planner wire versions.
- Proposed target: `contracts/ snapshots with parity tests; future consumer-side validation`.
- Imports: None.
- Direct database references: None; see imported repositories for transitive access.
- Admin coupling: No direct auth/workflow dependency.
- External services: None directly; service clients can be transitive.
- Existing tests: No direct module reference found; needs targeted extraction coverage.
- Decision: Retain wire shape; generated schema snapshot and parity checks, no runtime cross-repository import.

### `backend/app/services/research_administrative.py`

- Classification: **MOVE** (later extraction).
- Responsibility: Versioned transport edge; execution belongs to the shared ResearchPlanExecutor.
- Proposed target: `src/uranus_research_service/services/research_administrative.py`.
- Imports: `app.config`, `app.errors`, `app.research.context`, `app.research.normalize`, `app.research.wire.research_v8_schema`, `app.schemas.research_administrative_result`, `app.services.research_plan_execution`, `app.services.research_planner`.
- Direct database references: None; see imported repositories for transitive access.
- Admin coupling: Admin Request/app.state dependency to remove.
- External services: None directly; service clients can be transitive.
- Existing tests: `backend/tests/test_research_sql_provenance.py`, `backend/tests/test_research_internal_plan.py`, `backend/tests/test_research_administrative.py`, `backend/tests/test_research_administrative_areas_batch.py`, `backend/tests/test_administrative_integration_guards.py`, `backend/tests/test_administrative_geography.py`, `backend/tests/test_research_v12.py`, `backend/tests/test_research_grouping_flow.py`, `backend/tests/test_research_analytics.py`, `backend/tests/test_research_v9_adapter.py`.
- Decision: Preserve deterministic Research behavior in the execution service.

### `backend/app/services/research_conversational.py`

- Classification: **MOVE** (later extraction).
- Responsibility: v13 orchestration: semantic routing before any resolver, source or vector access.
- Proposed target: `src/uranus_research_service/services/research_conversational.py`.
- Imports: `app.auth.credentials`, `app.auth.service`, `app.config`, `app.errors`, `app.research.answer_facts`, `app.research.context`, `app.research.conversation`, `app.research.conversation_state`, `app.research.geography`, `app.research.normalize_v12`, `app.research.public_result`, `app.research.wire.research_v13_schema`, `app.schemas.research_conversation_v12`, `app.schemas.research_location`, `app.schemas.research_response`, `app.services.research_plan_execution`, `app.services.research_planner`.
- Direct database references: None; see imported repositories for transitive access.
- Admin coupling: app.auth.credentials, app.auth.service, Admin Request/app.state dependency to remove.
- External services: Planner HTTP, Qdrant HTTP.
- Existing tests: `backend/tests/test_research_v13.py`.
- Decision: Preserve deterministic Research behavior in the execution service.

### `backend/app/services/research_domain_client.py`

- Classification: **DEFER** (outside phase 1).
- Responsibility: Fixed server-to-server v4 routes; no browser credentials or routing selectors.
- Proposed target: `backend/app/services/research_domain_client.py`.
- Imports: `app.config`, `app.errors`, `app.schemas.project_knowledge`, `app.schemas.research_domain`.
- Direct database references: None; see imported repositories for transitive access.
- Admin coupling: No direct auth/workflow dependency.
- External services: None directly; service clients can be transitive.
- Existing tests: `backend/tests/test_project_knowledge.py`, `backend/tests/test_research_domain_contract.py`, `backend/tests/test_research_unified.py`.
- Decision: Historical pilot/project-knowledge path, separate from current v9–v13 execution; keep explicit legacy route during phased rollout.

### `backend/app/services/research_learning.py`

- Classification: **KEEP_IN_ADMIN** (retained in Admin).
- Responsibility: Best-effort learning after successful execution, isolated from source reads.
- Proposed target: `backend/app/services/research_learning.py`.
- Imports: `app.admin_database`, `app.repositories.research_suggestions`, `app.research.normalize`, `app.research.plan`, `app.research.wire.research_v13_schema`, `app.schemas.research_response`.
- Direct database references: None; see imported repositories for transitive access.
- Admin coupling: app.admin_database.
- External services: None directly; service clients can be transitive.
- Existing tests: `backend/tests/test_research_sql_provenance.py`, `backend/tests/test_research_suggestions.py`.
- Decision: Admin-owned persistence/import/learning; service receives only read-only geographic projection.

### `backend/app/services/research_legacy_conversation.py`

- Classification: **MOVE** (later extraction).
- Responsibility: Server-owned context for v11/v12 rollback; older browser contracts remain accepted.
- Proposed target: `src/uranus_research_service/services/research_legacy_conversation.py`.
- Imports: `app.auth.credentials`, `app.auth.service`, `app.config`, `app.errors`, `app.research.conversation_state`, `app.schemas.research_conversation`, `app.schemas.research_conversation_v12`, `app.schemas.research_location`, `app.schemas.research_response`.
- Direct database references: None; see imported repositories for transitive access.
- Admin coupling: app.auth.credentials, app.auth.service, Admin Request/app.state dependency to remove.
- External services: None directly; service clients can be transitive.
- Existing tests: No direct module reference found; needs targeted extraction coverage.
- Decision: Preserve deterministic Research behavior in the execution service.

### `backend/app/services/research_plan_execution.py`

- Classification: **MOVE** (later extraction).
- Responsibility: Deterministic execution of validated server-side plans. No inference or persistence.
- Proposed target: `src/uranus_research_service/services/research_plan_execution.py`.
- Imports: `app.config`, `app.database`, `app.errors`, `app.repositories.administrative_execution`, `app.repositories.research`, `app.repositories.research_execution`, `app.repositories.research_grouping`, `app.repositories.research_resolution`, `app.research.capabilities`, `app.research.context`, `app.research.geography`, `app.research.outcome`, `app.research.plan`, `app.research.sql_provenance`, `app.schemas.research_execution`, `app.services.semantic_search`.
- Direct database references: None; see imported repositories for transitive access.
- Admin coupling: No direct auth/workflow dependency.
- External services: None directly; service clients can be transitive.
- Existing tests: `backend/tests/test_research_sql_provenance.py`, `backend/tests/test_research_calendar.py`, `backend/tests/test_research_internal_plan.py`, `backend/tests/test_research_administrative.py`, `backend/tests/test_research_geography.py`, `backend/tests/test_administrative_integration_guards.py`, `backend/tests/test_administrative_geography.py`, `backend/tests/test_research_suggestions.py`, `backend/tests/test_research_taxonomy.py`, `backend/tests/test_taxonomy_index.py`, `backend/tests/test_research_v12.py`, `backend/tests/test_research_grouping_flow.py`, `backend/tests/test_research_grouping.py`, `backend/tests/test_research_chronology.py`, `backend/tests/test_taxonomy_flow.py`, `backend/tests/test_research_plan_execution.py`, `backend/tests/test_research_ordering_contract.py`, `backend/tests/test_research_analytics.py`, `backend/tests/test_research_v12_postgis.py`, `backend/tests/test_research_v9_adapter.py`, `backend/tests/test_research_semantic_eligibility.py`.
- Decision: Preserve deterministic Research behavior in the execution service.

### `backend/app/services/research_planner.py`

- Classification: **MOVE** (later extraction).
- Responsibility: Bounded server-to-server language planning. No retrieval, persistence or retries.
- Proposed target: `src/uranus_research_service/services/research_planner.py`.
- Imports: `app.config`, `app.errors`, `app.research.wire.research_v10_schema`, `app.research.wire.research_v11_schema`, `app.research.wire.research_v12_schema`, `app.research.wire.research_v13_schema`, `app.research.wire.research_v8_schema`, `app.research.wire.research_v9_schema`, `app.schemas.research_analytics`, `app.schemas.research_conversation`, `app.schemas.research_conversation_v12`, `app.schemas.research_geography`, `app.schemas.research_planner`.
- Direct database references: None; see imported repositories for transitive access.
- Admin coupling: No direct auth/workflow dependency.
- External services: Planner HTTP.
- Existing tests: `backend/tests/test_research_sql_provenance.py`, `backend/tests/test_research_calendar.py`, `backend/tests/test_research_internal_plan.py`, `backend/tests/test_research_v13.py`, `backend/tests/test_research_geography.py`, `backend/tests/test_project_knowledge.py`, `backend/tests/test_administrative_integration_guards.py`, `backend/tests/test_administrative_geography.py`, `backend/tests/test_research_taxonomy.py`, `backend/tests/test_research_v12.py`, `backend/tests/test_research_grouping_flow.py`, `backend/tests/test_research_conversation.py`, `backend/tests/test_research_domain_contract.py`, `backend/tests/test_research_chronology.py`, `backend/tests/test_taxonomy_flow.py`, `backend/tests/test_research_plan_execution.py`, `backend/tests/test_research_ordering_contract.py`, `backend/tests/test_research_planner.py`, `backend/tests/test_research_analytics.py`, `backend/tests/test_research_unified.py`, `backend/tests/test_research_geocoder.py`, `backend/tests/test_research_v12_postgis.py`.
- Decision: Preserve deterministic Research behavior in the execution service.

### `backend/app/services/research_suggestions.py`

- Classification: **KEEP_IN_ADMIN** (retained in Admin).
- Responsibility: Deterministic privacy gate and bounded learning weights; no inference services.
- Proposed target: `backend/app/services/research_suggestions.py`.
- Imports: None.
- Direct database references: None; see imported repositories for transitive access.
- Admin coupling: No direct auth/workflow dependency.
- External services: None directly; service clients can be transitive.
- Existing tests: `backend/tests/test_research_suggestions.py`.
- Decision: Admin-owned persistence/import/learning; service receives only read-only geographic projection.

### `backend/app/services/research_unified.py`

- Classification: **DEFER** (outside phase 1).
- Responsibility: Admin remains the only exact-data executor and public Research orchestrator.
- Proposed target: `backend/app/services/research_unified.py`.
- Imports: `app.admin_database`, `app.config`, `app.database`, `app.errors`, `app.repositories.research_areas`, `app.repositories.research_metrics`, `app.repositories.research_resolution`, `app.research.sql_provenance`, `app.schemas.research_domain`, `app.schemas.research_execution`, `app.schemas.research_unified`, `app.services.research_domain_client`.
- Direct database references: None; see imported repositories for transitive access.
- Admin coupling: app.admin_database, Admin Request/app.state dependency to remove.
- External services: None directly; service clients can be transitive.
- Existing tests: `backend/tests/test_research_sql_provenance.py`, `backend/tests/test_project_knowledge.py`, `backend/tests/test_research_unified.py`.
- Decision: Historical pilot/project-knowledge path, separate from current v9–v13 execution; keep explicit legacy route during phased rollout.

### `backend/app/services/semantic_search.py`

- Classification: **MOVE** (later extraction).
- Responsibility: Fixed-model retrieval with validated evidence and authoritative source rehydration.
- Proposed target: `src/uranus_research_service/services/semantic_search.py`.
- Imports: `app.config`, `app.database`, `app.errors`, `app.repositories.entities`, `app.repositories.research`, `app.repositories.research_areas`, `app.research.semantic_evidence`, `app.research.semantic_explanations`, `app.research.semantic_limits`, `app.research.vector_models`, `app.research.vector_transport`, `app.schemas.research`.
- Direct database references: None; see imported repositories for transitive access.
- Admin coupling: No direct auth/workflow dependency.
- External services: Encoder HTTP, Qdrant HTTP.
- Existing tests: `backend/tests/test_research_sql_provenance.py`, `backend/tests/test_research_calendar.py`, `backend/tests/test_taxonomy_semantic.py`, `backend/tests/test_search_gateway.py`, `backend/tests/test_research_domain_contract.py`, `backend/tests/test_semantic_search.py`, `backend/tests/test_semantic_genres.py`, `backend/tests/test_research_plan_execution.py`, `backend/tests/test_research_unified.py`, `backend/tests/test_research_v9_adapter.py`, `backend/tests/test_research_semantic_eligibility.py`.
- Decision: Preserve deterministic Research behavior in the execution service.

### `backend/app/services/taxonomy_resolution.py`

- Classification: **MOVE** (later extraction).
- Responsibility: Vectors propose vocabulary identities; the current public SQL snapshot authorizes them.
- Proposed target: `src/uranus_research_service/services/taxonomy_resolution.py`.
- Imports: `app.config`, `app.errors`, `app.repositories.research_taxonomy`, `app.research.taxonomy`, `app.research.taxonomy_policy`, `app.research.taxonomy_transport`, `app.research.vector_transport`, `app.schemas.research_execution`.
- Direct database references: None; see imported repositories for transitive access.
- Admin coupling: No direct auth/workflow dependency.
- External services: Encoder HTTP, Qdrant HTTP.
- Existing tests: `backend/tests/test_taxonomy_semantic.py`, `backend/tests/test_research_plan_execution.py`.
- Decision: Preserve deterministic Research behavior in the execution service.

### `backend/app/repositories/administrative_execution.py`

- Classification: **MOVE** (later extraction).
- Responsibility: Deterministic PostGIS execution; only resolved identities, polygons and category IDs.
- Proposed target: `src/uranus_research_service/repositories/administrative_execution.py`.
- Imports: `app.config`, `app.errors`, `app.repositories.research`, `app.research.plan`, `app.research.sql_provenance`, `app.schemas.research_administrative_result`, `sqlalchemy`, `sqlalchemy.ext.asyncio`, `typing`.
- Direct database references: None; see imported repositories for transitive access.
- Admin coupling: No direct auth/workflow dependency.
- External services: None directly; service clients can be transitive.
- Existing tests: `backend/tests/test_research_sql_provenance.py`, `backend/tests/test_administrative_integration_guards.py`, `backend/tests/test_administrative_geography.py`.
- Decision: Deterministic Research execution.
