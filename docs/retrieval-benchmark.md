# Human-reviewed evaluation preparation (Phase 2B.2b)

The new [public snapshot and annotation workflow](phase2b2b-ground-truth.md) is
separate from the historical pipeline benchmarks below. It contains 611 real public
events and 120 reviewable query proposals, with **zero approved cases**. It is a
**draft**, not usable ground truth or an official v3/v5 evaluation result.

`benchmark/ground-truth-v1.jsonl` uses the new snapshot-bound human-review schema.
Do not feed it into the old synthetic `index benchmark` evaluator, convert null grades
to zero, or infer relevance from pooled rankings. The approval gate and coverage report
must pass before a later explicit evaluator adapter/controlled comparison is introduced.
No such adapter, model comparison, threshold tuning or semantic activation is part of
this phase. [Annotation guidelines](retrieval-annotation-guidelines.md) define review,
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
end-to-end, embedding, Qdrant (including compatibility scan), and rehydration latency.
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

A controlled v3 report must be exported by a separately isolated v3 benchmark runner
using the same public documents, SQL filters and report fields. This repository does
not run a v3 encoder or access production v3 vectors. Existing live v3 collection
scores are not a valid comparison baseline. **No measured v3/v5 comparison result is
available yet**; the comparison's unit tests use explicitly artificial rankings.

## Measurement limits

Optional real encoder uses a loopback nondefault port, exact v5 version, query and
passage validation and deterministic repeat. Model weights remain in the separate
Encoder container. CI uses the synthetic HTTP encoder and requires no weights.
Build reports record consumer-process wall/CPU time and peak RSS (in pytest this is the
whole test runner); these exclude encoder-process CPU/RSS. Chunks/sec includes source,
chunking, validation and smoke work. No production performance or v5 superiority claim.
See [validation](validation.md) and checked-in artifacts for actual local measurements.
