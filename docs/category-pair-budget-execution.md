# Paired category review execution

This machine-only execution layer uses the contract merged in PR #17 at
`c3612692b01da36e69358c6991c10d4c9d3f44d6`. It performs no retrieval inference,
reevaluation, adjudication, training or production operation. `semantic_query=false`.

## Contract and authorization

`category_pair_execution` delegates all admission, reservation, dispatch and settlement
decisions to the unchanged `category_pair_budget.Ledger`. Its journal dispatch is written
before transport; raw JSON receipts are written exclusively and atomically before settlement.
No alternative budget calculation governs execution. Reporting uses the existing price/usage
functions. The old USD 44.2444125 whole-envelope guard remains unchanged.

The operator explicitly authorized USD 12.00 for 1,506 independent A/B pairs, 3,012 requests,
using `gpt-5.4-mini-2026-03-17`. Approval binds the frozen contract, order, packet, prompt,
prices and original token ceilings. The two pass directories and run IDs are separate.
Both requests receive identical blind inputs, without each other's responses.
`store=false`, reasoning `none`, temperature 0, 1,200 maximum output tokens, no tools,
no history, no pass C. Exactly one transport attempt per request, including for 429/5xx.

The frozen contract's `preparation_only`, `transport_enabled` and `consensus_rule` text
describe PR #17, which shipped the offline ledger only. Those artifacts are not edited.
This separately authorized wrapper supplies transport and completion-gated aggregation.

## Commands

Run from the repository root. The explicit `approve` command is an operator action,
never automatically called by the runner. An approval file is not permission to raise
limits or resume an ambiguous request.

```sh
uv run python -m uranus_research_service.category_pair_execution approve \
  --execution-root /tmp/category-coverage-machine-ab-v1-run \
  --reference 'Operator authorization in this task: USD 12, A/B only, reviewed PR #17' \
  --output /tmp/category-machine-ab-approval.json

# OPENAI_API_KEY must already be supplied through the environment.
uv run python -m uranus_research_service.category_pair_execution run \
  --approval /tmp/category-machine-ab-approval.json \
  --output /tmp/category-coverage-machine-ab-v1-run
```

Resume uses the identical arguments plus `--resume`, with the same code/approval hashes.
A saved receipt is reconciled offline. A dispatch without a receipt is ambiguous and
blocks without retransmission. Transport/schema failure stops at `request_failed_partial`;
budget and token admission failures stop at their original ledger statuses. Disk failure
also stops the process. A partial A/B pair stays quarantined, retaining B's reservation;
a failure cannot guarantee symmetric completed counts. There is no automatic continuation.
Budget continuation requires a new explicit approval through the reviewed ledger workflow.
This wrapper intentionally does not authorize that continuation.

## Offline audit and outputs

```sh
uv run python -m uranus_research_service.category_pair_execution export \
  --run /tmp/category-coverage-machine-ab-v1-run \
  --output benchmark/review/category-coverage-machine-ab-v1/results
uv run python -m uranus_research_service.category_pair_execution validate \
  --bundle benchmark/review/category-coverage-machine-ab-v1/results/run-bundle.json
```

The lossless bundle stores each original JSON file as exact text plus its SHA256:
execution binding, append-only journal, independent A/B receipts and attempt metadata.
This avoids thousands of separate Git files while retaining every byte. Validation
relocates receipts into a temporary directory and replays the original Ledger transitions
with the original logical execution root; it makes no network call and does not mutate
the original ledger. The wrapper code hash is pinned in the execution binding.

A partial export contains only audit evidence and measured usage/costs, never consensus.
Missing or ambiguous usage remains unknown, and its reservation stays outstanding.
`require_complete(state)` must pass before the existing `classify()` function is used
for consensus. Only equal, certain grades become `machine_agreed`; other pairs remain
`machine_conflict` or `machine_uncertain` with null consensus grade. The conflict pool
contains only the original blind candidate evidence, without previous grades or answers.
No historical label is replaced. No machine output is human ground truth.

The historical verdict remains `v5 provisionally fails one or more gates`.
No new metric or gate evaluation is performed by this layer.

## Executed outcome: stopped partial

The authorized real run stopped on **7 October 2026**, with
`request_failed_partial`, after 56 Responses API requests and 27 complete pairs.
Machine A has 28 valid answers. Machine B has 27 valid answers and one rejected
receipt; the remaining 1,478 pairs were not dispatched. There were no retries.

The final B answer referenced `venue_accessibility` for occurrence
`01a09f75-4a2d-7acd-b306-c188c8261312`, where that field is empty. The unchanged
validator rejected it with `empty_occurrence_field`. Its receipt was persisted
before settlement, and its reservation remains retained. No answer was repaired,
repeated, silently accepted or replaced with the A answer.

| Measured usage | A | B | Total |
|---|---:|---:|---:|
| Input tokens (including cached) | 51,715 | 51,715 | 103,430 |
| Output tokens | 4,058 | 4,035 | 8,093 |
| Cached input tokens | 0 | 36,096 | 36,096 |
| Reasoning tokens | 0 | 0 | 0 |
| Usage-priced USD | 0.05704725 | 0.03257895 | **0.08962620** |

These costs include the rejected B response. Rates are the frozen approved prices:
USD 0.75/M input, 0.075/M cached input, 4.50/M output. This is accounting from
provider-reported usage, not a provider invoice. All 56 responses have usage.
Ledger settled cost is separately **USD 0.08867055**; the failed request's full
**USD 0.01526175** reservation remains outstanding. The generic ledger report's
`unknown_usage_possible` flags the terminal failure conservatively; the outcome
report records that this particular failure has a saved, measured receipt.

Artifacts are under `benchmark/review/category-coverage-machine-ab-v1/`:
operator approval, `execution-outcome.json`, hash index and `results/` containing
`run-bundle.json`, `usage-cost-report.json` and its hash index. Per-pass receipt hashes
are included in the outcome. Replay verified the saved journal and settled receipts.

**No consensus or conflict pool exists**, because `require_complete` refuses this
partial state. There are no agreed/conflict/uncertain totals to report from an
incomplete run. No pass C, Astra call, reevaluation or production change occurred.
The historical verdict, labels, rankings, budget contracts and token ceilings remain
unchanged. Further dispatch is blocked; this task does not authorize repairing the
answer, altering the validator, or bypassing the failure state.

Receipt-set SHA256 (canonical JSON mapping of relative receipt paths to byte hashes):

- A: `5f39e973a9ee1a27fba4533699abc81323acfaf7ecbd7a22b2399c27296e2d38`
- B: `f11ce20c1905d40457af2d8fe0a5a6cc5b4a8008faae9dd7cb8d54f6f9db4114`
- Complete partial-run bundle: `1b011c47137b55aad791764867f7cdc3257f61a84e3e09a2a1bf43225faa3990`

Consensus/conflict-pool hashes are not applicable; those artifacts were deliberately
not generated for an incomplete run.

## Validation

Local checks: `uv sync --locked --offline`, Ruff, format, `git diff --check` pass.
Full suite: **772 passed, 24 skipped**. Integration tests require the guarded disposable
PostGIS/Qdrant endpoints, pinned Admin checkout or optional real-encoder endpoints;
none were supplied for this local run. New tests use synthetic HTTP transport, verify
failure/crash/resume behavior, enforce completion before consensus, and replay the
published real partial-run bundle without network access. No test makes a live API call.
