# Phase 2B.2b completion report — annotation-ready draft

Date: 2026-10-05. Base: merged runtime refactor `5dbc99eb3e8f2925543eeba1914a30ff070bd658`.
[PR #5](https://github.com/sndcds/uranus-research-service/pull/5) contains implementation
`6d54a11d8d8cb2610cc59064efe9b10c605591ff`; both CI jobs passed. It remains unmerged.
Tooling and public artifacts are prepared. **Human ground truth is not yet approved.**
The distinction is intentional: the definition of done allows a reviewable draft with
working pooling, human-maintained judgments, snapshot binding and coverage checks.

1. **Snapshot source:** explicitly user-authorized `uranus_reader` on the webserver,
   through pinned Admin public SELECTs in one REPEATABLE READ, READ ONLY transaction.
   Existing Admin source boundary passed; stricter service runtime boundary did not.
   Runtime checks/grants were unchanged. Public API GET probes were diagnostic only;
   no API-derived rows enter the final dataset. No private/workflow/user data exported.
2. **Snapshot hash:** canonical source SHA256
   `295d51592050b67be40d7a4de8dd3ac5885fbe2562700b3e3578f8b107785029`.
   JSONL file SHA256
   `2de49bc71942926e953f4de76d4b5dbcfe1780a6a2a20ee2b0feb6fa97cbf7f1`.
   Snapshot `public-events-20261005`; captured `2026-10-05T17:42:15.403053Z`;
   reference `2026-10-05T00:00:00+02:00`; timezone Europe/Berlin. Manifest includes
   exporter hash/source revision; every exported event/context has a document hash.
3. **Event count:** 611 public events, 1,134 public occurrences; 671 total source rows
   counted without exporting unpublished contents. Full fixed snapshot is committed;
   no artificial events fill gaps. Historical/undated public records are intentionally
   included. Public schema is annotation-specific, not an index-compatibility claim.
4. **Query count:** 120 **proposals**, not 120 confirmed ground-truth cases.
5. **Languages:** DE 50, DA 35, EN 35. Human linguistic review remains required.
6. **Categories:** accessibility 9; ambiguous 6; atmosphere 6; combined 7;
   cultural style 11; exhibition 8; family 12; genre 6; location 9;
   multiple results 7; music 8; no-hit hypotheses 6; outdoor 1; paraphrase 7;
   readings 2; theatre 6; venue 6; workshops 3. Proposal coverage is not approved
   relevance coverage. Optional outdoor/readings/workshop coverage is limited.
7. **Candidate pool:** deterministic lexical retrieval, historical UUID-only unions,
   eligible-corpus diversity samples, optional manually supplied eligible IDs. Target
   20/case, 2,352 total pairs, 574 distinct pooled events. Three hard-filtered Saturday
   queries have four candidates each; no eligibility relaxation. Final order is blinded
   and deterministic, with no model/rank/score in CSV or judgment records. No fresh
   model inference, live vector reads or live collection mutation was performed.
8. **Scale:** 0 irrelevant, 1 partial, 2 clear, 3 direct/strong; human reason required,
   plus supporting fields for positive labels. Null means unjudged. Optional independent
   A/B ratings require explicit adjudication on disagreement.
9. **Human review:** 0 reviewed, 0 approved, 0 populated relevance labels. Assistant
   query proposals are explicitly labeled as such in provenance/notes. Importing human
   CSV edits never advances or approves case status. Human approval is an external
   reviewer attestation with identity/time and retained review revisions.
10. **No-hit coverage:** six hypotheses, **zero confirmed no-hit cases**. Confirmation
    requires all pooled grades 0 and a human full-eligible-corpus review, not just a
    negative candidate pool.
11. **Multi-hit coverage:** seven explicit multiple-results proposals, **zero confirmed
    multi-relevant cases**. Other cases may also have multiple relevant events once judged.
12. **Unique relevant events:** 0 established; unique events judged 0. Mean judged
    candidates/query 0. Relevance distribution empty. These are honest annotation-status
    counts, not model-retrieval results.
13. **Validation:** schema, grade/range, duplicate case/event, UUID, no-hit consistency,
    review/adjudication, snapshot/document hashes, closed public projection, blind pooling,
    hard occurrence eligibility, deterministic export/order, grouping, CSV roundtrip and
    committed artifact/report checks are covered by tests. `--require-approved` rejects
    the committed draft. Local/CI execution results are recorded in `docs/validation.md`.
14. **Remaining gaps:** humans must review query interpretations/translations, complete
    annotations, add missed candidates, confirm negatives against the whole eligible
    corpus, adjudicate differences and approve case versions. Missing accessibility or
    other public evidence remains unknown. The pool may miss relevant events. Later
    evaluation still needs an explicitly reviewed mapping to index documents and proof
    of identical authoritative SQL eligibility for both models.
15. **Dataset status:** **draft**. Human approval, minimum approved language/category/
    no-hit/multi-hit coverage, diversity and concentration gates are unmet. Tooling does
    not manufacture labels, fill missing grades or claim an approved evaluation set.
16. **Historical sources:** 30 queries and 900 unjudged candidate rows from the pinned
    Admin 2026-09-27 Jina-v3/E5-small/E5-base exports. File hashes are in
    `benchmark/sources.json`. Ninety additional multilingual query suggestions reference
    themes present in the public corpus but carry no relevance judgments. Existing nine
    synthetic pipeline goldens are retained separately and never merged into this corpus.
17. **No v3/v5 quality claim:** no controlled model comparison occurred; neither complete
    human judgments nor paired same-corpus model runs exist. Existing relevance thresholds,
    quality gates and `semantic_query=false` remain unchanged.

No live writes, grants, reindex, collection creation/deletion, alias change, deployment,
service restart, Admin cutover, Encoder cutover, Planner/Encoder changes or v3 cleanup.
Read-only source inspection/export is the only live-system work.

Review entrypoints: [guidelines](retrieval-annotation-guidelines.md),
[generated coverage](retrieval-ground-truth-v1.md),
[CSV](../benchmark/annotation/ground-truth-v1.csv),
[complete public evidence](../benchmark/annotation/evidence.md),
[operator/reproduction workflow](phase2b2b-ground-truth.md).
