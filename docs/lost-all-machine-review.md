# Two-pass blind machine review of the 77 focused pairs

This is machine-proposed annotation and machine-only exploratory reevaluation, never
human-reviewed/approved judgments or ground truth. The Human workflow from PR #10 is
unchanged. The earlier 5,739-judgment Phase-2D-M run is not executed by this task.

## Baseline and separation

PR #9 was explicitly authorized and merged as `f4ace750002d4ef4962ecc7eb93274743d5b3890`;
PR #10 as `078bf7dd3445f5488a4dd91acba85f4b1ea5cf94`. Both had green checks and no
blocking reviews, threads or branch requirements. This work starts from the latter
main commit and has no open-PR dependency. Its own PR must not be auto-merged.

All prior benchmark/Human artifacts are byte-pinned by
`benchmark/review/lost-all-v1/machine/frozen-input-sha256.json`. The worker itself reads
only the two reviewer input files, the versioned judge prompt and its own code for
provenance hashes. It never invokes the operator review-plan loader, reads old labels
or rankings, or reads the other pass. Preparation/analysis and model judging are separate.

Input packet raw SHA256:
`068bd7b58e0a1aa7749d93223df7cfadc9dd35d4a72116138c7fd714703f03bb`.
Package metadata raw SHA256:
`b7e22e115b0892446128062426deca538f2ce807b47d998a214ae555173cdd02`.
The frozen packet has 77 opaque annotation IDs; hash or count changes abort.

## Judge contract

Uses the existing Answer contract, narrowed to `graded`, `uncertain`,
`needs_more_context`, with explicit boolean `uncertain`. Grades are strict integers
0–3, or null for either uncertainty state. Uncertainty is not zero. Positives require
nonempty cited fields and eligible occurrence IDs. Foreign occurrences and unsupported
fields fail validation. Valid structured output is not proof of semantic correctness.

The existing candidate rubric is authoritative, including the previously confirmed
single-concert interpretation of genre diversity. Workshop participation/young audience,
wheelchair access versus general reduced barriers, restrictions at each occurrence,
and evening/participatory dancing must all be checked separately. No rubric is tuned
to model results. Event data are untrusted evidence, never instructions.

The actual Responses API user payload has only opaque annotation ID, query, language,
rubric/checklist, eligibility and complete public evidence. Query ID, event ID and category
are deliberately omitted. No historical grades, sampling origin, ranking, scores, gates
or model provenance reach the judge. The API envelope necessarily names the *judge*
model; it does not name either retrieval system. No tools, web, conversation state or
previous response ID are provided. Instructions prohibit external knowledge and ranking
speculation. Tests exercise the actual HTTP payload, not just a template.

Model explicitly selected: `gpt-5.4-mini-2026-03-17`. Parameters: temperature 0,
reasoning effort `none`, 1,200 maximum output tokens, strict JSON Schema,
`store=false`, no seed claim. Two stateless request sequences have separate run IDs and
response IDs; each sees exactly the same rubric and evidence. Fixed settings do not
guarantee determinism or statistical independence. Correlated machine errors can agree.

The [official Structured Outputs documentation](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses)
and [model documentation](https://developers.openai.com/api/docs/models/gpt-5.4-mini)
were inspected on 2026-10-07. No judge inference uses these web pages as event evidence.

## Transport, persistence and failure handling

Reuses the merged `machine_judge.OpenAIJudge` fixed-origin bounded transport and
`atomic_new` persistence, without changing the historical module. API key only from
`OPENAI_API_KEY`; no key, cookies or provider error body is logged/stored. No redirects,
no proxy inheritance, JSON/identity response checks and strict timeout/size limits.

A per-run lock protects single-writer journals. Each request reserves its attempt
before network I/O; completion and valid answer are atomically fsynced/exclusively
published. Completed records are immutable. Restart requires `--resume` and exactly
matching input, model, prompt and worker hashes. Existing valid answers skip POSTs.
Recovery can publish a persisted successful completion after an interrupted final write.
An unknown in-flight attempt still consumes the maximum three-attempt budget.

Only transient network/429/selected server errors retry, with bounded exponential
backoff. Invalid JSON, refusals and contract violations fail closed without repair or
adaptive reprompting. A server-accepted request interrupted before persistence can be
billable without known usage; this is not an exactly-once billing guarantee.

## Commands

Run independently, after providing the environment key without printing it:

```sh
uv run python -m uranus_research_service.machine_blind_review run \
  --pass-id a --run-id focused-machine-20261007-a \
  --model gpt-5.4-mini-2026-03-17 --output /tmp/focused-machine-20261007-a
uv run python -m uranus_research_service.machine_blind_review run \
  --pass-id b --run-id focused-machine-20261007-b \
  --model gpt-5.4-mini-2026-03-17 --output /tmp/focused-machine-20261007-b
```

Default package is `benchmark/review/lost-all-v1`; default prompt is its
`machine/prompt-v1.txt`. Resume by repeating the same command with `--resume`.
Use a new destination/run ID for an intentionally new run, never overwrite prior answers.

Manual import accepts the same complete machine-pass envelope (manifest, records,
summary) produced by these commands. This preserves declared model/prompt/input and
request provenance; it is not cryptographic authentication of an external producer.
The importer rejects Human provenance and applies identical answer/evidence validation:

```sh
uv run python -m uranus_research_service.machine_blind_review import \
  --input /tmp/focused-machine-20261007-a/annotations-pass-a.json \
  --output /tmp/validated-machine-a.json
uv run python -m uranus_research_service.machine_blind_review compare \
  --a /tmp/focused-machine-20261007-a/annotations-pass-a.json \
  --b /tmp/focused-machine-20261007-b/annotations-pass-b.json \
  --output /tmp/focused-machine-agreement.json
uv run python -m uranus_research_service.machine_blind_review consensus \
  --input /tmp/focused-machine-agreement.json --output /tmp/focused-machine-consensus
uv run python -m uranus_research_service.machine_blind_review reevaluate \
  --input /tmp/focused-machine-agreement.json --output /tmp/focused-machine-evaluation.json
```

Offline commands need no API key. Complete pair coverage and two different pass/run
identities are mandatory; reused response IDs are rejected. Source runs remain intact.
A compare operation computes agreement only after both complete passes exist.

## Consensus and optional human review

- Equal grades and both certain: `machine_agreed`, agreed grade retained.
- Any uncertainty: `machine_uncertain`, grade null.
- Different certain grades: `machine_conflict`, grade null.

No two-vote majority and no automatic smoothing. Absolute differences and every grade
pair (including adjacent pairs and 0↔3) are reported. No third/adjudication pass is
implemented or executed. Only unresolved/conflicting pairs enter
`machine-review-needed.jsonl`, with original public evidence and status, without
retrieval provenance or either machine reason/grade that could anchor human assessment.
These files never populate Human answer/freeze/approval artifacts.

## Exploratory reevaluation limits

The optional reevaluation first validates/computes blind consensus, then separately
loads the fixed original stored rankings. Only agreed grades contribute; unresolved
pairs have no label. It reports the six original metrics, historical metrics, Top-10/20
coverage and unresolved counts for each of the four queries and each model. No new
embedding or ranking is produced, no threshold or gate changes.

Metrics reuse the original pooled evaluator: relevant >= 1, graded nDCG gain
`2**grade - 1`. Unknowns have zero gain for this limited pooled calculation, not an
irrelevance label. With no known positive, Recall/nDCG are null. Coverage and unresolved
counts must accompany interpretation; this selected pool is not corpus-wide ground truth.
Machine-only labels are kept distinct from the historical draft grades, not merged over
them. The historic verdict remains **v5 provisionally fails one or more gates**.
No follow-up metric can retrospectively change that verdict or authorize production.

## Safety

No production access, DB/Qdrant writes, deploy/restart, reindex, alias changes,
Jina inference, Encoder/Planner changes, training or threshold changes. Runtime
`semantic_query=false`. No Human Ground Truth is generated. Real API calls are explicit
operator execution; offline tests and existing CI never require OpenAI access.

## Executed results (2026-10-07)

The selected full passes are `focused-machine-20261007-a2` and
`focused-machine-20261007-b`, with **77 valid answers each**. An initial A run stopped
at the 52nd request on an `invalid_response_contract` rejection, after preserving
51 accepted answers. Its complete partial data and safe request metadata are retained
separately and excluded from consensus. The rejected body was not stored, so the exact
subcondition cannot be retrospectively determined. There was no parsing repair or
weakened validation. The replacement A run used identical model, prompt, parameters and
worker, in a new directory/run ID. It was selected by successful completion, not grades.

Both final passes completed without retries or failures. Overall execution (including
the excluded initial run): **206 requests, 205 accepted responses, one rejected response,
zero transport retries**. No third/adjudication pass was used.

| Selected run | Input tokens | Output tokens | Total tokens |
| --- | ---: | ---: | ---: |
| A2 | 137,892 | 11,684 | 149,576 |
| B | 137,892 | 11,670 | 149,562 |
| All execution, including initial A | 364,982 | 30,985 | 395,967 |

Final prompt SHA256:
`a9fa74d48d8b92676d6e9a47dfde0cf22c696dc16e6f1b16b72f5438c938b584`.

| Classification | Pairs |
| --- | ---: |
| machine_agreed | **70** |
| machine_conflict | **7** |
| machine_uncertain | **0** |
| machine_adjudicated | **0** |

All conflicts are adjacent: one 0↔1, two 1↔2, four 2↔3; no 0↔3 conflict.
`machine-review-needed.jsonl` contains exactly seven full-evidence pairs. Agreement
is machine agreement, not evidence that the 70 equal answers are correct; shared model
bias can survive unanimity. Reviewing only the seven is a triage option, not human
validation of the entire dataset.

Agreement and consensus were computed and hash-sealed before the offline ranking
read for reevaluation. Selected per-pass JSON files contain all accepted answers and
provenance. `request-ledger.jsonl` preserves compact safe metadata for every request;
atomic per-request runtime journals remain in `/tmp/focused-machine-20261007-*`.
`initial-pass-a-partial.json` and `execution-accounting.json` expose the failed attempt
and extra usage rather than hiding them. `consensus-seal.json` binds the selected
answers, agreement, consensus and triage bytes before deblinding.

### Machine-only exploratory reevaluation

These are **new machine-consensus labels**, not historical label corrections or Human
Ground Truth. The judged denominators differ between the historical and new columns.
Seven unresolved pairs stay unlabeled; no zero grade is imputed. The full artifact
includes Recall/HitRate@5/10, MRR@10, nDCG@10 and Top-10/20 coverage.

| Query | Historical v3 R@10 | Historical v5 R@10 | Machine v3 R@10 | Machine v5 R@10 | Unresolved pairs | Machine Top-10 coverage v3 / v5 |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| historical-q29 | 0.3333 | 0 | 0.6667 | 0.7500 | 2 | 90% / 90% |
| wheelchair-da | 0.5000 | 0 | 0.6667 | 0.4000 | 1 | 100% / 90% |
| dance-en | 0.5000 | 0 | 0.5000 | 0.7143 | 2 | 80% / 100% |
| concerts-en | 0.2857 | 0 | 0.4286 | 0.4286 | 2 | 90% / 90% |

Under this limited machine-consensus evaluation, each of the four v5 Top-10 lists
contains an agreed positive. This does **not** disprove the historical known-positive
loss, certify new grades, change the original gates, or establish overall superiority.
Wheelchair access still merits specific human evidence scrutiny; consensus is not an
accessibility guarantee. No global quality or production verdict is issued.

Artifacts are under `benchmark/review/lost-all-v1/machine/`; the frozen Human packet
and every original benchmark artifact remain unchanged. Tests recompute the published
agreement/consensus/evaluation offline and verify all code, input and accounting hashes.
