# Category coverage: explicit two-pass execution contract

## Purpose

This preparation-only change resolves the three-pass approval limitation documented
in [PR #14's pool preparation](category-coverage-blind-review-v1.md). The category
pool now has its own A/B entry point and approval schema. Historical Phase-2D-M
three-pass execution and the 77-pair two-pass review are unchanged.

Baseline main: `376cbda3c1818ec0f06e31a8ccb6b3112c2fc0e6`.
No provider requests, machine judgments, consensus, adjudication or operator
approval were created. A later adjudication would be a separate conflicts-only task.

## Frozen pool

Exactly 1,506 query×event pairs, 20 historically evaluable queries, categories
outdoor/theatre/venue/accessibility, no atmosphere. Preparation reuses the existing
full pool verifier, including frozen inputs, public evidence, ordering, eligibility,
query/category membership and all old artifact hashes.

New artifacts live in **`benchmark/review/category-coverage-two-pass-v1/`**, a sibling
of the frozen pool. Adding a `machine/` directory inside the old pool would violate
its existing exact-directory/reproducibility contract. No old files or validators
were relaxed to permit that.

The execution worker reads only the blind packet and its metadata as evidence.
Operator mappings are used during offline preparation for per-query/category cost
statistics; they are never part of a request. The worker does not read rankings,
old grades, A/B outputs from another pass, or retrieval/model-source provenance.

## Execution contract

- `pair_count: 1506`
- `passes: [machine-a, machine-b]`
- `pass_count: 2`
- `planned_requests: 3012` (unique judgments, before transport retries)
- `machine-c: disabled`
- exact model: `gpt-5.4-mini-2026-03-17`
- temperature 0, reasoning effort `none`, no seed sent
- `max_output_tokens: 1200`, `store: false`
- no tools, conversation history or `previous_response_id`

This retains the model identifier and settings used by the earlier 77-pair review.
Account availability and current provider limits were **not queried**. Unsupported
model/parameter responses fail closed; there is no substitution or fallback.
The operator must explicitly supply the exact model again at execution time.

Both passes use **identical prompt and request bodies**, with independent request
IDs, distinct deterministic run IDs and separate directories. Separate requests do
not imply statistically independent model errors. No A/B result enters another
request. Returned response IDs are recorded and checked for duplicates within each
pass; there is no shared response/history between passes.

The existing `lost-all-v1/machine/prompt-v1.txt` is reused byte-for-byte, together
with its `MachineAnswer` strict schema and evidence/occurrence validation. Generic
`BlindCandidate`/`api_payload` provide the closed nine-field pool projection.
Intent checks already present in the authoritative rubric are retained. The prompt
requires uncertainty to remain null-grade, conservative compound-intent judgments,
nonempty positive evidence and eligible occurrence IDs, and rejects instructions
inside event text. No prompt was optimized against new answers.

## Cost estimation

The locked local environment has no `tiktoken` installation or model-specific
local tokenizer. Nothing is downloaded. This version therefore uses a deliberately
conservative, deterministic estimate for **every actual request**, not an
extrapolation from earlier runs:

```text
estimated input tokens = UTF-8 bytes of httpx's serialized JSON request + 4096
estimated output tokens = configured output ceiling of 1200
```

Serialization is exactly `httpx.Request(..., json=payload).content`, matching the
unchanged transport's `json=` serialization. It includes prompt, complete evidence,
strict output schema and request envelope. The framing allowance is an explicit
local safety margin. It is not a tokenizer measurement, expected billing figure or
mathematical guarantee of provider token accounting. Output is a ceiling, not a
predicted average. Tests compare actual mock-transport HTTP bytes with the hashed
costed payloads. The report records one shape/hash per annotation ID; A/B are equal.

| Quantity | Per pass | A+B |
| --- | ---: | ---: |
| Requests before retries | 1,506 | 3,012 |
| Estimated input tokens | 18,653,075 | 37,306,150 |
| Output token ceiling | 1,807,200 | 3,614,400 |
| Estimated combined tokens | 20,460,275 | 40,920,550 |

Nearest-rank percentiles (identical for A and B):

| Per-request measure | Min | p50 | p90 | p95 | p99 | Max |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Estimated input tokens | 9,647 | 11,548 | 15,527 | 20,466 | 20,876 | 29,086 |
| HTTP JSON bytes | 5,551 | 7,452 | 11,431 | 16,370 | 16,780 | 24,990 |

| Category | Pairs | A+B input estimate | A+B output ceiling | A+B total estimate |
| --- | ---: | ---: | ---: | ---: |
| outdoor | 36 | 885,398 | 86,400 | 971,798 |
| theatre | 182 | 5,067,368 | 436,800 | 5,504,168 |
| venue | 286 | 6,991,128 | 686,400 | 7,677,528 |
| accessibility | 1,002 | 24,362,256 | 2,404,800 | 26,767,056 |

Per-query totals and the 20 largest opaque annotation IDs are in `cost-report.json`.
There are **zero oversized requests** under the declared local policy: ≤256 KiB
HTTP JSON and estimated input plus maximum output ≤131,072 tokens. These are
operator safety caps, **not verified provider capacity claims**. An oversized
request is never truncated or silently shortened. Shape/cost exports flag cases
outside these local caps and preparation refuses execution; the inherited absolute
payload guard can also reject an oversized request immediately. Future provider
capacity errors are terminal, not reasons to trim evidence or change the contract.

No current API prices are hardcoded. The published report has null monetary values.
Optional decimal-string operator prices are interpreted as USD per million tokens:

```sh
uv run python -m uranus_research_service.category_machine_execution dry-run \
  --model gpt-5.4-mini-2026-03-17 \
  --input-price-per-million '<operator-supplied-price>' \
  --output-price-per-million '<operator-supplied-price>' \
  --output /tmp/category-two-pass-priced
```

Replace both placeholders with operator-verified numeric prices. This produces a
new report and new hash; an approval must bind that exact report. No provider price
lookup, caching discount assumption or exchange-rate conversion occurs.

## Approval

Only `approval-schema.json` is published. **There is no authorized approval file.**
Before a real run an operator must separately provide a record validating against
that closed schema, with a real approval reference. The file gate records explicit
operator intent; it is not a cryptographic identity/authentication service.

Required bindings include exact model, packet/prompt hashes, raw contract and cost
report file hashes, 1,506 pairs, two passes, 3,012 planned judgments, maximum input
and output tokens, absolute `execution_root`, and explicit pass flags:
`machine-a: approved`, `machine-b: approved`, `machine-c: forbidden`.
Optional fields are operator pseudonym, approval timestamp and maximum USD amount.
Unknown keys, three-pass defaults, changed counts/model/hashes or approval of C fail.

`execution_root/machine-a` and `execution_root/machine-b` are the only permitted
output paths. Run output must be outside the repository's `benchmark/` tree.
Budgets are split equally between the passes (rounding down) so concurrent A/B
execution cannot double-spend a shared ceiling. Each attempt reserves its full
estimated input and maximum output **before** sending. Reservations are not refunded
on failure; usage is recorded separately. A request that would exceed either quota
is not sent. Unexpected actual usage above a reservation stops the pass.

There are at most three attempts per pair/pass. The nominal 3,012 judgments do not
include retries. The separate worst-case transport envelope is **9,036 attempts**,
111,918,450 estimated input tokens and 10,843,200 output tokens. Retries require
sufficient explicitly approved token headroom; approval of the no-retry estimate
does not implicitly grant this larger envelope. The report exposes both envelopes.
If an amount cap is supplied, explicit operator prices are required and the full
approved token envelope must fit that cap. No hidden or automatic budget increase.

The task does not issue cost approval or request permission to execute a real run.

## Offline dry run and verification

Run from repository root, always using a new output directory:

```sh
uv sync --locked --offline
uv run python -m uranus_research_service.category_machine_execution dry-run \
  --package benchmark/review/category-coverage-v1 \
  --model gpt-5.4-mini-2026-03-17 \
  --output /tmp/category-two-pass-dry
uv run python -m uranus_research_service.category_machine_execution validate \
  --package benchmark/review/category-coverage-v1 \
  --contract /tmp/category-two-pass-dry \
  --model gpt-5.4-mini-2026-03-17
diff -qr benchmark/review/category-coverage-two-pass-v1 /tmp/category-two-pass-dry
```

Dry-run means serialization/validation only. It never constructs a provider client,
reads an API key, calls an endpoint, generates a judgment or creates approval.
The seven output files are execution contract, cost report, request-shape report,
prompt binding, response schema, approval schema and artifact SHA256 index.

## Future real run — NOT executed or authorized here

After separate authorization, current-model/capacity/price checks and an operator
approval matching the chosen report, the existing transport can be used as follows.
The approval's `execution_root` must equal `/tmp/category-two-pass-execution` for
these examples; its token/amount limits must reflect the approved scope.

```sh
# OPENAI_API_KEY is supplied through the environment only, never on the command line.
uv run python -m uranus_research_service.category_machine_execution run \
  --package benchmark/review/category-coverage-v1 \
  --contract benchmark/review/category-coverage-two-pass-v1 \
  --model gpt-5.4-mini-2026-03-17 --pass-name machine-a \
  --approval /path/to/two-pass-approval.json \
  --output /tmp/category-two-pass-execution/machine-a
uv run python -m uranus_research_service.category_machine_execution run \
  --package benchmark/review/category-coverage-v1 \
  --contract benchmark/review/category-coverage-two-pass-v1 \
  --model gpt-5.4-mini-2026-03-17 --pass-name machine-b \
  --approval /path/to/two-pass-approval.json \
  --output /tmp/category-two-pass-execution/machine-b
```

There is no default pass or `all` option. Invalid/missing approval is rejected
before client construction, key access or network traffic. Each request is a single
case with no history. Exact response model identity is validated, with no fallback.

## Resume and persistence

Add `--resume` to the same command, retaining all bindings and the same destination.
Without it existing output is rejected. Resume requires identical normalized
approval, model, prompt, packet, pass/run identity, source-code hashes and `uv.lock`.
A changed budget/approval does not silently expand a previously started run.

An exclusive per-pass lock prevents concurrent writers. The existing fsync/exclusive
atomic publisher is reused. Per-attempt immutable files record request hash, unique
client request ID, attempt count, reserved tokens, timestamps, outcome, safe error
category, IDs, latency and usage. Accepted provider responses are stored separately
with SHA256 and strictly validated answers; successful records are never replaced.
No API key or provider error body is persisted or logged.

Valid stored answers are verified against the accepted response, reservation,
completion and configuration and skipped without another request. A completed
attempt whose final record publication was interrupted is recovered without
resending. A reserved attempt without a completion is **ambiguous and fail-closed**:
it may already have been billed. Operator audit is required, never automatic replay.

## Failure handling

Bounded exponential retry (2/4 seconds, at most three attempts) is only for transport
errors, 429, and 500/502/503/504. A narrow subclass of the existing transport excludes
HTTP 408 from this workflow's retry policy without changing historical behavior.

Malformed HTTP JSON, invalid structured output, refusal, wrong model, invalid grade,
foreign occurrence IDs, missing positive evidence and other contract failures are
terminal. No answer repair, follow-up prompt, grade-based retry or alternate model.
An unresolved/uncertain valid answer remains null-grade and is not retried.

## No pass C

The new CLI accepts only `machine-a` or `machine-b`; plan equality and the closed
approval schema independently enforce two passes. No pass-C prompt, run ID or
execution directory is created. These artifacts do not have a legacy `blind/plan.json`
layout, so the historical generic default cannot implicitly expand them to three
passes. Historical `machine_judge.PASSES` and all old workflows remain unchanged.

## Bindings and safety

Raw SHA256 values:

- Blind JSONL: `6b2b54c3c254d97f2972b04d122cc8e415eeff87e09d164d09a7902c45f3cd54`
- Reused prompt: `a9fa74d48d8b92676d6e9a47dfde0cf22c696dc16e6f1b16b72f5438c938b584`
- Execution contract: `57d86fe3c165bcc69468004aea4aa8d9c385275b578fd40688dbb28db980fdaf`
- Cost report: `f2473a0dc3e3fac49ed5d0f2c8ac7be774f7a3bc4e1da4a0e43b40ebe9b849a4`
- Approval schema: `a3b10b7edb5aec945672c53a8cdcd32027aa34beedade354b0bdc2a6bfa5de12`

No real API calls or new judgments; tests use explicitly synthetic responses and
approval fixtures in temporary directories. No Human Ground Truth or automatic
approval. No historical changes, v3/v5 inference, DB/Qdrant access, production,
deployment, restart, reindex, aliases, training or threshold changes.
`semantic_query=false`. The historical verdict remains
`v5 provisionally fails one or more gates`. No merge is authorized by this task.

## Validation

The final full local offline suite passed: **688 passed, 24 skipped**, including
39 new contract tests. `uv sync --locked --offline`, Ruff, formatting and diff checks
passed. Local integration skips require configured disposable PostGIS/Qdrant and
the pinned Admin checkout, or optional real-Encoder settings; no guards were disabled.
The existing CI workflow is unchanged and requires no real OpenAI traffic.
