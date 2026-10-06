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
| v3 Encoder | 16635 | 8 | 6 GiB / 8 GiB |
| v5 Encoder | 16636 | 8 | 6 GiB / 8 GiB |

Qdrant image: `sha256:0699e7733a6fa7fa7f6b95dcbed84ebb04584110da525cdfdef9f305c4f57738`.
Use new container storage without a production volume. Encoder roots and model caches
are read-only; temporary files use a bounded tmpfs. Model loading is offline.
The driver accepts only the ports above and collection names
`benchmark_events_jina_{v3,v5}_<build>`. Existing collections/reports are rejected;
there is no in-place resume or alias operation. An interrupted build needs a new ID.

Run sequentially to avoid concurrent model memory pressure:

```sh
uv sync --locked
export CONTROLLED_BENCHMARK_PROFILE=8cpu-8threads
# Start only the isolated v3 Encoder and isolated Qdrant; verify exact /version and /ready.
uv run python -m uranus_research_service.controlled_runner run \
  --model v3 --build 20261006_8cpu_001
# Stop only that benchmark Encoder, then start the isolated v5 Encoder.
uv run python -m uranus_research_service.controlled_runner run \
  --model v5 --build 20261006_8cpu_001
uv run python -m uranus_research_service.controlled_runner compare \
  --build 20261006_8cpu_001
```

The optional `scripts/controlled_resources.py --model v3|v5 --build ... --cpus 8` wraps each
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
CPU/memory limits, without flushing OS caches. Their unchanged backends retain
v3 ONNX intra-op=8/inter-op=1 and the explicitly user-authorized v5 benchmark
profile intra-op=8/inter-op=1. Both models are rerun from scratch under this profile.
The Encoder source itself defaults to one Torch thread; the external launcher below
uses its existing backend-injection interface to change only that execution setting. These measurements describe this
bounded benchmark environment, not production latency or capacity. Retrieval timing
includes query embedding, Qdrant and aggregation; frozen eligibility is prepared
before timing, and this benchmark has no PostgreSQL rehydration stage.

After artifact capture, stop only the disposable benchmark containers. Retain their
isolated collection data for inspection; no v3 production collection/cache cleanup
is part of this procedure. Production deployment, alias switches, semantic activation
and threshold changes require separate authorization.

## User-authorized eight-thread profile

The initial `20261006_001` run had a two-CPU limit and the original v5 one-thread
setting. v3 completed; v5 was interrupted at the user's request after the last emitted
checkpoint of 150 documents / 654 chunks. That pilot is **not** mixed into the final
comparison. Its artifacts remain historical measurements. New build
`20261006_8cpu_001` reruns both models with eight CPUs / eight intra-op threads.
Qdrant remains limited to one CPU. Model weights, precision, task adapters, pooling,
normalization, chunking, queries, labels and gates do not change.

The unchanged v5 source hardcodes one Torch thread. An external launcher in the
isolated Encoder workspace uses the existing `create_app(..., backend=...)` injection
interface. It changes only the thread profile after the original model load, and
asserts eight threads on every actual embed call. It is not a Research Service
runtime dependency or an Encoder repository change.

Before accepting readiness, the launcher compares three frozen DE/DA/EN queries and
three public passage probes at one versus eight threads, then repeats eight-thread
inference. Preregistered tolerances: max absolute vector difference <=1e-5, max vector
L2 difference <=1e-4, and repeat max difference <=1e-7. Failure aborts readiness. Probe
source and launcher hashes, unchanged Encoder source hash and observed differences
are stored in a separate parity artifact. This limited probe is not an all-input
bitwise identity claim. v5's loaded-startup RSS is measured after this parity warmup;
the v3 startup measurement has no corresponding inference warmup. Both query-latency
runs occur after complete corpus inference. No cold-start inference claim is made.

The exact external launcher is reproduced below for review. Copy it to the isolated
Encoder workspace, mount the frozen `thread-parity-probes-v1.json` at `/profile`, and
mount a dedicated writable benchmark report directory at `/profile-output`, owned
by the container UID 10001 (mode 0755). The first isolated startup exposed a report-
directory ownership mismatch; only that dedicated directory was corrected and the
benchmark container restarted before inference results were accepted. Run it
with the exact v5 environment and unchanged source, never a production Encoder.

```python
"""External isolated Encoder launcher; only the user-authorized thread profile differs."""

import hashlib
import importlib
import inspect
import json
import math
from pathlib import Path

import torch
from uranus_research_encoder.config import Settings
from uranus_research_encoder.model import TorchBackend

CAVEAT = "This benchmark uses a frozen draft relevance dataset containing machine proposals plus manually calibrated scoring policy. It is suitable for provisional comparative evaluation, not final production approval."


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class BenchmarkThreads8(TorchBackend):
    def load(self):
        super().load()
        probe_path = Path("/profile/thread-parity-probes-v1.json")
        probes = json.loads(probe_path.read_text())
        groups = [
            ("query", [p["text"] for p in probes["queries"]]),
            ("passage", [p["text"] for p in probes["passages"]]),
        ]
        if torch.get_num_threads() != 1:
            raise RuntimeError("original_thread_profile_mismatch")
        reference = [super(BenchmarkThreads8, self).embed(texts, kind) for kind, texts in groups]
        torch.set_num_threads(8)
        candidate = [super(BenchmarkThreads8, self).embed(texts, kind) for kind, texts in groups]
        repeated = [super(BenchmarkThreads8, self).embed(texts, kind) for kind, texts in groups]
        max_abs = max(
            abs(a - b)
            for x, y in zip(reference, candidate, strict=True)
            for u, v in zip(x, y, strict=True)
            for a, b in zip(u, v, strict=True)
        )
        max_l2 = max(
            math.sqrt(math.fsum((a - b) ** 2 for a, b in zip(u, v, strict=True)))
            for x, y in zip(reference, candidate, strict=True)
            for u, v in zip(x, y, strict=True)
        )
        repeat_abs = max(
            abs(a - b)
            for x, y in zip(candidate, repeated, strict=True)
            for u, v in zip(x, y, strict=True)
            for a, b in zip(u, v, strict=True)
        )
        if not (max_abs <= 1e-5 and max_l2 <= 1e-4 and repeat_abs <= 1e-7):
            raise RuntimeError("thread_profile_parity_failed")
        if torch.get_num_threads() != 8 or torch.get_num_interop_threads() != 1:
            raise RuntimeError("thread_profile_mismatch")
        report = {
            "caveat": CAVEAT,
            "execution_profile": "8cpu-8threads",
            "torch_version": torch.__version__,
            "intra_op_threads": 8,
            "inter_op_threads": 1,
            "reference_intra_op_threads": 1,
            "query_probe_count": len(probes["queries"]),
            "passage_probe_count": len(probes["passages"]),
            "probe_file_sha256": sha(probe_path),
            "launcher_sha256": sha(__file__),
            "unchanged_encoder_model_source_sha256": sha(inspect.getfile(TorchBackend)),
            "source_snapshot_hash": probes["source_snapshot_hash"],
            "input_sha256": probes["input_sha256"],
            "maximum_absolute_vector_difference": max_abs,
            "maximum_vector_l2_difference": max_l2,
            "eight_thread_repeat_maximum_difference": repeat_abs,
            "absolute_tolerance": 1e-5,
            "l2_tolerance": 1e-4,
            "repeat_tolerance": 1e-7,
            "status": "passed",
            "scope": "Three frozen DE/DA/EN queries and three public passage probes; not a claim of all-input bitwise identity.",
        }
        with Path("/profile-output/v5-thread-parity-20261006_8cpu_001.json").open("x") as stream:
            json.dump(report, stream, indent=2, sort_keys=True)
            stream.write("\n")
        print(
            json.dumps(
                {
                    "event": "benchmark_thread_profile_verified",
                    "threads": 8,
                    "max_abs_difference": max_abs,
                }
            ),
            flush=True,
        )

    def embed(self, texts, kind):
        if torch.get_num_threads() != 8:
            raise RuntimeError("thread_profile_mismatch")
        return super().embed(texts, kind)


torch.set_num_threads(8)
torch.set_num_interop_threads(1)
settings = Settings.from_env()
encoder_app = importlib.import_module("uranus_research_encoder.app")
encoder_app.app = encoder_app.create_app(settings, BenchmarkThreads8(settings.model_root))
importlib.import_module("uranus_research_encoder.__main__").main()
```
