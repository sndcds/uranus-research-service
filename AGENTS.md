# Development boundaries

This repository is phase 2A of a staged extraction from uranus-admin. Read README.md,
`docs/extraction-audit.md` and `docs/phase2-structured-execution.md`. `/query` executes
only validated Planner-v13 structured plans and safe conversation acts. Semantic
requests stop before normalization/resolution/SQL. Admin remains unchanged.

- No production deployments, service restarts, database grants, reindexes or alias
  switches without explicit task authorization. Never delete v3 collections/caches.
- Admin owns identity, login/session/CSRF, workflow tables, UI and suggestion learning.
- Planner interprets language into closed plans; no facts, tools, databases or vectors.
- Encoder stays a stateless offline HTTP model service; never load weights or remote
  code here. No ONNX-v5 dependency.
- PostgreSQL/PostGIS is authoritative; Qdrant is retrieval evidence only. SQL
  must be bounded, allowlisted, parameterized and read-only. Never execute model SQL.
- Fail closed on configuration/provider/contract failures. No response repair,
  older-contract fallback, automatic reindex or mixed v3/v5 query/write path.
- Contracts are pinned JSON snapshots with provenance and parity tests, not runtime
  Python imports from sibling repositories. Preserve the ported custom semantic
  validators; JSON Schema is not a substitute for every validator.
- Planner readiness uses GET /ready and OPTIONS /v13/plan without inference. Every
  actual plan response additionally passes the original closed v13 semantic validators.
- Query text, credentials, cookies, coordinates, vectors, raw provider replies and SQL
  bind values never enter logs. Provider errors have fixed safe messages.
- Do not copy the Admin research directory wholesale. Audit each component before
  extracting it; preserve tested semantics and explicit dependencies.
- Python 3.13/uv/FastAPI/Pydantic/httpx conventions. Use explicit SQLAlchemy/asyncpg source and area readers; no Admin writer engine.
- Checks: `uv sync --locked`, `uv run ruff check .`, `uv run ruff format --check .`,
  `uv run pytest -q`, `git diff --check`. Build deploy/Dockerfile locally when changed.
- Tests use synthetic upstream responses and pinned contracts. PostGIS tests require
  an empty loopback database with an explicit `_test` suffix; fixtures alone create
  and remove schemas/roles. Never use production credentials or disable these guards.
- Run `pytest -m integration` with TEST_DATABASE_URL and ADMIN_PARITY_ROOT for actual
  SQL and cross-repository parity. The reference Admin commit is pinned in the port
  manifest. Do not replace differential execution with copied expected mock results.
- No FastAPI Request/app.state or Admin auth dependencies in execution. Conversation
  ownership is a validated opaque X-Research-Principal, separate from the service key.
- Clearly distinguish unit, real PostGIS, controlled Planner, Docker and live evidence.
- Commit focused Conventional Commits and prepare a reviewable PR; do not merge unless asked.
