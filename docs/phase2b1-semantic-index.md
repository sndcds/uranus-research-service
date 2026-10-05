# Phase 2B.1: isolated semantic event indexing

The public `/query` semantic gate remains closed. `semantic_query` and
`semantic_query_enabled` are literal false; no environment flag enables them.
`semantic_index_ready` is separate, optional and false unless an explicitly configured
build passes Encoder metadata/readiness, collection dimensions/distance, manifest,
point ownership/identity, payload hash and full corpus/count verification. Structured
readiness remains independent of Encoder/Qdrant. `/version` reports expected v5 pins,
configured event collection name and semantic readiness. The subsequent runtime refactor
uses a ten-minute verified-generation cache: queries/readiness check collection info
and the reserved manifest directly; only initial/expired/invalidated readiness or an
explicit operator validation performs a full scan. See
[generation validation](semantic-generation-validation.md).

## Reviewed extraction

Source: Admin `340df4684611dbc4b8ec73a7702f1fad2ae1973c`.
[Port provenance](phase2b1-port-manifest.json) records reviewed module hashes.
Ported public builders/contracts, evidence contexts, evidence selection/explanations,
relevance policy, event snapshot SQL and reconciliation semantics. The local tokenizer
and legacy transport/index CLI were not copied. `vector_documents` retains the pure
public field builder needed by `event-public-v4`; its old intermediate event-public-v1
object is never an index destination. Only semantic documents may enter reconciliation.

- **Event:** active internal retrieval/build path; `event-public-v4` unchanged.
- **Venue/organization:** reviewed v1 payloads/builders/names retained; no build CLI or
  query dispatch in this phase. Existing live collections establish existence, not
  continued use by this service. Admin's normal semantic search dispatch is event-only.
  No speculative full reindex of those entities.
- **Taxonomy:** Admin has a semantic resolver and configured v3 policy, but this
  service's Phase-2A taxonomy resolution remains deterministic SQL. Semantic taxonomy,
  its transport and its v3 calibration are deliberately not ported. Future name reserved
  in the reindex plan; no v5 calibration or compatibility is asserted.
- Pure event time helper and complete SQL eligibility were selectively ported.
  Source and area readers retain the existing effective privilege checks.
- Encoder wire models/validators are local code plus pinned JSON snapshots from
  encoder commit `1938c72caa6102452ae0afa18ef86d9a95ead878`; no sibling runtime import.

## Runtime boundaries

Internal `retrieve_plan` revalidates the closed v13 envelope, normalizes using explicit
`allow_semantic=True`, resolves hard constraints, then invokes `retrieve`. Default
normalizer/capability calls remain semantic-disabled, as do the public coordinator
and structured executor. Low-level `retrieve` accepts validated resolved internal
filters for isolated tests/benchmarks; it does not accept caller-selected collections.

Complete SQL eligibility (maximum 10,000 events; overflow fails) precedes inference.
Empty eligibility makes no Encoder/Qdrant calls. All read snapshots close before HTTP.
Qdrant receives the entire eligible UUID set plus fixed owner/entity/version filters.
A maximum of 50 candidate chunks is requested. Public facts and selected occurrence
come from a fresh PostgreSQL snapshot using the original rehydration SQL.

Evidence must have the expected entity/owner/model/version/schema, valid public text,
matching content hash and explicit contexts. Context selection follows authoritative
venue/space/occurrence selection. Additionally, chunk text/kind/contexts must occur in
freshly rebuilt public sections in the same rehydration snapshot. Self-consistent but
stale Qdrant evidence is discarded. The fresh snapshot currently extracts the bounded
whole public event corpus; optimize only with parity tests before larger deployment.

Threshold is unchanged: `max(0.10, best_context_valid_score * 0.40)`. These are inherited
**v3-calibrated** constants, not a v5 quality certification. No user rollout follows
from smoke tests or the two-event benchmark.

## Operator use

```sh
# Protected environment/files: RESEARCH_API_KEY, ENCODER_API_KEY,
# QDRANT_API_KEY, RESEARCH_DATABASE_URL, RESEARCH_AREA_DATABASE_URL.
# Fixed origins: ENCODER_URL, QDRANT_URL. No implicit dotenv.
uv run uranus-research-service index plan --build-id test_trial --output validation/plan-trial.json
uv run uranus-research-service index build --isolated --build-id test_trial --output validation/index-build-trial.json
uv run uranus-research-service index validate --build-id test_trial --output validation/validate-trial.json
uv run uranus-research-service index benchmark --build-id test_trial \
  --cases tests/fixtures/retrieval_goldens.json --build-report validation/index-build-trial.json \
  --reference-time 2026-10-05T00:00:00+00:00 --output validation/benchmark-trial.json
```

Use the build report's reference_time when benchmarking a CLI build. CLI uses the
current clock; tests use a fixed reference. The fixture goldens require their documented
synthetic database, not arbitrary live data. A process lock prevents concurrent jobs
on one operator host. Multiple operator hosts are unsupported.

Writes require **all** of: maintenance client, `--isolated`, literal loopback IP,
nondefault explicit Qdrant port, `test_` build ID, no alias pointing at the collection.
This intentionally conservative phase has **no production override**. Operator must
still ensure the endpoint is disposable; a loopback proxy is not proof of isolation.
Never direct these commands at live endpoints or production readers.

Builds extract a complete public snapshot, close DB connections, call Encoder `/chunks`,
inspect existing owned v5 points, plan new/changed/metadata/unchanged/stale changes,
embed two passages per batch, upsert, replace metadata and delete stale chunks.
Sealed generations now reject writes; changed data requires a new build ID. Interrupted
unsealed builds lack readiness and may resume with the same build ID and a fresh report
path. Completion-marker removal/reconciliation of sealed generations is restricted to
explicit disposable recovery tests, with no CLI override. Only the planner supports partial
snapshots; production-facing build orchestration requires complete snapshots.

After payload verification, write the manifest, validate the collection, execute fixed
DE/DA/EN smoke retrieval, and exclusively create an immutable JSON report. Failures
produce a safe failure report when its destination is not already occupied. A failure
after sealing invalidates local trust but never deletes the sealed marker. Reports
contain hashes/counts/timings, not prose, vectors, credentials, coordinates or SQL binds.
No alias switch is exposed; the maintenance method explicitly rejects it. A future
reviewed blue/green operator command may implement it under separate authorization.
