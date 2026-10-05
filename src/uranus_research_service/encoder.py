"""Pinned encoder metadata consumer. Model weights never enter this process."""

import math

from pydantic import ValidationError

from uranus_research_service.clients import InternalClient
from uranus_research_service.encoder_contracts import (
    ChunkRequest,
    ChunkResponse,
    EmbedRequest,
    EmbedResponse,
)
from uranus_research_service.errors import DependencyError
from uranus_research_service.research.vector_documents import Chunk, content_hash
from uranus_research_service.version import ENCODER_EXPECTED


class EncoderClient(InternalClient):
    def __init__(self, settings, *, transport=None):
        super().__init__(settings, "encoder", transport=transport)

    def compatible(self, metadata, *, readiness=False):
        expected = {
            k: v
            for k, v in ENCODER_EXPECTED.items()
            if not readiness or k not in {"model_repository", "chunk_version"}
        }
        if (
            any(
                type(metadata.get(k)) is not type(v) or metadata.get(k) != v
                for k, v in expected.items()
            )
            or metadata.get("backend") != "torch"
            or (not readiness and metadata.get("service_version") != "0.2.0")
        ):
            raise DependencyError("encoder", "incompatible")

    async def ready(self):
        self.compatible(await self.get("/version"))
        health = await self.get("/ready")
        self.compatible(health, readiness=True)
        if health.get("status") != "ready":
            raise DependencyError("encoder", "unavailable")

    async def embed(self, texts, *, kind):
        request = EmbedRequest(model="jina-v5", texts=texts, kind=kind)
        await self.ready()
        raw = await self._request(
            "POST", "/embed", request.model_dump(mode="json"), response_limit=16 * 1024 * 1024
        )
        try:
            vectors = raw["vectors"]
            validate_vectors(vectors, len(texts))
            result = EmbedResponse.model_validate(raw)
            if result.embedding_version != ENCODER_EXPECTED["embedding_version"]:
                raise ValueError
            return result.vectors
        except (ValueError, KeyError, TypeError, ValidationError):
            raise DependencyError("encoder", "invalid_response") from None

    async def prepare(self, documents):
        result = {}
        await self.ready()
        for document in documents:
            request = ChunkRequest.model_validate(
                {
                    "model": "jina-v5",
                    "documents": [
                        {
                            "entity_id": str(document.entity_id),
                            "sections": [s.model_dump(mode="json") for s in document.sections],
                        }
                    ],
                }
            )
            raw = await self._request(
                "POST", "/chunks", request.model_dump(mode="json"), response_limit=16 * 1024 * 1024
            )
            try:
                response = ChunkResponse.model_validate(raw)
                if (
                    response.embedding_version != ENCODER_EXPECTED["embedding_version"]
                    or len(response.documents) != 1
                    or response.documents[0].entity_id != document.entity_id
                ):
                    raise ValueError
                chunks = []
                for i, chunk in enumerate(response.documents[0].chunks):
                    if (
                        type(raw["documents"][0]["chunks"][i]["chunk_index"]) is not int
                        or type(raw["documents"][0]["chunks"][i]["token_count"]) is not int
                        or chunk.chunk_index != i
                        or chunk.content_hash != content_hash(chunk.text)
                    ):
                        raise ValueError
                    value = Chunk.model_validate(chunk.model_dump(mode="json"))
                    expected = {
                        s.context
                        for s in document.sections
                        if s.kind == value.chunk_kind and value.text in s.text
                    }
                    if document.entity_type == "event" and (
                        not value.contexts
                        or None in expected
                        or not set(value.contexts).issubset(expected)
                    ):
                        raise ValueError
                    if value.text not in "\n\n".join(s.text for s in document.sections):
                        raise ValueError
                    chunks.append(value)
                if str(document.entity_id) in result:
                    raise ValueError
                result[str(document.entity_id)] = chunks
            except (ValueError, KeyError, TypeError, ValidationError):
                raise DependencyError("encoder", "invalid_response") from None
        return result


def validate_vectors(vectors, count):
    if not isinstance(vectors, list) or len(vectors) != count:
        raise ValueError("invalid_vectors")
    for vector in vectors:
        if (
            not isinstance(vector, list)
            or len(vector) != 1024
            or any(
                type(v) not in (int, float) or not math.isfinite(v) or abs(v) > 1.00001
                for v in vector
            )
        ):
            raise ValueError("invalid_vector")
        norm = math.sqrt(math.fsum(v * v for v in vector))
        if not math.isfinite(norm) or abs(norm - 1) > 1e-5:
            raise ValueError("invalid_vector_norm")
