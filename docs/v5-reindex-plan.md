# v5 reindex plan — not executed on live

Live findings: [read-only preflight](live-semantic-preflight.md). A future production
build requires separate authorization, a reviewed reader boundary, compatible v5
Encoder, capacity evidence and a different explicitly reviewed operator write policy.
The current CLI cannot perform it.

1. Open checked REPEATABLE READ / READ ONLY source and separate area snapshots.
   Extract all public event-public-v4 documents, bounded at 10,000 events/64 MiB;
   fail on overflow. Record document hash and complete source snapshot hash.
2. Close snapshots before Encoder/Qdrant calls. Event first and currently only.
   Venue/organization are deferred pending a demonstrated consumer; semantic taxonomy
   requires its own corpus, v5 manifest and new calibration.
3. Chunk exclusively through `/chunks`; record counts, hashes, average/max tokens.
   Same chunk_version does not imply equal v3/v5 chunk boundaries.
4. Use a fresh `kulturbytes_events_jina_v5_build_<id>`. Current isolated experiments
   require `<id>` beginning `test_`. Future reserved stable names are
   `kulturbytes_events_jina_v5_v1`, `kulturbytes_venues_jina_v5_v1`,
   `kulturbytes_organizations_jina_v5_v1`, `kulturbytes_event_taxonomy_jina_v5_v1`.
5. Reconcile in batches of two embeddings/upserts; scroll 64, delete 64. No retries
   in transport; operator retries the same build with a new immutable report path.
   New points precede stale deletion. Missing completion manifest prevents readiness.
6. Verify every persisted point/payload/ID, counts and hash; commit completion manifest;
   verify collection and multilingual smoke; save report, run reviewed goldens.
7. No alias change. A possible future alias is `kulturbytes_events_current`.
   Rollback in this phase means retaining the previous reader/collection untouched.
   An incomplete test build can be repaired or explicitly removed by its test fixture.
   No automatic cleanup, retention timer or v3 deletion.

## Capacity estimates

The isolated real-weight fixture: **2 public events, 5 chunks**, 20,480 raw vector
bytes (5 × 1024 × float32), about 8.7 KB serialized point payloads, plus manifest.
Live source entity/chunk counts for a v5 build were **not measured**. Existing 2,993
v3 event points are an observed inventory, not a v5 chunk estimate.

For planning only, budget `N * 4096` vector bytes plus actual serialized payload bytes.
A rough allocation envelope is 2–4 times that subtotal to allow HNSW, point IDs,
Qdrant metadata, payload/index structures, WAL and temporary segments; this is not a
measured compression/index factor. Additionally reserve storage for simultaneous old
and new collections, snapshots and optimization work. For the tiny fixture this gives
roughly 58–117 KB plus fixed engine/segment/WAL overhead, which can dominate tiny data.
No production collection size/throughput estimate is asserted without a representative
snapshot and isolated measurement. The live host's 14 GiB free space and high swap use
are insufficient evidence for safe writes.
