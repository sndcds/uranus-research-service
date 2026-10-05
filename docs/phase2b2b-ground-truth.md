# Phase 2B.2b: public snapshot and human annotation preparation

This phase delivers a **draft annotation dataset**, not approved ground truth or a
v3/v5 comparison. `semantic_query` remains literal false. Runtime, thresholds, Planner,
Encoder, Admin, collection data and deployment configuration are unchanged.

## Source and reproducibility

Following the user's explicit authorization of `uranus_reader`, the existing pinned
Admin public source extraction was used in a single REPEATABLE READ, READ ONLY source
transaction. The existing Admin `SOURCE_BOUNDARY` passed. The stricter Research Service
runtime boundary did **not** pass: its combined CREATE/TEMP privilege predicate was true.
No grants were altered, no boundary was weakened, and the broad reader was not configured
as a service runtime reader. This is a separate operator snapshot, with fixed public
SELECT projections and an explicit role check. No Admin metadata/writer engine was used.

`scripts/export_public_ground_truth_source.py` is the reproducible operator adapter for
Admin release `340df4684611dbc4b8ec73a7702f1fad2ae1973c`. It uses that release's existing
public event/date/type SQL and source privilege check. The date SELECT adds only the
existing effective public status expression and venue city. DB credentials are consumed
on the server, never exported. The script runs over SSH stdin with bytecode disabled,
writes no remote files, and emits only allowlisted, contact-scrubbed public evidence.
Failures print a fixed safe error. This is not a runtime import of a sibling repository.

Public includes released/cancelled/deferred/rescheduled event and effective occurrence
statuses, exactly as the existing source predicate. The total count (671) is aggregate
metadata; only 611 public event documents are exported, with 1,134 public occurrences.
No unpublished row contents, private contacts, workflow tables, users or secrets are
selected into the artifact. Text uses the existing `public_clean` sanitizer. Missing
text stays empty, not invented. The snapshot deliberately includes historical/undated
public events; it is not an upcoming-only inventory. Area geometry and private/admin
metadata are absent. Captured title/summary/description, languages/tags/type/genre labels,
price type and effective date/venue/space/accessibility evidence are explicitly typed.

Before the role clarification, anonymous GET probes checked the public API's shape and
counts; **no API data is part of this snapshot**. The final corpus comes from SQL only.
The initial diagnostic export was superseded by the final projection with explicit city
and occurrence status. No live encoder inference or Qdrant content access occurred.

The committed 611-row JSONL is the reproducible frozen source. Re-running the exporter
against a changing live database produces a **new** snapshot, not the historical state.
The manifest binds capture/reference times, timezone, counts, extractor SHA256, source
revision, canonical source hash, file SHA256 and deterministic UUID ordering. Each event
has its own document hash covering all exported evidence and contexts. Later annotation
never reads live data. File creation is exclusive; revisions use new destinations.

This `public-annotation-snapshot-v1` schema is separate from `event-public-v4`. It contains
public annotation evidence, not vectors, index payloads or a SQL database backup. A later
same-corpus model run must explicitly build both corpora from this frozen input and
validate its mapping/eligibility parity. No compatibility with a current live index is
asserted. The broad source timezone window is 1900–2100; out-of-window dates must be
handled explicitly in a new snapshot if introduced.

## Pooling and artifacts

`benchmark/query-proposals-v1.json` contains 30 historical unjudged queries plus 90
assistant-proposed multilingual queries, each explicitly awaiting human interpretation,
language and relevance review. Historical candidates are UUID-only unions from 900
unjudged rows across Jina v3, E5 small and E5 base; ranks and scores are discarded.
`benchmark/sources.json` pins source commit/file hashes. The nine old synthetic goldens
remain unchanged under `tests/fixtures`, classified `synthetic_pipeline_goldens` and
excluded from this corpus. Historical files are classified `historical_unjudged`.

For each query, filter by hard eligibility first. Pool round-robin from: token-frequency/
inverse-document-frequency lexical candidates over public evidence; available historical
UUIDs; and deterministic corpus coverage samples. Optional manual UUIDs are included
first but must pass eligibility. Historical ordering/ranking is not reused. Target 20,
allowed 10–30; if fewer eligible events exist, keep all without relaxing constraints.
Three Saturday cases have only four eligible events. Final review order is a canonical
hash permutation independent of ranking/source; event titles and complete evidence are
always public. No fresh model retrieval was required or performed.

- `benchmark/ground-truth-v1.jsonl`: snapshot-bound generated cases; grades/nulls and
  review fields are explicit. No source model/rank/score in judgments.
- `benchmark/annotation/ground-truth-v1.csv`: editable blinded review view; formula-prefix
  escaping prevents spreadsheet formulas. Evidence columns are immutable during import.
- `benchmark/annotation/evidence.md`: full public evidence keyed by UUID and document hash;
  never rely on truncated CSV excerpts alone.
- `benchmark/pool-audit.json`: candidate/eligibility counts, separate from annotation.
- `benchmark/ground-truth-v1-report.json` and generated
  [coverage page](retrieval-ground-truth-v1.md): proposals and approved evidence separated.
- `benchmark/schemas`: closed JSON Schema snapshots; runtime validators additionally
  enforce cross-field, snapshot/hash, human-review and eligibility invariants.

## Offline commands

Use the existing virtual environment. No model or network dependency is needed for these
commands. Output files/directories must not already exist.

```sh
# Only if explicitly acquiring a NEW source snapshot; current snapshot is committed:
ssh awendelk@webserver 'sudo -n env PYTHONDONTWRITEBYTECODE=1 /var/lib/uranus-admin/releases/340df4684611dbc4b8ec73a7702f1fad2ae1973c/backend/.venv/bin/python -B -' \
  < scripts/export_public_ground_truth_source.py > /tmp/new-public-export.json

uv run uranus-research-service benchmark snapshot-from-export \
  --input /tmp/new-public-export.json --exporter scripts/export_public_ground_truth_source.py \
  --snapshot-id new-public-snapshot --output /tmp/new-public-snapshot

uv run uranus-research-service benchmark prepare-pool \
  --snapshot benchmark/snapshots/public-events-20261005/events.jsonl \
  --manifest benchmark/snapshots/public-events-20261005/manifest.json \
  --queries benchmark/query-proposals-v1.json \
  --historical benchmark/historical-candidate-ids.json --output /tmp/new-review-pool

uv run uranus-research-service benchmark import-annotations \
  --snapshot benchmark/snapshots/public-events-20261005/events.jsonl \
  --manifest benchmark/snapshots/public-events-20261005/manifest.json \
  --cases benchmark/ground-truth-v1.jsonl \
  --annotation /tmp/human-edited.csv --output /tmp/human-edited.jsonl

uv run uranus-research-service benchmark coverage \
  --snapshot benchmark/snapshots/public-events-20261005/events.jsonl \
  --manifest benchmark/snapshots/public-events-20261005/manifest.json \
  --cases benchmark/ground-truth-v1.jsonl --output /tmp/coverage.json \
  --markdown-output /tmp/coverage.md
```

`validate-ground-truth` uses the same inputs as coverage. `--require-approved` rejects
this initial draft. `import-annotations` never approves or advances review status;
follow the [human workflow](retrieval-annotation-guidelines.md).

Coverage gates are dataset checks, registered before human labeling: all cases approved;
>=50 approved queries; >=5 per language; all 15 core categories; >=3 confirmed no-hit;
>=5 multi-relevant cases; >=30 unique relevant events; no more than 50% of queries sharing
a positive among the three most frequent relevant events; similar-query pairs reviewed
and grouped. These are conservative starting gates, not statistical validity claims.
Draft status persists if any gate fails. No tuning of existing model-quality gates.
