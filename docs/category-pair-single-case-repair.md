# Single-case category-pair repair v1

## Why repair exists

PR #18 stopped correctly at `request_failed_partial`. This separate contract permits
at most one **explicitly approved** fresh machine judgment for the rejected B receipt.
It is not human review or ground truth. No other candidate, pass or failure is covered.
Baseline: main `dc59e8f65f8bebb8d2aca3a6da1a0f832585be1d` (PR #18 merge).

## Original failure

- Annotation: `a0c166936ef7233017150f87aad87df5`; pass: `machine-b`.
- Validator: `empty_occurrence_field`; field: `venue_accessibility`.
- Occurrence: `01a09f75-4a2d-7acd-b306-c188c8261312`.
- Original response: `resp_0fe6381848dede2b016ac63c671ee487d2a9b15e1bc64a2cb8`.
- Original client request: `777eb05f-eb0a-5ddf-93ea-25b08f35e193`.
- Original rejected request cost: USD **0.00095565**.
- All original receipts cost USD **0.08962620**, including that rejected request.

## Why this is not a retry

The old receipt remains rejected, immutable and fully audit-able. Repair uses a new
run ID and client request ID with `repair_attempt=1`; a returned response ID must be new.
The repair has a separate authorization and accounting. There is no retry loop, no
response repair, no automatic second attempt and no grade-based request selection.
HTTP 429/5xx, network errors, refusal, malformed output and evidence failure are terminal.

## Frozen bindings

`benchmark/review/category-coverage-machine-ab-v1/repair-v1/repair-contract.json`
binds the bundle, receipt, failure state, original IDs/approval/prompt/packet, model,
usage, costs, original artifacts and implementation hashes. Preparation and execution
replay the original Ledger offline and reproduce the original failure before proceeding.

| Binding | SHA256 |
|---|---|
| Original run bundle | `1b011c47137b55aad791764867f7cdc3257f61a84e3e09a2a1bf43225faa3990` |
| Rejected receipt | `7dd1398cdbc167eca1196a1ecfdec0bd711be5dfb964787fd83de03317ccbc43` |
| Original failure state | `20b3b8ac2cbf23f4d5893c86fd7af731ac28256ab3b474cb43ecdd6bc88ac23e` |
| Original approval (canonical JSON) | `52d9dc8b01acbeb07a60debd0a30d2077df8212dde91ce347f057b9a1781a870` |
| Unchanged prompt | `a9fa74d48d8b92676d6e9a47dfde0cf22c696dc16e6f1b16b72f5438c938b584` |
| Unchanged blind packet | `6b2b54c3c254d97f2972b04d122cc8e415eeff87e09d164d09a7902c45f3cd54` |

The actual HTTP body must match the original request byte hash
`477180bf5fcf07275903e0fc73399de0171faa4cbe4ad3ec1103b430c69d1d84`.
Only the transport request ID changes. Operator bindings never enter the judge payload.

## Prompt policy

**Prompt unchanged.** The frozen prompt already explicitly requires positive grades to
cite actual nonempty supporting fields. That directly covers the observed failure.
The prompt, rubric, scale, query, evidence and candidate are byte-identical to the original.
No A answer, old B answer, failure context, ranking or prior grade is included.

The repair acceptance boundary additionally checks every cited field, including citations
in negative/uncertain answers, for real nonempty content. Whitespace-only text is empty.
This stricter check does not relax or modify the original validators. The original prompt
allows missing-field references for negative/uncertain judgments: such references can still
fail this repair-specific acceptance boundary. They will be rejected, never silently removed
or used to trigger another request. An accepted uncertain answer remains null-grade; acceptance
means contract validity, not certainty about relevance.

## Approval

The closed `category-single-repair-approval-v1` schema binds exactly this case, pass,
contract and original hashes, the frozen model/prompt/packet, execution root, one request,
and both token ceilings. It requires explicit permission plus immutable-receipt and
unchanged-validator flags. An old A/B approval cannot authorize this repair.

Proposed cap: **USD 0.10**. Conservative request ceiling: **USD 0.01526175**, using
13,149 estimated input tokens and at most 1,200 output tokens at the original frozen prices.
A real approval file must be created only after a separate explicit operator authorization.
Preparation does not create an approved file or fake execution artifacts.

```sh
# Already prepared artifacts: verify without API/network.
uv run python -m uranus_research_service.category_single_repair validate

# Only AFTER explicit operator authorization:
uv run python -m uranus_research_service.category_single_repair approve \
  --reference '<explicit operator authorization reference>' \
  --output /tmp/category-single-repair-approval.json
```

The preparation command writes exclusively to a new directory; it never overwrites:

```sh
uv run python -m uranus_research_service.category_single_repair prepare \
  --output /tmp/reproduced-single-repair-contract
```

## One-request execution

```sh
# OPENAI_API_KEY must already be in the environment. Never put it on the command line.
uv run python -m uranus_research_service.category_single_repair run \
  --approval /tmp/category-single-repair-approval.json
```

The contract fixes `/tmp/category-pair-single-repair-v1-run` as the execution root.
Configuration: `gpt-5.4-mini-2026-03-17`, `store=false`, reasoning `none`, temperature 0,
max output 1,200, no tools, no history, no fallback. No availability-probe API request.

## Append-only persistence

An exclusive lock and durable pending attempt precede the sole API request. Receipt
is persisted atomically before validation/outcome/reconciliation. A repeat `run` refuses
any already-started execution, including a crash with unknown dispatch outcome. It never
blindly resends. A crash requires an offline audit; there is no automatic recovery request.
No original journal method that mutates state is called.

```sh
uv run python -m uranus_research_service.category_single_repair validate-run \
  --run /tmp/category-pair-single-repair-v1-run
uv run python -m uranus_research_service.category_single_repair publish \
  --run /tmp/category-pair-single-repair-v1-run
```

Offline validation recomputes acceptance, cost and reconciliation from the saved receipt.
Publication preserves exact bytes using exclusive writes into `repair-v1/`, with a separate
`repair-run-sha256.json`. The preparation index and all PR-18 files remain untouched.

## Reconciliation

A valid new receipt produces a new append-only reconciliation with:
`original_machine_b_receipt=rejected`, `effective_response_source=repair-v1`, and
`effective_pair_completion=repaired`. Effective completed pairs would be 28; the original
Ledger remains at 27 pairs and `request_failed_partial`. The old receipt is not replaced
in any original artifact. Failure leaves the effective pair incomplete.

## Cost accounting

The original rejected cost is retained. Repair cost is additional, measured with the same
existing usage/price functions; cached tokens are handled separately and output includes
reasoning tokens once. Cumulative cost includes **all** original receipts, including the
rejected one, plus the repair. No refund or credit is inferred. Unknown usage stays unknown,
not zero. Costs are usage-priced estimates at frozen rates, not provider invoices.

The original USD 0.01526175 outstanding reservation is not released by this overlay.
Any future continuation must reconcile both original rejected and repair charges without
resetting the original budget or token limits. The repair is an additional request; it must
not be disguised as one of the original 3,012 dispatches.

## Continuation boundary

`ready_for_reviewed_continuation` describes a logical repaired pair only. It is **not** an
executable Ledger state or continuation approval. A new reviewed execution step and explicit
approval are required for the remaining 1,478 pairs. This module cannot run them.

## No consensus yet

Even a successful repair leaves most pairs incomplete. The original `require_complete`
guard still rejects the state. No consensus, conflict-pool analysis or reevaluation is
implemented or invoked here. The historical verdict remains unchanged.

## Safety

No Astra, retrieval inference, Qdrant/DB access, production change, deployment, training,
threshold tuning, alias change or semantic activation. `semantic_query=false` remains
unchanged. Offline tests use clearly synthetic provider responses and no live API key.

## Prepared artifact identity

- Repair contract SHA256: `79a91d9ce3094f6f3599129aff117f9c2447a53102549af1ebee8202cef104b0`
- Approval schema SHA256: `5a6efcb369f85d510757b03980f907bb2653dae17296537e075559c9de23c2b9`
- Repair run ID: `repair-v1-59d3e9ac7936fe2a37300859`
- Repair client request ID: `10780ab0-f2c4-54c7-9325-2ca19a2b396b`

Preparation itself grants no approval. No receipt, accepted/rejected outcome, token usage
or live reconciliation is fabricated when the explicit repair authorization is absent.

## Authorized execution outcome

Following the operator's explicit authorization in this task, one real request was
executed with the prepared, unchanged `gpt-5.4-mini-2026-03-17` contract. Additional
permission to use Astra was not exercised; it did not change this pinned model contract.
The result was **accepted**, then independently revalidated offline and published with
exclusive writes. No other request followed.

| Item | Recorded value |
|---|---|
| API requests / repair attempt | 1 / 1 |
| Returned model | `gpt-5.4-mini-2026-03-17` |
| Repair response ID | `resp_095618ad43f47a30016ac71392005c87d294f616816111acfb` |
| Input tokens | 1,927 |
| Output tokens | 147 |
| Cached input / reasoning tokens | 0 / 0 |
| Repair cost | USD **0.00210675** |
| Original rejected request cost, retained | USD 0.00095565 |
| Original rejected request + repair | USD 0.00306240 |
| All original receipts + repair | USD **0.09173295** |
| Repair reconciliation status | `ready_for_reviewed_continuation` |
| Effective completed pairs / remaining | 28 / 1,478 |
| Original Ledger state | unchanged: `request_failed_partial`, 27 completed pairs |

New artifact byte hashes:

- Approval: `f4ca540a30cb5b549e2bc957d6100a2681f188837bb7c99f410120ec534068a1`
- Receipt: `c9e35848d70e12e01fe4d9986947f6e782117bdde7f368d2c5535cae6237f4a6`
- Outcome: `26b3eb308605d9cebec950b362a93c2dd2095242c7e060ae7f55c6b00aa4f2c3`
- Reconciliation: `a2f74cfb524d36971d1a634188e0a6d1f135b197a0e299c668e11fa2c0b64813`

The original B receipt remains rejected and present byte-for-byte. All original journal
entries and PR-18 artifacts retain their hashes. Consensus and full-run continuation
remain blocked. No Astra call, reevaluation or production operation occurred.

## Validation

Local: `uv sync --locked --offline`, Ruff, format and `git diff --check` pass.
Full suite: **821 passed, 24 skipped**. Local integration skips require guarded disposable
PostGIS/Qdrant endpoints, a pinned Admin checkout or optional real encoder endpoints.
The repair-specific tests use synthetic HTTP responses and offline replay of the one
published real receipt; CI requires no live OpenAI key or API execution.
