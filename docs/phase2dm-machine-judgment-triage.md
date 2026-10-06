# Phase 2D-M: blind machine-judgment triage

## Scope and status

A separate exploratory machine strand, based on `main` after PR #8, merge
`e653ff53547e29c0835e836440d2e6ac4bec6651`. Phase 2D-A's human workflow,
judgments, approval gate and freeze mechanism are unchanged. No machine output is
converted to a human annotation or passed to the human freeze command.

**This delivery stops at implementation, tests and the small cost pilot. The full
5,739-judgment run requires a new explicit cost authorization from Aurelius.**
There are no real full-run consensus sets, expanded metrics, gate decisions or
human-triage results yet. Synthetic end-to-end fixtures run only under pytest.

All future reports must say:

> Exploratory machine-consensus judgments, not human-reviewed or human-approved labels, not gold labels or ground truth, and not production approval. Correlated model errors remain possible.

The historical statement also remains unchanged:

> This benchmark uses a frozen draft relevance dataset containing machine proposals plus manually calibrated scoring policy. It is suitable for provisional comparative evaluation, not final production approval.

## Immutable inputs and stage separation

[Historical input pins](../benchmark/contracts/phase2dm-input-sha256.json) cover the
prior benchmark and Phase-2D-A artifacts, human workflow implementation and original
evaluator. Preparation verifies every hash. The worker receives a separate directory
containing only the frozen blind packet, its public package descriptor, versioned
prompts, closed response schema, policy and execution plan. It never loads the
operator mapping, case IDs, historical grades, retrieval scores or rankings.

Preparation is a separate operator process. It extracts model-free language/category/
text-length strata into an **operator-only** file for later bias reporting. That file
is hashbound to the plan but is never sent to the judge. Actual API payloads are
allowlisted and tested, including nested public evidence. The opaque annotation ID
is the only candidate identity sent. Public evidence is not rejected merely because
ordinary text happens to contain a string such as “v5”.

The API worker verifies input bytes, package identity and its own source-code hash
before each pass. The source code hash, exact model, prompt hash, package hash and
plan hash bind resumable outputs. Input/model/prompt/code changes require a new plan
and output location; no silent fallback or reuse across incompatible runs.

## Official API and pinned model

The pilot explicitly uses `gpt-5.4-mini-2026-03-17`. The CLI requires an explicit
model ID at preparation and execution, checks `GET /v1/models/<model>`, and requires
the response model to match exactly. An unavailable model or unsupported parameter
fails closed; no alternate model is chosen.

The worker uses the official `https://api.openai.com/v1/responses` endpoint through
existing httpx, strict JSON Schema under `text.format`, `store=false`, temperature 0,
reasoning effort `none` and maximum 1,200 output tokens. No tools, previous response,
conversation state or other candidate judgments are sent. These settings are fixed,
not a guarantee of bitwise deterministic output. No seed semantics are claimed.

API keys come only from `OPENAI_API_KEY`. The CLI never prints keys or provider
bodies. Fixed origin, no redirects, no environment proxy inheritance, no forwarded
cookies, identity content encoding, JSON response checks, 60-second timeout and
256 KiB request/response bounds apply. Only sanitized identifiers, usage, latency,
status and safe error categories are persisted alongside accepted judgments.

Sources inspected on 2026-10-06:
[model, snapshot and prices](https://developers.openai.com/api/docs/models/gpt-5.4-mini),
[Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs),
[API pricing](https://developers.openai.com/api/docs/pricing).
Published standard token rates are stored as a dated observation, not executable
fallback prices: $0.75/M input, $4.50/M output. The estimator ignores cache/batch
discounts and tax. Model/pricing mismatches or observations older than seven days
are rejected for cost-report generation. Account-specific availability still needs
an actual API check.

## Three separate passes, same rubric

`machine-a`, `machine-b`, `machine-c` each use their own stateless requests and run ID.
The common [judge instructions](../benchmark/annotation/phase2dm/prompt/judge-v1.txt)
and authoritative candidate rubric are identical. Only the preregistered checking
order differs:

- A: eligibility → central query requirements → rubric.
- B: supporting evidence → restrictions/missing requirements → eligibility/rubric.
- C: event-wide versus occurrence-specific evidence → requirements/eligibility → rubric.

No pass sees another pass's answer; no instructions adapt to outcomes. These are
three independent machine-judgment passes operationally, **not three humans or
statistically independent samples**. Shared-model errors may persist unanimously.

The frozen scale remains 0–3. `uncertain` and `needs_more_context` require null grade.
Confidence is an uncalibrated machine self-assessment. Positive grades require real,
nonempty cited fields and an eligible occurrence anchoring the event context.
Non-positive states may cite a field precisely because evidence is absent; this does
not create positive evidence. Foreign occurrence IDs are always rejected.

The concert rubric remains multiple genres in a single concert program. Accessibility
requires the actual specific access claim, restrictions and matching occurrence;
a generic accessibility word is not evidence of every requested facility. Event text
is untrusted data and cannot override instructions. No artist/venue/world-knowledge
inference is authorized. The reason is short, evidence-bound and cannot refer to
retrieval systems or their outcomes. Structured validation checks contracts, not
semantic truth; machine mistakes remain possible.

## Resume, retries and failures

Each run has an exclusive process lock. Before a POST, an immutable attempt reservation
is persisted; after a response, safe metadata and any accepted judgment are atomically
published with fsync and exclusive creation. Completed answer files are never replaced.
A successful attempt whose final record was interrupted can be recovered from its
persisted result. Completed valid records skip POSTs on resume.

Transient network errors, 429 and selected temporary HTTP failures have at most three
attempts **across resumes**, with bounded backoff. Contract failures, refusals, wrong
model, redirects and malformed responses stop without repair. A crash after server
acceptance but before local persistence can leave an unknown/billable attempt; retries
are not an exactly-once billing guarantee. Usage may be unavailable for such failures.
Output directories must remain intact when resuming; copying a plan to a fresh directory
is not a supported way to reset its attempt budget.

## Cost pilot and approval boundary

The preregistered pilot selects one deterministic candidate from each language ×
within-language UTF-8-length quartile: 12 candidates, three passes, 36 intended
judgments. Sampling uses no labels or retrieval metadata. The pilot directory and
`purpose=dry-run` distinguish its answers from full-run labels; sealing rejects pilot
rows. No consensus or retrieval-quality conclusion is computed from this sample.

Costs are estimated from measured API input/output usage. Population weighting by
language/length stratum projects to 5,739 judgments; a plain pilot mean is also
reported. One sample per stratum does not justify a calibrated confidence interval.
The three-attempt stress estimate is illustrative, not a spending guarantee.
Pilot observations are not copied into the full run.

The initial pilot is preserved separately. Pass A and C completed; pass B stopped
on a validation rejection. An independent request with the same rejected payload
reproduced `missing_occurrence`, a check reachable for non-positive states citing
absent occurrence evidence. The original rejected structured body was not retained,
so its precise rejection condition cannot be retrospectively proven from the generic
error category alone. The validator was corrected only for non-positive references
to absent fields; positive-evidence checks stayed strict. Prompt, rubric, model,
sample and consensus policy did not change. A new worker hash and separately versioned
pilot were used after regression testing. No earlier result was overwritten.

The corrected pilot completed **36/36**, with zero failed attempts. Measured plain
means: **2,003.42 input tokens** and **171.31 output tokens** per request. Weighted
projection for all 5,739 judgments: **11,536,781 input** and **964,034 output tokens**.
At the observed standard prices this is **$12.99**, or **$38.97** in the illustrative
three-attempt scenario. Neither number is a hard spend cap.

Including the initial partial pilot and the one diagnostic POST, 66 real judging
requests were made: 64 accepted outputs, one rejected response and one diagnostic.
Their recorded usage totals 135,183 input / 11,357 output tokens, approximately
**$0.1525** at uncached standard prices. No billing invoice was inspected.

[Cost report](../benchmark/results/phase2dm/dry-run.json),
[all-pilot accounting](../benchmark/results/phase2dm/pilot-accounting.json),
[initial pilot](../benchmark/results/phase2dm/pilot-initial/plan.json), and
[corrected pilot](../benchmark/results/phase2dm/pilot-20261006-v2/plan.json) are separate.
Published per-pass rows and compact request ledgers retain exact accepted judgments,
usage, identifiers and hashes; atomic per-request runtime journals remain in the work
directory. The initial worker and diagnostic script are archived as text to bind their
execution hashes. No empty full-run result or consensus files are created.

## Preregistered machine consensus

[Policy](../benchmark/annotation/phase2dm/policy-v1.json) is fixed before full-run
judgments or retrieval deblinding:

- **Strict:** all three graded, identical grade. Zero is a valid consensus grade.
- **Majority:** includes strict; otherwise all three graded, two identical, third
  directly adjacent, and all three confidences at least 0.8.
- Differences of two or more are material; no auto-acceptance even for a 2/3 vote.
- Any uncertain/context state leaves both variants unresolved. Null never becomes zero.

Raw vote majority, adjacent disagreement and material disagreement are recorded
separately from acceptance. This is intentionally more conservative than an unrestricted
2/3 majority. The confidence cutoff is a fixed triage heuristic, not calibration.

All three complete full runs are required before consensus. Inter-run machine agreement
includes pairwise exact/within-one agreement, 4×4 matrices, Cohen's kappa, state disagreement,
three-way unanimity and confidence distributions. Only two graded responses contribute
to a pairwise grade matrix. Degenerate kappa is null. Language, category and length-bin
reports include grade/uncertainty distributions and agreement, before ranking deblinding.
Those reports support inspection; different grade rates alone do not establish bias.

Consensus sets, disagreements, agreement and model-free bias reports are written first.
A final seal binds their SHA256 and all three raw run hashes. This seal is machine
provenance only, not a human approval. Evaluation verifies the seal **before** loading
mapping or rankings. It does not use Phase-2D-A's human freeze mechanism.

## Exploratory evaluation after authorization and completion

The offline evaluator reuses the exact complete stored rankings and original metric
implementation and gates. Existing grades always win on conflict. Machine consensus
adds only previously unjudged pairs; disagreement with a historical grade is recorded
with old/new grades, mode and confidence. No automatic claim is made that either is
correct. This conservative retention policy can preserve historical label errors.

Strict and majority use their own new judgment hashes, but each applies identical
labels to both retrieval models. Original exclusions and the 105-case cohort remain;
the six no-hit hypotheses never enter official-style gate calculations. No vectors,
thresholds, aggregation, ranking scores or source eligibility change.

Separate outputs include Recall@10, MRR@10, nDCG@10, languages/categories, the four
known-positive-loss cases, Top-10/20 coverage, per-case deltas and diagnostic/balanced/
full-selected summaries. The full historical cohort is also shown but is not an
unbiased global estimate after targeted expansion. Historical metrics/gates remain
untouched. Use “passes/fails under exploratory machine-consensus judgments” and
“historical known-positive loss disappears under [mode] machine-consensus expansion”,
never a claim that human validation disproved a failure.

## Triage after deblinding

Operator triage priority: material inter-run disagreement, unresolved state, potential
gate change, historical total-loss cases, failed categories, low confidence, remainder.
Gate sensitivity is a **post-judgment hypothetical 0-versus-3 endpoint screen**, using
unchanged gate tolerances and stored rankings. It creates no labels and tunes no policy.

The smaller review subset includes all material/unresolved/gate-sensitive pairs,
non-unanimous total-loss/failed-category pairs and low-confidence pairs. Its eventual
size depends on results; no reduction is claimed before a full run. Historical conflicts
are also preserved in a separate operator report. All original pool rows remain auditable.
The human-facing triage packet contains only original blind evidence, no machine grades,
reasons, confidence, priority or expected impact. Human reviews can be imported as a
partial batch through the unchanged Phase-2D-A workflow, independently of machine output.

## Reproduction

No new Python dependencies or service CLI/request routes were added. Operator example:

```sh
uv run python -m uranus_research_service.machine_cli prepare \
  --work /tmp/phase2dm-pilot --model gpt-5.4-mini-2026-03-17 --build-id phase2dm_pilot
# Set OPENAI_API_KEY securely in the environment; do not print it.
uv run python -m uranus_research_service.machine_cli run \
  --work /tmp/phase2dm-pilot --model gpt-5.4-mini-2026-03-17 --purpose dry-run
uv run python -m uranus_research_service.machine_cli cost \
  --work /tmp/phase2dm-pilot --pricing benchmark/annotation/phase2dm/pricing-20261006.json
```

**Stop here for cost authorization.** The future `--purpose full --approval <file>`
requires an external approval reference, exact plan hash, exact dry-report hash and
5,739 authorized judgments. It is a declared authorization record, not an identity
verification mechanism. No such real approval file is generated by this implementation.

The prepared current plan is also recorded in
`benchmark/annotation/phase2dm/manifest.json`. To reconstruct the measured pilot's
plan, use build ID `phase2dm_20261006_002` with the pinned model and unchanged worker.
The protected blind packet need not be duplicated in the result directory. Restore the
measured `dry-run.json` into that work directory before a separately authorized full run.
An approval record must contain `authorization: explicit-cost-approval`,
`approval_reference`, `plan_sha256`, `dry_report_sha256` (canonical JSON SHA256) and
`max_judgments: 5739`. That record is deliberately absent in this delivery.

Only after a full run: `seal --work <work> --output <work>/consensus`, inspect its
pre-deblinding bias/agreement reports, then `evaluate --work <work> --output <new-dir>`.
The evaluator never overwrites an existing output directory. To hand off a later triage
packet, copy its blind candidates and package descriptor under the two filenames
expected by the unchanged offline human UI; do not include operator triage metadata.

Tests use synthetic providers/judgments only and exercise the full offline sealing and
evaluation path in temporary directories. The all-zero synthetic expansion must leave
original quality metrics/gates exactly unchanged while increasing coverage. No synthetic
result is committed as a real machine run. Existing CI, PostGIS/Qdrant/Admin parity and
Docker checks remain required; no weights are downloaded for the new tests.

No deployments, production access, DB/Qdrant writes, aliases, reindexing, new embeddings,
model/LoRA changes or semantic activation are part of this work. `semantic_query=false`.
