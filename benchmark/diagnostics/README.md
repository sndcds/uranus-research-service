# Isolated post-benchmark diagnostics, 2026-10-06

This benchmark uses a frozen draft relevance dataset containing machine proposals plus manually calibrated scoring policy. It is suitable for provisional comparative evaluation, not final production approval.

These files diagnose the immutable `20261006_8cpu_001` run at PR #7 baseline
`d8bb72957c33e6d9ef2a9838ec4e54041f3e90a7`. They are not new benchmark results,
new judgments, threshold proposals or replacement gate decisions.

## Offline reconstruction

```sh
uv run python scripts/analyze_retrieval_regressions.py --output /tmp/reconstruction.json
```

Compare the parsed output with
[`v5-regression-reconstruction-20261006.json`](../results/v5-regression-reconstruction-20261006.json).
The utility verifies every original result and frozen-input hash and checks that
re-evaluation exactly reproduces the saved comparison. Output uses exclusive-create;
existing files cannot be overwritten. Full original rankings remain in the original
v3/v5 reports. The new artifact reconstructs all requested positives, neighbors,
Top-10 lists, exact chunk texts/contexts, category cases and improvement controls.

## Fixed inputs and pre-execution limits

[`20261006-regression-plan.json`](20261006-regression-plan.json) was written before
model inference. SHA256:
`67b4170b0cc735ca961ed83dd4dffd4320b860d3176003b53dc195fc8f63028e`.

Selection: four total-loss queries, their first v3/v5 known positives, v5 leaders and
strongest frozen-zero competitors. Deduplicate identical chunk text. Exact source
point IDs and character spans are retained. German paraphrases are exploratory,
not new benchmark cases or judgments. No selection was changed after seeing scores.

The independent v3 parity sample uses five DE/DA/EN queries (including the DE outdoor
query) and eight relevant/competing passages, all 13 inputs in **both** roles.
Passages range from 20 to 476 v3 tokens; query lengths are 6–12 tokens. It includes
short, medium and long retrieval chunks, not a maximum-8192-token stress test.

Pre-execution acceptance: max absolute error ≤ `1e-6`; mean absolute error ≤ `1e-7`;
cosine ≥ `1−1e-10`; L2 norm error ≤ `1e-6`; 1024 finite dimensions; identical full
ordering and Top 3 on the eight-candidate pool. These are small float32 comparison
margins and were not relaxed after execution. Both roles use their exact separate
Jina retrieval adapters and the same native merged weights as the ONNX exports.

## Actual isolated execution

Model imports are only in `scripts/isolated_adapter_diagnostics.py`, outside the
Research Service runtime and its dependency set. The worker refuses execution
without both an explicit environment marker and a container environment. It verifies
installed versions, all Encoder source hashes and required model/export file hashes
before inference. This is an authorized standalone diagnostic, not an Encoder change.

Executed on the AI host in four **new sequential disposable containers** with
`--network none`, read-only root, 8 CPUs, 6 GiB memory / 8 GiB memory+swap, no ports
and read-only model, source and venv mounts. Only a new output directory is writable.
No production container, Qdrant, SQL reader or HTTP model service is called.
[The exact launch script](run-isolated-20261006.sh) records paths and image digest.
It uses the already available test venv; no package/model downloads or image build.

Preparation used a new `/home/awendelk/adapter-diagnostics-20261006` directory:

- `input/`: copied worker and plan (named `plan.json` on the host).
- `contracts/`: unchanged v3/v5 artifact manifests and adapter-audit-v1 fixtures.
- `v3-source/`: `git archive 48ce71550d5dad8c697facd3767aef8b4be97cc1 src` from the
  Encoder repository. The v5 source mount remains the original benchmark source.
- `output/`: initially empty, immutable per-mode JSON outputs.

Run `sh run-isolated-20261006.sh` there only after reviewing these dedicated paths.
An existing output makes the worker abort. For another execution, select a new
isolated output directory/container-name suffix; do not overwrite this run.
The initial attempt failed before inference because the numeric container UID had
no username for Torch's default temporary cache. Setting
`TORCHINDUCTOR_CACHE_DIR=/tmp/torchinductor` fixed this without changing test code,
inputs or tolerances. No successful result was overwritten.

For native parity, `merge_verified` reconstructs the appropriate LoRA merge **only
in memory**, checks all 147 merged weight hashes against the benchmark merge audit,
then embeds with eight threads. Merge arithmetic uses one thread as in the original
export. No trained/adapter/export weight file is written. The ONNX worker uses the
unchanged `MergedOnnxBackend` with Basic optimization and eight intra-op threads.
The v5 worker retains the original retrieval adapter and pooling; prefix-free and
content-relocated inputs exist only inside the diagnostic process.

## Reports and reproducibility

Copy completed per-mode outputs to a separate local temporary directory, then:

```sh
uv run python scripts/summarize_adapter_diagnostics.py \
  --workers /tmp/uranus-diagnostic-workers \
  --plan benchmark/diagnostics/20261006-regression-plan.json \
  --output /tmp/v3-parity.json
```

The assembler rejects changed model, Encoder source, plan, worker code or artifact
hashes. Raw worker byte hashes are retained in the report; JSON reserialization
changes those hashes even when vectors remain the same. The committed report
contains complete vectors and provenance so the numerical calculations can be
repeated offline without weights or retaining duplicate worker vector files.

- [v3 parity](../results/v3-benchmark-onnx-parity-20261006.json): **PASS**, 26 vector
  comparisons; both vector arrays, norms, component errors, cosine, five full/Top-3
  ranking checks, source/graph/external-weight/adapter/test-code hashes.
- [v5 probes](../results/v5-regression-diagnostics-20261006.json): 58 unique forwards;
  15 distinct original chunk texts plus fixed variants; canonical scores and
  counterfactual scores. This is the worker's unmodified JSON output.
- [Reconstruction](../results/v5-regression-reconstruction-20261006.json): deterministic
  saved-ranking analysis; no new inference.
- [Interpretation](../../docs/v5-regression-root-cause-analysis.md): R6 with explicit
  component-attribution limits; fine-tuning not yet justified.

No v3/v5 cross-space dot products, global counterfactual ranking, new quality gate,
new threshold, human approval or production claim. All original benchmark artifacts
retain their original hashes; new artifacts have a separate checksum index here.

Offline checks: `uv sync --locked --offline`, `uv run ruff check .`,
`uv run ruff format --check .`, `uv run pytest -q`, `git diff --check`.
Local result: 484 passed / 24 skipped, including 13 new tests without model weights.
Original frozen input bytes and all original result hashes remain unchanged.
