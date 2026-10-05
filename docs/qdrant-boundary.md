# Qdrant extraction and collection boundary

No phase-1 Qdrant client, connection, collection creation, write or alias operation.
The following is based on Admin source, not an inventory of running servers.

| Entity | Current registered collection | Document schema | Proposed separate v5 collection |
| --- | --- | --- | --- |
| event | kulturbytes_events_jina_v3_v1 | event-public-v4 | kulturbytes_events_jina_v5_v1 |
| venue | kulturbytes_venues_jina_v3_v1 | venue-public-v1 | kulturbytes_venues_jina_v5_v1 |
| organization | kulturbytes_organizations_jina_v3_v1 | organization-public-v1 | kulturbytes_organizations_jina_v5_v1 |
| taxonomy | kulturbytes_event_taxonomy_jina_v3_v1 | taxonomy-public-v1 | kulturbytes_event_taxonomy_jina_v5_v1 |

The active normal semantic query uses the event collection. Venue/organization
collections have operator indexing and evidence contracts, but are not queried by
that event-only endpoint. Taxonomy retrieval is optional and gated by a reviewed
policy; source configuration alone does not establish production activation.
The legacy event pilot instead derives `<QDRANT_COLLECTION_PREFIX>_events_<model>`.
Its historical E5/v3 registries and candidate-only gateway are not a fallback for
current validated evidence retrieval.

All proposed v5 collections use **1024, Cosine**, initially preserving Admin's
unnamed vector convention. `index_owner` is `kulturbytes-semantic-search-v1` for
entity collections and `kulturbytes-taxonomy-v1` for taxonomy.

## Payload and IDs

Retain entity type/ID, display name, source update timestamp, document schema,
embedding model/version, content hash, chunk kind/index/text and required evidence
contexts. Event contexts carry occurrence/venue/space associations; filters include
area IDs, composite genre keys and existing public location metadata. Organization
areas distinguish home from activity. Avoid copying private contacts or unrelated
source columns. PostgreSQL remains the source of facts and eligibility.

Entity point IDs are UUID5 over `entity_type:entity_id:chunk_kind:content_hash` using
the existing namespace. Legacy event pilot IDs differ; do not rewrite them in place.
Taxonomy IDs use UUID5 of collection plus the canonical vocabulary key. Changing
collection for v5 naturally separates taxonomy IDs. Preserve the algorithm and
hash normalization; no random per-run point IDs.

`vector_sync` reuses unchanged embeddings, updates metadata separately, embeds
changed content in bounded batches and deletes stale chunks only after upserts.
Full-snapshot reconciliation can remove orphaned/deleted/publicly-ineligible
entities; partial snapshots may only reconcile selected entities. Foreign owners,
wrong entity and wrong embedding space must fail before any destructive action.

## Compatibility and evidence

Current `Qdrant.info()` only checks dimensions and Cosine. The future consumer must
also verify a collection manifest with model, revision/embedding version, document
schema and owner. Collection metadata is supported by current
[Qdrant collection APIs](https://qdrant.tech/documentation/manage-data/collections/).
Verify the deployed Qdrant version before choosing metadata versus a separate
manifest mechanism. Never infer compatibility from a collection name alone.

Preserve SQL eligibility → query embedding → bounded vector candidates → evidence
validation → authoritative SQL rehydration → context selection → threshold/order.
Payload hash equality proves self-consistency, not freshness against changed SQL
text; phase 2 must also compare evidence against the current document/context.
Top-K results do not establish exact counts, population totals or authoritative dates.

## Blue/green design only

1. Build a new entity-specific `kulturbytes_<entities>_jina_v5_build_<id>` collection.
2. Validate complete source snapshot, vector count, manifest, foreign points, finite
   normalized vectors, smoke retrieval and reviewed same-corpus benchmarks.
3. Record an immutable build report and the old alias target.
4. An explicitly authorized operator command may atomically switch an entity alias,
   e.g. `kulturbytes_events_current`; queries/benchmarks never switch aliases.
5. Rollback switches the alias **and consumer encoder expectation** to the matched
   old deployment. A v5 query encoder cannot safely query a v3 alias target.

Keep all old collections/build reports until a separately authorized cleanup.
Partial builds remain inactive. Phase 1 neither creates the proposed collections
nor asserts that aliases already exist.
