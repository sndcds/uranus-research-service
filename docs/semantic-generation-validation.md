# Semantic generation validation

The public semantic query capability remains literal false. This internal refactor
changes validation scheduling, not relevance policy, SQL eligibility or evidence
freshness. There is no deployment, activation, live indexing or alias operation.

## Full validation and verified state

`QdrantClient.validate()` remains the explicit full-validation entrypoint. It reads
collection dimensions/distance, scrolls every point with the existing bounds,
validates the closed manifest with exact v5 pins, validates every point's owner,
entity, public payload, chunk, content hash, contexts and deterministic UUID, and
verifies document/chunk counts and the canonical persisted corpus hash. Foreign
points fail. The collection count includes the reserved manifest point.

Only successful full validation followed by a cheap identity/count recheck publishes
`VerifiedSemanticGeneration`. The frozen dataclass records entity, collection, build,
manifest digest, corpus and source snapshot hashes, model/version/revision,
dimensions/distance, chunk/document versions, owner, point count and UTC validation
time. Values come from the validated manifest; no untrusted defaults are supplied.
The state is private process trust, not a serializable permission or caller input.
`ResearchRuntime.semantic_generation` exposes the runtime-owned client's state;
there is no module singleton or persisted trust across restarts.

The digest uses the existing canonical SHA-256 implementation: UTF-8 JSON, sorted
keys, compact separators, `ensure_ascii=False`, `allow_nan=False`. It includes all
validated manifest fields, including creation time and source snapshot identity.

## Cheap validation and query behavior

After complete SQL eligibility and query embedding, search requires fresh verified
state. It performs exactly two bounded metadata operations:

1. GET the fixed collection's information; require unnamed 1024-dimensional Cosine
   vectors and the verified point count, including the one manifest point.
2. POST retrieve-by-ID to `/collections/<fixed-name>/points` for **only**
   `00000000-0000-0000-0000-000000000001`, without vectors. Require one exact ID,
   closed manifest, exact pins/entity/build, and the verified manifest digest.

There is no scroll or corpus hashing in this path. Missing, expired or mismatching
trust fails closed and clears cached verification. It never triggers full validation,
repair, writes or reindex inside the query. Empty SQL eligibility still avoids all
Encoder and Qdrant operations. The check's cost does not depend on collection size;
Qdrant retrieval and SQL execution have their own costs.

Every returned hit separately passes UUID/deterministic-ID, eligibility, owner,
entity, model/version/schema, chunk kind/index/text/hash and evidence-context checks.
Duplicate IDs and invalid scores fail closed. Invalid hits invalidate semantic trust.
Current PostgreSQL rehydration and current public section/context matching are
unchanged. Valid hashes or cached collection trust never substitute for that freshness
check. The existing bounded whole-corpus SQL document extraction is unchanged and
is not claimed to have constant cost.

## Readiness, TTL and concurrency

Initial semantic readiness checks Encoder compatibility/readiness, then full Qdrant
validation. Later readiness checks verify Encoder and use the cheap generation check.
Full validation repeats only on initial state/process restart, ten-minute TTL expiry,
known invalidation, explicit `index validate`, or build completion. A cheap mismatch
fails that readiness call; a subsequent readiness call may perform full validation.

The **600-second monotonic TTL** bounds trust freshness without imposing full scans
on ordinary frequent health probes. It is not refreshed by cheap checks. UTC time is
recorded for diagnostics only, so wall-clock changes do not extend trust. Expired
queries fail closed; readiness performs recovery. TTL is not an allowance for stale
hit evidence. There is no new timer/background task.

An instance-local async lock serializes full validation and cheap checks. Concurrent
readiness callers share the first successful full validation rather than scanning in
parallel. Failure or cancellation clears trust and releases the lock. Explicit
operator calls intentionally request a fresh full validation. Counters record full
validation attempts, manifest-check attempts and generation invalidations, without
query text, payloads, vectors or high-cardinality labels.

Semantic capability derives from Encoder readiness plus a current verified generation;
expiry/invalidation immediately makes `semantic_index_ready=false`. Structured
readiness is independent and `semantic_query=false` under every outcome. The existing
readiness deadline still applies: an oversized/slow full scan fails closed.

## Immutable generations and maintenance

A sealed generation must never be changed in place. New data requires a new build ID
and a later separately authorized cutover. Maintenance methods now reject any existing
reserved completion marker, even before local full validation or if the marker is
malformed. This is stricter than allowing writes until a local validation succeeds.
The guard survives process restart because it reads Qdrant rather than a local flag.
It covers build entry, upsert, payload replacement, delete (including the marker),
and manifest writes. Existing alias, isolated-loopback, nondefault-port and `test_`
build-ID guards remain. No production override or CLI recovery flag was added.

Unsealed interrupted builds can still resume. Reconciliation/recovery tests explicitly
construct `QdrantMaintenance(test_recovery=True)` on a disposable target; alias guards
still apply and writes invalidate local verification. This constructor-only exception
is for destructive fixture exercises, never an active collection or runtime. Direct
low-level transport calls used to inject corruption in tests are not a maintenance
workflow. A failed smoke after sealing records failure and invalidates local trust;
it does not remove the sealed manifest. Use a new generation for an ordinary retry.

This is an operator trust boundary, not protection against an administrator or another
writer with unrestricted Qdrant credentials. Operators must exclude external/in-flight
writers before validation and use the existing single-operator process lock. Multiple
writer hosts are unsupported. A same-count payload/vector mutation that leaves the
manifest unchanged cannot be detected by metadata alone; no such guarantee is claimed.
Returned payload corruption is checked per hit, stale evidence against PostgreSQL,
and corpus drift by subsequent full validation. Never mutate sealed generations or
reuse a build name; external mutation violates the trust assumption.

## Operator report and regression evidence

`uranus-research-service index validate --build-id <id> --output <new-report.json>`
performs full validation and exclusively writes a safe report: status, collection,
build ID, manifest digest, documents, chunks, total point count and validation duration
(seconds). It contains no secrets, vectors, raw manifest or source prose.

`tests/test_semantic_generation.py` installs a failing `points()` spy after initial
validation and successfully runs 100 complete internal retrieves: one initial scroll,
100 cheap checks, 100 queries, zero further scans. Disposable Qdrant/PostGIS tests also
spy on a real internal retrieve and verify retrieve-by-ID and count semantics. These
are operation-count regressions, not production latency or quality benchmarks.
