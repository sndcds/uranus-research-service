# Human annotation guidelines

This is a review task, not a model evaluation. The initial files contain query proposals
and candidate pairs, **no relevance judgments**. The assistant must never approve its
own proposed labels. Reviewers judge only the frozen public evidence and record their
own identifier. No model/rank/score provenance is shown in the annotation view.

## Scale and evidence

| Grade | Meaning | Illustrative example for “quiet live music in a cosy atmosphere” |
| --- | --- | --- |
| 0 | Irrelevant or required semantic evidence absent | An unrelated talk; no relevant musical program |
| 1 | Weak/partial relevance | Music is evidenced, but the desired atmosphere is not |
| 2 | Clearly relevant | Live music plus credible, matching atmospheric descriptions |
| 3 | Direct/strong match | Public text explicitly describes an intimate, quiet live performance |

These examples are instructions, not labels for any snapshot event. Do not grade by
keyword overlap alone. Synonyms and indirect descriptions can establish meaning; explain
why. A shared word, genre stereotype, venue reputation or personal knowledge alone cannot.
For every judgment enter a short reason; positive grades also require `supporting_fields`.
Quote or identify the relevant public passage and, where applicable, the occurrence/venue/
space UUID in the reason. Full public evidence is in `benchmark/annotation/evidence.md`;
find the event UUID and verify its document hash. The CSV excerpt is only an introduction.

Missing information is **unknown**. Missing wheelchair-access information does not prove
accessibility or inaccessibility. If accessibility is an essential requested property,
a positive accessibility judgment requires actual public access evidence in the applicable
context; otherwise grade 0 with “not evidenced”, not “not accessible”. A statement about
one space cannot establish access to another. Preserve venue, space and occurrence context.

For vague requests, write a defensible interpretation in case notes before labeling. If
reviewers cannot agree on the interpretation, leave the case generated/unapproved or
revise it as a new version. Do not quietly choose an interpretation to improve metrics.

## Hard eligibility before semantics

`eligibility` is an explicit, closed snapshot predicate: optional start-date bounds,
ISO weekdays (Monday=1 … Sunday=7), exact normalized public city and venue UUID. All
conditions must hold on the **same occurrence**. Default means all public snapshot
events, including historical events; it does not imply “today” or “upcoming”. Undated
events cannot satisfy dated filters. Cancelled/deferred/rescheduled public statuses
remain visible evidence and must be considered in the human interpretation.

For the Saturday proposals, 2026-10-10 and Flensburg are hard conditions; jazz is judged
semantically. Genre/accessibility text is not silently converted into a taxonomy or
geospatial predicate. The reviewer must confirm this interpretation against the intended
research question. Unsupported hard requirements require a new reviewed predicate or a
revised case, not an improvised filter. This annotation predicate is not a complete
Planner-v13/PostGIS implementation; later evaluation must demonstrate equivalent SQL
eligibility for these exact cases and population before comparison.

An event outside hard eligibility may never receive a judgment in the case; the validator
rejects it. Inspect only the relevant occurrence(s) when assessing location/access evidence.
A city string is not a municipality boundary. Do not infer geometry or venue inheritance
beyond the captured effective public context.

## No-hit, multiple hits and pool bias

The six `no_hit` query proposals are hypotheses, not confirmed negatives.
`expected_no_hit` starts null. Set it true only after all candidate judgments are 0 **and**
a reviewer has inspected the whole eligible frozen corpus (record
`no_hit_review_scope: full_eligible_corpus`). A pool with no positive result alone does not
prove no hit. Positive cases must have at least one grade above 0; keep every relevant
alternative, not only a preferred answer. Document partial matches consistently.

Pooling can miss relevant events. Use full-corpus browsing to add obvious missing
candidates through a manual UUID input and prepare a new immutable pool. Historical ID
sets, lexical retrieval and deterministic coverage sampling have different biases; none
is ground truth. No fresh v3/v5 inference or live collection query was run for these pools.
Unjudged is null/unknown, **never zero**. No official recall, precision or nDCG should be
computed by silently treating unjudged retrieved documents as negatives. A later evaluator
must reject unjudged results or publish an explicit pooled-evaluation protocol and limits.

## Review and approval

1. Preserve the original snapshot and generated files. Work on a new CSV/JSONL revision.
2. Review query language, category, interpretation, hard eligibility and `query_group`.
   DE/DA/EN translations are deliberate related cases, not independent observations.
   Exact duplicate queries are rejected; similar same-language pairs are reported.
   Automated string similarity cannot discover every translation/paraphrase: human
   grouping review remains required. Language fluency, especially Danish, must be checked.
3. Enter `reviewer_a`, `relevance_a`, final `relevance`, reason and supporting fields in
   the CSV. Optional reviewer B should annotate an independent copy without seeing A's
   grades. Combine later. Disagreement requires `adjudicated_relevance`; final relevance
   must match it. Reviewer identities must differ. No assistant/LLM grades count as human.
4. `import-annotations` checks immutable evidence columns and imports edits into a **new
   generated draft**, never approved data. It deliberately does not advance status.
5. Human case review sets `expected_no_hit`, interpretation notes and `review_status:
   reviewed` in a new JSONL. Every pooled candidate needs a final human grade. A human
   approver then creates an `approved` revision with `approved_by` and aware `approved_at`.
   These fields are reviewer attestations, not authentication or proof of authorship;
   retain reviewed revisions/code review as the external approval record.
6. Validate hashes, references and coverage. Only approved cases in a reviewed dataset
   may enter an official benchmark. This task performs no approval. Keep `purpose` null
   until a separately agreed calibration/evaluation protocol assigns groups together.

Do not reuse judgments after changing event text, context, snapshot, reference time or
eligibility. New content requires new hashes and renewed human review. Do not copy private
contacts, user queries, workflow notes or unpublished content into reasons or query proposals.
