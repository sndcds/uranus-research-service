"""Opt-in model diagnostics for a network-disabled disposable Encoder container only.

No HTTP, database, Qdrant, training, adapter persistence or benchmark execution.
Imports of model packages occur only inside the explicitly isolated worker.
"""

import argparse
import hashlib
import json
import os
from importlib.metadata import version
from pathlib import Path


def digest(path):
    with path.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def load(path):
    return json.loads(path.read_text())


def checked(path, expected):
    actual = digest(path)
    if actual != expected:
        raise ValueError("artifact_hash_mismatch: " + path.name)
    return actual


def variants(text, start, end):
    if not 0 <= start < end <= len(text):
        raise ValueError("span_bounds")
    span = text[start:end]
    rest = text[:start] + text[end:]
    middle = len(rest) // 2
    return {
        "original": text,
        "evidence_only": span,
        "evidence_first": span + rest,
        "evidence_middle": rest[:middle] + span + rest[middle:],
        "evidence_last": rest + span,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("native-query", "native-passage", "onnx", "v5"))
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--contracts", type=Path, required=True)
    args = parser.parse_args()
    if os.environ.get("ISOLATED_ADAPTER_DIAGNOSTICS") != "1" or not Path("/.dockerenv").exists():
        raise SystemExit("explicit_disposable_container_required")
    if args.output.exists():
        raise SystemExit("immutable_output_exists")
    for key in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE", "PYTHONDONTWRITEBYTECODE"):
        if os.environ.get(key) != "1":
            raise SystemExit("offline_environment_required")
    for p, expected in {
        "torch": "2.11.0+cpu",
        "transformers": "5.17.0",
        "peft": "0.21.1",
        "onnxruntime": "1.30.0",
    }.items():
        if version(p) != expected:
            raise ValueError("runtime_version_mismatch")
    plan = load(args.plan)
    evidence = load(args.contracts / "adapter-audit-v1/evidence.json")
    generation = "v5" if args.mode == "v5" else "v3"
    contract = evidence["contracts"][generation]
    import uranus_research_encoder

    source = Path(uranus_research_encoder.__file__).parent
    hashes = {}
    for row in evidence["encoder_source_provenance"]:
        if row["revision"] == contract["encoder_commit"] and row["path"].startswith("src/"):
            filename = Path(row["path"]).name
            hashes[filename] = checked(source / filename, row["sha256"])
    result = {
        "schema": "isolated-adapter-diagnostic-worker-v1",
        "mode": args.mode,
        "plan_sha256": digest(args.plan),
        "test_code_sha256": digest(Path(__file__)),
        "encoder_commit": contract["encoder_commit"],
        "encoder_source_sha256": hashes,
        "model_revision": contract["model_revision"],
        "libraries": {p: version(p) for p in ("torch", "transformers", "peft", "onnxruntime")},
        "scope": "isolated exploratory diagnostics; no benchmark result replacement",
    }
    if args.mode == "v5":
        v5(args, plan, result)
    else:
        v3(args, plan, result)
    with args.output.open("x") as f:
        f.write(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"mode": args.mode, "status": "completed"}), flush=True)


def v3(args, plan, result):
    import numpy as np

    manifest = load(args.contracts / "jina-v3-merged-artifacts.json")
    root = Path("/merged")
    # Bind every used export file, including tokenizers and merge audits.
    result["export_sha256"] = {
        p: checked(root / p, row["sha256"]) for p, row in manifest["files"].items()
    }
    snapshot = (
        Path("/v3cache/models--jinaai--jina-embeddings-v3-hf/snapshots") / result["model_revision"]
    )
    required = [
        "config.json",
        "model.safetensors",
        "tokenizer.json",
        "tokenizer_config.json",
        "special_tokens_map.json",
    ]
    required += [
        f"retrieval_{task}/{name}"
        for task in ("query", "passage")
        for name in ("adapter_config.json", "adapter_model.safetensors")
    ]
    result["source_sha256"] = {
        p: checked(snapshot / p, manifest["source_sha256"][p]) for p in required
    }
    texts = [t["text"] for t in plan["parity_inputs"]]
    if args.mode == "onnx":
        from uranus_research_encoder.merged_onnx_backend import MergedOnnxBackend

        backend = MergedOnnxBackend(root, intra_op_threads=8, optimization="basic")
        backend.load()
        result["vectors"] = {kind: backend.embed(texts, kind) for kind in ("query", "passage")}
        result["token_counts"] = [backend.count(t) for t in texts]
    else:
        import torch
        from transformers import AutoModel, AutoTokenizer
        from uranus_research_encoder.merged_export import merge_verified

        task = args.mode.split("-")[1]
        adapter = "retrieval_" + task
        # Match export merge arithmetic; inference separately uses eight threads.
        torch.set_num_threads(1)
        torch.set_num_interop_threads(1)
        torch.use_deterministic_algorithms(True)
        model, info = AutoModel.from_pretrained(
            snapshot,
            local_files_only=True,
            trust_remote_code=False,
            use_safetensors=True,
            dtype=torch.float32,
            attn_implementation="eager",
            output_loading_info=True,
        )
        if any(info.get(k) for k in ("missing_keys", "mismatched_keys", "error_msgs")):
            raise ValueError("native_weights_incomplete")
        info = model.load_adapter(
            str(snapshot / adapter), adapter_name=adapter, adapter_kwargs={"local_files_only": True}
        )
        if (
            any(f".{adapter}." in k for k in info.missing_keys)
            or info.mismatched_keys
            or info.unexpected_keys
        ):
            raise ValueError("adapter_incomplete")
        model.set_adapter(adapter)
        model.to("cpu").eval()
        audit = merge_verified(model, adapter)
        original = load(root / f"retrieval-{task}/merge-audit.json")["weights"]
        expected = {r["name"]: r["merged_sha256"] for r in original}
        actual = {r["name"]: r["merged_sha256"] for r in audit}
        if actual != expected:
            raise ValueError("merged_weights_differ_from_benchmark")
        result["exact_merged_weight_matches"] = len(actual)
        result["merged_weight_sha256"] = actual
        model.eval()
        tokenizer = AutoTokenizer.from_pretrained(
            snapshot, local_files_only=True, trust_remote_code=False
        )
        torch.set_num_threads(8)
        vectors, counts = [], []
        with torch.inference_mode():
            for text in texts:
                inputs = tokenizer(text, return_tensors="pt", truncation=False)
                hidden = model(**inputs).last_hidden_state.float()
                mask = inputs["attention_mask"][..., None]
                pooled = (hidden * mask).sum(1) / mask.sum(1).clamp(min=1)
                vector = torch.nn.functional.normalize(pooled, dim=1)[0].numpy().copy()
                vectors.append(vector.tolist())
                counts.append(int(inputs["input_ids"].shape[1]))
        result["vectors"] = {task: vectors}
        result["token_counts"] = counts
    if any(not np.isfinite(v).all() for v in result["vectors"].values()):
        raise ValueError("nonfinite_vectors")


def v5(args, plan, result):
    import torch
    from uranus_research_encoder.model import TorchBackend

    root = Path("/v5cache")
    snapshot = (
        root / "models--jinaai--jina-embeddings-v5-text-small/snapshots" / result["model_revision"]
    )
    manifest = load(args.contracts / "jina-v5-artifacts.json")
    result["artifact_sha256"] = {
        r["path"]: checked(snapshot / r["path"], r["sha256"]) for r in manifest["artifacts"]
    }
    backend = TorchBackend(root)
    backend.load()
    torch.set_num_threads(8)
    torch.set_num_interop_threads(1)
    cache = {}

    def raw(text):
        if text not in cache:
            with torch.inference_mode():
                backend._model.set_adapter("retrieval")
                inputs = backend._tokenizer(
                    text, return_tensors="pt", truncation=False, padding=True
                )
                hidden = backend._model(**inputs).last_hidden_state.float()
                last = inputs["attention_mask"].sum(1) - 1
                pooled = hidden[torch.arange(hidden.shape[0]), last]
                cache[text] = torch.nn.functional.normalize(pooled, dim=1)[0].tolist()
        return cache[text]

    def dot(a, b):
        return sum(x * y for x, y in zip(a, b, strict=True))

    # Canonical code equivalence before any counterfactual analysis.
    probe = plan["cases"][0]
    query = probe["query"]
    doc = plan["texts"][probe["target_text_id"]]
    parity = {}
    for text, kind, prefix in ((query, "query", "Query: "), (doc, "passage", "Document: ")):
        official = backend.embed([text], kind)[0]
        difference = max(abs(a - b) for a, b in zip(official, raw(prefix + text), strict=True))
        if difference > 1e-7:
            raise ValueError("diagnostic_forward_differs_from_encoder")
        parity[kind] = difference
    result["canonical_forward_max_difference"] = parity
    cases = []
    for c in plan["cases"]:
        qvariants = {
            "canonical": "Query: " + c["query"],
            "no_query_prefix": c["query"],
            "german": "Query: " + c["german_query"],
        }
        scores = []
        for d in c["documents"]:
            text = plan["texts"][d["text_id"]]
            for qname, qt in qvariants.items():
                for dname, dt in (("canonical", "Document: " + text), ("no_document_prefix", text)):
                    scores.append(
                        {
                            **d,
                            "query_variant": qname,
                            "document_variant": dname,
                            "score": dot(raw(qt), raw(dt)),
                        }
                    )
        target = plan["texts"][c["target_text_id"]]
        span = c["evidence_span"]
        windows = []
        for label, text in variants(target, span["start"], span["end"]).items():
            windows.append(
                {
                    "variant": label,
                    "text_sha256": hashlib.sha256(text.encode()).hexdigest(),
                    "characters": len(text),
                    "tokens": backend.count(text),
                    "score": dot(raw("Query: " + c["query"]), raw("Document: " + text)),
                }
            )
        cases.append({"case_id": c["case_id"], "scores": scores, "content_variants": windows})
    result["cases"] = cases
    result["unique_forward_count"] = len(cache)
    result["limitations"] = [
        "Small selected chunk pools; no corpus ranks or benchmark gates.",
        "Prefix removal is out of the published model contract.",
        "German formulations are diagnostic paraphrases, not new labels.",
        "Relocation changes attention/position too; it cannot isolate pooling causality.",
    ]


if __name__ == "__main__":
    main()
