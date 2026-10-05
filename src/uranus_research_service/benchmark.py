"""Reproducible offline evaluation. No legacy encoder is reachable from query runtime."""

import math
from pathlib import Path
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from uranus_research_service.json_codec import decode
from uranus_research_service.semantic_manifest import digest
from uranus_research_service.version import EMBEDDING_VERSION, MODEL_REVISION

# Registered before measurement. Absolute macro-average drops; no post-hoc tuning.
GATES = {"Recall@10": 0.02, "MRR@10": 0.03, "nDCG@10": 0.03, "language_recall_drop": 0.05}


class GoldenCase(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    id: str = Field(min_length=1, max_length=80)
    query: str = Field(min_length=1, max_length=1001)
    language: Literal["de", "da", "en"]
    category: Literal["accessibility", "location", "descriptive", "general"] = "general"
    expected_event_ids: list[str] = Field(min_length=1, max_length=10000)
    graded_relevance: dict[str, int] = Field(default_factory=dict)

    @model_validator(mode="after")
    def valid(self):
        if len(set(self.expected_event_ids)) != len(self.expected_event_ids):
            raise ValueError("duplicate_judgment")
        for identity in [*self.expected_event_ids, *self.graded_relevance]:
            UUID(identity)
        if any(type(v) is not int or not 0 <= v <= 3 for v in self.graded_relevance.values()):
            raise ValueError("invalid_relevance")
        if any(
            i not in self.expected_event_ids and grade > 0
            for i, grade in self.graded_relevance.items()
        ):
            raise ValueError("inconsistent_relevance")
        return self


def load_cases(path):
    path = Path(path)
    if path.stat().st_size > 8_000_000:
        raise ValueError("benchmark_input_limit")
    raw = path.read_bytes()
    # Strict JSON parser rejects duplicate keys and NaN, including JSONL records.
    values = (
        [decode(line) for line in raw.splitlines() if line.strip()]
        if path.suffix == ".jsonl"
        else decode(raw)
    )
    if not isinstance(values, list) or not 1 <= len(values) <= 1000:
        raise ValueError("benchmark_case_limit")
    cases = [GoldenCase.model_validate(v) for v in values]
    if len({c.id for c in cases}) != len(cases):
        raise ValueError("duplicate_case")
    return cases


def metrics(case, ranked):
    if len(set(ranked)) != len(ranked):
        raise ValueError("duplicate_ranked_entity")
    expected = set(case.expected_event_ids)
    grades = {i: case.graded_relevance.get(i, 1) for i in expected}
    result = {}
    for k in (5, 10):
        count = len(expected.intersection(ranked[:k]))
        result[f"Recall@{k}"] = count / len(expected)
        result[f"HitRate@{k}"] = float(count > 0)
    result["MRR@10"] = next((1 / (i + 1) for i, v in enumerate(ranked[:10]) if v in expected), 0.0)
    dcg = sum((2 ** grades.get(v, 0) - 1) / math.log2(i + 2) for i, v in enumerate(ranked[:10]))
    ideal = sum(
        (2**v - 1) / math.log2(i + 2)
        for i, v in enumerate(sorted(grades.values(), reverse=True)[:10])
    )
    result["nDCG@10"] = dcg / ideal if ideal else 0.0
    return result


def evaluate(cases, runs):
    if set(runs) != {c.id for c in cases}:
        raise ValueError("benchmark_cases_mismatch")
    values = {c.id: metrics(c, runs[c.id]["ranked_ids"]) for c in cases}
    return {
        key: sum(v[key] for v in values.values()) / len(values)
        for key in next(iter(values.values()))
    }


async def run_benchmark(cases, source, encoder, qdrant, *, now):
    from uranus_research_service.schemas.research_execution import ExecutionSemanticFilters
    from uranus_research_service.semantic import retrieve

    manifest = await qdrant.validate()
    before, _ = await source.snapshot(now=now)
    snapshot_hash = digest([d.model_dump(mode="json") for d in before])
    if snapshot_hash != manifest.source_snapshot_hash:
        raise ValueError("benchmark_snapshot_mismatch")
    runs = {}
    for case in cases:
        result = await retrieve(
            source, encoder, qdrant, ExecutionSemanticFilters(q=case.query, page_size=10), now=now
        )
        runs[case.id] = {
            **result.model_dump(exclude={"items"}),
            "ranked_ids": [str(i.entity_key) for i in result.items],
        }
    after, _ = await source.snapshot(now=now)
    if digest([d.model_dump(mode="json") for d in after]) != snapshot_hash:
        raise ValueError("benchmark_source_changed")
    return {
        "model": manifest.embedding_model,
        "revision": manifest.model_revision,
        "embedding_version": manifest.embedding_version,
        "collection": qdrant.collection,
        "source_snapshot_hash": snapshot_hash,
        "query_set_hash": digest([c.model_dump() for c in cases]),
        "reference_time": now.isoformat(),
        "gates": GATES,
        "runs": runs,
        "metrics": evaluate(cases, runs),
    }


def compare(cases, v3, v5):
    # Separate recorded runs, same SQL population and source corpus; never dual query.
    for field in ("source_snapshot_hash", "query_set_hash", "reference_time"):
        if not v3.get(field) or v3[field] != v5.get(field):
            raise ValueError("unmatched_benchmark_inputs")
    if v3.get("model") != "jinaai/jina-embeddings-v3" or v5.get("model") != "jina-v5":
        raise ValueError("benchmark_model_mismatch")
    legacy_revision = "d18862d9a48706220815554fac3ebb4dfa46fc28"
    legacy_version = (
        legacy_revision + ":native-transformers5.17.0-retrieval-normalized-f32:"
        "sections-480-overlap64-v2"
    )
    if (
        v3.get("revision") != legacy_revision
        or v3.get("embedding_version") != legacy_version
        or v5.get("revision") != MODEL_REVISION
        or v5.get("embedding_version") != EMBEDDING_VERSION
    ):
        raise ValueError("benchmark_embedding_identity_mismatch")
    if v3["query_set_hash"] != digest([c.model_dump() for c in cases]):
        raise ValueError("benchmark_queries_mismatch")
    for run in (v3, v5):
        for field in (
            "revision",
            "embedding_version",
            "collection",
            "documents",
            "average_tokens",
            "max_tokens",
        ):
            if field not in run:
                raise ValueError("benchmark_provenance_missing")
    for case in cases:
        a, b = v3["runs"][case.id], v5["runs"][case.id]
        if not a.get("eligibility_hash") or a["eligibility_hash"] != b.get("eligibility_hash"):
            raise ValueError("benchmark_eligibility_mismatch")
    old, new = evaluate(cases, v3["runs"]), evaluate(cases, v5["runs"])
    failures = [k for k in ("Recall@10", "MRR@10", "nDCG@10") if old[k] - new[k] > GATES[k]]
    regressions = []
    for case in cases:
        a, b = (
            metrics(case, v3["runs"][case.id]["ranked_ids"]),
            metrics(case, v5["runs"][case.id]["ranked_ids"]),
        )
        if a["HitRate@10"] and not b["HitRate@10"]:
            regressions.append(case.id)
    groups = {}
    for key in ["de", "da", "en", "accessibility", "location", "descriptive"]:
        subset = [c for c in cases if c.language == key or c.category == key]
        if not subset:
            failures.append("missing_coverage_" + key)
            continue
        drop = sum(
            metrics(c, v3["runs"][c.id]["ranked_ids"])["Recall@10"]
            - metrics(c, v5["runs"][c.id]["ranked_ids"])["Recall@10"]
            for c in subset
        ) / len(subset)
        groups[key] = drop
        if drop > GATES["language_recall_drop"]:
            failures.append(key)
    doc3 = {d["entity_id"]: d for d in v3["documents"]}
    doc5 = {d["entity_id"]: d for d in v5["documents"]}
    if doc3.keys() != doc5.keys() or any(
        doc3[k]["document_hash"] != doc5[k]["document_hash"] for k in doc3
    ):
        raise ValueError("benchmark_documents_mismatch")
    return {
        "v3": old,
        "v5": new,
        "gates": GATES,
        "failures": failures,
        "catastrophic_regressions": regressions,
        "group_recall_drop": groups,
        "passed": not failures and not regressions,
        "changed_chunk_documents": sum(
            doc3[k]["chunk_hashes"] != doc5[k]["chunk_hashes"] for k in doc3
        ),
    }
