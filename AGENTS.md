# Development boundaries

This repository is phase 1 of an extraction from uranus-admin. Read README.md and
`docs/extraction-audit.md` before changes. Current behavior is health/version/strict
dependency readiness and an explicitly disabled query contract. Do not imply that
planned execution already runs.

- No production deployments, service restarts, database grants, reindexes or alias
  switches without explicit task authorization. Never delete v3 collections/caches.
- Admin owns identity, login/session/CSRF, workflow tables, UI and suggestion learning.
- Planner interprets language into closed plans; no facts, tools, databases or vectors.
- Encoder stays a stateless offline HTTP model service; never load weights or remote
  code here. No ONNX-v5 dependency.
- PostgreSQL/PostGIS is authoritative; Qdrant is retrieval evidence only. Future SQL
  must be bounded, allowlisted, parameterized and read-only. Never execute model SQL.
- Fail closed on configuration/provider/contract failures. No response repair,
  older-contract fallback, automatic reindex or mixed v3/v5 query/write path.
- Contracts are pinned JSON snapshots with provenance and parity tests, not runtime
  Python imports from sibling repositories. Preserve custom semantic validators when
  execution is ported later; JSON Schema is not a substitute for every validator.
- Phase-1 Planner readiness is the user-selected route check, not full running-schema
  attestation: GET /ready and OPTIONS on the exact versioned route, without inference.
- Query text, credentials, cookies, coordinates, vectors, raw provider replies and SQL
  bind values never enter logs. Provider errors have fixed safe messages.
- Do not copy the Admin research directory wholesale. Audit each component before
  extracting it; preserve tested semantics and explicit dependencies.
- Python 3.13/uv/FastAPI/Pydantic/httpx conventions. Keep dependencies minimal; add
  SQLAlchemy/asyncpg only with actual database execution in a later phase.
- Checks: `uv sync --locked`, `uv run ruff check .`, `uv run ruff format --check .`,
  `uv run pytest -q`, `git diff --check`. Build deploy/Dockerfile locally when changed.
- Tests use synthetic upstream HTTP responses and pinned contracts, never production
  services. Clearly distinguish unit, live, Docker and quality benchmark evidence.
- Commit focused Conventional Commits and prepare a reviewable PR; do not merge unless asked.
