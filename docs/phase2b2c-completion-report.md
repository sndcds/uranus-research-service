# Phase 2B.2c completion report

This benchmark uses a frozen draft relevance dataset containing machine proposals plus manually calibrated scoring policy. It is suitable for provisional comparative evaluation, not final production approval.

**Provisional verdict: v5 provisionally fails one or more gates.**

## 1. Frozen inputs

Baseline: merged PR #6, `dfa9f58ac8f22129ef4bf6aebf0c26f679bea517`. All five inputs remain byte-identical to that commit.

| Input | SHA256 |
| --- | --- |
| `benchmark/ground-truth-v1.jsonl` | `a72b04ca44655ca4e8ba456e8d9698ff6ebbe47e1dde54f075780c9e6e4a8b53` |
| `benchmark/snapshots/public-events-20261005/events.jsonl` | `2de49bc71942926e953f4de76d4b5dbcfe1780a6a2a20ee2b0feb6fa97cbf7f1` |
| `benchmark/annotation/manual-calibration-v1.json` | `179376bf2f01e6fcd2df447e0085a6cd340dd96b9eabeffc37f2f67f25f44ba5` |
| `benchmark/annotation/machine-proposals-v1.jsonl` | `ecf09f60fb6a31a96f5ecd21b39a7686df6f12726a814e7d764e443e54fbbc48` |
| `benchmark/annotation/machine-rubrics-v1.json` | `ef0ea425dc00ffcf9471573a9e76304faebfbb75ee3aa674c64d6555c6e273f3` |

`source_snapshot_hash` (canonical public records): `295d51592050b67be40d7a4de8dd3ac5885fbe2562700b3e3578f8b107785029`. The file byte hash is separately listed above.

## 2–3. Exact v3/v5 contracts

| Pin | v3 | v5 |
| --- | --- | --- |
| service_version | `0.1.0` | `0.2.0` |
| contract_version | `uranus-research-encoder-v1` | `uranus-research-encoder-v1` |
| model | `jina-v3` | `jina-v5` |
| model_repository | `jinaai/jina-embeddings-v3-hf` | `jinaai/jina-embeddings-v5-text-small` |
| model_revision | `d18862d9a48706220815554fac3ebb4dfa46fc28` | `dd76d535f5447ca3897a9c893fb1e612ead98192` |
| dimensions | `1024` | `1024` |
| chunk_version | `sections-480-overlap64-v2` | `sections-480-overlap64-v2` |
| backend | `onnx-merged` | `torch` |
| runtime | `onnxruntime-1.30.0-cpu` | `torch-2.11.0+cpu-transformers-5.17.0-peft-0.21.1-cpu` |
| embedding_version | `d18862d9a48706220815554fac3ebb4dfa46fc28:native-transformers5.17.0-retrieval-normalized-f32:sections-480-overlap64-v2` | `dd76d535f5447ca3897a9c893fb1e612ead98192:native-qwen3-torch2.11.0-transformers5.17.0-peft0.21.1-cpu-eager-retrieval-query-document-last-token-l2-f32-d1024:sections-480-overlap64-v2` |

Source commits, graph/model file digests, adapters, prefixes and pooling are pinned under `benchmark/contracts/`. All ten v3 artifacts and six v5 artifacts were verified before inference. v3 uses the existing production-compatible image/model files in a new isolated container; no production collection or endpoint supplies baseline results. v5 uses native Torch with the retrieval adapter, Query:/Document: prefixes, last-token pooling, float32 and one L2 normalization. No ONNX-v5 or Encoder source change.

## 4. Corpus

611 public events, 1,134 captured occurrences, 671 source rows. Snapshot `public-events-20261005`, captured 2026-10-05T17:42:15.403053Z, reference time `2026-10-05T00:00:00+02:00`, Europe/Berlin. This task reads the frozen export; it does not query a live database.

Both models use the identical deterministic `benchmark-public-snapshot-sections-v1` document projection. Missing production fields are not invented. Eligibility follows only the case’s frozen hard predicates, all on one occurrence; no implicit future-date restriction or new Planner interpretation is added. Occurrence-context chunks are restricted to eligible occurrences. This is not a claim of production-document or live SQL parity.

## 5. Chunking differences

v3: 1989 chunks; v5: 2080 chunks. 89 documents differ in chunk count and 181 differ in actual chunk text sequence. Each unchanged Encoder provides its own legitimate 480-token / 64-overlap chunking. The common version label does not guarantee common boundaries.

The per-document hashes, chunk hashes and token counts are in `benchmark/results/chunk-differences-20261006_8cpu_001.json`; token/character distributions are in the model reports and benchmark report.

## 6. Build manifests

| Model | Isolated collection | Manifest SHA256 | Corpus SHA256 |
| --- | --- | --- | --- |
| v3 | benchmark_events_jina_v3_20261006_8cpu_001 | a97a0a4be3a0541724662d8832609bf9561c3edd736311c55d8e3b798f82a577 | b9fe823e48e6a89c366db6d20a87e3bc6b077861333198d26c45f3858b8e059a |
| v5 | benchmark_events_jina_v5_20261006_8cpu_001 | 492657baf001f7ccc81b06fbe197e3eec7ee727813308333976edd3774507bd6 | 68dcbb605671f66a0be8ca066d87ad7d05139c17d5dc91b5638382cc88e32dd7 |

Both builds passed complete collection validation (size/distance, manifest, point count, every deterministic point/payload and stored vector). No active collection was modified. Collections are separate model generations, with no aliases. Resource and environment sidecars record the bounded isolated setup.

## 7. Evaluator

`controlled-draft-retrieval-v1`; exact cosine search over eligible chunks; event score=max eligible chunk score; ties by event UUID (point UUID within event). Same projection, source/query/judgment hashes, reference time, event/occurrence eligibility, aggregation, K and evaluator are asserted. Re-evaluation of immutable reports is deterministic. Full event rankings are retained, with no duplicate event from multiple chunks.

Binary relevant means grade >=1. nDCG uses 2^grade−1. Unjudged remains unknown in raw artifacts; provisional pooled ranking metrics assign zero gain while preserving rank, and Recall denominators contain known positives only. Threshold curves omit unjudged pairs. These conventions limit any quality inference.

## 8. Included/excluded cases

120 executed queries per model; 105 included in provisional gates. Included languages: DA=27, DE=47, EN=31.

| Excluded case | Reason |
| --- | --- |
| historical-q23 | no_judged_positive_not_confirmed_negative |
| historical-q24 | no_judged_positive_not_confirmed_negative |
| wheelchair-en | no_judged_positive_not_confirmed_negative |
| dance-da | no_judged_positive_not_confirmed_negative |
| saturday-de | no_judged_positive_not_confirmed_negative |
| saturday-da | no_judged_positive_not_confirmed_negative |
| saturday-en | no_judged_positive_not_confirmed_negative |
| cityart-da | no_judged_positive_not_confirmed_negative |
| open-da | no_judged_positive_not_confirmed_negative |
| koreanopera-de | unresolved_no_hit |
| koreanopera-da | unresolved_no_hit |
| koreanopera-en | unresolved_no_hit |
| harpsichord-de | unresolved_no_hit |
| harpsichord-da | unresolved_no_hit |
| harpsichord-en | unresolved_no_hit |

## 9–12. Overall, language, category and gate results

| Gate | v3 | v5 | Delta | Pass? |
| --- | --- | --- | --- | --- |
| Recall@10 | 0.2550 | 0.2998 | +0.0447 | yes |
| MRR@10 | 0.3225 | 0.4543 | +0.1318 | yes |
| nDCG@10 | 0.2252 | 0.3038 | +0.0787 | yes |
| language:da:Recall@10 | 0.1428 | 0.2189 | +0.0761 | yes |
| language:de:Recall@10 | 0.3477 | 0.3832 | +0.0355 | yes |
| language:en:Recall@10 | 0.2122 | 0.2436 | +0.0314 | yes |
| category:accessibility:Recall@10 | 0.3697 | 0.4137 | +0.0440 | yes |
| category:ambiguous:Recall@10 | 0.2154 | 0.2487 | +0.0333 | yes |
| category:atmosphere:Recall@10 | 0.2457 | 0.1657 | -0.0800 | no |
| category:combined:Recall@10 | 0.2833 | 0.3500 | +0.0667 | yes |
| category:cultural_style:Recall@10 | 0.3375 | 0.5594 | +0.2219 | yes |
| category:exhibition:Recall@10 | 0.2173 | 0.2143 | -0.0030 | yes |
| category:family:Recall@10 | 0.1490 | 0.2077 | +0.0587 | yes |
| category:genre:Recall@10 | 0.4611 | 0.5500 | +0.0889 | yes |
| category:location:Recall@10 | 0.2201 | 0.2979 | +0.0778 | yes |
| category:multiple_results:Recall@10 | 0.1205 | 0.0727 | -0.0478 | yes |
| category:music:Recall@10 | 0.2237 | 0.2587 | +0.0350 | yes |
| category:outdoor:Recall@10 | 0.3750 | 0.2500 | -0.1250 | no |
| category:paraphrase:Recall@10 | 0.2500 | 0.3333 | +0.0833 | yes |
| category:readings:Recall@10 | 0.0000 | 0.2500 | +0.2500 | yes |
| category:theatre:Recall@10 | 0.2361 | 0.1597 | -0.0764 | no |
| category:venue:Recall@10 | 0.3389 | 0.2414 | -0.0975 | no |
| category:workshops:Recall@10 | 0.3929 | 0.5357 | +0.1429 | yes |
| lost-all-relevant cases | 0.0000 | 4.0000 | +4.0000 | no |

Full Recall@5/@10, HitRate@5/@10, MRR@10 and nDCG@10, including language/category tables, are in [the benchmark report](v3-v5-benchmark-report.md). No gates were adjusted after inference. Per-case rankings/scores, best relevant ranks, known relevant IDs and metric deltas are in the comparison JSON.

## 13. Threshold analysis

[Exploratory threshold report](v5-threshold-analysis.md): fixed candidate grid independently per model; precision, recall, F1, FPR and language/category curves use judged pairs only. No independent calibration/evaluation split is claimed for this correlated draft dataset. Existing production threshold behavior is unchanged. Insufficient evidence for a production v5 threshold recommendation.

## 14. Latency and resources

Embedding, Qdrant, aggregation and total retrieval have separate mean/p50/p95/max measurements for all 120 queries. Build throughput and full-validation durations are also recorded. Encoder PID RSS/CPU is sampled separately from driver CPU; v3 and v5 run sequentially with equal container limits. See measured tables and resource sidecars.

The shared host has swap activity and uncontrolled other workloads; there is no production performance claim. v3 retains ONNX threads 8/1, v5 benchmark torch threads=8. v5 loaded-startup RSS follows its limited thread-parity warmup; v3 has no equivalent inference warmup. VmHWM is process-lifetime and may include loading/warmup before sampling. Loaded-startup and end-of-query RSS are measured; pre-load startup RSS and an independent idle steady-state experiment were not measured. Frozen eligibility is precomputed; there is no PostgreSQL rehydration latency in this isolated ranking benchmark.

## 15–16. Regressions and improvements

See [case inspection](v3-v5-case-analysis.md). Material changes were preregistered as loss of all relevant top-10 hits or absolute Recall@10/MRR@10/nDCG@10 change >=0.10. Inspection uses frozen query wording, both top chunks/boundaries, model-specific scores, identical eligibility and unchanged labels. Suggested causes are observational hypotheses, not new labels.

## 17–18. Data quality and unresolved no-hit handling

All 2,352 judgments remain machine proposals plus 280 manually calibrated scoring-policy pairs, not human-approved Ground Truth. No approvals, labels, calibration scores or rubrics changed. Many retrieved events are unjudged; score separation and pooled recall cannot establish true corpus precision/recall. Translation groups are related, and small categories amplify individual-case changes.

All six koreanopera/harpsichord DE/DA/EN hypotheses remain unresolved and excluded from Recall/MRR/nDCG gates. Their thresholded return counts are exploratory, not confirmed false positives. Nine further cases without judged positives are also excluded, not silently treated as true no-hit cases.

## 19. Provisional verdict and validation

v5 provisionally fails one or more gates. This does not grant production approval.

Local: locked offline sync; Ruff; format; 465 tests passed, 24 integration/optional-model tests skipped; diff check; frozen byte comparisons. CI separately runs disposable PostGIS/Qdrant, pinned Admin differential parity, contract/unit tests and the offline Docker build. Real v3/v5 inference was manual on the isolated AI-host environment, with exact pins and full collection validation. See [validation evidence](validation.md).

## 20. Remaining activation blockers and boundaries

- Human approval and expanded judgments for retrieved but unjudged candidates; resolve all six no-hit hypotheses against the eligible corpus.
- Review material regressions and improvements without post-hoc relabeling to improve model results.
- A separately reviewed calibration/evaluation split and measured v5 relevance policy.
- Production document/SQL integration validation, intended v5 endpoint deployment approval and capacity planning.
- Separate authorization for production build, alias/cutover, Admin adapter and semantic activation.

`semantic_query=false` remains literal. No production deployment, production service restart, live DB write, production Qdrant write, live reindex, alias switch, Admin cutover, Planner/Encoder source change, human approval or v3 cleanup occurred. Only dedicated benchmark containers/collections were created; those Encoder containers and isolated Qdrant are stopped after the run.
