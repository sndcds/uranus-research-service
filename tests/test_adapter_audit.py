"""Pin audit evidence to the completed benchmark; no model imports or downloads."""

import hashlib
import json
from pathlib import Path

import pytest

from uranus_research_service.controlled_runner import V3, V5
from uranus_research_service.version import ENCODER_EXPECTED

ROOT = Path(__file__).resolve().parents[1]
CONTRACTS = ROOT / "benchmark/contracts"
AUDIT = CONTRACTS / "adapter-audit-v1"


def read(path):
    return json.loads(path.read_bytes())


def test_adapter_config_bytes_match_executed_artifact_pins():
    evidence = read(AUDIT / "evidence.json")
    v3 = read(CONTRACTS / "jina-v3-merged-artifacts.json")
    v5 = read(CONTRACTS / "jina-v5-artifacts.json")
    mapping = {
        "v3-model-config.json": v3["source_sha256"]["config.json"],
        "v3-query-adapter-config.json": v3["source_sha256"]["retrieval_query/adapter_config.json"],
        "v3-passage-adapter-config.json": v3["source_sha256"][
            "retrieval_passage/adapter_config.json"
        ],
        "v5-retrieval-adapter-config.json": next(
            f["sha256"]
            for f in v5["artifacts"]
            if f["path"] == "adapters/retrieval/adapter_config.json"
        ),
    }
    assert evidence["fixture_sha256"] == mapping
    for name, expected in mapping.items():
        assert hashlib.sha256((AUDIT / name).read_bytes()).hexdigest() == expected


@pytest.mark.parametrize("generation,expected", [("v3", V3), ("v5", V5)])
def test_audited_contract_matches_benchmark_and_executed_source(generation, expected):
    evidence = read(AUDIT / "evidence.json")
    contract = evidence["contracts"][generation]
    provenance = read(CONTRACTS / "model-provenance.json")[generation]
    for key in ("model_repository", "model_revision", "dimensions", "backend"):
        assert contract[key] == expected[key]
    assert contract["encoder_commit"] == provenance["encoder_commit"]
    observed = evidence["observed"][
        "v3_installed_encoder_source_sha256" if generation == "v3" else "v5_encoder_source_sha256"
    ]
    sources = {
        Path(s["path"]).name: s["sha256"]
        for s in evidence["encoder_source_provenance"]
        if s["revision"] == contract["encoder_commit"] and s["path"].startswith("src/")
    }
    assert observed == sources
    assert contract["custom_training_used"] is False
    if generation == "v5":
        probe = read(ROOT / "benchmark/results/v5-thread-parity-20261006_8cpu_001.json")
        assert observed["model.py"] == probe["unchanged_encoder_model_source_sha256"]
        assert provenance["adapter"] == contract["adapter_subdirectory"] == "adapters/retrieval"
        assert contract["model_revision"] == ENCODER_EXPECTED["model_revision"]


def test_v3_two_merged_retrieval_loras_not_legacy_task_bank():
    evidence = read(AUDIT / "evidence.json")
    manifest = read(CONTRACTS / "jina-v3-merged-artifacts.json")
    contract = evidence["contracts"]["v3"]
    assert contract["query_adapter"] == "retrieval_query"
    assert contract["document_adapter"] == "retrieval_passage"
    for task in ("query", "passage"):
        assert manifest["tasks"][task]["source_adapter"] == "retrieval_" + task
        graph = evidence["actual_graph_inspection"]["graphs"][task]
        assert graph["inputs"] == ["input_ids", "attention_mask"]
        assert graph["lora_initializers"] == graph["task_id_nodes"] == []
        assert graph["sha256"] == manifest["files"][f"retrieval-{task}/model.onnx"]["sha256"]
        assert evidence["observed"]["v3_merge_audits"][task]["exact_weight_matches"] == 147
        config = read(AUDIT / f"v3-{task}-adapter-config.json")
        assert (config["peft_type"], config["r"], config["lora_alpha"]) == ("LORA", 4, 1)
    assert (
        manifest["files"]["retrieval-query/model.onnx.data"]["sha256"]
        != manifest["files"]["retrieval-passage/model.onnx.data"]["sha256"]
    )
    assert evidence["historical_bank_audit"]["used_by_benchmark"] is False
    assert evidence["historical_merged_parity"]["same_graph_file_hash"] is False
    assert evidence["historical_merged_parity"]["same_external_weight_file_hashes"] is True


def test_v5_shared_real_lora_plus_role_prefixes():
    evidence = read(AUDIT / "evidence.json")
    contract = evidence["contracts"]["v5"]
    config = read(AUDIT / "v5-retrieval-adapter-config.json")
    assert contract["query_adapter"] == contract["document_adapter"] == "retrieval"
    assert (contract["query_prefix"], contract["document_prefix"]) == ("Query: ", "Document: ")
    assert contract["peft_at_inference"] == "0.21.1"
    assert config["peft_type"] == "LORA"
    assert config["task_type"] == "FEATURE_EXTRACTION"
    assert config["r"] == config["lora_alpha"] == 32
    assert config["lora_dropout"] == 0.1
    assert config["inference_mode"] is True
    assert set(config["target_modules"]) == {
        "q_proj",
        "k_proj",
        "v_proj",
        "o_proj",
        "gate_proj",
        "up_proj",
        "down_proj",
    }
    assert evidence["observed"]["v5_adapter_tensor_summary"]["count"] == 392
    assert evidence["verdict"] == "A"
    # Cache presence must not be mistaken for active task selection.
    files = evidence["observed"]["v5_snapshot_files"]
    assert "adapters/classification/adapter_model.safetensors" in files
    assert "modeling_jina_embeddings_v5.py" in files


def test_completed_benchmark_artifacts_remain_byte_identical():
    base = ROOT / "benchmark/results"
    for name, expected in read(base / "artifact-sha256.json")["files"].items():
        with (base / name).open("rb") as stream:
            assert hashlib.file_digest(stream, "sha256").hexdigest() == expected
