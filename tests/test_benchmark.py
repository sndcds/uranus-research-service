import copy

import pytest

from uranus_research_service.benchmark import GoldenCase, compare, metrics
from uranus_research_service.semantic_manifest import digest

A = "00000000-0000-0000-0000-000000000030"
B = "00000000-0000-0000-0000-000000000031"


def test_metrics_hand_computed():
    c = GoldenCase(id="one", query="jazz", language="de", expected_event_ids=[A, B])
    r = metrics(c, [B])
    assert r["Recall@5"] == r["Recall@10"] == 0.5
    assert r["MRR@10"] == r["HitRate@5"] == r["HitRate@10"] == 1
    assert r["nDCG@10"] == pytest.approx(1 / (1 + 1 / 1.584962500721156))
    assert all(v == 0 for v in metrics(c, []).values())
    with pytest.raises(ValueError):
        metrics(c, [A, A])


def reports():
    cases = [
        GoldenCase(id=lang, query="jazz", language=lang, category=category, expected_event_ids=[A])
        for lang, category in [("de", "accessibility"), ("da", "location"), ("en", "descriptive")]
    ]
    base = {
        "source_snapshot_hash": "a" * 64,
        "query_set_hash": digest([c.model_dump() for c in cases]),
        "reference_time": "2026-10-05T00:00:00+00:00",
        "revision": "pinned",
        "embedding_version": "pinned",
        "collection": "isolated",
        "average_tokens": 20,
        "max_tokens": 20,
        "documents": [{"entity_id": A, "document_hash": "doc", "chunk_hashes": ["chunk"]}],
        "runs": {c.id: {"ranked_ids": [A], "eligibility_hash": "a" * 64} for c in cases},
    }
    legacy_revision = "d18862d9a48706220815554fac3ebb4dfa46fc28"
    from uranus_research_service.version import EMBEDDING_VERSION, MODEL_REVISION

    old = {
        **copy.deepcopy(base),
        "model": "jinaai/jina-embeddings-v3",
        "revision": legacy_revision,
        "embedding_version": legacy_revision
        + ":native-transformers5.17.0-retrieval-normalized-f32:sections-480-overlap64-v2",
    }
    new = {
        **copy.deepcopy(base),
        "model": "jina-v5",
        "revision": MODEL_REVISION,
        "embedding_version": EMBEDDING_VERSION,
    }
    return cases, old, new


def test_comparison_gates_and_provenance():
    cases, v3, v5 = reports()
    assert compare(cases, v3, v5)["passed"]
    v5["runs"]["da"]["ranked_ids"] = []
    result = compare(cases, v3, v5)
    assert not result["passed"] and result["catastrophic_regressions"] == ["da"]
    v5["runs"]["da"]["eligibility_hash"] = "different"
    with pytest.raises(ValueError, match="eligibility"):
        compare(cases, v3, v5)
    cases, v3, v5 = reports()
    v5["documents"][0]["document_hash"] = "changed"
    with pytest.raises(ValueError, match="documents"):
        compare(cases, v3, v5)
