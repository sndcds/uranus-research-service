# Category coverage blind review v1

## Goal and baseline

This preparation-only follow-up targets **all 20 historically evaluable queries** in
outdoor, theatre, venue and accessibility, using stored build `20261006_8cpu_001`.
Baseline main is `b86edbffd312fb11e7fe3248d0f2eb593799894a` (PR #13).
[The category reassessment](v3-v5-category-reassessment-after-machine-review.md)
found outdoor/theatre/venue unchanged because the earlier 77-pair pool supplied no
new applicable coverage; accessibility remained insufficient evidence. Atmosphere's
regression disappeared under that limited machine expansion, so atmosphere is
excluded here. There is **no atmosphere overlap**.

Historical verdict remains `v5 provisionally fails one or more gates`.

> This benchmark uses a frozen draft relevance dataset containing machine proposals plus manually calibrated scoring policy. It is suitable for provisional comparative evaluation, not final production approval.

No judgments, metric reevaluation or new quality verdict are produced here.

## Selection

Rules are fixed in `category_coverage_review.RULES` and copied into
`review-plan.json`. Both models contribute symmetrically. For each evaluable case:

1. Include the union of both stored Top-10 event lists.
2. Include every historical positive, and retain already sealed machine positives
   from PR #12 as additional references. The latter are applicable to `wheelchair-da`
   only; their grades never enter the blind package. No positive is lost for being
   outside Top-20. Retention is not endorsement of a historical or machine grade.
3. Include historical grade-zero references within either tie-inclusive Top-20.
4. Extend both prefixes to Top-20 if any signal holds: Top-10 Jaccard ≤ 0.25;
   a known-positive rank gap ≥ 10; either model loses a known-positive Top-10 hit;
   absolute historical case contribution to the category Recall@10 delta ≥ 0.02;
   or at least five Top-10 entries of either model are historically unjudged.
5. Extend each selected prefix through its entire exact stored-score tie block.
   No rounding, score recalibration, ranking reordering or alternative tie-breaking.

The contribution is the original per-case v5−v3 Recall@10 difference divided by
that category's historically evaluated case count. Existing evaluator `metrics()`
is reused only to compute this selection signal. No new evaluation definition or
judgment-dependent tuning is introduced. All 20 cases trigger Top-20 expansion.

Explicit known-positive/negative references are not additional ranking cutoffs.
Negative references can include events beyond a raw Top-20 cutoff when tied there.
`selection-report.json` preserves complete tie-block membership; `provenance.json`
records source ranks/scores, old grades, selection reasons and tie references per
pair. These files are **operator-only**, outside `reviewer/`.

## Pool size

**1,506 independent query×event tasks**: 36 outdoor, 182 theatre, 286 venue and
1,002 accessibility. Languages by task: DE 476, DA 410, EN 620. This exceeds a small
manual batch because complete score ties must be retained: 12 cases have cutoff
ties and four accessibility cases are flagged `large_tie_pool`.

Disjoint accounting: 134 v3-only Top-10, 134 v5-only Top-10, 66 shared Top-10,
80 additional positives, 19 additional historical zeros, 285 other Top-20 additions,
and 788 remaining tie additions. These groups are assigned in this order to avoid
double counting. Tie blocks can also contain references accounted as positives or
zeros; full membership is recorded separately.

| Case | Category | Pairs | v3-only 10 | v5-only 10 | Shared 10 | Extra positive | Extra zero | Other Top-20 | Other tie | Tie end ranks |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| historical-q03 | accessibility | 24 | 2 | 2 | 8 | 1 | 0 | 11 | 0 | — |
| historical-q11 | outdoor | 36 | 6 | 6 | 4 | 5 | 0 | 15 | 0 | — |
| historical-q27 | accessibility | 230 | 9 | 9 | 1 | 1 | 8 | 20 | 182 | v3: 211 |
| kuehlhaus-da | venue | 64 | 9 | 9 | 1 | 12 | 0 | 20 | 13 | v3: 34 |
| kuehlhaus-de | venue | 58 | 9 | 9 | 1 | 10 | 0 | 20 | 9 | v3: 34 |
| kuehlhaus-en | venue | 60 | 9 | 9 | 1 | 9 | 0 | 19 | 13 | v3: 34 |
| museumsberg-da | venue | 34 | 6 | 6 | 4 | 3 | 0 | 12 | 3 | v3: 24 |
| museumsberg-de | venue | 35 | 5 | 5 | 5 | 0 | 0 | 15 | 5 | v3: 26 |
| museumsberg-en | venue | 35 | 6 | 6 | 4 | 4 | 1 | 14 | 0 | — |
| puppet-da | theatre | 26 | 3 | 3 | 7 | 2 | 0 | 11 | 0 | — |
| puppet-de | theatre | 26 | 4 | 4 | 6 | 1 | 0 | 11 | 0 | — |
| puppet-en | theatre | 24 | 3 | 3 | 7 | 2 | 0 | 9 | 0 | — |
| stage-da | theatre | 36 | 10 | 10 | 0 | 1 | 1 | 14 | 0 | — |
| stage-de | theatre | 36 | 8 | 8 | 2 | 1 | 1 | 16 | 0 | v3: 21 |
| stage-en | theatre | 34 | 9 | 9 | 1 | 1 | 0 | 14 | 0 | — |
| stepfree-da | accessibility | 226 | 8 | 8 | 2 | 8 | 3 | 17 | 180 | v3: 217 |
| stepfree-de | accessibility | 239 | 8 | 8 | 2 | 10 | 2 | 15 | 194 | v3: 221, v5: 22 |
| stepfree-en | accessibility | 237 | 9 | 9 | 1 | 8 | 3 | 18 | 189 | v3: 220 |
| wheelchair-da | accessibility | 24 | 8 | 8 | 2 | 1 | 0 | 5 | 0 | v5: 23 |
| wheelchair-de | accessibility | 22 | 3 | 3 | 7 | 0 | 0 | 9 | 0 | v3: 21 |

Large tie pools: `historical-q27` (230), `stepfree-da` (226), `stepfree-de` (239),
`stepfree-en` (237). None is silently truncated. A separately preregistered bounded
secondary sample could later reduce annotation effort, but is **not prepared or
substituted here** and could not claim the full pool's projected coverage. No API
execution or expenditure is authorized by preparation.

Event identity is UUID, never title. The same event in different queries, including
translations, remains independently judged. Categories with no evaluable cases
would explicitly report `no_evaluable_cases` and null coverage, not zero coverage.

## Coverage before and expected coverage after

Before means original frozen draft judgments, **not** the PR #12 expanded labels.
Values are macro averages across all historically evaluable queries per category.
Presence of a grade, including grade zero, counts as judged; unjudged does not.
After is a **conditional projection** if every selected task receives a valid grade.
Uncertain/needs-more-context responses would remain unknown and reduce achieved
coverage. No actual post-review coverage is claimed.

| Category | Evaluable / selected queries | Pairs | v3 Top-10 before | v5 Top-10 before | v3 Top-20 before | v5 Top-20 before | Target Top-10 / Top-20, both models |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| outdoor | 1 / 1 | 36 | 30.00% | 20.00% | 15.00% | 15.00% | 100% / 100% |
| theatre | 6 / 6 | 182 | 15.00% | 15.00% | 11.67% | 10.83% | 100% / 100% |
| venue | 6 / 6 | 286 | 26.67% | 20.00% | 15.00% | 15.00% | 100% / 100% |
| accessibility | 7 / 7 | 1002 | 15.71% | 22.86% | 9.29% | 16.43% | 100% / 100% |

## Blindness and evidence

The reviewer directory contains **only** the existing offline `review.html`,
`blind-candidates.jsonl` and `annotation-package.json`. Distribute this directory
alone. Operator mapping, selection reports and this document must not accompany
blind judging.

Candidates use the existing nine-field `BlindCandidate` format: opaque annotation
ID, query, language, reference time, eligibility, public event, eligible occurrence
IDs, rubric and scale. No category, query ID, top-level event ID, model, rank, score,
old grade, machine grade, gate outcome, priority or analyst conclusion is exported.
Nested occurrence/venue IDs are evidence identifiers required for exact context.

All frozen public fields are retained, including full description, types, tags,
spaces, venues, dates, accessibility text and restrictions. **All event occurrences
remain visible for context**, but only the exact eligibility-matching occurrence
IDs are marked eligible by the reused UI. The model prompt likewise restricts
judgments to eligible occurrences. Evidence from an ineligible occurrence must not
be transferred. Nothing is inferred or supplemented from outside sources.

The existing query-specific rubric remains the prefix of each rubric string;
explicit intent checks from this task are appended in the same field, keeping the
established schema and UI. Outdoor requires actual outdoor activity; theatre venue
type alone does not establish a requested performance; venue queries require the
actual eligible occurrence location; accessibility requires the particular documented
access condition, retaining restrictions. No scale change: 0–3, with explicit
uncertain/needs-more-context states, neither converted to zero.

Seed: `category-coverage-v1-20261007`. IDs use the first 32 hex characters of the
existing canonical SHA256 `order_key(seed, "annotation", case_id, event_id)`.
Presentation is sorted by `order_key(seed, "presentation", annotation_id)`, not
category, positivity or either ranking. The plan stores both original mapping and
final order. Collision/duplicate checks fail closed.

Tests reject forbidden metadata, compare all public evidence to the frozen source,
and inspect actual serialized judge HTTP requests through **synthetic MockTransport**.
No content-substring blacklist rejects legitimate public prose. Public text remains
untrusted evidence, rendered by the existing text-only UI and subject to the
existing prompt-injection instructions.

## Human review workflow

From the repository root, validate before distributing the package:

```sh
uv run python -m uranus_research_service.category_coverage_review validate
xdg-open benchmark/review/category-coverage-v1/reviewer/review.html
```

Enter a local pseudonym and select both JSON files from `reviewer/`. The existing UI
supports previous/next, progress, grades 0–3, uncertainty, notes and evidence fields.
Browser-local saving is bound to package and pseudonym. Regularly export answers
as a backup; resume via the UI's own-answer import. Separate reviewers must use
separate pseudonyms and not see each other's answers. No login, server, network or
database is needed. No answer file has been created by this task.

Validate a later human-declared export (this does not approve or freeze it):

```sh
uv run python -m uranus_research_service.category_coverage_review validate-review \
  --input /path/to/annotations-aurelius.json
```

Validation accepts incomplete work for resume; its reported entry count is **not**
a completed-grade count. Human review, conflict adjudication, explicit approval and
any derived reevaluation remain separate later actions. Existing judgments are never
overwritten.

## Machine review readiness

Evidence and strict answer contracts reuse the existing generic `machine_judge`
worker; there is no new provider client, judging implementation or data transformation.
Offline staging copies the reviewer packet byte-for-byte and binds the existing
versioned prompts, policy, schema, worker hash and explicit future model identifier:

```sh
uv run python -m uranus_research_service.category_coverage_review prepare-machine \
  --output /tmp/category-coverage-machine-v1 \
  --model exact-future-model-id --build-id category-coverage-v1
```

This command makes no API request. The explicit model is recorded, not verified or
selected automatically. Synthetic tests exercise distinct `machine-a` and `machine-b`
requests with the same packet, including uncertainty and occurrence-aware validation.
No run sees the other's outputs. No real machine answer files are published here.

**Existing worker limitation:** the reused Phase-2D-M worker retains its closed
three-pass prompt inventory and cost-approval envelope (`3 × N`). Staging lists
only A/B as planned but includes the required C prompt file; that does not schedule
or execute C. The generic CLI defaults to all passes, so a later separately authorized
run must explicitly select `--pass-name machine-a` or `--pass-name machine-b`.
For example, the existing pilot entry point is `machine_cli run --work
/tmp/category-coverage-machine-v1 --model <exact-model-id> --purpose dry-run
--pass-name machine-a`, then separately B. **Do not run these in this task.**

Full-run cost approval is not manufactured or bypassed. The existing cost-report
CLI expects a three-pass pilot, so a later two-pass full execution must explicitly
resolve that operator approval/reporting limitation before running. This preparation
proves A/B evidence/HTTP/answer compatibility, not a ready two-pass cost or consensus
pipeline. The old fixed 77-pair runner, seven-pair adjudicator and historical
seal/evaluate mappings are intentionally unchanged and must not be used blindly
for this new pool. No quality comparison is part of preparation.

## Reproducibility and integrity

The generator checks 171 preexisting benchmark/code files against
`benchmark/contracts/category-coverage-v1-input-sha256.json`, itself pinned by SHA256.
This includes the snapshot, queries, historical and later machine judgments,
rankings/results/comparison, chunks, audits, contracts, UI, rubrics and reused code.
Input mismatch, unknown IDs, missing eligible occurrences or duplicate pairs fail
closed. Existing frozen eligibility and deterministic rankings are reused unchanged.

Generate to a **new destination**, never overwrite the committed package:

```sh
uv run python -m uranus_research_service.category_coverage_review prepare \
  --output /tmp/category-coverage-reproduction
uv run python -m uranus_research_service.category_coverage_review validate \
  --package /tmp/category-coverage-reproduction
diff -qr benchmark/review/category-coverage-v1 /tmp/category-coverage-reproduction
```

Exclusive atomic JSON writes are reused. Interrupted/incomplete exports fail
validation rather than being accepted as complete. Validation recomputes selection,
evidence and order, verifies all published file hashes and the exact reviewer file
allowlist, and compares the reused UI/schema. No timestamp makes the export drift.
`artifact-sha256.json` binds every generated file and the generator code.

Raw file SHA256:

- Input manifest: `ddd603c072cc52178839294dddc2c39b08604cb65e210b172d0c5f5e7c2dc3b3`
- Review plan: `ced8eedf32d8b16ee4fd58ff49514b58710cbbddecadec00100335ced88ce606`
- Blind JSONL: `6b2b54c3c254d97f2972b04d122cc8e415eeff87e09d164d09a7902c45f3cd54`
- Annotation-package JSON: `0e043cfd64ee821eac75ca71540d0888634a60226ab3e643baae37f4feb581a0`

Canonical package/packet digests in metadata are distinct from raw-file hashes:

- Package binding: `63938b4632854a1771a785e7796105b578c7e1711815e9aae2c55a472e5ec38f`
- Packet binding: `f40051792f5f6147670f6abb4674c263013054af64e5458a21db414c1eead0a3`

## Limits and production boundary

This is a targeted, nonrandom diagnostic pool. Complete Top-10/20 coverage would
not establish corpus-wide relevance completeness or unbiased global model quality.
No annotation, agreement, human ground truth, category reclassification, gate change
or fine-tuning recommendation is created. Original metrics and verdict remain
historical. Previous human/machine artifacts are byte-identical.

No API calls, retrieval inference, model downloads, Encoder/Planner changes, SQL or
Qdrant queries/writes, production access, deployment, restart, reindex, alias switch,
training or threshold tuning. `semantic_query=false` is unchanged. This PR must not
be merged automatically; later machine execution requires separate authorization.

## Validation

Local `uv sync --locked --offline`, Ruff, formatting and diff checks passed. The
full offline run completed with **648 passed, 24 skipped**; the subsequently added
all-1,506-payload serialization test passed separately (**1 passed**). All 21 new
test cases therefore passed. Skipped tests require explicitly configured PostGIS,
disposable Qdrant, pinned Admin parity checkout or optional real-provider environments.
The existing CI remains unchanged and runs its disposable integration services and
Docker build; no external model/API dependency was added.
