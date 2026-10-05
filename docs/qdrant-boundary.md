# Qdrant boundary — Phase 2B.1

PostgreSQL is authoritative. Qdrant supplies retrieval evidence only. Query and
maintenance use separate classes, fixed validated origins, an API key, no redirects,
`trust_env=False`, identity content encoding, strict JSON, a total request deadline,
4 MiB request limit and 16 MiB response limit. Provider bodies never become errors.
There are no arbitrary caller-selected collection names or HTTP indexing endpoints.

Event collection: `kulturbytes_events_jina_v5_v1`; build collections:
`kulturbytes_events_jina_v5_build_<id>`. Venue and organization use analogous plural
names. Actual writes in this phase require a `test_` build ID and isolated target.
Unnamed 1024-dimensional Cosine vectors only; named vectors or a different distance,
model, version, revision, owner, entity or schema fail closed. Existing live v5-named
collections use a different contract and are explicitly not adopted.

## Manifest

Reserved point `00000000-0000-0000-0000-000000000001`, manifest owner
`uranus-research-service-manifest-v1`, fixed unit vector. It has no entity_id and is
explicitly excluded from search. Corpus chunk count excludes this one extra point.
The manifest contains index owner, entity, public document schema, exact embedding
identity/revision/version, dimensions, distance, chunk version, build ID, timestamp,
source snapshot hash, persisted corpus hash, document count, chunk count, complete=true.
Closed schema: `contracts/semantic/Manifest.json`.

The reserved-point strategy works with the tested Qdrant 1.19.0 REST contract and keeps
completion invalidation in the same point API. Live 1.19.1 exposes collection metadata,
but its existing metadata is a different contract. No reliance on writable collection
custom metadata or name-based compatibility. Manifest owner is an integrity boundary,
not a cryptographic defense against an administrator controlling Qdrant credentials.

Validation reads info plus a bounded full scroll (64 points/page, 100,001 total cap),
rejects repeated IDs/offsets, verifies deterministic IDs and closed public payloads,
and checks the complete hash/count. Full validation publishes process-local immutable
verified generation state for ten minutes. Queries use collection info and a direct
manifest-point fetch; they never scroll or automatically revalidate. Mismatch or expiry
invalidates semantic readiness and fails closed. Large full scans may still exceed the
readiness deadline. See [generation validation](semantic-generation-validation.md).
Before creating a completion marker, persisted
payloads must equal desired payloads, with only the Admin one-ULP coordinate tolerance.
The stored JSON is then hashed exactly, so later drift is detected.

## Identity and maintenance

Point UUID = UUIDv5(namespace `f6d7a7df-8744-4d7b-a928-0a3df9335a36`,
`<entity_type>:<entity_uuid>:<chunk_kind>:<sha256 UTF-8 chunk text>`).
Embedding identity is **not** in the ID; isolation is guaranteed by collections and
manifest/version validation. Changed content changes the ID, triggers a new embedding
and stale deletion. Metadata changes preserve the vector; unchanged points are skipped.
Foreign/v3 points cause failure even if their IDs or dimensions happen to match.

Builds never target the stable active name. Aliased or sealed build collections refuse
ordinary writes, including completion-marker deletion. New data needs a new generation.
Unsealed interrupted builds can resume; only explicit disposable recovery tests may
modify a sealed, unaliased test generation. No recovery override is exposed by the CLI.
No automatic retry/reindex/fallback, production override, alias mutation or collection
cleanup is implemented. Integration fixture teardown deletes only its generated local
test collection; live data is never addressed by it.
