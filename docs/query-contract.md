# Structured query and conversation contract — Phase 2A

Service 0.2.0, internal contract `uranus-research-service-v1`. The planned envelope
from Phase 1 is now implemented; `/query` no longer returns the placeholder 501.
This activates an internal feature without changing the existing Admin browser API.
Generated schemas/OpenAPI are in `contracts/service`; Admin/Planner pins remain intact.

## HTTP boundary

Health is unauthenticated liveness only. All other endpoints require one internal
Bearer key. `/query` additionally requires exactly one `X-Research-Principal`, 64
lowercase hex characters. Cookies, Origin headers, duplicate authentication/principal
headers and routing query strings are rejected. Principal format validation does not
prove its derivation: the authenticated server caller is responsible for a dedicated
service-scoped HMAC over its authenticated session context. Never accept the principal
from a browser, or forward the underlying session, user ID or Admin credentials.

Request fields: query (1–2000 nonblank characters), timezone (configured event zone),
language (auto/de/da/en), optional opaque conversation_id, optional LocationContext.
Extra SQL/model/collection/backend/provider/planner selectors and conversation_context
are forbidden. The 32 KiB streaming body bound and timeouts apply before model parsing.
A non-auto language sets the initial conversation language; later Planner language
selection retains the existing v13 behavior. No query rewriting is performed.

```json
{"query":"Welche Veranstaltungen gibt es am Wochenende?","timezone":"Europe/Berlin","language":"auto","conversation_id":null,"location_context":null}
```

## Response mapping

| Current Admin response | Service response | Future Admin proxy |
| --- | --- | --- |
| ResearchExecutionResponse | `schema_version` + `response` containing unchanged inner schema | validate then unwrap |
| answer_text, language, query, original planner envelope | unchanged | unchanged |
| resolution, result, execution, observed_at, timezone, diagnostics | unchanged semantics | unchanged |
| sql_provenance | original explicit instrumentation/redaction | unchanged |
| conversation_id / summary | opaque handle; v13 summary remains null | unchanged |
| ConversationResponse | same alternative inside response | unwrap |
| SemanticResearchPage | unavailable in Phase 2A | future Phase 2B |

Successful envelope: `{"schema_version":"uranus-research-service-v1","response":{…}}`.
Response schema parity tests compare actual ported Pydantic models with pinned Admin
snapshots. No runtime Python imports from Admin or Planner are used.

## Planner validation and routing

Only POST `/v13/plan` executes. The metadata client retains older route checks for
contract diagnostics, but runtime rejects a configured non-v13 contract. Every actual
response passes PlanResponseV13 and all nested custom validators: exact outer/nested
original_query, configured timezone, schema version v13, prompt research-planner-v19,
model/diagnostic agreement, interaction kind/mode, semantic algebra, strict types and
extra-field rejection. Injected clients are revalidated too. Duplicate JSON keys and
nonfinite values are rejected. No retry, repair, inference during readiness or fallback.

Greeting, acknowledgement, social and help return before normalization, resolution or
SQL. Correction/clarification acts keep the original routing. A research plan carrying
`semantic` is rejected before normalization, pending-state storage or SQL with a 200
ConversationResponse: kind clarification, act unsupported, reason unsupported_constraint.
The direct capability/executor boundary also rejects semantic with HTTP 422. No semantic
constraint is discarded to execute the remaining structured filters.

## Conversation state

The ported process-local store retains TTL 1800 seconds, capacity 256, eight entries
per principal, at most four bounded summaries, pending clarification, language, safe
AnswerFacts and busy-turn rejection. Owner mismatch/expiry issues a new opaque handle
and needs_context; another principal never obtains existing state. Failed/cancelled
turns release busy state. Sensitive location contexts suppress summaries/facts as before.
No raw transcript, SQL rows, vectors, coordinates or Admin credentials are stored.

Use one worker/instance or explicit sticky routing until shared state is separately
reviewed. There is no persistence, Admin identity system or implicit global singleton.

## Safe errors

| Failure | HTTP |
| --- | --- |
| Missing/invalid service authentication | 401 |
| Missing/invalid principal, malformed/extra request fields, wrong event zone | 422 |
| Oversized streaming request | 413 |
| Planner timeout/auth/unavailable | 503 |
| Invalid Planner response/identity/contract | 502 |
| Unsupported direct plan/constraint | 422 |
| DB unavailable or unsafe privilege boundary | 503 |
| Invalid execution plan | 502 |
| Conversation busy/capacity or request deadline | 503 |

Public messages are centrally fixed; original SQL/provider exception strings are not
returned or logged. Valid clarifications/unsupported conversation dispositions remain
successful semantic conversation responses, not fabricated empty result sets.

## Readiness capabilities

`query_enabled` is a last-successful-readiness indicator, initially false. `/ready`
checks Planner availability/v13 route and both database boundaries. It updates
structured_query/conversation/spatial; semantic_query always remains false. Optional
Geocoder readiness and inventory validation update named_place_resolution and
administrative_grouping. `/version` has no dependency calls. No Encoder or Qdrant calls
occur in readiness/query. Source/area preflights repeat before structured resolution
and SQL reads even if no prior /ready request occurred.
