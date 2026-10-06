"""Assemble a hash-bound parity report from isolated workers without model imports."""

import argparse
import hashlib
import json
import math
from pathlib import Path


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def vector_metrics(left, right):
    if len(left) != 1024 or len(right) != 1024:
        raise ValueError("dimension_mismatch")
    if any(type(v) not in (float, int) or not math.isfinite(v) for v in left + right):
        raise ValueError("invalid_vector")
    nl = math.sqrt(math.fsum(v * v for v in left))
    nr = math.sqrt(math.fsum(v * v for v in right))
    if not nl or not nr:
        raise ValueError("zero_vector")
    differences = [abs(a - b) for a, b in zip(left, right, strict=True)]
    return {
        "dimensions": 1024,
        "native_norm": nl,
        "onnx_norm": nr,
        "max_absolute_difference": max(differences),
        "mean_absolute_difference": math.fsum(differences) / len(left),
        "cosine_similarity": math.fsum(a * b for a, b in zip(left, right, strict=True)) / nl / nr,
    }


def ranking(query, documents, ids):
    return sorted(
        ids,
        key=lambda k: (-math.fsum(a * b for a, b in zip(query, documents[k], strict=True)), k),
    )


def assemble(root, outputs, plan_path):
    plan = read(plan_path)
    manifest = read(root / "benchmark/contracts/jina-v3-merged-artifacts.json")
    workers = {m: read(outputs / f"{m}.json") for m in ("native-query", "native-passage", "onnx")}
    expected_files = {k: v["sha256"] for k, v in manifest["files"].items()}
    code_hash = sha(root / "scripts/isolated_adapter_diagnostics.py")
    evidence = read(root / "benchmark/contracts/adapter-audit-v1/evidence.json")
    commit = evidence["contracts"]["v3"]["encoder_commit"]
    source_hashes = {
        Path(r["path"]).name: r["sha256"]
        for r in evidence["encoder_source_provenance"]
        if r["revision"] == commit and r["path"].startswith("src/")
    }
    required = {
        "config.json",
        "model.safetensors",
        "tokenizer.json",
        "tokenizer_config.json",
        "special_tokens_map.json",
    }
    required.update(
        f"retrieval_{kind}/{file}"
        for kind in ("query", "passage")
        for file in ("adapter_config.json", "adapter_model.safetensors")
    )
    for name, worker in workers.items():
        if worker["mode"] != name or worker["plan_sha256"] != sha(plan_path):
            raise ValueError("worker_identity_mismatch")
        if worker["test_code_sha256"] != code_hash or worker["export_sha256"] != expected_files:
            raise ValueError("execution_hash_mismatch")
        if worker["encoder_commit"] != commit or worker["encoder_source_sha256"] != source_hashes:
            raise ValueError("encoder_source_mismatch")
        if set(worker["source_sha256"]) != required:
            raise ValueError("source_hashes_incomplete")
        if name.startswith("native-") and worker["exact_merged_weight_matches"] != 147:
            raise ValueError("merge_audit_incomplete")
        if worker["model_revision"] != manifest["source"]["revision"]:
            raise ValueError("revision_mismatch")
        for path, digest in worker["source_sha256"].items():
            if digest != manifest["source_sha256"][path]:
                raise ValueError("source_hash_mismatch")
        if worker["token_counts"] != workers["onnx"]["token_counts"]:
            raise ValueError("tokenization_mismatch")
    limits = plan["tolerances"]
    rows = []
    for kind in ("query", "passage"):
        for i, item in enumerate(plan["parity_inputs"]):
            native = workers["native-" + kind]["vectors"][kind][i]
            onnx = workers["onnx"]["vectors"][kind][i]
            metrics = vector_metrics(native, onnx)
            passed = (
                metrics["max_absolute_difference"] <= limits["max_absolute_difference"]
                and metrics["mean_absolute_difference"] <= limits["mean_absolute_difference"]
                and metrics["cosine_similarity"] >= limits["min_cosine_similarity"]
                and abs(metrics["native_norm"] - 1) <= limits["norm_absolute_error"]
                and abs(metrics["onnx_norm"] - 1) <= limits["norm_absolute_error"]
            )
            rows.append(
                {
                    "input_id": item["id"],
                    "kind": kind,
                    "tokens": workers["onnx"]["token_counts"][i],
                    **metrics,
                    "passed": passed,
                    "native_vector": native,
                    "onnx_vector": onnx,
                }
            )
    ranks = []
    candidates = [t["id"] for t in plan["parity_inputs"] if t["purpose"] == "candidate"]
    for i, item in enumerate(plan["parity_inputs"]):
        if item["purpose"] != "query":
            continue
        rank = {}
        for backend in ("native", "onnx"):
            query = workers["native-query" if backend == "native" else "onnx"]["vectors"]["query"][
                i
            ]
            docs = {
                t["id"]: workers["native-passage" if backend == "native" else "onnx"]["vectors"][
                    "passage"
                ][j]
                for j, t in enumerate(plan["parity_inputs"])
                if t["purpose"] == "candidate"
            }
            rank[backend] = ranking(query, docs, candidates)
        n = len(candidates)
        squared = sum(
            (rank["native"].index(cid) - rank["onnx"].index(cid)) ** 2 for cid in candidates
        )
        ranks.append(
            {
                "input_id": item["id"],
                **rank,
                "top3_identical": rank["native"][:3] == rank["onnx"][:3],
                "full_order_identical": rank["native"] == rank["onnx"],
                "spearman_deterministic_order": 1 - 6 * squared / (n * (n * n - 1)),
            }
        )
    return {
        "schema": "v3-benchmark-onnx-parity-v1",
        "scope": "Small independent numerical parity; no retrieval benchmark or gate change.",
        "benchmark_build": plan["benchmark_build"],
        "status": "PASS"
        if all(r["passed"] for r in rows) and all(r["full_order_identical"] for r in ranks)
        else "FAIL",
        "preregistered_tolerances": limits,
        "plan_sha256": sha(plan_path),
        "test_code_sha256": code_hash,
        "assembler_code_sha256": sha(Path(__file__)),
        "launch_script_sha256": sha(root / "benchmark/diagnostics/run-isolated-20261006.sh"),
        "worker_sha256": {m: sha(outputs / f"{m}.json") for m in workers},
        "provenance": {
            m: {k: v for k, v in worker.items() if k != "vectors"} for m, worker in workers.items()
        },
        "inputs": plan["parity_inputs"],
        "vectors": rows,
        "rankings": ranks,
        "summary": {
            "vector_pairs": len(rows),
            "max_absolute_difference": max(r["max_absolute_difference"] for r in rows),
            "max_mean_absolute_difference": max(r["mean_absolute_difference"] for r in rows),
            "min_cosine_similarity": min(r["cosine_similarity"] for r in rows),
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--workers", type=Path, required=True)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = assemble(args.root, args.workers, args.plan)
    with args.output.open("x") as f:
        f.write(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n")


if __name__ == "__main__":
    main()
