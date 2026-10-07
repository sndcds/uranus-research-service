# Blind machine adjudication of seven cases

This is machine adjudication, not human review or human Ground Truth. It does not
supersede the human workflow, the two original passes, or the historical benchmark.
The historical verdict remains `v5 provisionally fails one or more gates`.

## Inputs and blindness

The worker opens only the frozen seven-row `machine-review-needed.jsonl` evidence
file and the versioned prompt (plus its own code for hashing). Input SHA256:
`7c274d8640ffa4b74ed936c527d47a7eef7ef47fe96225fb76bf9b954da7a5d4`.
This matches PR #11's consensus seal. Exact IDs, count, hash and closed public
schema are validated before requests. Operator status is stripped. Query/event
identity and category do not enter the HTTP payload. Public `released` status is
retained as event evidence; it is not machine-consensus status. The input itself
is never modified.

The actual HTTP body is covered by a MockTransport allowlist test. Each independent
request contains one opaque ID, query, language, unchanged rubric/intent checks,
eligibility/reference time and complete public event/occurrence evidence. No
retrieval provenance, earlier answers or grades reach the judge. Event text is
explicitly untrusted evidence, never instructions. Concert diversity retains the
single-concert interpretation. Accessibility remains occurrence-specific.

## Predeclared configuration

Provider OpenAI; exact requested/required returned model `gpt-6-astra`; Responses
API; `reasoning.effort=high`; `store=false`; strict JSON Schema; no tools, history,
previous response, seed or temperature. The [official model documentation](https://developers.openai.com/api/docs/models/gpt-6-astra)
supports high reasoning and structured outputs. The [API changelog](https://developers.openai.com/api/docs/changelog)
explicitly excludes custom temperature/top_p for Astra (checked 2026-10-07).
Temperature is omitted, not silently substituted. No alternate model is allowed.

The limit is fixed at 8,192 output tokens before execution to accommodate high
reasoning as well as a short (maximum 1,200-character) visible explanation. No
limit or prompt is adjusted after seeing judgments. Transport has a 60-second
request timeout, 10-second connection timeout, fixed origin, no redirects or
environment proxies, and bounded identity-encoded JSON responses.

## Persistence and failures

Exclusive atomic, fsynced writes preserve every terminal response and safe attempt
metadata. A process lock prevents concurrent runs. Explicit `--resume`
requires identical code/prompt/input/parameters; successful or terminal failed
cases are not repeated. An interrupted request with unknown outcome becomes
unresolved rather than being silently sent again. Only transport/429/transient
server errors receive up to three attempts with exponential backoff. Schema errors,
refusals and incomplete responses do not trigger repair or retries. Uncertainty
has null grade. No fallback to either earlier judge is permitted.

A model-availability rejection aborts before result creation. Safe errors exclude
provider bodies and credentials. CLI reads only `OPENAI_API_KEY`; do not place a
key in any command argument or artifact.

## Reproduction

Run from repository root, with the API key already in the environment:

```sh
uv run python -m uranus_research_service.machine_blind_adjudication run \
  --model gpt-6-astra \
  --input benchmark/review/lost-all-v1/machine/machine-review-needed.jsonl \
  --output /tmp/lost-all-astra-adjudication
uv run python -m uranus_research_service.machine_blind_adjudication validate \
  --input /tmp/lost-all-astra-adjudication --output /tmp/astra-validation.json
uv run python -m uranus_research_service.machine_blind_adjudication combine \
  --input /tmp/lost-all-astra-adjudication --output /tmp/astra-combined.json
uv run python -m uranus_research_service.machine_blind_adjudication reevaluate \
  --input /tmp/astra-combined.json --output /tmp/astra-reevaluation.json
```

Only `run` uses the network. Existing destinations require explicit resume; derived
outputs are exclusive. Validation and derivation use no encoder, Qdrant or API.
The combined artifact retains 70 agreed grades and adds only valid adjudications.
Conflicts/uncertainty/failures stay unknown; no human status is produced.

Reevaluation uses the unchanged complete stored rankings, grade >= 1 and the
existing six metrics. It reports historical, consensus-only and adjudicated
variants separately, coverage at 10/20, positive IDs and best positive rank.
Pooled metrics assign no gain to unjudged results but do not manufacture zero
labels. This selection of four cases cannot establish a global gate pass.

## Execution evidence

Executed 2026-10-07 after 614 passing offline tests (24 integration skips).
The API returned exactly `gpt-6-astra` for all seven responses. All seven passed
schema/evidence/occurrence validation: **7 machine_adjudicated, 0 unresolved**.
Grades: **four grade 1, three grade 3**. Seven Responses requests, one model
availability GET, zero retries, zero failed/rejected responses. Usage: **11,456
input + 1,937 output = 13,393 tokens**. Full response/request IDs, payload/code
hashes, timestamps and latency are in the immutable run records.

The new combined set has **70 machine_agreed + 7 machine_adjudicated**. No original
consensus entry was overwritten. Each of the four candidate top-10 lists for each
retrieval model now has 100% machine-judgment coverage. Top-20 coverage remains
partial. The historical known-positive loss is absent under this machine-only
set; it was already absent under PR #11's consensus-only set. This is not human
confirmation and does not establish a global gate pass.

Prompt SHA256: `56bd1e47d30c28eccd87dcab02bc173c16400aee631e359972f039e9f1e07cfd`.

### Machine-only metrics after adjudication

| Query | Model | Recall@5 | Recall@10 | Hit@5 | Hit@10 | MRR@10 | nDCG@10 | Top-20 coverage |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| historical-q29 | v3 | 0.2857 | 0.6429 | 1.0000 | 1.0000 | 1.0000 | 0.6724 | 60% |
| wheelchair-da | v3 | 0.3125 | 0.6250 | 1.0000 | 1.0000 | 1.0000 | 0.6763 | 75% |
| dance-en | v3 | 0.2500 | 0.5625 | 1.0000 | 1.0000 | 1.0000 | 0.4955 | 55% |
| concerts-en | v3 | 0.2174 | 0.4348 | 1.0000 | 1.0000 | 1.0000 | 0.4186 | 65% |
| historical-q29 | v5 | 0.3571 | 0.7143 | 1.0000 | 1.0000 | 1.0000 | 0.8569 | 60% |
| wheelchair-da | v5 | 0.2500 | 0.4375 | 1.0000 | 1.0000 | 1.0000 | 0.6135 | 95% |
| dance-en | v5 | 0.3125 | 0.6250 | 1.0000 | 1.0000 | 1.0000 | 0.6597 | 75% |
| concerts-en | v5 | 0.2174 | 0.4348 | 1.0000 | 1.0000 | 1.0000 | 0.3805 | 60% |

Every best positive rank is 1; unresolved count is zero for each case. Positive
Top-10 UUIDs, all six historical/consensus-only/adjudicated metrics and coverage
are retained in `machine-adjudicated-reevaluation-v1.json`.

### Consensus-only versus plus adjudication

| Query | v3 Recall@10 before → after | v5 Recall@10 before → after |
|---|---:|---:|
| historical-q29 | 0.6667 → 0.6429 | 0.7500 → 0.7143 |
| wheelchair-da | 0.6667 → 0.6250 | 0.4000 → 0.4375 |
| dance-en | 0.5000 → 0.5625 | 0.7143 → 0.6250 |
| concerts-en | 0.4286 → 0.4348 | 0.4286 → 0.4348 |

Recall can decrease when newly judged positives enlarge its denominator, even
though judged coverage improves. No judgments or thresholds were tuned to these
results. Interpretation remains limited to four selected cases and machine labels.

### Offline validation and CI

`uv sync --locked`, Ruff, format, full pytest and `git diff --check` passed before
API execution. Local service-dependent integration tests require TEST_DATABASE_URL,
TEST_QDRANT_URL, ADMIN_PARITY_ROOT or optional TEST_ENCODER_URL and remain skipped
without those isolated fixtures. Existing CI still runs disposable PostGIS/Qdrant,
Admin parity and Docker without real OpenAI calls. Published artifacts can be
revalidated with the same `validate` command, using the committed `adjudication/run`
directory; the regression test recomputes the derived artifacts offline.


## Safety

No production access, DB/Qdrant writes, new retrieval embeddings, reindex, alias
change, deployment, restart, model training, threshold change or semantic
activation. `semantic_query=false`. Existing artifacts remain byte-identical.
No PR merge is authorized by this task.
