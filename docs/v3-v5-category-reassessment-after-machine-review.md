# Category reassessment after machine review

## Summary

**Atmosphere's negative Recall@10 delta disappears under the expanded machine-assisted
judgment subset**: −0.0800 → +0.0318. This is driven by one deliberately selected query,
`dance-en`, out of five historically evaluated atmosphere queries. It is not a
representative fresh category annotation or a correction of the historical result.

**Outdoor, theatre and venue have no new applicable judgments.** Their numerical
regressions remain in the original data, but this follow-up neither confirms them
with better coverage nor rules them out. They are `unchanged_no_new_coverage`.

**Accessibility is a diagnostic watch category**, not a failed historical category.
`wheelchair-da` still favors v3 after full Top-10 coverage, but only one of seven
evaluated accessibility queries received new judgments. Its category average still
favors v5. A systematic accessibility defect is not established (`insufficient_evidence`).

No category meets the meaning of `regression_still_supported` through broad new
coverage. Fine-tuning is not justified by this evidence; targeted further investigation
is appropriate. No model, label policy, threshold or historical result was optimized.

## Historical baseline

Build `20261006_8cpu_001`, 611 events, 120 executed queries and the **same 105 included
cases**. Baseline main: `23467bba450299c762f6e0e4ff743c67682f5985` (PR #12 merged).
The complete historical `compare(v3, v5)` output was reproduced exactly before
any expansion. All historical inputs, grades, full rankings, scores, eligibility,
aggregation, tie ordering and excluded cases remain byte-identical.

Historical verdict remains **`v5 provisionally fails one or more gates`**.

| Category | Historical v3 R@10 | Historical v5 R@10 | Delta | Historical category gate |
|---|---:|---:|---:|---|
| atmosphere | 0.245714 | 0.165714 | -0.080000 | fail |
| outdoor | 0.375000 | 0.250000 | -0.125000 | fail |
| theatre | 0.236111 | 0.159722 | -0.076389 | fail |
| venue | 0.338889 | 0.241392 | -0.097497 | fail |
| accessibility | 0.369702 | 0.413658 | +0.043956 | pass |

## New judgment source

The immutable source is
`benchmark/review/lost-all-v1/machine/adjudication/machine-consensus-plus-adjudication-v1.json`:
**70 machine_agreed + 7 machine_adjudicated, 0 unresolved, 77 unique pairs**.
SHA256: `44bf662e9bc8dc4a80ce431a45a30d5a954ca2c2addec2b985d08d4e29f82722`.
Bindings to the original sealed consensus, seven Astra records and frozen review
packet are validated, not inferred from the filename.

Across the entire four-query source, **62 pairs were previously unjudged**, 15 already
had historical grades; 5 of those disagree. Of the 62 additions, **32 belong to the
five target categories** (16 atmosphere, 16 accessibility). The other source queries
are not reinterpreted as evidence about these categories. No label transfers occur
between different queries, language variants or events sharing a title.

Three modes are explicit:

- `historical`: unchanged original evaluation.
- `machine-expanded` (primary): add only previously unjudged pairs; retain every
  historical grade, including a historical positive contradicted by machine zero.
- `machine-override-exploratory`: **exploratory sensitivity analysis** replacing
  historical grades only at the 77 reviewed pairs. It is never the primary result.

Conflicts are preserved with old/machine grades and provenance in
`historical-label-conflicts.json`; none is adjudicated or silently resolved here.
The source has no calibrated confidence values, so conflict confidence is explicitly
null. There is no Human Ground Truth or human approval.

## Coverage

Denominators are historically evaluated cases only: 25 across the five categories.
All 28 target-category queries are visible in the case artifact; three historically
excluded queries remain excluded. Atmosphere has 6 total/5 included queries;
accessibility has 9 total/7 included queries. Coverage is the macro fraction of
Top-K event IDs with an explicit judgment; unknown is never converted into a zero label.

| Category | Included queries | Newly touched | New pairs | v3 Top-10 before → after | v5 Top-10 before → after |
|---|---:|---:|---:|---:|---:|
| atmosphere | 5 | 1 (20.0%) | 16 | 14.0% → 32.0% | 14.0% → 34.0% |
| outdoor | 1 | 0 (0.0%) | 0 | 30.0% → 30.0% | 20.0% → 20.0% |
| theatre | 6 | 0 (0.0%) | 0 | 15.0% → 15.0% | 15.0% → 15.0% |
| venue | 6 | 0 (0.0%) | 0 | 26.7% → 26.7% | 20.0% → 20.0% |
| accessibility | 7 | 1 (14.3%) | 16 | 15.7% → 28.6% | 22.9% → 35.7% |

Top-20 coverage is separately retained in `coverage-delta.json` and per case. The
fully machine-judged **selected pool** must not be confused with complete corpus
judgments. Even the touched queries retain unknown candidates outside this pool.

## Category results

Values below are **machine-expanded**, retaining all historical grades. Category
gate calculations reuse the original −0.05 allowed Recall@10 drop; no metric or
threshold changes. Passing a category calculation here is not a global gate pass.

| Category | v3 R@10 | v5 R@10 | Delta | Classification |
|---|---:|---:|---:|---|
| atmosphere | 0.251597 | 0.283361 | +0.031765 | `regression_not_supported_under_expanded_machine_judgments` |
| outdoor | 0.375000 | 0.250000 | -0.125000 | `unchanged_no_new_coverage` |
| theatre | 0.236111 | 0.159722 | -0.076389 | `unchanged_no_new_coverage` |
| venue | 0.338889 | 0.241392 | -0.097497 | `unchanged_no_new_coverage` |
| accessibility | 0.387559 | 0.476158 | +0.088599 | `insufficient_evidence` |

### Atmosphere

Only `dance-en` changed. Its case delta shifts from −0.5 to +1/17, changing the
category delta by +0.111765. The other four evaluated queries, including the
previous positive contribution from `quiet-da`, are untouched. Aggregate Top-10
judged coverage is still only 32%/34% for v3/v5. Thus the classification describes
the observed expanded-machine arithmetic, with **low confidence in generalization**.

### Outdoor

`historical-q11` remains the only evaluated case: 0.375 versus 0.25, delta −0.125.
No new judgments apply. **Insufficient new coverage to materially reassess this
category**; no broader outdoor pattern can be established from one old case.

### Theatre

No new judgments apply to `puppet-de`, `stage-en` or any other theatre query.
Their old case deltas remain −0.125 and −0.333333 respectively. The category
remains numerically −0.076389, without new corroborating coverage.

### Venue

No new judgments apply to the Museumsberg DE/DA/EN queries or `kuehlhaus-de`.
Museumsberg's old case deltas remain −0.166667, −0.285714 and −0.142857;
Kühlhaus DE remains −0.066667. Translations of the same venue intent are not
independent evidence of a newly confirmed general venue defect.

### Accessibility — diagnostic watch category

`wheelchair-da` receives 16 additions: 14 machine-positive and 2 machine-zero.
Both Top-10 lists become 100% judged; Top-20 coverage is 75% v3 / 95% v5.
Recall@10 becomes **0.625 v3 / 0.4375 v5**, narrowing the case delta from −0.5
to −0.1875. This is a remaining **case-specific ranking disadvantage under these
machine judgments**. Both models now have a positive at rank 1. The category
average is +0.088599 for v5 because the other six evaluated cases are unchanged.
Only 1/7 queries is newly covered; this task cannot determine whether the case is
isolated or part of a systematic accessibility problem. No accessibility or safety
guarantee may be inferred from these labels.

## Case-level findings

The complete artifact lists all 28 target-category cases, exclusions, six metrics
in all modes, best positive ranks, new positive/zero UUIDs, new positive Top-10 IDs,
conflicts and category-delta contributions. Important cases:

| Query | Historical R@10 v3 / v5 | Expanded R@10 v3 / v5 | Best rank before → after (v3 / v5) | Added pairs |
|---|---:|---:|---|---:|
| dance-en | 0.500000 / 0.000000 | 0.529412 / 0.588235 | 7 → 1 / 13 → 1 | 16 |
| wheelchair-da | 0.500000 / 0.000000 | 0.625000 / 0.437500 | 9 → 1 / 17 → 1 | 16 |
| historical-q11 | 0.375000 / 0.250000 | 0.375000 / 0.250000 | 2 → 2 / 2 → 2 | 0 |
| puppet-de | 0.750000 / 0.625000 | 0.750000 / 0.625000 | 1 → 1 / 1 → 1 | 0 |
| stage-en | 0.666667 / 0.333333 | 0.666667 / 0.333333 | 5 → 5 / 2 → 2 | 0 |
| museumsberg-de | 0.833333 / 0.666667 | 0.833333 / 0.666667 | 1 → 1 / 1 → 1 | 0 |
| museumsberg-da | 0.571429 / 0.285714 | 0.571429 / 0.285714 | 2 → 2 / 1 → 1 | 0 |
| museumsberg-en | 0.428571 / 0.285714 | 0.428571 / 0.285714 | 1 → 1 / 1 → 1 | 0 |
| kuehlhaus-de | 0.200000 / 0.133333 | 0.200000 / 0.133333 | 1 → 1 / 1 → 1 | 0 |

`dance-en` receives 15 new positive and one new zero judgment. The historical
positive event `019db61e-a230-7e9b-a02a-8d59e4662280` remains grade 1 despite the
machine grade 0. Consequently primary Recall@10 is **9/17 versus 10/17**,
not the earlier machine-only 9/16 versus 10/16. In the separately labeled override
sensitivity, the latter values reappear and atmosphere delta is +0.0325. This
small difference does not change the directional conclusion, and is not a reason
to replace the historical label. Accessibility has no historical conflicts and
identical additive/override results.

Five source conflicts: three `concerts-en`, one `historical-q29`, one `dance-en`.
Only the last belongs to the five target categories. Complete event IDs and grades
are in the separate conflict artifact; no historical file is modified.

## Selection bias / limitations

The 77-pair pool was deliberately selected for four historical known-positive-loss
queries, not sampled randomly from categories. Improved coverage can change recall
both through new hits and larger positive denominators. A zero label is distinct
from an unjudged candidate. The original evaluator's documented pooled zero-gain
convention remains, with unknown labels still absent. No threshold curves are run.

The category classification rule is explicit in code: no new pairs means unchanged;
a nonnegative expanded delta on a formerly negative category means not supported
under expanded machine judgments; a smaller remaining negative delta means weakened.
Calling a remaining regression newly supported would additionally require at least
80% of evaluated cases touched and 90% Top-10 coverage for both models. These are
interpretation safeguards, not new benchmark gates, and no current category meets
them. Accessibility is kept as insufficient evidence for a systematic diagnosis.

The old and new judgments are machine-assisted and fallible. Arithmetic reproduction
is exact; causal or category-wide confidence remains low. No new root-cause or
retrieval-model experiment was performed.

## Fine-tuning implication

**B — targeted further investigation; a Kulturbytes-specific v5 LoRA is not justified
at present.** Prioritize independent human review of wheelchair access evidence and
additional accessibility cases; expand blind coverage for the untouched theatre and
venue cases before deciding whether a consistent semantic failure exists. Outdoor
still has only its single historical case. This follow-up provides no adequately
covered multi-case pattern warranting experimental fine-tuning. No training occurs.

## Reproduction and validation

From repository root:

```sh
uv sync --locked --offline
uv run --offline python -m uranus_research_service.category_reassessment \
  --output /tmp/category-reassessment-new
uv run ruff check .
uv run ruff format --check .
uv run pytest -q
git diff --check
```

The output directory must not already exist. No API key or external service is
needed for this command. The pinned manifest binds 155 existing benchmark/code
files to main, SHA256:
`f2b8fbdfef91accbc1330ce5c60ce88f9cf101ea39b5b824672be86a12a4c1e5`.
Existing source seals and exact historical comparison are also verified before
writing. Output hashes and analysis-code hash are in `artifact-sha256.json`.

Implementation reuses `machine_analysis.expanded_cases` and
`controlled_evaluation.compare` → `summarize` → `metrics`. Existing category-report
logic was inspected; the new projection adds the missing coverage and conservative
classification without duplicating metric or gate definitions. The override mode
only changes an in-memory copy and uses the same evaluator.

Tests verify frozen bytes, 77/70/7 bindings, pair-specific additive updates,
conflicts, deterministic reports, coverage counts, excluded-case preservation,
no network/provider calls, no encoder/Qdrant imports and unchanged historical
verdict. Existing service-dependent integration tests retain their guards and CI
fixtures; no test needs a live OpenAI call or model weights.

## Production boundary

No production access/deployment, DB/SQL calls or writes, Qdrant search/writes,
reindex, encoder inference, new embeddings, chunking, alias switch, training,
threshold tuning or Human Ground Truth. `semantic_query=false` remains unchanged.
No global gate approval; no PR auto-merge. The original benchmark and its verdict
remain historical, immutable and reproducible.
