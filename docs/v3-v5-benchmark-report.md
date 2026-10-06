# Controlled v3/v5 benchmark — preregistered protocol

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

Real-model execution and measured results: pending. No production approval or activation.

Material-case inspection is defined before results: loss of all relevant top-10 hits,
or an absolute deterioration of at least 0.10 in Recall@10, MRR@10 or nDCG@10.
These are inspection triggers only; they do not change the quality gates above.
Use the analogous improvement triggers and cover DE/DA/EN examples. Inspect returned
chunk text, boundaries, eligibility and existing labels without relabeling anything.
