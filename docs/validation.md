# Phase-2B.2b ground-truth preparation — 2026-10-05

Final local suite: **404 passed, 2 optional real-Encoder tests skipped (34.13 s)**:
382 unit tests plus 22 disposable PostGIS/Qdrant/Admin parity integration tests.
The 25 new ground-truth tests cover schema/grade/review invariants, blinded pools,
source/document hashes, deterministic export, query groups, hard occurrence filters,
CSV import, schema snapshots and the actual committed public draft/report.
`--require-approved` correctly rejects the draft. No relevance labels were generated.

Locked sync, Ruff/format and upstream Admin/Planner/Encoder contract parity passed.
Live evidence is limited to read-only source checks and the user-authorized
`uranus_reader` export. Integration tests used local synthetic databases only, never
production credentials/data. No v3/v5 comparison or threshold measurement was run.
See [completion report](phase2b2b-completion-report.md) for counts and review gaps.
Implementation commit `6d54a11d8d8cb2610cc59064efe9b10c605591ff` passed both jobs in
[PR CI](https://github.com/sndcds/uranus-research-service/actions/runs/37352629018)
and [push CI](https://github.com/sndcds/uranus-research-service/actions/runs/37352574689).
CI retains its existing unit/Docker and PostGIS/Qdrant/pinned Admin jobs. Local offline
Docker build passed (`02e005d58a28`); the annotation coverage CLI succeeded as non-root
with network disabled and a read-only public-artifact mount. CSV newline normalization
was retested with all 25 annotation tests. Both disposable test containers were removed.
The ongoing review and current-head checks are on
[PR #5](https://github.com/sndcds/uranus-research-service/pull/5); no merge was performed.

# Phase-2B.2a-runtime validation — 2026-10-05

Runtime refactor only; no benchmark/ground-truth work or live access. Final local
suite: **379 passed, 2 optional real-Encoder tests skipped (13.16 s)**, comprising
357 unit and 22 actual disposable PostGIS/Qdrant/Admin parity tests. Locked sync,
Ruff, format, diff checks and upstream contract parity passed. Local Docker build
and networkless non-root import/gate smoke passed.

The operation-count regression performs 100 internal retrieves with a failing
`Qdrant.points()` spy after initial full validation: zero additional scans. Real
Qdrant integration verifies direct manifest retrieval, manifest-inclusive counts,
sealed-write rejection, and no scan during an internal retrieve. TTL, concurrent
readiness, restart, cancellation, identity/count/manifest changes and strict hit
validation have dedicated tests. SQL freshness and public semantic rejection remain.

Full details and remote CI evidence: [completion report](phase2b2a-runtime-completion-report.md).
The historical Phase-2B.1 measurements below are unchanged and are not measurements
of the new request path. No production performance or quality claim is made.

# Phase-2B.1 validation — 2026-10-05

**338 passed** in the combined final local run: 314 unit/contract tests and 24
integration tests, including two optional real Encoder tests. No skipped tests in
that run. Python 3.13, locked dependencies, disposable PostGIS 16/3.5 and Qdrant 1.19.0.
Admin reference commit remains `340df4684611dbc4b8ec73a7702f1fad2ae1973c`.

Commands completed successfully:

```sh
uv sync --locked
uv run --no-sync ruff check .
uv run --no-sync ruff format --check .
# TEST_DATABASE_URL: empty disposable loopback research_phase2b1_test
# TEST_QDRANT_URL: disposable loopback port 16333
# TEST_ENCODER_URL: optional local v5 container on loopback port 16335
# ADMIN_PARITY_ROOT: untouched pinned local Admin checkout
uv run --no-sync pytest -q
git diff --check
uv run --no-sync python scripts/build_wheelhouse.py
uv build --wheel --out-dir wheelhouse
docker build --network=none -f deploy/Dockerfile -t uranus-research-service:phase2b1 .
```

Local image build succeeded, image prefix `d12dc3aa55c9`, non-root runtime unchanged.
No deployment or service restart. CI now includes disposable Qdrant with its image
digest pinned; optional real-weight tests skip unless explicitly configured. Hosted
CI status is recorded in the PR; local success is not a claim about a remote run.

## Evidence boundaries

- Unit: bounded Encoder/Qdrant transports, strict v5 version/backend/vector validation,
  required manifest fields/types, missing/wrong manifests, deterministic IDs, foreign
  owners/versions/entities, hashes/context checks, reconciliation/partial-snapshot
  safety, threshold and independently computed metric examples. Semantic readiness
  cannot block structured readiness. Public semantic `/query` remains rejected.
- Real PostGIS/Qdrant + synthetic Encoder: full build, unchanged repeat, source text
  change/reembedding/stale deletion, missing-manifest recovery, SQL-eligible filtering,
  authoritative public-status recheck, stale evidence, tampered payloads and dimensions,
  immutable reports and fixture teardown. Encoder calls assert zero checked-out DB
  connections. Existing structured SQL/Planner-fixture/Admin parity also passed.
- Differential semantic parity: untouched pinned Admin and this service independently
  extract the same synthetic PostGIS source and area documents; complete JSON matches.
- Real Jina-v5: local existing Encoder image, read-only offline model cache, exact
  repository/revision/version/backend, normalized 1024 query and passage vectors,
  exact repeated-query determinism, actual chunking and full test build/benchmark.
  Encoder code was not changed and weights were not loaded in this service.
- Live: read-only inventory only, separately documented in
  [live-semantic-preflight.md](live-semantic-preflight.md). No live inference.

## Actual local real-weight measurements

Artifacts (immutable JSON):
[index build](../validation/index-build-test_real_15d52723843e.json),
[retrieval benchmark](../validation/benchmark-test_real_15d52723843e.json).
Two public events / five chunks / nine synthetic goldens. Three language smoke queries
also completed with validated evidence. All six reported retrieval quality metrics
are 1.0 on this tiny fixture. **No representative quality or superiority claim.**
No controlled same-corpus v3 baseline was run; there is no measured v3/v5 result.

| Measurement | Local observed value |
| --- | ---: |
| Full build including smoke | 5.156 s |
| Passage embedding time | 3.400 s |
| Build Qdrant time | 0.129 s |
| Build throughput (whole job) | 0.970 chunks/s |
| Consumer/test-runner CPU time | 0.338 s |
| Consumer/test-runner peak RSS | 111,304,704 bytes |
| Mean semantic retrieval | 0.530 s |
| Mean query embedding | 0.458 s |
| Mean Qdrant including validation | 0.013 s |
| Mean rehydration + context selection | 0.037 s |

CPU/RSS describe the service/test-runner process, not Encoder process usage. Values are
single local runs on synthetic data, not production capacity/latency estimates.
No warm/cold distribution, independently judged corpus, controlled v3 baseline or
Encoder peak-RSS instrumentation was completed; those remain explicit validation gaps.

---

# Phase-2A validation — 2026-10-05

Service 0.2.0, contract uranus-research-service-v1. Structured execution only;
Admin remains unchanged. No production deployment, grants, Qdrant operations,
Encoder inference or reindex. Historical Phase-1 results follow separately below.

## Final local checks

Python 3.13.15, uv 0.12.5, Linux x86_64, branch feat/phase2a-structured, based on
service main dc59671. Source pins/hashes are in phase2-port-manifest.json and
contracts/sources.json. The isolated test database was loopback-only, named
research_phase2a_test, in an owned disposable PostGIS 17/3.5 container. Credentials
and rows were synthetic. TEST_DATABASE_URL below was exported for that test database;
it was not a production DSN.

```sh
UV_CACHE_DIR=/tmp/uv-research-service uv sync --locked --offline
UV_CACHE_DIR=/tmp/uv-research-service uv run --no-sync ruff check .
UV_CACHE_DIR=/tmp/uv-research-service uv run --no-sync ruff format --check .
TEST_DATABASE_URL="$TEST_DATABASE_URL" \
  ADMIN_PARITY_ROOT=/home/awendelk/git/uranus-admin .venv/bin/pytest -q
UV_CACHE_DIR=/tmp/uv-research-service uv run --no-sync python scripts/verify_upstream_contracts.py \
  --admin /home/awendelk/git/uranus-admin \
  --planner /home/awendelk/git/uranus-research-planner \
  --encoder /home/awendelk/git/uranus-research-encoder
git diff --check
```

Final full suite: **273 passed in 19.84 seconds**, no skips. Lockfile sync, Ruff,
format and upstream Admin/Planner/Encoder snapshot parity passed. Ordinary tests
block socket connections; integration tests explicitly use the guarded disposable DB.
Sandbox-denied loopback/cache attempts were rerun with the authorized local test
connection and writable uv cache; no safety guards were relaxed.

Coverage includes real PostgreSQL/PostGIS execution, enforced read-only transactions,
privilege rejection (including NOINHERIT ownership and missing schema USAGE), closed
v13/custom validators, semantic rejection before SQL, safe conversation routing/state,
principal isolation/concurrency, AnswerFacts, SQL provenance, provider failures,
request/response limits and log privacy.

**31 Golden Cases** execute both the new service and untouched Admin commit
340df4684611dbc4b8ec73a7702f1fad2ae1973c against identical synthetic rows, Planner
fixtures, date/timezone and geographic inventory. Independent expected results and
full differential responses pass, including counts, identities/order, resolved filters,
SQL provenance, AnswerFacts, answer text, clarification and conversation state. Only
random conversation IDs, observation timestamps and timings are excluded. The Admin
test bridge adapts only its metadata connection to the separate test reader.

The actual Planner HTTP client is exercised with controlled HTTP responses, including
strict failure cases. These results do **not** measure a live Planner model's language
quality, real deployed source DDL, retrieval quality or production capacity.

## Final Docker checks

```sh
UV_CACHE_DIR=/tmp/uv-research-service uv run --no-sync python scripts/build_wheelhouse.py
UV_CACHE_DIR=/tmp/uv-research-service uv build --wheel --out-dir wheelhouse
docker build --network=none -f deploy/Dockerfile -t uranus-research-service:phase2a .
python /tmp/phase2a-docker-smoke.py
```

The second command refreshed the service wheel after the final privilege-check change.
Locked/hash-checked dependency wheels were unchanged. Build passed; final image:
`sha256:a1873cfa60898782429218784ae7fb2a728327a9fea177aa8b37fbf51e978313`.

The local smoke script created and removed its own container with network none,
UID/GID 10001, read-only root, dropped capabilities, no-new-privileges, 16 MB tmpfs,
256 MB memory, 1 CPU and 64 PID limit, using a mounted synthetic key. It checked:

- /health: 200, exact liveness body; unauthenticated /version: 401.
- Authenticated /version: 200, service 0.2.0, structured capability unverified and
  semantic capability false without configured dependencies.
- /ready: 503 without upstream configuration; /query: 422 without principal,
  503 with principal but unavailable Planner. No invented results.
- UID 10001, denied root write, inspected container restrictions, no key in logs.

This smoke verifies packaging/security and fail-closed missing-dependency behavior.
Successful structured execution is covered by the host PostGIS integration suite,
not claimed as a live-upstream Docker test. GitHub workflow definitions add separate
unit/build and disposable-PostGIS/Admin-parity jobs; local results are not CI results.

## Remaining operational work / Phase 2B

Provision reviewed reader roles and verify deployed DDL, configure live Planner and
optional Geocoder/complete administrative inventory, then run live-language and
capacity checks. No Admin adapter/cutover is activated. Semantic retrieval, Jina-v5
inference, new Qdrant collections, reindex, evidence/threshold benchmarks and v3/v5
comparison remain Phase 2B. ONNX-v5 and any v3 cleanup are separate work.

---

# Historical Phase-1 validation — 2026-10-05

This is infrastructure/contract validation, not Research execution, a retrieval
benchmark or production validation. The new service runs alongside unchanged Admin
execution. No PostgreSQL/Qdrant calls, collection changes, model inference, reindex,
service restart or deployment were performed.

## Local checks

Python 3.13, uv, Linux x86_64. Commands run in the new service checkout:

```sh
uv sync --locked
uv run --no-sync ruff check .
uv run --no-sync ruff format --check .
uv run --no-sync pytest -q
```

Results: lockfile resolved successfully; Ruff passed; format check passed;
**126 tests passed in 1.70 seconds** in the final checkout. Unit tests actively prohibit socket connections.
Coverage includes strict requests/configuration, metadata/version compatibility,
Planner route selection, safe transport failures, auth-before-parsing, streaming
limits, timeouts, concurrency, log privacy and contract parity. Upstream responses
are synthetic fixtures; these are not real-model or live-provider results.

An additional check exported actual schemas/metadata from the pinned sibling source
checkouts, each using its own installed environment:

```sh
uv run --no-sync python scripts/verify_upstream_contracts.py \
  --admin /path/to/uranus-admin \
  --planner /path/to/uranus-research-planner \
  --encoder /path/to/uranus-research-encoder
```

Admin, Planner and Encoder parity passed. Source commits and snapshot hashes are in
`contracts/sources.json`. Planner/Admin response schemas v9–v13 matched separately
exported snapshots. This does not attest schemas in any deployed service.

A separate local ASGI check against the existing Planner route implementation passed
for all five routes v9–v13: GET /ready plus OPTIONS /vN/plan, HTTP 405 with Allow POST.
An injected provider rejected inference. No network or planning call occurred. As
selected for phase 1, runtime readiness checks route availability; validation of
actual plan responses (including custom semantic validators) belongs to phase 2.

## Docker

The original network-install Docker build failed because the local Docker daemon
could not reach package servers. The final build explicitly prepares locked,
hash-checked wheels on the host and installs them without Docker build networking:

```sh
uv run --no-sync python scripts/build_wheelhouse.py
docker build --network=none -f deploy/Dockerfile -t uranus-research-service:phase1 .
```

Both commands succeeded. Validated image:
`sha256:35c5359d30da8cb05122c0517112abe5829c5270b3355f4a899ec42c85f5c305`.
Wheelhouse is ignored by Git. Rebuild it after code/lock changes; use the target
Python/OS/architecture. Docker requires the base image to be locally available or
pulled separately; `--network=none` isolates build steps, not base-image acquisition.

An ephemeral container was run with network `none`, UID/GID 10001, read-only root,
all capabilities dropped, no-new-privileges, a 16 MB /tmp tmpfs, 256 MB memory,
1 CPU and 64 PID limit. A read-only synthetic key file was mounted. Local requests
from inside that container verified:

| Check | Observed |
| --- | --- |
| /health without credentials | 200, exactly `{"status":"ok"}` |
| /version without credentials | 401 |
| /version with internal key | 200, Jina v5, query_enabled=false |
| /ready without configured upstream keys | 503, fail closed before network |
| Valid /query | 501, no fabricated result |
| UID and filesystem write probe | UID 10001, root write denied |
| Container inspection | read-only root, network none, capabilities dropped |
| Logs | synthetic key absent |

Only this validation container was removed afterward. This is a disabled-path
smoke test, not a live upstream readiness success or a capacity benchmark.

## Outstanding work

Phase 2 must port and test actual Planner response validation, deterministic SQL
execution, evidence safety, indexing and conversation semantics with explicit
injected dependencies. Then add the Admin adapter and contract parity for its real
proxy response. Provision reviewed read-only DB access and separate v5 collections;
validate manifests, perform real corpus reindex/quality/capacity benchmarks and
prepare an explicitly approved cutover/rollback. None of these are activated here.
ONNX-v5 and any cleanup of v3 data remain separate tasks.
