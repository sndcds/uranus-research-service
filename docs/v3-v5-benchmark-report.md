# Controlled v3/v5 benchmark — measured report and preregistered protocol

This benchmark uses a frozen draft relevance dataset containing machine proposals plus manually calibrated scoring policy. It is suitable for provisional comparative evaluation, not final production approval.

Baseline inputs are pinned to merged PR #6, commit `dfa9f58ac8f22129ef4bf6aebf0c26f679bea517`.
All five input byte hashes are recorded in `benchmark/contracts/phase2b2c-input-sha256.json`.
Labels, calibration policy and query rubrics are immutable in this phase.

Before inference: 611 public snapshot events, 120 cases, 2352 machine-proposed judgments.
Include 105 cases with at least one judged positive. Exclude six unresolved no-hit
hypotheses and nine additional cases without positive judgments. No excluded case is
promoted to confirmed no-hit. Their rankings remain exploratory artifacts.

Both models receive the same deterministic `benchmark-public-snapshot-sections-v1`
documents. These contain captured title/subtitle/summary/description/types/genres/tags,
price type and occurrence-bound location/accessibility; absent production fields are not
invented. This is a controlled snapshot projection, not a claim of production document
parity. Chunking is exclusively the respective unchanged Encoder `/chunks` contract,
480 tokens with up to 64 overlap. Model tokenizers and actual chunks may differ.

Search uses exact Qdrant cosine search over every eligible chunk, without a similarity
threshold or arbitrary chunk top-K cap. Event eligibility uses the frozen predicate;
occurrence-specific evidence is further restricted to the matching captured occurrences.
Aggregate by maximum eligible chunk score per event; tie-break by event UUID, and by
point UUID within an event. Keep top 5/10 for ranking metrics. Full event scores support
within-model exploratory threshold analysis. No production relevance threshold changes.

Binary relevance is grade >=1. nDCG uses gain `2^grade-1` and log2 rank discount.
Unjudged remains unknown in artifacts. For **provisional pooled ranking metrics only**,
unjudged results contribute zero gain and retain their rank positions; Recall's denominator
contains only known positive judgments. This explicit pooling convention can penalize a
model for retrieving relevant but unjudged events. Report top-10 unjudged coverage and
inspect material changes. Do not infer true corpus recall or human-approved relevance.
Threshold precision/recall/F1/FPR uses judged pairs only, excluding unknown labels.

Preregistered absolute-drop gates are unchanged: macro Recall@10 <=0.02, MRR@10 <=0.03,
nDCG@10 <=0.03, every language/category Recall@10 <=0.05, and no previously successful
case losing all relevant top-10 hits. Missing required language coverage invalidates
comparison. All six no-hit hypotheses are excluded from these gates.

Threshold curves use a fixed grid [-1, 0, .05, ..., 1] separately per model. They are
**exploratory, unsplit**, with no tuned production recommendation: draft labels, small
subgroups and related translations do not justify an independent calibration/evaluation
claim. Raw cosine levels are not calibrated across models.

Both exact-model runs completed on the shared AI host with eight CPUs / eight intra-op threads each. **v5 provisionally fails one or more gates**: overall metrics improve, but atmosphere, outdoor, theatre, venue and the lost-all gate fail. No production approval or activation.

Material-case inspection is defined before results: loss of all relevant top-10 hits,
or an absolute deterioration of at least 0.10 in Recall@10, MRR@10 or nDCG@10.
These are inspection triggers only; they do not change the quality gates above.
Use the analogous improvement triggers and cover DE/DA/EN examples. Inspect returned
chunk text, boundaries, eligibility and existing labels without relabeling anything.

## Measured results — 20261006_8cpu_001

This benchmark uses a frozen draft relevance dataset containing machine proposals plus manually calibrated scoring policy. It is suitable for provisional comparative evaluation, not final production approval.

v5 provisionally fails one or more gates.

The 105 included cases use the frozen draft judgments. Six unresolved no-hit hypotheses and nine other cases without judged positives remain excluded from gates. All 120 queries were executed for each model.

| Metric | v3 | v5 | Delta |
| --- | --- | --- | --- |
| HitRate@10 | 0.6381 | 0.7429 | 0.1048 |
| HitRate@5 | 0.4667 | 0.5714 | 0.1048 |
| MRR@10 | 0.3225 | 0.4543 | 0.1318 |
| Recall@10 | 0.2550 | 0.2998 | 0.0447 |
| Recall@5 | 0.1471 | 0.1812 | 0.0341 |
| nDCG@10 | 0.2252 | 0.3038 | 0.0787 |

### Preregistered gates

| Gate | v3 | v5 | Delta | Pass? |
| --- | --- | --- | --- | --- |
| Recall@10 | 0.2550 | 0.2998 | 0.0447 | yes |
| MRR@10 | 0.3225 | 0.4543 | 0.1318 | yes |
| nDCG@10 | 0.2252 | 0.3038 | 0.0787 | yes |
| language:da:Recall@10 | 0.1428 | 0.2189 | 0.0761 | yes |
| language:de:Recall@10 | 0.3477 | 0.3832 | 0.0355 | yes |
| language:en:Recall@10 | 0.2122 | 0.2436 | 0.0314 | yes |
| category:accessibility:Recall@10 | 0.3697 | 0.4137 | 0.0440 | yes |
| category:ambiguous:Recall@10 | 0.2154 | 0.2487 | 0.0333 | yes |
| category:atmosphere:Recall@10 | 0.2457 | 0.1657 | -0.0800 | no |
| category:combined:Recall@10 | 0.2833 | 0.3500 | 0.0667 | yes |
| category:cultural_style:Recall@10 | 0.3375 | 0.5594 | 0.2219 | yes |
| category:exhibition:Recall@10 | 0.2173 | 0.2143 | -0.0030 | yes |
| category:family:Recall@10 | 0.1490 | 0.2077 | 0.0587 | yes |
| category:genre:Recall@10 | 0.4611 | 0.5500 | 0.0889 | yes |
| category:location:Recall@10 | 0.2201 | 0.2979 | 0.0778 | yes |
| category:multiple_results:Recall@10 | 0.1205 | 0.0727 | -0.0478 | yes |
| category:music:Recall@10 | 0.2237 | 0.2587 | 0.0350 | yes |
| category:outdoor:Recall@10 | 0.3750 | 0.2500 | -0.1250 | no |
| category:paraphrase:Recall@10 | 0.2500 | 0.3333 | 0.0833 | yes |
| category:readings:Recall@10 | 0.0000 | 0.2500 | 0.2500 | yes |
| category:theatre:Recall@10 | 0.2361 | 0.1597 | -0.0764 | no |
| category:venue:Recall@10 | 0.3389 | 0.2414 | -0.0975 | no |
| category:workshops:Recall@10 | 0.3929 | 0.5357 | 0.1429 | yes |
| lost-all-relevant cases | 0.0000 | 4.0000 | 4.0000 | no |

### Per-language

| language | Cases | v3 Recall@10 | v5 Recall@10 | v3 MRR@10 | v5 MRR@10 | v3 nDCG@10 | v5 nDCG@10 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| da | 27 | 0.1428 | 0.2189 | 0.1144 | 0.3810 | 0.0999 | 0.2567 |
| de | 47 | 0.3477 | 0.3832 | 0.4885 | 0.5694 | 0.3394 | 0.3759 |
| en | 31 | 0.2122 | 0.2436 | 0.2520 | 0.3436 | 0.1610 | 0.2356 |

### Per-category

| category | Cases | v3 Recall@10 | v5 Recall@10 | v3 MRR@10 | v5 MRR@10 | v3 nDCG@10 | v5 nDCG@10 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| accessibility | 7 | 0.3697 | 0.4137 | 0.1706 | 0.2560 | 0.2184 | 0.2590 |
| ambiguous | 5 | 0.2154 | 0.2487 | 0.6000 | 0.4200 | 0.2836 | 0.2693 |
| atmosphere | 5 | 0.2457 | 0.1657 | 0.1319 | 0.6000 | 0.1458 | 0.2307 |
| combined | 3 | 0.2833 | 0.3500 | 0.2004 | 0.5000 | 0.1142 | 0.3151 |
| cultural_style | 10 | 0.3375 | 0.5594 | 0.5600 | 0.7310 | 0.3804 | 0.5994 |
| exhibition | 8 | 0.2173 | 0.2143 | 0.3906 | 0.2135 | 0.1922 | 0.1382 |
| family | 12 | 0.1490 | 0.2077 | 0.4468 | 0.4704 | 0.2189 | 0.2713 |
| genre | 6 | 0.4611 | 0.5500 | 0.2349 | 0.3115 | 0.2575 | 0.3499 |
| location | 9 | 0.2201 | 0.2979 | 0.2009 | 0.6407 | 0.1941 | 0.3529 |
| multiple_results | 7 | 0.1205 | 0.0727 | 0.2131 | 0.2143 | 0.1089 | 0.1205 |
| music | 8 | 0.2237 | 0.2587 | 0.1137 | 0.5229 | 0.1551 | 0.3079 |
| outdoor | 1 | 0.3750 | 0.2500 | 0.5000 | 0.5000 | 0.3639 | 0.2342 |
| paraphrase | 7 | 0.2500 | 0.3333 | 0.2857 | 0.5238 | 0.2214 | 0.3777 |
| readings | 2 | 0.0000 | 0.2500 | 0.0000 | 0.0500 | 0.0000 | 0.0886 |
| theatre | 6 | 0.2361 | 0.1597 | 0.2000 | 0.2500 | 0.1608 | 0.1189 |
| venue | 6 | 0.3389 | 0.2414 | 0.5833 | 0.6833 | 0.3725 | 0.4441 |
| workshops | 3 | 0.3929 | 0.5357 | 0.5000 | 0.4861 | 0.4151 | 0.4244 |

### Corpus and actual chunks

| Measure | v3 | v5 |
| --- | --- | --- |
| Documents | 611 | 611 |
| Chunks | 1989 | 2080 |
| Chunks/document mean | 3.2553 | 3.4043 |
| Chunks/document p50 | 3.0000 | 3.0000 |
| Chunks/document p95 | 5.0000 | 5.0000 |
| Chunks/document max | 25.0000 | 25.0000 |
| Tokens/chunk mean | 117.0307 | 136.4601 |
| Tokens/chunk p50 | 17.0000 | 23.0000 |
| Tokens/chunk p95 | 462.0000 | 464.0500 |
| Tokens/chunk max | 480.0000 | 480.0000 |
| Characters/chunk mean | 467.5359 | 453.0159 |
| Characters/chunk p50 | 53.0000 | 55.0000 |
| Characters/chunk p95 | 1839.6000 | 1595.0500 |
| Characters/chunk max | 2345.0000 | 2381.0000 |

89 documents differ in chunk count; 181 differ in the sequence of actual chunk texts. Same chunk version label does not imply identical chunks. Both use the legitimate max-480/overlap-64 contract; document-to-chunk hash/token mappings are in the chunk-differences artifact.

### Ranking coverage and scores

| Measure | v3 | v5 |
| --- | --- | --- |
| No relevant result in top 10 | 38 | 27 |
| Zero returned events (all 120 cases) | 0 | 0 |
| Mean returned events (full ranking) | 584.0000 | 584.0000 |
| Mean best relevant rank (full ranking) | 26.0667 | 15.4571 |
| Unjudged top-10 slots (105 cases) | 874 | 839 |

Cosine scales below are model-specific, not cross-model calibrated confidence. Relevant/irrelevant distributions use judged pairs only.

| Model / population | Count | Mean | p50 | p95 | Min | Max |
| --- | --- | --- | --- | --- | --- | --- |
| v3 / top_score | 105 | 0.4800 | 0.4736 | 0.6072 | 0.2710 | 0.6990 |
| v3 / relevant_scores | 700 | 0.3271 | 0.3271 | 0.5255 | 0.0342 | 0.6364 |
| v3 / irrelevant_judged_scores | 1400 | 0.1935 | 0.1840 | 0.3729 | -0.0829 | 0.5552 |
| v5 / top_score | 105 | 0.5271 | 0.5294 | 0.6577 | 0.2886 | 0.7560 |
| v5 / relevant_scores | 700 | 0.3751 | 0.3789 | 0.5481 | 0.0849 | 0.7560 |
| v5 / irrelevant_judged_scores | 1400 | 0.2412 | 0.2235 | 0.4332 | -0.0039 | 0.6032 |

### Performance (isolated shared host)

All 120 sequential query timings; milliseconds. Total covers embedding, Qdrant and event aggregation, not precomputed eligibility or PostgreSQL rehydration. No production latency claim.

| Model / stage | Mean ms | p50 ms | p95 ms | Max ms |
| --- | --- | --- | --- | --- |
| v3 / embedding | 74.3711 | 72.3639 | 92.0719 | 152.6785 |
| v3 / qdrant | 20.7632 | 20.5265 | 25.0365 | 27.4840 |
| v3 / aggregation | 20.0578 | 19.5860 | 27.1195 | 30.7037 |
| v3 / total | 115.2736 | 114.3443 | 138.5508 | 202.4482 |
| v5 / embedding | 454.6565 | 390.0699 | 895.6261 | 2329.7974 |
| v5 / qdrant | 28.8236 | 25.4315 | 49.9747 | 126.9591 |
| v5 / aggregation | 20.7789 | 20.6006 | 29.5872 | 33.5284 |
| v5 / total | 504.3352 | 441.6433 | 935.5680 | 2379.0268 |

| Build measure | v3 | v5 |
| --- | --- | --- |
| chunking_seconds | 9.1078 | 11.4604 |
| embedding_seconds | 874.3627 | 2466.1650 |
| full_validation_seconds | 1.3878 | 1.4540 |
| passage_chunks_per_second | 2.2748 | 0.8434 |
| seconds | 887.1932 | 2481.5550 |

| Encoder process measure | v3 | v5 |
| --- | --- | --- |
| Loaded startup RSS (GiB) | 3.1956 | 2.8517 |
| End RSS (GiB) | 3.6758 | 2.9535 |
| Peak RSS (GiB) | 3.6758 | 3.7836 |
| Encoder CPU seconds | 4580.7700 | 19275.0200 |
| Mean CPU % (one core=100%) | 504.6033 | 756.1455 |

Memory rows above are GiB; CPU is Encoder PID only, with one logical CPU = 100%. Resource sidecars define loaded-startup and end-of-query steady-state RSS. Both encoders were limited to eight CPUs and 6 GiB RAM / 8 GiB RAM+swap, sequentially on a shared host. OS cache/swap and other workloads are uncontrolled.

### Cases losing all relevant top-10 results

- `historical-q29`: Participatory art workshops for young people
- `wheelchair-da`: Kulturtilbud med dokumenteret adgang for kørestole
- `dance-en`: A lively evening for dancing
- `concerts-en`: Concerts spanning different musical genres

### Measurement and inspection limits

The 874/1,050 v3 and 839/1,050 v5 unjudged top-10 slots are 83.24% and 79.90% respectively. Apparent relevance in these unknown results was not turned into new labels. See [all 30 material regression inspections and representative improvements](v3-v5-case-analysis.md). Small groups (outdoor: one case; atmosphere: five; theatre/venue: six each) make individual cases influential.

The loaded v5 startup RSS was measured after the one/eight-thread parity warmup; v3 had no equivalent inference warmup. Query timings for both models follow the entire corpus build. Peak RSS uses process-lifetime VmHWM, so it can include startup/parity before the sampled build/query interval; v5 sampled peak was 3,242,872,832 bytes (3.020 GiB). CPU time is only the Encoder PID during the measured driver interval. These are not cold-start or isolated idle steady-state comparisons.

The limited v5 parity probe passed (maximum absolute component difference 6.33e-8, vector L2 difference 5.38e-7; eight-thread repeat difference 0). The v3 eight-CPU rerun reproduced all 120 pilot rankings and scores exactly. Source hashes of the executed runner, evaluator and resource sampler match this repository. See [reproduction and resource-profile details](controlled-benchmark-reproduction.md) and the retained sidecars.

Full completion evidence: [Phase 2B.2c report](phase2b2c-completion-report.md). Threshold analysis remains [exploratory](v5-threshold-analysis.md); no production threshold was changed.
