# Phase 2B.2a-runtime completion report

Date: 2026-10-05. Implementation: `01c2a62a17562c6904f4b9807391efa772526b16`,
based on merged Phase 2B.1 `4a956f1a414d1d69f1ce67fe38624f471783b136`.
[Review PR #4](https://github.com/sndcds/uranus-research-service/pull/4).
This runtime-only task supersedes the earlier benchmark-dependent stop for this
narrow scope; no benchmark data, judgments, runners or thresholds were changed.

1. **Old O(N) behavior:** every internal `QdrantClient.search()` called full
   validation, including all-point scroll, payload validation and corpus hashing.
2. **New request behavior:** cached verified state is required. Collection info and
   one retrieve-by-ID manifest request precede search; no query can initiate a full
   scan, including on a cache miss, expiry or mismatch.
3. **VerifiedSemanticGeneration:** frozen, instance-owned dataclass containing all
   requested identity, schema, model, corpus, count and validation-time fields.
   `ResearchRuntime.semantic_generation` exposes that runtime's state. No persistent
   or module-global trust; full validation is its only publishing path.
4. **Manifest digest:** canonical UTF-8 JSON SHA-256 over every validated manifest
   field; independent of dictionary order and Python object hash. Determinism tested
   against a fixed known digest.
5. **Full-validation triggers:** initial/expired/invalidated semantic readiness,
   explicit `index validate`, build completion and restart. All original full checks
   remain, plus strict integer chunk indexes and a final metadata/manifest recheck.
   The operator report now includes safe identity, digest, counts, duration and status.
6. **Cheap check:** require the fixed collection, 1024/Cosine, exact reserved manifest
   ID, closed manifest/exact pins, entity/build, digest and point count. Actual Qdrant
   retrieve-by-ID and manifest-inclusive count semantics passed integration tests.
7. **TTL:** ten minutes measured monotonically; cheap checks cannot renew it. This
   bounds validation freshness without full scans at every readiness probe. Expired
   queries fail; only readiness/operator work revalidates.
8. **Invalidation:** collection disappearance, vector contract changes, missing or
   modified manifest, count changes, invalid hits, full-validation failure/cancellation
   and maintenance writes clear trust. Semantic readiness becomes false; structured
   readiness and the literal-false public semantic capability remain independent.
9. **Immutable generation:** ordinary maintenance refuses any completion marker,
   including malformed markers and markers validated by another process. New data
   requires a new build ID. Existing isolated endpoint/build/alias guards remain.
   Only explicit disposable `test_recovery=True` exercises sealed-build recovery;
   there is no CLI or live override. External writer exclusion remains an operator
   responsibility; cheap checks cannot detect every same-count out-of-band mutation.
10. **Concurrency:** an async instance lock serializes verification. Ten concurrent
    readiness calls share one initial scan. Cancellation invalidates state and releases
    the lock. No automatic recovery is performed inside a query.
11. **Hit validation:** every result checks UUID and deterministic point ID, eligible
    entity, owner, embedding identity/schema, chunk kind/index/text/hash and contexts.
    Duplicate IDs/invalid scores fail closed. No relaxation of evidence safety.
12. **SQL freshness:** eligibility, authoritative rehydration and current public
    document/context matching are unchanged. A test confirms stale current-document
    evidence is rejected even with an unchanged valid collection manifest. Existing
    whole-corpus SQL document extraction remains a separate scaling limitation.
13. **Performance regression:** a mandatory failing `points()` spy surrounds 100
    complete internal retrieves after one full validation. Observed: one initial scan,
    100 query-time manifest checks, 100 queries, zero further scans. The same spy also
    guards a real disposable-Qdrant/PostGIS retrieve. This proves operation-count
    behavior, not production latency, throughput or retrieval quality.
14. **Tests:** final local suite **379 passed, 2 skipped in 13.16 seconds**: 357 unit
    tests and 22 integration tests. Only two optional real-Encoder tests were skipped;
    no model was loaded. Includes 31 structured Admin differential goldens, semantic
    document parity, full-validation failures, real SQL/Qdrant evidence freshness,
    generation expiry/mismatch/restart, concurrency and immutable-write guards.
    Locked dependency sync, Ruff, formatting, diff checks and upstream
    Admin/Planner/Encoder contract parity passed. Admin reference remains
    `340df4684611dbc4b8ec73a7702f1fad2ae1973c`; Encoder remains
    `1938c72caa6102452ae0afa18ef86d9a95ead878`.
15. **CI:** existing workflow is unchanged: unit/contracts/Ruff/format/locked
    dependencies/offline Docker, plus disposable PostGIS/Qdrant and pinned Admin
    parity. Both jobs passed in the implementation commit's
    [PR CI run](https://github.com/sndcds/uranus-research-service/actions/runs/37348577926)
    and [push CI run](https://github.com/sndcds/uranus-research-service/actions/runs/37348514726).
    Current-head results remain visible on PR #4. No deployment workflow was added.
16. **Docker:** local offline build succeeded as
    `uranus-research-service:phase2b2a-runtime`, image `4149b96d5850`. The new service
    wheel used the existing locked, hash-checked dependency wheelhouse. A networkless
    container confirmed generation-module import, 600-second TTL, semantic false and
    UID 10001. Disposable PostGIS 16/3.5 and Qdrant 1.19.0 were loopback-only test
    containers with synthetic credentials/data; no live service was accessed.
17. **Remaining activation blockers:** representative reviewed ground truth,
    controlled same-corpus v3/v5 comparison, measured threshold review, intended v5
    Encoder endpoint and production capacity validation remain separate work.
    Operational enforcement of immutable generations and a separately authorized
    activation/cutover are still required. No claim of v5 quality superiority or
    production readiness follows from this refactor.

No live access/writes, production deployment, live reindex, alias change, service
restart, Admin cutover, semantic activation or v3 cleanup. No Planner, Encoder or
Admin changes. Public semantic query stays disabled. This PR is not a deployment or
merge authorization.

See [generation validation](semantic-generation-validation.md) for the full trust
model, failure behavior and maintenance boundary.
