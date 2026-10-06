# Phase 2D-A: blind judgment expansion

## 1. Motivation

Phase 2D tests whether incomplete judgments contribute to the historical gate failures.
It changes judgment coverage, not either model. This PR prepares independent human review;
it makes **no new retrieval-quality decision**. No human annotations have been supplied.

> This benchmark uses a frozen draft relevance dataset containing machine proposals plus manually calibrated scoring policy. It is suitable for provisional comparative evaluation, not final production approval.

## 2. Scope

Offline selection, evidence export, local annotation UI, strict import, agreement, conflict
and approval gates. No model weights, network clients, DB readers, Qdrant, inference,
reindexing or service changes. `semantic_query=false` is unchanged. Phase 2D-B will implement
and execute the expanded evaluation after real annotations, adjudication and explicit approval.
Neither PR may be merged automatically.

## 3. Historical baseline

PR #7 merged as `1ff0439134ecdd30ab65a4a3e3665de0ad65244d`. Build `20261006_8cpu_001`
contains 611 documents, 1,989 v3 / 2,080 v5 chunks, 120 executed queries and 105 cases in gates.
Recall@10: 0.2550 → 0.2998; MRR@10: 0.3225 → 0.4543; nDCG@10: 0.2252 → 0.3038.
Language gates passed; atmosphere, outdoor, theatre and venue gates failed. Four cases lost
all **known positive** Top-10 hits. R6 remains the historical diagnosis.

[Input manifest](../benchmark/contracts/phase2d-input-sha256.json) protects 61 historical files: all pre-existing
benchmark files and the original evaluator, snapshot/ground-truth contracts and guidelines.
SHA256 is checked before every operator action; a test also anchors the manifest itself.
Full stored rankings must contain every eligible event exactly once and retain their
original ordering. Original scores, judgments, metrics, gates and diagnostic results are unchanged.

## 4. Preregistered sampling

[Sampling plan](../benchmark/annotation/phase2d/sampling-plan.json) was fixed before any new
relevance judgments. Seed: `kulturbytes-phase2d-blind-v1`. SHA256 sorting, not Python's
process-dependent hash or PRNG, orders selections and presentation.

1. Four total-loss cases: union of both Top-20 lists plus every existing grade > 0.
2. Every case in the four failed categories: both Top-10 lists plus positives; use Top-20
   if Top-10 Jaccard ≤ 0.25 or any known positive differs by ≥10 positions.
3. Outside these categories and already selected cases, select up to four per language
   from original evaluable cases with the same symmetric disagreement, a Top-5 candidate
   ranked ≥30 by the other model, or ≥8 unjudged Top-10 candidates in either model.
   Selection within language uses seeded SHA256 order, not the largest regression.
4. Disjoint controls: up to two per language × original Recall@10 direction. Neutral means
   absolute delta ≤0.02; the remaining two directions favor v3 or v5 respectively.
   Controls use both Top-10 lists plus positives.

Every cutoff extends through the entire exact stored-score tie block. This makes some tasks
large: stepfree-da has 226 candidates and historical-q10 has 212. Their tie blocks are not
truncated to reduce annotation effort. No epsilon changes
or truncation after union. Event-level ranking aggregation is already frozen; no chunk
selection or new aggregation occurs. All pairs are unique `case_id × event_id`; translations
remain separate tasks. The pre-shuffle pool, final order, selection evidence and seed live
in the **operator-only** [mapping bundle](../benchmark/annotation/phase2d/blind-mapping.json).

## 5. Selection-bias limits

The diagnostic sample deliberately overrepresents problems. Controls are balanced across
available strata, not a random sample of the whole corpus. Categories and translations
are correlated; neither subset is an unbiased global estimator. There are **no remaining
DA/v3-improvement cases in the disjoint control population**. That cell is empty, not filled
with a duplicate, synthetic case or overlapping diagnostic case.

## 6. Blind procedure and practical use

Give each annotator **only** these three files:

- [review.html](../benchmark/annotation/phase2d/review.html)
- [blind-candidates.jsonl](../benchmark/annotation/phase2d/blind-candidates.jsonl)
- [annotation-package.json](../benchmark/annotation/phase2d/annotation-package.json)

Aurelius opens `review.html` directly in a browser (`file://`), enters a pseudonym, then
selects the two data files together. No server, installation, CDN or network access is
needed. Each task shows the query, rubric, public event text, dates, venues, spaces and
accessibility evidence. A conditionally eligible occurrence is labeled accordingly; its
UUID is not presented as something the reviewer must interpret. Mark the supporting fields
and specific supporting occurrence for positive contextual judgments. Give a short reason
for every completed judgment, including zero, uncertainty or missing context.

Use next/previous or the task-number field. Download answers regularly; local browser storage
is only a convenience. Resume by loading the same package and **your own** downloaded answer
file. Every download is a draft `phase2d-human-annotations-v1` JSON batch. No actual answer,
adjudication or frozen-judgment files are committed in 2D-A.

Use separate browser profiles/devices for independent annotators. Do not share answer files
until both have submitted. The UI cannot prove reviewer identity or prevent someone opening
another person's files; independence is a procedural requirement. Since this repository
also contains historical results, reviewers should receive the three-file handoff, not
browse the repository, mapping, this diagnostic document or historical results during review.
If a reviewer already knows model-specific outcomes, disclose that limitation before freeze.
Opaque IDs are stable SHA256-derived identifiers; this is blinding, not cryptographic secrecy
against an adversarial reviewer with the seed and complete source repository.

## 7. Authoritative rubric

The existing scale is **0–3**, not the illustrative 0–2 scale in the task description:

| Grade | Meaning |
|---|---|
| 0 | Irrelevant or required property not evidenced |
| 1 | Genuine, evidenced partial relevance |
| 2 | Clearly relevant with a limitation |
| 3 | Direct, explicit full match |

The [existing guidelines](retrieval-annotation-guidelines.md) and per-query frozen rubric
are preserved. `uncertain`, `needs_more_context` and `pending` have `grade=null`, never zero.
No inference from artist identity, venue reputation or missing information. Accessibility
must distinguish step-free access, wheelchair access, toilets, assistance and restrictions
at the specific occurrence. A positive contextual judgment requires an eligible occurrence;
structural validation cannot certify the human semantic interpretation of its evidence.

The requester explicitly confirmed **the existing single-event interpretation** for
“Concerts spanning different musical genres”: multiple genres in one concert program,
not diversity across the result set. This clarification is in the new sampling plan and
annotation rubric; the historical rubric file and all historical grades remain untouched.
This is rubric clarification, not approval of any relevance judgment.

## 8. Independent annotation and agreement

Both A and B independently grade each selected pair. The workflow accepts partial A-only
batches; it cannot freeze them. No artificial B, machine suggestions or copied A judgments
count as human agreement. Pseudonyms suffice; no unnecessary personal information is stored.

The validator enforces closed schemas, strict integers 0–3 (not booleans), unique known IDs,
package binding, reasons, nonempty supporting fields and occurrence membership. It does
not transfer judgments between query languages. Agreement uses only pairs with two completed
grades: raw agreement, quadratic weighted agreement, Cohen's kappa, quadratic weighted kappa
and a **4×4** confusion matrix. Missing/uncertain pairs are counted separately. Degenerate
kappa is null; class imbalance and reviewer independence limit interpretation.

## 9. Adjudication

Every grade disagreement requires human adjudication, including 0 vs 2 and 0 vs 3. An agreed
human grade that differs from the existing frozen draft grade also produces a conflict record
with old/new grades, provenance and `adjudication_required=true`. Existing judgments are never
silently overwritten. The new version records previous grade and the adjudicated decision;
original files remain immutable. Missing/uncertain independent reviews cannot be bypassed by
adjudication. Every conflict must be resolved, and unrelated adjudication rows are rejected.

## 10. Human approval gate

No actual freeze occurs in 2D-A. The future freeze command first builds a reviewable **draft**.
Explicit externally supplied approval must reference that exact draft SHA256, an aware date,
a human pseudonym and an approval reference. Altered review/adjudication inputs invalidate
approval. The tool validates an attestation and hashes, not human authentication. Codex may
not populate or invoke a real approval on its own authority. The UI has no approval control.

## 11. Freeze procedure

All selected pairs require two independent, completed judgments and all conflicts resolved.
The draft includes input/package hashes, document hashes, annotators, adjudicator, prior grades
and adjudication hash. Deterministic inputs produce identical output; timestamps come only
from the human approval, not the machine clock. Files use exclusive creation and cannot
replace earlier artifacts. Store new versioned outputs in a new work directory.

## 12. Re-evaluation (2D-B, not run)

After approval, evaluate the **same stored full rankings** against one expanded judgment set
for both models. No model calls or new embeddings. Keep the original 105-case cohort for
comparable gates; retain the six unresolved no-hit exclusions and other original exclusions.
If adjudication removes a case's last positive denominator, stop rather than silently change
the cohort. Newly evaluable cases may be a separately labeled exploratory analysis.

Reuse original metric implementation, event aggregation and gate limits. Unknown documents
stay unknown in raw data; the original explicitly provisional pooled metric policy gives them
zero gain, not a grade-0 judgment. Coverage must accompany every metric. New evaluator outputs,
comparison, category and total-loss reports belong under `benchmark/results/phase2d/` with
new hashes. Original artifacts are never rewritten. This implementation intentionally does
not yet expose a re-evaluation command or produce expanded results.

## 13. Judgment coverage

[Before-annotation coverage](../benchmark/results/phase2d/judgment-coverage.json) covers all
120 queries and both models, with per-case Top-10/20 positive, frozen-zero and unjudged counts,
plus language/category/subset aggregates. The table below uses judged slots / returned slots;
all rows currently have ten/twenty returned events. **After values are unavailable**, not zero.

| Group | v3 Top-10 before | v3 after | v5 Top-10 before | v5 after | v3 Top-20 before | v5 Top-20 before |
|---|---:|---|---:|---|---:|---:|
| All 120 cases | 16.50% | pending | 19.88% | pending | 13.22% | 15.94% |
| DE | 25.10% | pending | 27.73% | pending | 18.70% | 22.46% |
| DA | 8.43% | pending | 15.12% | pending | 8.92% | 12.43% |
| EN | 12.21% | pending | 13.37% | pending | 9.65% | 10.09% |
| atmosphere | 11.67% | pending | 13.33% | pending | 10.00% | 11.67% |
| outdoor | 30.00% | pending | 20.00% | pending | 15.00% | 15.00% |
| theatre | 15.00% | pending | 15.00% | pending | 11.67% | 10.83% |
| venue | 26.67% | pending | 20.00% | pending | 15.00% | 15.00% |
| Four total-loss cases | 12.50% | pending | 2.50% | pending | 12.50% | 8.75% |
| Balanced controls | 25.62% | pending | 29.38% | pending | 19.38% | 20.94% |

Top-20 before/after, separately:

| Group | v3 before | v3 after | v5 before | v5 after |
|---|---:|---|---:|---|
| All 120 cases | 13.22% | pending | 15.94% | pending |
| DE | 18.70% | pending | 22.46% | pending |
| DA | 8.92% | pending | 12.43% | pending |
| EN | 9.65% | pending | 10.09% | pending |
| atmosphere | 10.00% | pending | 11.67% | pending |
| outdoor | 15.00% | pending | 15.00% | pending |
| theatre | 11.67% | pending | 10.83% | pending |
| venue | 15.00% | pending | 15.00% | pending |
| Four total-loss cases | 12.50% | pending | 8.75% | pending |
| Balanced controls | 19.38% | pending | 20.94% | pending |

Phase 2D-B must show separate before/after tables
for both cutoffs and distinguish existing, newly positive, newly zero, unresolved, conflicted
and adjudicated pairs. A top-ranked unjudged event is not a false positive.

Stopping policy: complete the entire preregistered pool including ties. The target is ≥90%
Top-10 coverage for each model and preferably ≥80% Top-20 on prioritized cases; completing
Top-20 unions yields 100% there. Top-10-only controls do not guarantee Top-20 saturation.
Uncertainty cannot be turned into zero to meet a target. If another round is needed, preregister
a new deterministic selection before reviewing its candidates; do not expand automatically.

## 14. Total-loss reassessment (pending)

For historical-q29, wheelchair-da, dance-en and concerts-en, 2D-B will show old positives,
newly confirmed positives, old/new recall, coverage and whether known-positive loss remains.
Use TL-A only if loss persists with high coverage; TL-B if newly confirmed relevant v5 hits
remove the loss; TL-C for mixed evidence; TL-D for insufficient evidence. No classifications
are assigned before human review.

## 15. Category gates (pending)

Outdoor's historical −0.125 came from one query/one known hit, not broad evidence. Inspect
that case, dance-en, both theatre regressions, and Museumsberg DE/DA/EN separately from
Kühlhaus. Original gates and decisions stay historical. Any new pass must read “passes under
the Phase-2D expanded judgment set”, never “the original benchmark actually passed”.

## 16. Diagnostic vs balanced expansion

| Subset | Queries | Unique pairs |
|---|---:|---:|
| Diagnostic (priorities 1–3) | 34 | 1,587 |
| Balanced controls (priority 4) | 16 | 326 |
| Total, disjoint | 50 | 1,913 |

Priority counts: 4 total-loss, 18 additional failed-category, 12 material-disagreement,
16 control cases. In 2D-B, report diagnostic, balanced and full expanded-set signals separately.
Do not make a global claim from the problem-oriented sample alone.

## 17. Bias and leakage audit

Exports use closed allowlisted metadata and full snapshot evidence. No model name, source,
rank, score, delta, gate, regression/improvement label, historical grade or expected outcome
is exported. The field validator checks nested event/eligibility schema; it does not reject
ordinary public text containing words such as “model” or “v5”. No model-specific chunks are
shown. Mapping/selection provenance remains in a separate operator file. Package validation
reconstructs expected inputs and rejects altered packets or mapping on import.

## 18. Current results: preparation only

Selected languages: DE 17, DA 15, EN 18. Categories: accessibility 3, ambiguous 3,
atmosphere 6, cultural_style 1, exhibition 6, family 5, genre 3, location 2, music 2,
multiple_results 2, outdoor 1, paraphrase 2, theatre 6, venue 6, workshops 2.
No human annotations, agreement report, adjudicated set, frozen set or expanded quality
results exist. The package remains draft. Tests use expressly synthetic records only.

## 19. Limits

Pooled judgments may miss relevant events outside the pool; unjudged remains unknown.
Human semantic evidence checking is indispensable; code only checks structural consistency.
The existing labels remain machine-proposed/calibrated draft policy, even after new human
labels are added. Single-annotator completion is useful progress but insufficient to freeze
under this two-reviewer protocol. Threshold tuning and model optimization are out of scope.

## 20. Reproducibility and CLI

From the repository root (no model weights required):

```sh
uv run python -m uranus_research_service.blind_cli export --output /tmp/phase2d-new-package
uv run python -m uranus_research_service.blind_cli validate \
  --package benchmark/annotation/phase2d --a /path/annotations-a.json --output /tmp/a-validation.json
uv run python -m uranus_research_service.blind_cli import \
  --package benchmark/annotation/phase2d --a /path/annotations-a.json --output /tmp/a-import.json
uv run python -m uranus_research_service.blind_cli agreement \
  --package benchmark/annotation/phase2d --a /path/annotations-a.json \
  --b /path/annotations-b.json --output /tmp/agreement.json
uv run python -m uranus_research_service.blind_cli adjudication \
  --package benchmark/annotation/phase2d --a /path/annotations-a.json \
  --b /path/annotations-b.json --output /tmp/conflicts.json
```

Export requires a new directory; all outputs require nonexistent filenames. The standalone
`review.html` can be copied unchanged to the newly exported directory. JSON schemas for
annotations, adjudication and approval are beside the package. Adjudication binds both
submitted review files via `review_inputs_sha256` (canonical SHA256 of the ordered two batches).
The conflict output includes this hash so the human adjudication file can reference it.
The `freeze` command requires both batches and `--adjudicated`; without `--approval` it only
writes a draft. With a valid, explicitly authorized human approval it writes a new frozen
artifact. **Do not execute that approval step in 2D-A.**

The Phase-2D artifact index hashes the prepared files and implementation separately from the
historical input manifest. Unit tests cover deterministic sampling, tie expansion, blinding,
unknown states, independence, agreement, conflicts, evidence references and approval binding.
Existing offline and integration CI continue unchanged. The static page has no frontend build
or dependencies; browser state is not a source of truth until exported and validated.

## 21. Human approval

The only human decision received during preparation confirms the existing concert rubric.
It approves **no event grades and no frozen dataset**. A/B annotation, conflict resolution
and explicit dataset approval remain outstanding. Do not manufacture empty answer artifacts
or a second annotator.

## 22. Next decision

Review/merge 2D-A only through the normal human PR process, then annotate independently.
After approval, a separate 2D-B PR can re-evaluate and distinguish coverage bias, remaining
regression, mixed evidence or insufficient agreement. Fine-tuning is not justified by this
preparation step; no new recommendation is inferred. Production readiness—including latency,
resources, rollback, candidate index, Admin parity, observability, deployment and licensing—
remains a separate decision even if later expanded-judgment gates pass.
