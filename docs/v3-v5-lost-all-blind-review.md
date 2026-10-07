# Four-case blind human review (v1)

## Motivation and boundaries

The frozen `20261006_8cpu_001` benchmark remains historical and unchanged:
**v5 provisionally fails one or more gates**. Better aggregate draft metrics do not
resolve the four known-positive Top-10 losses. Unjudged results are unknown, not
irrelevant. This follow-up prepares actual human assessment of those candidates.

This delivery contains **no human judgments and no new evaluation results**.
The existing labels are machine-proposed/calibrated draft judgments. Four deliberately
selected queries cannot establish quality across all 120 queries or authorize production.
No machine judge or new model inference is used. PR #9's separate machine work is not
part of this branch; the baseline is main at `e653ff53547e29c0835e836440d2e6ac4bec6651`.

> This benchmark uses a frozen draft relevance dataset containing machine proposals plus manually calibrated scoring policy. It is suitable for provisional comparative evaluation, not final production approval.

## Pool and blindness

Selection is fixed before human results: union of both Top-10 event sets **plus every
existing positive**. The optional retention clause is used even beyond Top 20, so no
known positive disappears from review. Deduplication is by `(query ID, event UUID)`.
Identical titles never merge UUIDs or transfer judgments across queries. The original
stored event ordering defines Top 10, including its UUID tie break; this small follow-up
does not extend tie blocks. Full rankings and exact scores remain in the operator-only
provenance for reconstruction.

| Query | Only v3 Top 10 | Only v5 Top 10 | Both | Additional known positive | Total |
| --- | ---: | ---: | ---: | ---: | ---: |
| historical-q29 | 4 | 4 | 6 | 2 | 16 |
| wheelchair-da | 8 | 8 | 2 | 1 | 19 |
| dance-en | 7 | 7 | 3 | 1 | 18 |
| concerts-en | 9 | 9 | 1 | 5 | 24 |
| Total | 28 | 28 | 12 | 9 | **77** |

The actual size exceeds the estimated 40–60 because the two systems' Top-10 sets have
little overlap. There is no trimming based on desired outcomes. Languages: 19 Danish
and 58 English pairs; there is no German query in this explicitly limited task.

Before review, judged counts (both zero and positive draft labels) are:

| Query | v3 Top 10 | v5 Top 10 | v3 Top 20 | v5 Top 20 |
| --- | ---: | ---: | ---: | ---: |
| historical-q29 | 1/10 | 0/10 | 1/20 | 1/20 |
| wheelchair-da | 1/10 | 1/10 | 2/20 | 3/20 |
| dance-en | 1/10 | 0/10 | 2/20 | 1/20 |
| concerts-en | 2/10 | 0/10 | 5/20 | 2/20 |

All Top-10 pairs are in the pool. Complete *graded* answers would give 100% human
Top-10 coverage for each model. Uncertain answers do not count as judged. This pool
does not promise complete Top-20 or corpus-wide coverage.

Seed: `focused-human-review-v1-20261007`. Review IDs are the first 32 hex characters
of SHA256 of canonical JSON `[seed, "review", case_id, event_id]`. Presentation order
is ascending SHA256 of `[seed, "presentation", review_id]`. There is no random state
or rank-based ordering. Query/event IDs are present as requested for source identity,
but prior grades, ranks, scores and retrieval provenance are absent from the packet.

Only hand reviewers the **`reviewer/` directory**. Do not send this operator report,
`review-plan.json` or `provenance.json`. The reused HTML loads only the two explicitly
selected reviewer files, has `connect-src 'none'`, uses text rendering for event content
and never reads provenance. Metadata allowlists and closed public event/eligibility
schemas reject injected model/rank/label fields; genuine event prose is not rejected
because of an accidental substring. Tests compare full event/occurrence evidence with
the original Phase-2D-A packet. No summary generation or evidence truncation occurs.

## Rubric and practical human workflow

The frozen 0–3 rubric remains authoritative: 0 absent/irrelevant, 1 evidenced partial
relevance, 2 clear but constrained relevance, 3 explicit full match. `uncertain` and
`needs_more_context` remain null grades. No human answers are prefilled.

The existing query rubric is preserved verbatim with visible requirement checklists:
art + participation + young audience; culture + documented wheelchair access at the
specific occurrence (including toilet/access restrictions); active dancing + lively
atmosphere + evening; live concert + multiple genres **within one program**. The latter
interpretation was already explicitly confirmed for Phase 2D-A. No result-list diversity
reinterpretation is introduced. Unknown target age/time/access remains unknown.

Reuse the existing Phase-2D-A `review.html` byte-for-byte. No second frontend or server.
The original `blind_cli.py` is itself hash-pinned by the historical Phase-2D artifact
index. An attempted command extension was rejected by that existing test and reverted.
Rather than rewrite historical hashes, the small `lost_all_review` module entrypoint
uses the same CLI conventions and unchanged shared exporter/validators. This documented
exception preserves the stronger historical immutability requirement.
Enter a local pseudonym, select both package files, read the complete evidence, mark
0/1/2/3 or uncertainty, and use previous/next/jump. Progress and resumption are provided.
For compatibility with the existing strict human contract, a brief reason is required
for every non-pending response, not merely an optional comment. Positive grades require
supporting fields and at least one eligible occurrence; all four combined intents are
context-sensitive. Do not cite a missing field as positive evidence.

Each change is saved synchronously in one browser `localStorage` transaction keyed by
package hash and reviewer. A browser closure preserves successful writes; a storage
failure is displayed. Use a browser/profile permitting local-file storage and export
answers periodically. Clearing browser storage or device failure requires restoring
an exported JSON backup. Never share another reviewer's answers before independent
review. The CLI publishes outputs atomically with fsync + exclusive linking and refuses
to overwrite files. A partial CLI write cannot publish a truncated judgment artifact.

## Commands: Generator → Review → Validate → Import → Reevaluation

From the repository root, first verify the checked-in package (new output path required):

```sh
uv run python -m uranus_research_service.lost_all_review check-lost-all-review \
  --package benchmark/review/lost-all-v1 --output /tmp/review-check.json
xdg-open benchmark/review/lost-all-v1/reviewer/review.html
```

In the browser select `blind-candidates.jsonl` and `annotation-package.json` from that
same `reviewer/` directory. Export `annotations-aurelius.json` to a local working folder.
Do not commit fabricated or empty answers. For an independently regenerated packet:

```sh
uv run python -m uranus_research_service.lost_all_review prepare-lost-all-review \
  --output /tmp/focused-human-review-v1
```

Validate even an incomplete response batch; the report lists missing/pending IDs and
uncertain counts. Import requires all 77 entries to be answered (uncertainty is allowed):

```sh
uv run python -m uranus_research_service.lost_all_review validate-lost-all-review \
  --package benchmark/review/lost-all-v1 --a /tmp/annotations-aurelius.json \
  --output /tmp/review-validation.json
uv run python -m uranus_research_service.lost_all_review import-lost-all-review \
  --package benchmark/review/lost-all-v1 --a /tmp/annotations-aurelius.json \
  --output /tmp/focused-human-judgments-v1.json
uv run python -m uranus_research_service.lost_all_review reevaluate-lost-all \
  --package benchmark/review/lost-all-v1 --a /tmp/focused-human-judgments-v1.json \
  --output /tmp/focused-human-reevaluation-v1.json
```

Only run the last steps after actual human review. Import binds answers to their
query/event/document via the fixed plan, records source hashes and declared human
provenance, and preserves the raw normalized submission for verification. Unknown,
duplicate, foreign-occurrence, invalid-grade and changed-package inputs fail closed.
Incomplete submissions are reported by validation and rejected by import. A reviewer
pseudonym is a provenance declaration, not authentication or production approval.
This focused single-review follow-up is **not** Phase 2D-A's independently reviewed,
adjudicated and human-approved frozen dataset; that stronger workflow stays unchanged.

## Reevaluation semantics (implemented, not yet executed with human inputs)

The evaluator reads the complete old rankings unchanged and reuses the original
metric function: binary relevant means grade >= 1, graded nDCG uses `2**grade - 1`,
K=5/10, no relevance threshold change. It reports all six requested metrics per case
and macro means over these four cases, separately for each model. With no known
positive, Recall/nDCG are undefined (`null`) and defined-case counts accompany means;
Hits/MRR remain zero. Unjudged entries have zero gain in these provisional pooled
metrics only; this is not a negative judgment or a corpus-recall guarantee.

Three distinct views are reported: historical draft, expanded mixed provenance, and
human-only. **Only in the new derived follow-up**, reviewed grades replace old draft
grades for the same pair; disagreements are explicitly recorded. Historical files
never change. Unreviewed old draft grades remain in the mixed view. A reviewed uncertain
pair removes the previous draft grade from the mixed view and remains unknown.

Outputs include old best known rank, new best human rank, relevant Top-10 IDs,
newly graded former-unjudged pairs, conflicts, unresolved IDs, coverage and a conservative
missing-judgment-only disappearance flag. Any unresolved pair leaves the total-loss
conclusion indeterminate. Disappearance solely through missing judgments is reported
only if new relevant Top-10 hits were previously unjudged, with no old-label conflicts
and no unresolved answers. Both-model failure is not a retrieval success.

The **historical frozen benchmark verdict** remains
`v5 provisionally fails one or more gates`. The **expanded-review reevaluation verdict**
is a four-case follow-up only. No global gates are rerun, overwritten or declared passed;
no inference is made about all 120 queries. No review result exists at delivery time.

## Hashes and reproducibility

All baseline benchmark artifacts and reports are byte-pinned in
`benchmark/contracts/lost-all-input-sha256.json`. Existing Phase-2D/2C hash checks are
also executed, including complete ranking population, eligibility and judgment identity.
The generator and every import/evaluation revalidate them. A mismatch aborts.

| Input | SHA256 |
| --- | --- |
| Query/ground truth | `a72b04ca44655ca4e8ba456e8d9698ff6ebbe47e1dde54f075780c9e6e4a8b53` |
| Public event snapshot | `2de49bc71942926e953f4de76d4b5dbcfe1780a6a2a20ee2b0feb6fa97cbf7f1` |
| v3 result/full rankings | `242b7c3c31537942ba960f009962ba2a48dae5ffb14a12360a57f4086f6eb8f2` |
| v5 result/full rankings | `e0ef32e5dba8d51d3a8086d73557e2f2b3418ee729b6e4863cf1c0a9f9f2760b` |
| Draft machine judgments | `ecf09f60fb6a31a96f5ecd21b39a7686df6f12726a814e7d764e443e54fbbc48` |

Raw `review-plan.json` file SHA256 (including final newline):
`a056f314d64fa52509a3d5eae997f31b622e09e298bc6dc875c4e53509781087`.
Canonical plan digest used by the existing ReviewBatch contract:
`1054abb042ed57f39e708df1c74fbea9c9f69db69c729203dd0393bd8d7dca05`.
`artifact-sha256.json` pins all generated pool/package/UI/provenance files. Unit tests
anchor the canonical plan and compare independent exports byte-for-byte.

## Validation and safety

Tests cover the four-case union, stable order/IDs, same-title distinct UUIDs, full
occurrence/combined-intent evidence, allowlisted blind metadata, invalid/duplicate/
unknown grades and IDs, uncertainty/completeness, hash failures, atomic no-overwrite,
synthetic-only deterministic evaluation with network disabled, and historical byte
identity. Synthetic responses are temporary test fixtures, never human artifacts.

Required checks: locked offline uv sync, Ruff, format, full pytest and diff check.
External integration fixtures retain their existing guards and CI requirements.
No production, DB writes, Qdrant writes, Encoder inference, training, threshold tuning,
alias/cutover or semantic activation. `semantic_query=false`. No PR merge.

Local validation on 2026-10-07: **537 passed, 24 skipped**; locked offline sync,
Ruff, format, diff check and the actual package-check CLI passed. The 24 skipped
tests are the existing external integration modules: `test_database`,
`test_structured_queries` (disposable PostGIS), `test_admin_parity` and
`test_semantic_parity` (pinned Admin environment), `test_semantic_index`
(disposable Qdrant), and optional `test_real_encoder` (real Encoder endpoint).
Their guards were not disabled. Required disposable integration/Docker validation
remains in the unchanged GitHub CI; no real-weight run is authorized by this task.
