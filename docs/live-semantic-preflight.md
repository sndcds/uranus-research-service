# Live semantic preflight — 2026-10-05

Read-only SSH inspection explicitly authorized via `awendelk@webserver`. Observations
at approximately 16:46–17:00 Europe/Berlin; a point-in-time inventory, not readiness
for a production build. Only GET requests, filesystem/system metadata reads and
read-only PostgreSQL catalog SELECTs were performed. Existing service credentials
were consumed inside a remote Python process; no secret values were printed or saved.

## OBSERVED

- Qdrant **1.19.1**; collection/alias metadata authenticated with the existing key.
  All listed collections green; all have indexed_vectors_count=0, two segments.
  Alias list is empty.
- Host root filesystem: 77 GiB total, 61 GiB used, **14 GiB available**, 83% used.
  RAM: 3915 MiB total, 2991 used, 923 available (242 free); swap: 6501 total,
  6311 used, 189 free. Four CPUs; load 2.61 / 1.74 / 1.43 at first observation.
- PostgreSQL **16.15**, PostGIS **3.4.2** in inspected `gis` and `oklab` databases.
  Roles `uranus_reader`, `registry_reader`, `uranus_console_reader` exist and can
  log in; none has superuser, CREATE ROLE or CREATE DATABASE attributes.
  This does **not** prove the service's effective least-privilege boundary.
- Existing configured Planner `/ready`: HTTP 200, status ready. No planning performed.
- Encoder `/health`: HTTP 200, status ok. Configured EMBEDDING_URL uses port 6335.
  Authenticated `/version` and `/ready` on this endpoint report **0.1.0 / jina-v3**,
  repository `jinaai/jina-embeddings-v3-hf`, revision
  `d18862d9a48706220815554fac3ebb4dfa46fc28`, dimensions 1024,
  backend **onnx-merged**, chunk version `sections-480-overlap64-v2`.
  Embedding version:
  `d18862d9a48706220815554fac3ebb4dfa46fc28:native-transformers5.17.0-retrieval-normalized-f32:sections-480-overlap64-v2`.
  It is ready for its own v3 contract and **incompatible with this v5 consumer**.
- No listener on the expected Research Service loopback port 6338; `/version`
  and `/ready` connection attempts failed. No claim about another deployment address.
- Existing research AI SSH tunnel was active initially and in auto-restart state at
  a later inventory read. No intervention was performed.

| Collection | Points | Vectors | Storage |
| --- | ---: | --- | --- |
| kulturbytes_events_jina_v3_v1 | 2993 | 1024 Cosine | vectors/payload on disk |
| kulturbytes_venues_jina_v3_v1 | 300 | 1024 Cosine | vectors/payload on disk |
| kulturbytes_organizations_jina_v3_v1 | 151 | 1024 Cosine | vectors/payload on disk |
| kulturbytes_event_taxonomy_jina_v3_v1 | 115 | 1024 Cosine | vectors/payload on disk |
| kulturbytes_project_knowledge_jina_v3_v1 | 75 | 1024 Cosine | payload on disk |
| kulturbytes_events_jina_v5_build_20261005T091117 | 656 | named `dense`, 1024 Cosine | payload on disk |
| kulturbytes_events_jina_v5_smoke_20261005T085249_1024 | 12 | named `dense`, 1024 Cosine | payload on disk |
| kulturbytes_events_jina_v5_smoke_20261005T085249_512 | 12 | named `dense`, 512 Cosine | payload on disk |
| kulturbytes_events_jina_v5_smoke_20261005T085249_256 | 12 | named `dense`, 256 Cosine | payload on disk |
| uranus_bench_events_e5_base | 1128 | 768 Cosine | vectors/payload on disk |
| uranus_bench_events_e5_small | 1128 | 384 Cosine | vectors/payload on disk |
| uranus_bench_events_jina_v3 | 1124 | 1024 Cosine | vectors/payload on disk |

Existing v3 HNSW configuration: m=16, ef_construct=100, full_scan_threshold=10000,
max_indexing_threads=1, HNSW on_disk=false. Existing v5 build metadata reports
owner `kulturbytes-research-planner-v5`, embedding_schema_version `jina-v5-events-v1`,
chunk_schema_version `events-v1`, chunk_max_words=220, chunking_enabled=true.
These collections predate this task. They were neither created nor adopted by it.
They have a different document/chunk/owner contract and cannot satisfy the new manifest.

## INFERRED

High swap occupancy and low available memory warrant an isolated capacity trial before
any later production operation. Free disk alone cannot establish safe write capacity.
Names containing v5 do not establish vector-space or evidence compatibility.

## NOT CHECKED

Production write capacity, collection contents/vectors, model inference, application
DB reader effective grants/ownership, authoritative source counts, full collection disk
sizes, encoder deployed elsewhere, service deployed elsewhere, production reindex,
alias switching and rollback performance. The supplied claim of a validated v5 encoder
is supported by the separate repository/local test, not this live endpoint.

No collection, point, alias, database grant, deployment, reader, service, Admin,
Planner, Encoder or v3 data was changed. No live write override was used.
