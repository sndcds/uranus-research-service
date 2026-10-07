# Category coverage: paired A/B budget contract v1

## Scope and baseline

Baseline main: `b87cfd3f2a93b91baad3c33fc839c6eab55d1bda`.
This PR prepares an **offline-only contract and state machine**. It has no provider
transport, API-key handling or `run` command. No actual approval, A/B judgments,
consensus, adjudication, reevaluation or provider requests are created. Review of
this PR is required before a later execution task connects a worker.

The historical PR #15 two-pass contract, code, hashes and USD 44.2444125 envelope
check remain unchanged. The new version lives in the sibling
`benchmark/review/category-coverage-pair-budget-v1/`, without adding files inside
any sealed historical package. The new approval cannot validate under the old schema.

## Why a separate budget contract

The original contract requires the entire conservative token envelope to fit the
monetary approval before starting. With the pinned tariff, that envelope costs
USD 44.2444125. It therefore correctly rejects USD 12.00.

This version instead admits one **whole A/B pair** at a time against the cumulative
USD 12.00 operator maximum. Pilot projections are not used to grant credit, set a
target spend, shorten evidence or relax reservations. Completing all 1,506 pairs is
not guaranteed under the cap.

The model, prompt, packet and output schema are unchanged:

- `gpt-5.4-mini-2026-03-17`
- temperature 0, reasoning `none`, `store=false`, 1,200 maximum output tokens
- no tools, history, fallback, pass C or automatic retry
- exact existing blind request serializer and answer/evidence validator

The contract binds the old execution/cost-report hashes, prompt/packet hashes,
response schema, code/dependency hashes, frozen prices and the new order.

## Request order and independence

Before any request, sort all 1,506 opaque annotation IDs by SHA256 of the canonical
JSON array `["category-coverage-paired-order-v1", annotation_id]`. The frozen
`request-order.json` records this order and both requests' identical payload hash
and conservative token estimates. The contract binds its canonical digest; approval
also binds its actual file SHA256. Reordering or editing a payload fails validation.

Within a pair, A precedes B. Both use the same candidate and immutable prompt.
`request_intent` builds only the existing blind payload; it does not read an answer.
Distinct run IDs, client request IDs and `machine-a/` / `machine-b/` response
directories separate the passes. The journal is shared only for cost and scheduling.
No category, ranking, previous grade or conflict signal controls the order.
Separate requests are not a claim of statistically independent model errors.

## Admission and accounting

All monetary arithmetic uses Decimal USD and frozen explicit tariff parameters
from the already versioned pilot price manifest. Nothing fetches prices at runtime.

Before admitting pair `i`:

```text
reservation_each = uncached_input_rate × conservative_input_estimate_i / 1e6
                 + output_rate × 1200 / 1e6

actual_settled_cost + outstanding_reservations + 2 × reservation_each <= 12.00
```

Both reservations are committed in one durable journal event **before A can be
handed to a future worker**. B's reservation survives A's settlement. No next pair
can start until both receipts have passed model/schema/evidence/usage validation.

Validated settlement replaces that request's monetary reservation with its actual
usage cost. Cached input gets a discount only for explicit valid cached counts;
missing detail is priced uncached and remains unknown in the receipt. Reasoning
is already included in output tokens and is not charged again. Unknown usage,
refusal, invalid JSON/schema, wrong model, unpriced service tier, foreign response
IDs or usage exceeding a reservation do not release money.

Only the pinned `default` service tier is priced. Another tier requires separate
operator review. The reservation uses the unchanged byte-plus-framing estimate;
it is not a provider-side account spending limit. Out-of-envelope usage is terminal
and requires reconciliation, never permission to continue spending.

## Additional hard technical limits

Conservative token reservations are **never refunded**, even if a response is short
or cached:

| Limit | Per pass | Combined |
| --- | ---: | ---: |
| Input reservation tokens | 18,653,075 | 37,306,150 |
| Output reservation tokens | 1,807,200 | 3,614,400 |
| Requests, including any possibly sent intent | 1,506 | 3,012 |

One attempt per pair/pass. An interrupted or failed attempt is never automatically
resent. The count limit cannot be enlarged by resume or a continuation approval.
No truncation, alternate model or silent retry is available.

## Approval schema

`approval-schema.json` is the closed new schema. **There is no actual approval file
in this PR.** A future operator record must contain:

- explicit operator approval and contract-review references;
- exact model, packet/prompt, old execution/cost-report and price hashes;
- new contract/order hashes, 1,506 pairs, two passes, 3,012 requests;
- `machine-a: approved`, `machine-b: approved`, `machine-c: forbidden`;
- `max_amount_usd: "12.00"`, exact original token ceilings;
- one absolute execution root outside `benchmark/`, with fixed A/B subdirectories;
- initial or continuation kind, with continuation binding both prior approval and
  the stopped state.

The file gate records explicit operator intent; it does not authenticate a human
identity. A reference is not a human annotation or Human Ground Truth approval.
The earlier task's cost authorization does not activate a transport in this PR.

## Budget stop and continuation

If the next **whole pair** does not fit the remaining monetary budget, append
`budget_exhausted_partial`. No part of that pair is dispatched. The accepted prefix
contains equal numbers of A and B receipts. No subsequent admission, consensus or
reevaluation is allowed under the stopped approval.

A new explicit continuation approval must match the same immutable contract/order
and bind both the prior approval hash and stopped-state hash. Reusing the old
approval fails. No cost, token or request counter is reset. A continuation approval
is necessary, **not sufficient**: with unchanged spending and cap, the same next pair
will still be refused. Raising the cap or changing price/reservation policy would
require a separately reviewed contract and further authorization.

## Persistence, crash recovery and resume

An exclusive process lock covers the execution root. Append-only, fsynced journal
events have sequential names, predecessor hashes and resulting-state digests.
Reopening replays every transition and revalidates receipt hashes, frozen bindings,
usage and approvals. There is no mutable checkpoint to silently reset spending.

A request intent is durable before a payload is handed out. Receipts are atomically
published before settlement. If a process dies between those two writes, a saved
receipt can be reconciled **offline**, without a new provider call. If a dispatched
request has no receipt, whether it was billed is unknown: retain its entire
reservation and require operator audit. Never replay it automatically.

| State | Permitted next action |
| --- | --- |
| `ready` | Check and reserve the next whole pair |
| `pair_reserved` | Hand out A exactly once |
| `in_flight` with saved receipt | Validate/reconcile that receipt offline |
| `in_flight` without receipt | Operator audit; no resend or next pair |
| `pair_partial` | Hand out the already reserved B only |
| `budget_exhausted_partial` | New explicit approval; then recheck unchanged limits |
| `technical_limit_partial` | Stop; token/call limits remain hard |
| `request_failed_partial` | Operator audit; no automatic continuation |
| `complete` | No further requests |

Two remote API calls cannot form an atomic provider transaction. A crash or failure
can leave one raw receipt in quarantine. **Only fully settled pairs count as
completed**; a partial pair is never exported as a completed A/B set. The state
machine cannot make an already sent request disappear. Recovery may finish the
reserved partner only when the first receipt is durably valid; it does not restart A.

`require_complete` rejects any partial, stopped or incomplete set. There is no
consensus or reevaluation implementation in this PR; a later consumer must use this
guard and full artifact validation. Working/quarantined receipt directories must
not be imported into historical consensus tooling.

## Offline commands

```sh
uv run python -m uranus_research_service.category_pair_budget prepare \
  --output /tmp/category-pair-budget-preparation

uv run python -m uranus_research_service.category_pair_budget validate \
  --contract benchmark/review/category-coverage-pair-budget-v1

diff -qr benchmark/review/category-coverage-pair-budget-v1 \
  /tmp/category-pair-budget-preparation

# A future operator supplies this file after review; this command only validates it.
uv run python -m uranus_research_service.category_pair_budget check-approval \
  --contract benchmark/review/category-coverage-pair-budget-v1 \
  --approval /path/to/operator-approval.json \
  --output /tmp/category-paired-execution
```

There is deliberately no `run` command. Tests use explicitly synthetic approvals
and receipts in temporary directories. They cover full low-usage completion,
worst-case budget exhaustion, exact budget equality, both-request reservation,
independent token limits, A/B isolation, pass C rejection, no resend, orphan receipt
reconciliation, locks, journal tampering, cached/reasoning accounting, continuation
binding and byte-identical artifact regeneration.

## Safety

No real API requests, A/B results, consensus, Astra, reevaluation, retrieval inference,
DB/Qdrant access, training, production deployment, restart or semantic activation.
No historical benchmark files, labels, gates, thresholds or pilot artifacts change.
`semantic_query=false` and the historical benchmark verdict remain unchanged.
