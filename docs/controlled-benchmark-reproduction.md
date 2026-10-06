# Reproduce the isolated controlled benchmark

This benchmark uses a frozen draft relevance dataset containing machine proposals plus manually calibrated scoring policy. It is suitable for provisional comparative evaluation, not final production approval.

The operator module is separate from HTTP execution. No service configuration flag
enables it. It does not use production collections or SQL readers. Source fields and
eligibility come exclusively from the captured public snapshot.

## Frozen inputs and model provenance

Start from the benchmark branch with locked Python 3.13 dependencies. The five byte
hashes in `benchmark/contracts/phase2b2c-input-sha256.json` must match before and after
each run. Those inputs were also compared byte for byte with merged PR #6 at
`dfa9f58ac8f22129ef4bf6aebf0c26f679bea517` before inference.

`benchmark/contracts/model-provenance.json` identifies the unchanged Encoder source
commits, pooling, task adapters, prefixes, runtimes and v3 image. The adjacent v3 and
v5 artifact manifests pin actual model files; verify every file, not only the revision
label. v3 response schema snapshots are pinned separately. No native weights or
ONNX-v5 dependency is introduced into the Research Service.

The run uses the exact v3 production-compatible **image and model artifacts in a new
isolated container**, not production inference or a production vector collection.
The v5 runtime uses the unchanged v5 Encoder source with torch 2.11.0+cpu,
transformers 5.17.0 and peft 0.21.1. The older staging virtual environment with
torch 2.8.0, transformers 4.57.6 and peft 0.18.1 was unsuitable and was not used.
The matching existing test dependencies were mounted read-only into a separate
v5 container. No running Encoder was switched to another model or runtime.

## Isolated endpoint contract

Provision disposable containers on a dedicated benchmark network with **loopback-only**
published ports. Use a dedicated synthetic key of at least 32 characters, supplied
through `CONTROLLED_BENCHMARK_KEY` to the driver and through the corresponding service
key variables to the containers. Do not reuse production credentials.

| Component | Loopback port | CPU limit | Memory / memory+swap limit |
| --- | --- | --- | --- |
| Qdrant 1.19.1 | 16633 | 1 | 512 MiB / 512 MiB |
| v3 Encoder | 16635 | 2 | 6 GiB / 8 GiB |
| v5 Encoder | 16636 | 2 | 6 GiB / 8 GiB |

Qdrant image: `sha256:0699e7733a6fa7fa7f6b95dcbed84ebb04584110da525cdfdef9f305c4f57738`.
Use new container storage without a production volume. Encoder roots and model caches
are read-only; temporary files use a bounded tmpfs. Model loading is offline.
The driver accepts only the ports above and collection names
`benchmark_events_jina_{v3,v5}_<build>`. Existing collections/reports are rejected;
there is no in-place resume or alias operation. An interrupted build needs a new ID.

Run sequentially to avoid concurrent model memory pressure:

```sh
uv sync --locked
# Start only the isolated v3 Encoder and isolated Qdrant; verify exact /version and /ready.
uv run python -m uranus_research_service.controlled_runner run \
  --model v3 --build 20261006_001
# Stop only that benchmark Encoder, then start the isolated v5 Encoder.
uv run python -m uranus_research_service.controlled_runner run \
  --model v5 --build 20261006_001
uv run python -m uranus_research_service.controlled_runner compare \
  --build 20261006_001
```

The optional `scripts/controlled_resources.py --model v3|v5 --build ...` wraps each
run on the actual 20261006 environment. Its explicit dedicated container names must
be reviewed before reuse on a different host/date. It samples only the Encoder PID,
excluding driver CPU. Startup RSS means the loaded Encoder before document inference;
steady-state RSS means RSS after all queries. Peak RSS uses process VmHWM plus a
one-second sampler. CPU percentage uses one logical core as 100%.

## Reproducibility and limits

Each model fully validates its newly built collection, including all point IDs,
payloads and stored vectors. Queries request exact cosine search across eligible
chunks and use one shared deterministic event aggregation/evaluator. Reports record
eligible events and occurrences, input hashes, semantic document hashes, manifest,
per-document chunk hashes/token counts, ranking scores and stage timings.

Comparison rejects differing source/query/judgment hashes, reference time, evaluator,
document projection, eligible event/occurrence sets, labels or metric policy. The
comparison command also rechecks both reports against current frozen inputs and
exact model pins. Comparing the same immutable reports produces identical JSON.
Wall-clock timing and raw floating-point scores from a fresh model run need not be
byte-identical across machines; exact report reproducibility refers to deterministic
evaluation of fixed run artifacts.

The shared AI host has eight logical CPUs, about 16 GiB RAM and 16 GiB swap. Other
workloads and swap activity are uncontrolled. Encoders run sequentially with equal
CPU/memory limits, without flushing OS caches. These measurements describe this
bounded benchmark environment, not production latency or capacity. Retrieval timing
includes query embedding, Qdrant and aggregation; frozen eligibility is prepared
before timing, and this benchmark has no PostgreSQL rehydration stage.

After artifact capture, stop only the disposable benchmark containers. Retain their
isolated collection data for inspection; no v3 production collection/cache cleanup
is part of this procedure. Production deployment, alias switches, semantic activation
and threshold changes require separate authorization.
