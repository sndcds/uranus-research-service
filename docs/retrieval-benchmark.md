# Phase 2B.2c controlled draft comparison

An explicitly authorized provisional comparison now has a separate
[operator and frozen protocol](v3-v5-benchmark-report.md). It uses the machine-proposal
artifact plus scoring policy, never converts the original null human judgments to zero,
and does not grant human approval. Both exact-model runs are complete: v5 provisionally fails the gates despite higher aggregate metrics. See the [completion report](phase2b2c-completion-report.md), [case inspection](v3-v5-case-analysis.md), [exploratory thresholds](v5-threshold-analysis.md) and [reproduction guide](controlled-benchmark-reproduction.md). The old synthetic evaluator below is unchanged.

This benchmark uses a frozen draft relevance dataset containing machine proposals plus manually calibrated scoring policy. It is suitable for provisional comparative evaluation, not final production approval.

# Human-reviewed evaluation preparation (Phase 2B.2b)

The new [public snapshot and annotation workflow](phase2b2b-ground-truth.md) is
separate from the historical pipeline benchmarks below. It contains 611 real public
events and 120 reviewable query proposals, with **zero approved cases**. It is a
**draft**, not usable ground truth or an official v3/v5 evaluation result.

`benchmark/ground-truth-v1.jsonl` uses the new snapshot-bound human-review schema.
Do not feed it into the old synthetic `index benchmark` evaluator, convert null grades
to zero, or infer relevance from pooled rankings. The approval gate and coverage report
are still required for a human-ground-truth claim. No adapter, model comparison,
threshold tuning or semantic activation was part of Phase 2B.2b. Phase 2B.2c separately
authorizes the explicitly provisional draft comparison described above. [Annotation guidelines](retrieval-annotation-guidelines.md) define review,
no-hit confirmation, hard eligibility, grouping and unjudged-result handling.

The nine cases below are classified **synthetic_pipeline_goldens**. Historical
900-result exports are **historical_unjudged**, used only as candidate-ID/query sources.
Neither is silently promoted into human-approved relevance.

# Retrieval benchmark

`tests/fixtures/retrieval_goldens.json` contains nine **synthetic** goldens: DE/DA/EN,
accessibility, location and descriptive questions. Two public events plus one draft
are created by the guarded PostGIS fixture. The optional real-weight test adds a
relaxed-jazz description and step-free venue access, then restores both fields.
These are pipeline goldens, not a representative or independently judged quality set.

Cases accept id, query, language, expected_event_ids, optional graded_relevance (0–3)
and category. UTF-8 JSON/JSONL, at most 1,000 cases/8 MB; IDs unique. Reports store
case IDs, ranked event IDs, eligibility hashes and timings; query prose stays in the
explicit input file and is never logged.

Metrics are macro-averaged Recall@5/10, HitRate@5/10, MRR@10 and nDCG@10 (gain 2^grade−1,
log2(rank+1) discount). Unjudged results have zero gain; expected IDs default to grade 1.
Duplicate result IDs fail. Each run records candidate/returned counts, best score,
end-to-end, embedding, Qdrant (request-time generation verification), and rehydration latency.
The current internal retrieval uses the preserved v3 relevance threshold.

## Registered comparison gates

Before measurement: macro Recall@10 drop ≤0.02, MRR@10 and nDCG@10 drop ≤0.03;
DE/DA/EN and accessibility/location/descriptive subgroup Recall@10 drop ≤0.05.
No previously successful case may lose every relevant top-10 result. Missing category
or language coverage fails. These are proposed conservative engineering gates, not
statistical confidence bounds. Taxonomy is inactive and excluded; activate only with
its own dataset/calibration.

```sh
uv run uranus-research-service index compare --cases goldens.json \
  --v3 controlled-v3.json --v5 controlled-v5.json --output comparison.json
```

Comparison consumes separately recorded runs; no normal request ever dual-queries.
It recomputes both metrics using the same evaluator. Require identical source snapshot
hash, query-set hash, reference time, case IDs, per-case eligibility hash and document
hashes. Require model/revision/embedding_version/collection attribution plus per-document
chunk hashes/counts and average/max token counts. Different chunk hashes are reported,
not hidden by an equal chunk-version label. `benchmark.run_benchmark` verifies the
source hash against the collection and checks it again after the run.

At the end of Phase 2B.1, no measured v3/v5 result or exact isolated v3 runner was
available; those unit tests use artificial rankings. The separate Phase 2B.2c runner
now indexes the same frozen public snapshot for both models and applies identical
snapshot predicates; it does not access production v3 vectors or load model weights
in the Research Service. Its reports use a separate versioned schema. Existing live
v3 collection scores remain an invalid comparison baseline.

## Measurement limits

Optional real encoder uses a loopback nondefault port, exact v5 version, query and
passage validation and deterministic repeat. Model weights remain in the separate
Encoder container. CI uses the synthetic HTTP encoder and requires no weights.
Build reports record consumer-process wall/CPU time and peak RSS (in pytest this is the
whole test runner); these exclude encoder-process CPU/RSS. Chunks/sec includes source,
chunking, validation and smoke work. No production performance or v5 superiority claim.
See [validation](validation.md) and checked-in artifacts for actual local measurements.
