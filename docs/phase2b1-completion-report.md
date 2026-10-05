# Phase 2B.1 delivery report

Implementation and isolated v5 validation are complete; representative retrieval
quality and measured same-corpus v3/v5 comparison remain outstanding. The rollout
criteria are therefore **not all proven**. Nothing is enabled for users.

1. **Ported modules:** public semantic/document contracts and builders, vector-document
   pure helpers, evidence contexts/validation/explanations, relevance limits, sync
   planning, event snapshot SQL and complete eligibility. Precise source hashes in
   `phase2b1-port-manifest.json`. No wholesale Admin copy or runtime sibling imports.
2. **Encoder:** `/version`, `/ready`, `/embed`, `/chunks`; exact 0.2.0/v5/Torch identity,
   closed contracts, bounded fixed-origin transport, strict vector and chunk checks.
3. **Qdrant:** separate query/maintenance classes; collection info, scroll, query,
   build creation, upsert, payload replacement, point deletion, read-only aliases.
   Live writes/active collection writes and alias switching are disabled.
4. **Manifest:** required complete identity, source/corpus hashes/counts, reserved point,
   full content verification. Missing fields cannot default to a v5 identity.
5. **Names:** separate `kulturbytes_events_jina_v5_build_<id>`; current write guard
   requires `test_` IDs. Venue/organization contracts retained; taxonomy v5 deferred.
6. **Index pipeline:** complete source snapshot closed before HTTP, Encoder chunking,
   incremental reuse, changed-content embedding, metadata updates, stale reconciliation,
   completion marker, validation, multilingual smoke and immutable reports.
7. **Evidence safety:** exact owner/entity/model/version/schema/hash/eligibility and
   source context checks, plus current public document freshness verification.
8. **Rehydration:** authoritative public/date/venue/space/occurrence SQL, followed by
   context selection and unchanged v3 relevance algorithm. No Qdrant factual authority.
9. **Dataset:** nine synthetic DE/DA/EN goldens across accessibility, location and
   descriptive categories; two public fixture events and a draft exclusion.
10. **v3/v5:** reproducible offline report comparison and preregistered gates exist;
    controlled v3 runner/report and representative paired measurement are still absent.
    Existing production v3 data is not substituted as a baseline.
11. **Performance:** actual local v5 build/retrieval measurements and process CPU/RSS
    recorded in `validation.md`; Encoder CPU/peak RSS and production-scale behavior
    were not measured. No production claims.
12. **Tests:** final combined run **338 passed**, including 24 real integration tests
    (two with real Encoder) and untouched Admin differential execution. Ruff, format,
    locked sync and diff checks passed.
13. **CI:** disposable Qdrant added to existing PostGIS/Admin-parity job, no weights
    required. Refer to the PR checks for actual hosted results.
14. **Docker:** local offline wheel-based image build passed; no deployment.
15. **Live preflight:** documented OBSERVED/INFERRED/NOT CHECKED. Qdrant 1.19.1;
    configured Encoder still v3/onnx-merged; no alias; existing foreign v5 collections.
16. **Live unchanged:** no collections/points/aliases/grants/readers/deployments/services
    changed, no inference/reindex, no Admin/Planner/Encoder changes, no v3 deletion.
17. **Before Phase 2B.2:** complete controlled v3 baseline and representative judged
    goldens, assess per-language/category regressions and v5 thresholds, instrument
    Encoder resources, verify actual readers/capacity and intended v5 endpoint. Review
    scaling of full collection validation/current-document refresh. Decide whether
    additional entity/taxonomy consumers justify migration. Any live build, alias
    operation, Admin adapter or public semantic activation requires a separate task.
