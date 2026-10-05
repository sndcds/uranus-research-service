# Jina v5 consumer migration — Phase 2B.1

The v5 consumer, isolated event build pipeline and internal retrieval are implemented.
The service calls Encoder HTTP only: no local weights, tokenizer, Torch or ONNX dependency.
Public semantic `/query`, Admin cutover and production reindex remain disabled.
See [implementation](phase2b1-semantic-index.md) and [live inventory](live-semantic-preflight.md).
The inspected live Admin embedding endpoint still reports v3 and is rejected by this client.

## Exact expected encoder space

- Service baseline: `uranus-research-encoder 0.2.0`.
- HTTP: `uranus-research-encoder-v1`, model `jina-v5`.
- Repository: `jinaai/jina-embeddings-v5-text-small`.
- Revision: `dd76d535f5447ca3897a9c893fb1e612ead98192`.
- Dimensions: 1024; chunks: `sections-480-overlap64-v2`.
- Embedding version:
  `dd76d535f5447ca3897a9c893fb1e612ead98192:native-qwen3-torch2.11.0-transformers5.17.0-peft0.21.1-cpu-eager-retrieval-query-document-last-token-l2-f32-d1024:sections-480-overlap64-v2`.

Native Qwen3, one retrieval LoRA, Query:/Document: prefixes, last-token pooling,
once-only float32 L2 normalization, 32768-token input limit. Those mechanics belong
solely to Encoder. The client checks exact repository/revision/dimension/chunk and
embedding version plus Torch backend, not just the `jina-v5` label. `/ready` lacks
repository/chunk fields, so those are verified at `/version`; common fields are
checked again in `/ready`. Unexpected types (including boolean dimensions) fail.
No ONNX-v5 dependency or inference is included.

## Original extraction map (status superseded by Phase 2B.1 report)

| Existing location | Migration responsibility |
| --- | --- |
| research/vector_models.py | replace active v3 registry/repository/revision/embedding-version with exact v5 metadata; do not relabel old vectors |
| research/vector_transport.py | switch model requests and entity guard; validate encoder version/readiness; add full collection manifest validation |
| research/semantic_contracts.py | register separate event/venue/organization v5 names; preserve document schemas/owner |
| services/semantic_search.py | fixed v5 consumer; preserve SQL eligibility/rehydration and context selection |
| research/vector_sync.py | update model guard, reject foreign spaces, preserve hashes/IDs/metadata-only changes/stale deletion |
| research/vector_index.py | v5 operator-only build jobs, complete snapshot reporting and separate build target |
| research/taxonomy.py, taxonomy_transport.py, taxonomy_index.py | separate taxonomy v5 collection and encoder metadata |
| services/taxonomy_resolution.py, research/taxonomy_policy.py | v5 consumer, new reviewed corpus/embedding-specific calibration; reject old policy |
| research/search_gateway.py | historical candidate-only v3 pilot; do not port as a fallback |
| research/vector_benchmark.py, taxonomy_benchmark.py | preserve reviewed judgments; add exact v5 provenance and same-corpus comparison |

The linked [audit inventory](extraction-inventory.json) lists individual imports and
source tests. Particularly affected: test_vector_index, test_vector_metadata,
test_semantic_knowledge_index, test_semantic_search, test_semantic_relevance,
test_semantic_genres, test_taxonomy_index, test_taxonomy_semantic,
test_taxonomy_flow and test_research_semantic_eligibility. Unit fixtures must update
identity deliberately; historical v3 reports must retain their original metadata.
The appended occurrence inventory below records exact source locations.

## Collection recommendation and controlled rollout

Use `kulturbytes_events_jina_v5_v1`, `kulturbytes_venues_jina_v5_v1`,
`kulturbytes_organizations_jina_v5_v1`, `kulturbytes_event_taxonomy_jina_v5_v1`.
Event retrieval is active in the normal code path; venue/organization have registered
index/evidence paths; taxonomy is activated only with a reviewed policy. Actual live
configuration was not inspected in phase 1. Legacy event pilot and project-knowledge
collections are distinct responsibilities; document them, do not blindly migrate them.

A later full build reads a bounded authoritative snapshot, constructs existing
public documents, uses Encoder's unchanged chunk-v2 contract, and writes deterministic
IDs into a new v5 build collection. Validate counts, manifests, owner/schema/model,
orphan reconciliation and smoke retrieval before any activation. Incremental jobs
reuse unchanged embeddings and update metadata independently. No job writes both
spaces unless explicitly designated as a controlled comparison job.

For v3/v5 comparison use the same source snapshot and reviewed relevant/graded IDs.
Record corpus/document hash, actual chunk hash/count, revision, embedding/chunk version,
collection, cases, recall@5/10, MRR@10, nDCG@10, hit rate@5/10 and latencies. New v5
tokenization/prefix counting can change chunk boundaries even with identical chunk
code. Thresholds must be remeasured; do not claim a quality gain from the model name.

An explicitly authorized cutover switches the service encoder expectation and all
applicable aliases together after successful validation/benchmarking. Rollback
restores the old matched consumer+encoder+alias set. Never send v5 queries to an old
v3 alias or upsert v5 vectors into v3 collections. Keep v3 collections, caches and
historical reports until separately authorized cleanup. No such operation happens
in phase 1.

## Model license

The [official model repository](https://huggingface.co/jinaai/jina-embeddings-v5-text-small)
identifies CC-BY-NC-4.0 for weights. Review those conditions before commercial use;
this document gives no legal assessment. Service code uses AGPL-3.0-only.

## Audited v3 source occurrences

Paths and line numbers at the pinned Admin commit (code/tests only):

- `backend/app/research/semantic_contracts.py`: 24, 25, 26.
- `backend/app/research/taxonomy.py`: 12, 15.
- `backend/app/research/taxonomy_index.py`: 84.
- `backend/app/research/taxonomy_transport.py`: 17.
- `backend/app/research/vector_index.py`: 49, 262, 264, 266.
- `backend/app/research/vector_models.py`: 18, 52, 53.
- `backend/app/research/vector_sync.py`: 97.
- `backend/app/research/vector_transport.py`: 93.
- `backend/app/services/semantic_search.py`: 34.
- `backend/app/services/taxonomy_resolution.py`: 49.
- `backend/tests/test_research_plan_execution.py`: 806, 808.
- `backend/tests/test_research_semantic_eligibility.py`: 60, 207.
- `backend/tests/test_semantic_genres.py`: 156, 172, 194, 306.
- `backend/tests/test_semantic_knowledge_index.py`: 28, 249, 271, 272, 277, 282, 500, 571, 632, 668, 681, 845, 855.
- `backend/tests/test_semantic_search.py`: 59, 98, 332, 336, 366, 821.
- `backend/tests/test_vector_metadata.py`: 236, 271.
