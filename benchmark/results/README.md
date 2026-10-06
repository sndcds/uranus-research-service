# Controlled benchmark artifacts

This benchmark uses a frozen draft relevance dataset containing machine proposals plus manually calibrated scoring policy. It is suitable for provisional comparative evaluation, not final production approval.

The final comparison uses only build `20261006_8cpu_001`: eight CPUs and eight intra-op threads for each sequential Encoder. Qdrant has one CPU.

Build `20261006_001` is a historical pilot with two-CPU limits and the original v5 one-thread setting. v3 completed; v5 was interrupted on explicit user request after its last emitted checkpoint of 150 documents / 654 chunks. Its final processed count was not captured. The v5 resource sidecar records termination, not successful completion; its end RSS must not be read as post-query steady-state RSS. No v5 result or quality comparison exists for that pilot.

Pilot v3 artifacts are retained for provenance and the resource-profile repeatability check. They are excluded from the final v3/v5 comparison. Frozen inputs, labels and gates were not changed when the execution profile changed.

`chunks-*.json` holds the public chunk evidence separately from compact ranking comparisons. It contains no vectors. `resources-*.json` measures only the dedicated Encoder PID, excluding driver CPU. `v5-thread-parity-*.json` records limited one/eight-thread and repeat probes, with source hashes and tolerances; it is not all-input bitwise identity or model-quality approval.

Final verdict: **v5 provisionally fails one or more gates**. Both exact-model builds and all 120 queries completed; 105 cases enter gates. The four failing categories are atmosphere, outdoor, theatre and venue; four cases lose all known relevant top-10 hits. See [report](../../docs/v3-v5-benchmark-report.md), [case inspection](../../docs/v3-v5-case-analysis.md), [threshold analysis](../../docs/v5-threshold-analysis.md) and [completion](../../docs/phase2b2c-completion-report.md).

`chunk-differences-*.json` maps all 611 document hashes to each model’s actual chunks. `case-inspection-*.json` is separate analyst evidence, not new labels. `artifact-sha256.json` records byte digests of the immutable JSON results (excluding itself). `environment-20261006_8cpu_001.json` confirms the dedicated containers are stopped and records hashes of the executed code; production services were not stopped.
