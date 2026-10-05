# Phase 2A: structured Research execution

Baseline: service main dc59671; Admin source 340df4684611dbc4b8ec73a7702f1fad2ae1973c.
This phase extends the completed Phase-1 audit before porting execution. Admin is a
read-only reference; no routes, configuration, credentials or production data change.

## Reviewed port boundaries

- MOVE and adapt `research_conversational`: replace credential extraction and Request
  with an authenticated opaque principal, explicit store, planner and executor.
- MOVE and adapt `research_plan_execution`: retain temporal/order/count/group/area SQL
  dispatch; inject source database and resolver; remove semantic execution entirely.
- MOVE pure plan/normalization/geography/capability/outcome/conversation/answer-facts/
  public-result/provenance modules and their closed schema dependencies. Retain actual
  Pydantic semantic validators, not just JSON Schema validation.
- MOVE structured repositories: research, execution, grouping, administrative SQL,
  deterministic resolution, place and area metadata. Inject dependencies into resolver.
- EXTRACT ONLY required pure helpers from general Admin entity/activity/quality modules:
  pagination, literal search escaping, public search field definitions, image/location
  projection, URL syntax check and timezone guard. No workflow or user search imported.
- EXTRACT ONLY canonical taxonomy SQL constants. No semantic taxonomy policy/fallback,
  indexing, vector transport, model inference or semantic candidate collection is ported.
- MOVE Geocoder transport and administrative inventory/resolver: needed by existing
  structured named-place and multi-boundary/grouping semantics; inject optional client
  explicitly. Missing client/inventory fails closed for affected paths.
- KEEP Admin auth, sessions, CSRF, learning, activity, findings, workflows and routes.

## Database and area decision

Use separate source and metadata reader engines. Metadata access is limited to the
existing read-only `admin.research_area` contract (not broad Admin access). A projection
view is preferable operationally but would require new DDL not present in the source;
this phase preserves existing SQL through a separately verified least-privilege role.
Preflight checks effective role/ownership/grants, schema CREATE and DML, required tables
and read access. Neither runtime provisions roles nor migrates schemas.

Snapshots remain REPEATABLE READ / READ ONLY. Planner and Geocoder work completes
outside source snapshots; no inference runs inside a database transaction.

## Semantic exclusion

Reject semantic selection before normalization/resolution/SQL and again at the executor
capability gate. Return the existing `unsupported_constraint` conversation disposition;
direct invalid/unsupported execution calls retain the 422 boundary. There is no
structured-only fallback for a semantic plan and no vector/encoder runtime dependency.

## Implemented runtime

`ResearchRuntime` explicitly constructs/injects PlannerClient, source ResearchDatabase,
area ResearchDatabase, ResearchResolver, optional Geocoder, ConversationStore and
ResearchPlanExecutor. No globals or Admin Request/app.state are used. Version 0.2.0
activates the planned v1 response envelope without changing Admin's browser routes.

Structured records (event/venue/organization), event/occurrence count, venue/organization/
event aggregate, multidimensional grouping, comparison, exact taxonomy, spatial rank,
calendar/recurring weekday/month constraints, cached inside/outside areas and complete
administrative grouping preserve the original SQL/normalizer/answer semantics.
Missing geographic inventory/geocoder and unresolved or ambiguous identities remain
explicit failures/clarifications; no geography or ranking is invented.

The narrow metadata reader was chosen over a new view because the existing deployed
relation contract is known and no production DDL is authorized. The query resolver
checks both readers before source resolution; each read context repeats preflight.
Unsafe roles are rejected even when current_transaction_read_only is on.

## Conversation ownership and response safety

A 64-character lowercase hex X-Research-Principal is required alongside the service
Bearer key. The future trusted caller derives the opaque HMAC principal; the service
validates format and binds opaque conversation handles to it, not to Admin sessions.
Store TTL/capacity/summary limits and privacy suppression are ported unchanged. No
transcript, SQL rows, coordinates or vectors enter state. Non-research acts route out
before any database, resolver or executor call.

Answer text is produced from projected safe AnswerFacts, never an LLM. The versioned
response wraps the unchanged Admin ResearchExecutionResponse/ConversationResponse.
Original provenance uses context-local explicit SQL instrumentation and the same
allowlist/redaction, with no global SQLAlchemy listener. Fixed errors map Planner
invalid/unavailable to 502/503 and DB unsafe/unavailable to 503; unsupported plans use
existing clarification or 422 boundaries. Logs contain operative fields only.

## Parity evidence

The differential harness executes the untouched pinned Admin in its own interpreter.
The only Admin test adapter replaces its DML-oriented metadata connection preflight
with the fixture's separate read-only area connection. SQL, resolution, planner
validators, normalizers, conversation routing and rendering are not replaced.

31 structured goldens use identical synthetic PostGIS rows, Planner fixtures, reference
date (2026-10-04), timezone and geographic inventory. Both implementations are checked
against independent expected counts/identities/order, then compared across the complete
response, SQL text/parameters, facts, pending clarification and summaries. Only opaque
random conversation handles, observation timestamps and diagnostic timing are omitted.
All result/provenance/fact fields remain compared. Full execution passed; see
[validation](validation.md) for exact commands and scope. This is not a live-language
quality benchmark or a claim of deployed production compatibility.

## Phase 2B / operational follow-ups

Provision reviewed source/area readers and verify actual DDL before rollout. Supply
reachable fixed Planner/optional Geocoder origins and an authoritative complete area
inventory for relevant paths. Check live v13 inference and capacity separately.
Admin adapter/cutover, Jina-v5 inference, Qdrant collections/reindex/evidence/thresholds
and v3/v5 quality benchmarks remain unimplemented. No production or model changes
were made, and no v3 data cleanup is authorized.
