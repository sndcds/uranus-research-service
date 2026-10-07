# Category coverage cost pilot

## Purpose

Baseline: `29c5063f81bacabc884fba7f7a4bcd0941d66ed5` (PR #15 merged).
Twenty independent Responses requests calibrate **usage and cost only**. They do
not contribute judgments to A/B, consensus, human review, or reevaluation.
The original category A/B contract and historical benchmark remain unchanged.

## Selection

Selection is fixed before requests and uses the existing exact serialized HTTP
payload sizes, opaque IDs and category membership only. The old operator files are
hash checked; only category membership is projected from them. No ranks, scores,
previous grades, expected relevance or quality signals influence selection.

Sort the 1,506 payloads by `(UTF-8 byte count, annotation_id)`. Partition at zero-based
ranks `0,301,602,1129,1430,1506` (approximately 0–20%, 20–40%, 40–75%,
75–95%, 95–100%). Select four per stratum. In the first four strata select one per
category; in the largest stratum select two accessibility, one theatre, one venue.
Within a quota select the smallest SHA256 of the canonical JSON array
`["category-coverage-cost-pilot-v1", "select", annotation_id]`, without replacement.
Order the 20 requests by the corresponding `"order"` hash.

This yields accessibility 6, outdoor 4, theatre 5, venue 5. Selection is not a
simple random sample or population-proportionate category sample. The entire
operational size population and selected IDs/hashes are saved for reproduction.
No category or sampling metadata enters a provider request. The selected maximum is
16,704 bytes versus 24,990 in the full population: the extreme tail is extrapolated,
not directly measured. All four largest-stratum samples exceed the population p95.

Artifacts live in the sibling `benchmark/review/category-coverage-cost-pilot-v1/`:
the old pool and PR #15 contract both have sealed directory contracts. Adding a
pilot inside either old directory would weaken their existing reproducibility tests.

## Pilot Approval

The CLI cannot generate approval. An operator supplies a separate closed
`category-cost-pilot-approval-v1` record binding model, prompt, packet, selection,
code, request count, token limits, and a single absolute execution directory.
`approved=true`, `pilot_only=true` and a real approval reference are required.
This approval cannot validate against the full-run A/B approval schema.

The user's explicit instruction authorizes this one 20-request pilot. The published
approval records that instruction, not an invented reviewer identity, human label
approval, or authorization of 3,012 requests. No A/B approval is generated.

## Real API execution

```sh
uv run python -m uranus_research_service.category_machine_cost_pilot prepare \
  --package benchmark/review/category-coverage-v1 \
  --output /tmp/category-cost-pilot-preparation

# Operator supplies a pilot approval bound to that selection and output directory.
# OPENAI_API_KEY must be an environment variable, never a CLI argument.
uv run python -m uranus_research_service.category_machine_cost_pilot run \
  --pilot /tmp/category-cost-pilot-preparation \
  --approval /path/to/pilot-approval.json \
  --model gpt-5.4-mini-2026-03-17 \
  --output /tmp/category-cost-pilot-run
```

The worker reuses PR #15's exact `request_for` and transport: same prompt, closed
blind projection, strict JSON schema, temperature 0, reasoning `none`, output cap
1,200, `store=false`, no tools, no history. There is no model fallback or model
availability probe. The only network operation is one POST per selected candidate.

**At most 20 POST attempts.** No automatic retries, even for 429/network errors:
the hard request cap takes precedence over recovery. Failures stop the pilot.
A fsynced exclusive reservation precedes each send. An interrupted attempt consumes
its slot and blocks unattended continuation. `--resume` skips completed slots with
identical selection/model/prompt/code/approval; it never retries a failed or
interrupted slot. Concurrent runs in the approved directory are locked out.
Completion records, usage and ledger are published atomically and never overwritten.
Do not recreate the approved directory to replay the pilot.

## Token usage

Per request: opaque annotation ID, ordinal, actual HTTP payload SHA256, provider
request ID, response ID, exact returned model, input/output/total tokens, cached
input and reasoning tokens, latency, timestamp, retries and status.
Missing cached/reasoning detail remains null. It is not reported as measured zero.
For pricing, unknown cached input gets no discount. Reasoning tokens are already
part of output tokens and are not charged twice.

The answer passes the existing evidence/occurrence/schema validator, then its
content is discarded. No raw provider body, reason, grade, supporting evidence or
API key is persisted. The CLI validates recorded usage offline:

```sh
uv run python -m uranus_research_service.category_machine_cost_pilot validate \
  --pilot benchmark/review/category-coverage-cost-pilot-v1 \
  --pilot-run benchmark/review/category-coverage-cost-pilot-v1/run
```

Usage-only records cannot be imported as A/B completion records or annotation
answers. CI tests inspect the actual HTTP request bytes with a synthetic transport.

## Cost model

Pricing is supplied explicitly, never fetched by runtime code. A separate versioned
price manifest records the operator's rate source, date, currency and service tier.
The [official GPT-5.4 mini page](https://developers.openai.com/api/docs/models/gpt-5.4-mini)
lists USD per million tokens: input 0.75, cached input 0.075, output 4.50
(observed 2026-10-07, standard global endpoint; no batch/region uplift).

```text
cost = ((input - cached) × input_rate + cached × cached_rate
        + output × output_rate) / 1,000,000
```

These are tariff-derived usage costs, not account invoices. Credits, taxes and
future tariff changes are not included. CLI price arguments are mandatory:

```sh
uv run python -m uranus_research_service.category_machine_cost_pilot analyze \
  --pilot benchmark/review/category-coverage-cost-pilot-v1 \
  --pilot-run benchmark/review/category-coverage-cost-pilot-v1/run \
  --input-price-per-million 0.75 \
  --cached-input-price-per-million 0.075 \
  --output-price-per-million 4.50 \
  --output /tmp/category-cost-analysis.json
```

## Full A/B projection

For each size-stratum × category cell, estimate actual input tokens per serialized
byte and output length from pilot responses. Apply those rates to every population
payload, then multiply by two. The single outdoor payload in the largest stratum
has no sampled cell: its projection explicitly falls back to the largest stratum.
The fallback ID is reported. No linear unweighted `pilot cost × 150.6` estimate is
used, which would over-weight the deliberately oversampled large requests.

Lower/central/upper use observed cell minima/means/maxima, respectively. Lower
uses the greatest observed cache fraction, central the mean, upper no caching.
Also report central with no cache discount. These scenarios are **not statistical
confidence bounds**; most cells have one observation. No full run is authorized
by any projection.

## Conservative ceiling comparison

PR #15's original cost-report hash and numbers are retained: 37,306,150 estimated
input tokens and 3,614,400 maximum output tokens for A+B before retries. The
conservative no-cache tariff calculation is reported beside empirical estimates,
never replaced by them. This byte-plus-framing estimate is an operational planning
ceiling, not a mathematical guarantee of provider accounting. Retries would require
separate approval and are not included in the empirical 3,012-request projection.

## Limits

Only 20/1,506 payloads are sampled. Category quotas and large accessibility payloads
can influence the estimates. Answer length, cache behavior and provider prices may
change. This pilot measures no relevance quality or category metrics. No production,
DB/Qdrant, retrieval inference, training, thresholds, deployment or activation is
involved. `semantic_query=false` remains unchanged.

## No Judgment Use

All pilot answers are operationally discarded after validation. No grade
distribution is reported; no machine/human consensus or ground truth is produced.
The historical verdict remains `v5 provisionally fails one or more gates`.

## Measured pilot (2026-10-07)

Exactly 20 Responses POSTs completed with the pinned model
`gpt-5.4-mini-2026-03-17`, returned service tier `default`. All 20 passed the
existing answer contract, with zero retries/failures. No answer content was retained.

| Usage | Measured tokens |
| --- | ---: |
| Input | 44,530 |
| Output (including any reasoning) | 2,827 |
| Total | 47,357 |
| Cached input | 0 |
| Reasoning | 0 |

| Per-request statistic | Input tokens | Output tokens |
| --- | ---: | ---: |
| Min | 1,138 | 119 |
| p50 (nearest rank) | 1,637 | 135 |
| p95 | 4,579 | 179 |
| Max | 4,581 | 193 |

Pilot tariff cost: **USD 0.046119**; mean 0.00230595, median 0.001913625,
p95 0.004038 per request.

| Projection for 3,012 requests, no retries | USD |
| --- | ---: |
| Empirical lower scenario | 6.0654465 |
| Empirical central scenario (also without cache) | 6.0690525 |
| Empirical upper scenario | 6.07255275 |
| Unchanged PR #15 conservative contract estimate | 44.2444125 |

The central estimate projects 5,584,970 input and 417,850 output tokens, about
**13.72%** of the conservative tariff estimate. The extremely narrow empirical
scenario spread reflects nearly empty sampling cells, **not precision or a reliable
cost bound**. Use the separate conservative estimate for safety planning; the pilot
does not authorize either budget. Category quotas and the unmeasured extreme payload
tail remain substantial limitations.

Bindings:

- Selection SHA256: `36a014612414831e7b36858491c5c3ab726589d65d53b0329029724e48b7a671`
- Packet SHA256: `6b2b54c3c254d97f2972b04d122cc8e415eeff87e09d164d09a7902c45f3cd54`
- Prompt SHA256: `a9fa74d48d8b92676d6e9a47dfde0cf22c696dc16e6f1b16b72f5438c938b584`
- Original cost-report SHA256: `f2473a0dc3e3fac49ed5d0f2c8ac7be774f7a3bc4e1da4a0e43b40ebe9b849a4`

`artifact-sha256.json` binds the selection, schema, user-authorized pilot approval,
price manifest, run configuration, all reservations/usage records, request ledger
and analysis. `historical-input-sha256.json` protects all 180 pre-existing benchmark
files against the baseline commit. Published artifacts are revalidated by offline
CI tests, including recomputation of the cost report. The original request bodies
can be reconstructed from the frozen blind packet and unchanged PR #15 serializer.
The original response contents intentionally cannot be reconstructed from this pilot.

## Validation

Local final validation: `uv sync --locked --offline`, Ruff, format and diff checks
passed; `uv run pytest -q`: **714 passed, 24 skipped**. The 26 pilot tests require
neither a key nor network access. Skipped integration tests require disposable
PostGIS/Qdrant, a pinned Admin reference checkout, or an optional real encoder;
none was configured for this local run. The unchanged PR CI separately exercises
disposable integration services and builds the Docker image without model downloads.
