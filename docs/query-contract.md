# Query and conversation contract

Internal service contract: `uranus-research-service-v1`; service version `0.1.0`.
Only `/health`, `/version`, `/ready`, and a **disabled** `/query` are exposed.
No successful Research response is fabricated in phase 1. A valid authenticated
POST `/query` returns HTTP 501 and `error.code=query_not_enabled`; malformed input
returns 422, oversized bodies 413. Generated schemas are committed in `contracts/service`.

```json
{"query":"Welche Veranstaltungen gibt es am Wochenende in Flensburg?","timezone":"Europe/Berlin","language":"auto","conversation_id":null,"location_context":null}
```

The request forbids extra keys, nonfinite values, blank/overlong queries, invalid
IANA zones and languages outside de/da/en/auto. Model, collection, SQL, backend,
provider and planner version are not request selectors. LocationContext preserves
Admin's coordinates/name/source shape and validates coordinate pairs. Query text
is not normalized silently. Browser requests still go solely to Admin.

## Future response mapping (not yet an implemented success endpoint)

| Current Admin response | Future service response | Future Admin proxy response |
| --- | --- | --- |
| ResearchExecutionResponse | versioned envelope: `schema_version`, `response` | unwrap `response` after validation |
| answer_text, language | unchanged inside response | unchanged |
| query, plan (original versioned planner envelope) | unchanged | unchanged |
| resolution, result, execution | unchanged | unchanged |
| sql_provenance | same allowlist/redaction | unchanged |
| observed_at, timezone, diagnostics | unchanged semantics | unchanged |
| conversation_id, conversation_summary | opaque ID; same version-specific exposure rules | unchanged |
| ConversationResponse (kind=conversation) | same alternative in response envelope | unchanged |
| SemanticResearchPage | separate future semantic endpoint | same existing browser shape |

Evidence is already carried by semantic result items; do not introduce a conflicting
parallel top-level evidence representation. Preserve existing needs-clarification,
unsupported, infrastructure failure and top-K/non-authoritative semantics. A missing
service is an explicit error, never an automatic local fallback.

Admin's current browser QueryRequest has query, conversation_id,
conversation_context and location_context. The future internal request adds timezone
and language from validated server configuration. It deliberately omits caller-owned
conversation_context for v13. Migration of v11/v12 browser contexts needs explicit
compatibility treatment rather than silently ignoring them. Existing Admin request,
execution and conversation response snapshots document these differences.

## Planner contract strategy

The source Admin setting defaults to `legacy` and explicitly supports v9–v13.
The modern conversational path is v13 when configured; no production configuration
was read for this phase-1 task. The new service expects **v13** by default and can
explicitly select v9/v10/v11/v12 for compatibility testing. There is no negotiated
fallback. Exact pinned Planner/Admin response schemas match for all five versions.
Enum ordering is canonicalized as a set, preserving every other JSON Schema keyword.

Per user decision, readiness checks Planner `/ready` plus OPTIONS on exactly the
selected `/vN/plan` (405 and Allow: POST). That attests route availability only.
Future actual replies must pass schema-version/prompt-version, original-query,
timezone and all existing Pydantic semantic validators. JSON Schema snapshots alone
do not capture those custom validators. Phase 1 exposes no method to execute plans
or accept an unvalidated planner response for research. Planner is unchanged.

## Conversation and principal design

Current Admin `ConversationStore` is process-local, TTL 1800 seconds, bounded to
256 entries/eight per session, with four bounded semantic summaries, pending
clarification, safe answer facts, language and a busy-turn flag. It stores no raw
transcript, SQL rows, embeddings or browser location coordinates. Current ownership
is a digest of the Admin credential; that coupling must not leave Admin.

Later Admin mints a domain-separated keyed pseudonym for an authenticated session
and sends it in a dedicated internal header, alongside a distinct service Bearer
credential. Use a dedicated principal derivation secret and include a caller/service
namespace. The browser cannot supply/override the header. The Research Service only
stores the pseudonym and random conversation handle; no session cookie, bearer token,
raw account ID or reversible credential. Rotate derivation keys by expiring handles.
Authentication and authorization remain Admin concerns.

Ownership mismatch/expiry, concurrency rejection, private-location state suppression
and no-transcript guarantees require regression tests during extraction. Process-local
state implies one instance or explicitly sticky routing until a reviewed shared
store exists. Phase 1 implements no conversation persistence or principal migration.
