"""Synthetic HTTP encoder: no tokenizer, weights or quality claims."""

import json
from uuid import UUID

import httpx

from uranus_research_service.research.semantic_documents import event_document
from uranus_research_service.research.vector_documents import content_hash
from uranus_research_service.version import EMBEDDING_VERSION, ENCODER_EXPECTED

VECTOR = [1.0] + [0.0] * 1023


def document(i=30, title="Jazz im Haus"):
    return event_document(
        {
            "entity_id": UUID(int=i),
            "organization_id": UUID(int=10),
            "title": title,
            "status": "released",
        },
        {},
    )


def encoder_handler(request):
    assert "cookie" not in request.headers
    if request.url.path == "/version":
        return httpx.Response(
            200, json={**ENCODER_EXPECTED, "service_version": "0.2.0", "backend": "torch"}
        )
    if request.url.path == "/ready":
        return httpx.Response(
            200,
            json={
                **{
                    k: v
                    for k, v in ENCODER_EXPECTED.items()
                    if k not in {"model_repository", "chunk_version"}
                },
                "status": "ready",
                "backend": "torch",
            },
        )
    body = json.loads(request.content)
    assert body["model"] == "jina-v5"
    if request.url.path == "/embed":
        return httpx.Response(
            200,
            json={
                "embedding_version": EMBEDDING_VERSION,
                "vectors": [VECTOR for _ in body["texts"]],
                "metrics": {"text_count": len(body["texts"]), "token_count": 10},
            },
        )
    assert request.url.path == "/chunks"
    return httpx.Response(
        200,
        json={
            "embedding_version": EMBEDDING_VERSION,
            "documents": [
                {
                    "entity_id": d["entity_id"],
                    "chunks": [
                        {
                            "chunk_index": i,
                            "chunk_kind": s["kind"],
                            "text": s["text"],
                            "contexts": [s["context"]] if s["context"] else [],
                            "token_count": 20,
                            "content_hash": content_hash(s["text"]),
                        }
                        for i, s in enumerate(d["sections"])
                    ],
                }
                for d in body["documents"]
            ],
        },
    )
