# Phase-1 validation — 2026-10-05

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
