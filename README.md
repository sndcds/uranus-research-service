# Uranus Research Service

Internal Research orchestration boundary for Kulturbytes/Uranus. **Phase 1**:
configuration, authenticated metadata endpoints, dependency compatibility clients,
contract snapshots and extraction design. `/query` validates its closed request
and returns HTTP 501 `query_not_enabled`; it performs no Research execution.

```text
Browser → uranus-admin (identity, UI, workflows)
                     ↓ internal authenticated HTTP (future)
              uranus-research-service
                ├─ Planner: language → validated plan
                ├─ PostgreSQL/PostGIS: authoritative facts (future)
                ├─ Qdrant: non-authoritative retrieval (future)
                └─ Encoder: offline Jina-v5 embedding runtime
```

This repository provides the orchestration boundary. It does not provide an Admin
UI, LLM provider, model runtime, vector database, source database or autonomous agent.
Admin still executes Research. No consumer or production service is switched here.

## Local use

Python 3.13 and uv, following the neighboring repositories:

```sh
uv sync --locked
# Set protected key files and dependency origins; see .env.example.
uv run uranus-research-service
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
```

No `.env` is loaded implicitly. `RESEARCH_API_KEY_FILE` is preferred over the
environment key; the same file convention applies to `PLANNER_API_KEY` and
`ENCODER_API_KEY`. Files must be absolute paths. File read errors fail startup;
there is no credential fallback. No keys or model weights belong in the image.

`GET /health` is unauthenticated process liveness. `/version`, `/ready` and `/query`
require one internal Bearer key. Browser cookies and Origin headers are rejected.
The executable listens on port 6338; use loopback publication as shown in Compose.

## Readiness and current limitation

The encoder is pinned to service 0.2.0's `uranus-research-encoder-v1`, Jina v5,
revision `dd76d535f5447ca3897a9c893fb1e612ead98192`, 1024 dimensions and
`sections-480-overlap64-v2`. Exact embedding-version and Torch compatibility are
checked using metadata only. There is no embedding or model download.

Planner readiness checks `/ready` and sends `OPTIONS` to the configured
`/v9/plan`–`/v13/plan` route, requiring HTTP 405 and `Allow: POST`. This verifies
availability of the configured route without any inference. It does **not** attest
the running response schema. The user selected this phase-1 policy; full validation
of actual plan responses against the pinned contracts belongs to phase 2. No fallback
to another route/version is attempted, and Planner itself remains unchanged.
Even with compatible dependencies, readiness includes `query_enabled: false`.
PostgreSQL and Qdrant are not configured or contacted in phase 1.

See [extraction audit](docs/extraction-audit.md), [query contract](docs/query-contract.md),
[database boundary](docs/database-boundary.md), [Qdrant boundary](docs/qdrant-boundary.md),
[v5 migration](docs/jina-v5-consumer-migration.md) and
[validation](docs/validation.md). Snapshot provenance is in `contracts/sources.json`.

## Container build

Prepare locked/hash-checked wheels on Python 3.13 Linux for the target architecture,
then build without Docker network access:

```sh
uv run python scripts/build_wheelhouse.py
docker build --network=none -f deploy/Dockerfile -t uranus-research-service:phase1 .
# Provide protected key files, then use deploy/compose.example.yml.
```

The wheelhouse is ignored by Git; it contains the service wheel and dependencies
selected from uv.lock, never credentials or model artifacts. Rebuild it after source
or lockfile changes. The Docker build installs with `--no-index` and hash verification.
The image runs as UID 10001 and supports read-only root plus a small /tmp tmpfs.

## License

Service code: AGPL-3.0-only, matching the existing Uranus repositories; see LICENSE.
Jina v5 weights are separate and published under CC-BY-NC-4.0. Review the model's
license conditions before commercial use. This repository includes no model weights
and makes no legal assessment of a deployment.
