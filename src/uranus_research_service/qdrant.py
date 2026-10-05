"""Fixed-role Qdrant transport. Maintenance exists only on an isolated operator client."""

import json
import math
from urllib.parse import urlsplit
from uuid import UUID, uuid5

from pydantic import TypeAdapter

from uranus_research_service.clients import InternalClient
from uranus_research_service.encoder import validate_vectors
from uranus_research_service.errors import DependencyError
from uranus_research_service.research.semantic_contracts import COLLECTIONS, OWNER, Payload
from uranus_research_service.research.vector_documents import POINT_NAMESPACE, Chunk, content_hash
from uranus_research_service.semantic_generation import SemanticGenerationVerifier
from uranus_research_service.semantic_manifest import MANIFEST_ID, Manifest, collection_name
from uranus_research_service.version import EMBEDDING_VERSION, MODEL


class QdrantClient(InternalClient):
    def __init__(self, settings, *, entity="event", build_id=None, transport=None):
        super().__init__(settings, "qdrant", transport=transport)
        self.entity, self.build_id = entity, build_id
        self.collection = collection_name(entity, build_id)
        self.path = "/collections/" + self.collection
        self.max_bytes = 16 * 1024 * 1024
        self.generation_verifier = SemanticGenerationVerifier(self)

    async def call(self, method, suffix, body=None, *, missing_ok=False):
        result = await self._request(method, self.path + suffix, body, missing_ok=missing_ok)
        if result is None and missing_ok:
            return None
        if not isinstance(result, dict) or result.get("status") != "ok" or "result" not in result:
            raise DependencyError("qdrant", "invalid_response")
        return result["result"]

    async def aliases(self):
        raw = await self._request("GET", "/aliases")
        if raw.get("status") != "ok" or not isinstance(raw.get("result", {}).get("aliases"), list):
            raise DependencyError("qdrant", "invalid_response")
        return raw["result"]["aliases"]

    async def info(self):
        value = await self.call("GET", "", missing_ok=True)
        if value is None:
            return None
        try:
            vector = value["config"]["params"]["vectors"]
            if (
                type(vector["size"]) is not int
                or vector["size"] != 1024
                or vector["distance"] != "Cosine"
            ):
                raise ValueError
        except (KeyError, TypeError, ValueError):
            raise DependencyError("qdrant", "incompatible") from None
        return value

    async def points(self):
        points, offset, seen = {}, None, set()
        total_bytes = 0
        while True:
            response = await self.call(
                "POST",
                "/points/scroll",
                {
                    "limit": 64,
                    "with_payload": True,
                    "with_vector": False,
                    **({"offset": offset} if offset is not None else {}),
                },
            )
            if not isinstance(response, dict) or not isinstance(response.get("points"), list):
                raise DependencyError("qdrant", "invalid_response")
            for point in response["points"]:
                identity = str(point["id"])
                UUID(identity)
                if identity in points or len(points) >= 100001:
                    raise ValueError("invalid_collection_points")
                total_bytes += len(json.dumps(point["payload"], ensure_ascii=False).encode())
                if total_bytes > 128 * 1024 * 1024:
                    raise ValueError("collection_payload_limit")
                points[identity] = point["payload"]
            offset = response.get("next_page_offset")
            if offset is None:
                return points
            if str(offset) in seen:
                raise ValueError("invalid_scroll")
            seen.add(str(offset))

    def validate_payload(self, payload):
        if (
            not isinstance(payload, dict)
            or payload.get("index_owner") != OWNER
            or payload.get("entity_type") != self.entity
            or payload.get("embedding_model") != MODEL
            or payload.get("embedding_version") != EMBEDDING_VERSION
            or payload.get("document_schema_version") != COLLECTIONS[self.entity].document_version
            or type(payload.get("chunk_index")) is not int
            or not isinstance(payload.get("chunk_text"), str)
            or content_hash(payload["chunk_text"]) != payload.get("content_hash")
        ):
            raise ValueError("foreign_or_invalid_point")
        metadata = {
            "embedding_model",
            "embedding_version",
            "chunk_index",
            "chunk_kind",
            "chunk_text",
            "content_hash",
            "evidence_contexts",
        }
        TypeAdapter(Payload).validate_python(
            {k: v for k, v in payload.items() if k not in metadata}
        )
        Chunk.model_validate(
            {
                "chunk_index": payload["chunk_index"],
                "chunk_kind": payload["chunk_kind"],
                "text": payload["chunk_text"],
                "content_hash": payload["content_hash"],
                "contexts": payload.get("evidence_contexts", []),
                "token_count": 1,
            }
        )
        if self.entity == "event" and not payload.get("evidence_contexts"):
            raise ValueError("missing_evidence_context")

    def validate_point(self, identity, payload):
        self.validate_payload(payload)
        expected = str(
            uuid5(
                POINT_NAMESPACE,
                f"{self.entity}:{payload['entity_id']}:{payload['chunk_kind']}:{payload['content_hash']}",
            )
        )
        if identity != expected:
            raise ValueError("point_identity_mismatch")

    async def get_manifest(self):
        result = await self.call(
            "POST",
            "/points",
            {"ids": [MANIFEST_ID], "with_payload": True, "with_vector": False},
        )
        if not isinstance(result, list) or len(result) != 1:
            raise ValueError("missing_or_invalid_manifest")
        point = result[0]
        if not isinstance(point, dict) or point.get("id") != MANIFEST_ID:
            raise ValueError("manifest_point_identity")
        manifest = Manifest.model_validate(point.get("payload"))
        if manifest.entity_type != self.entity or manifest.build_id != self.build_id:
            raise ValueError("manifest_collection_identity")
        return manifest

    async def validate(self):
        return await self.generation_verifier.validate()

    async def _validate_full(self):
        info = await self.info()
        if info is None:
            raise ValueError("missing_collection")
        points = await self.points()
        raw = points.pop(MANIFEST_ID, None)
        if raw is None:
            raise ValueError("missing_manifest")
        manifest = Manifest.model_validate(raw)
        for identity, payload in points.items():
            self.validate_point(identity, payload)
        manifest.verify(entity=self.entity, build_id=self.build_id, points=points)
        if info.get("points_count") != len(points) + 1:
            raise ValueError("collection_count_mismatch")
        return manifest

    async def search(self, vector, *, entity_ids, limit=50):
        if not entity_ids:
            return []
        if not 1 <= len(entity_ids) <= 10000 or not 1 <= limit <= 50:
            raise ValueError("invalid_search_limit")
        ids = sorted({str(UUID(str(i))) for i in entity_ids})
        validate_vectors([vector], 1)
        await self.generation_verifier.verify_generation_current()
        result = await self.call(
            "POST",
            "/points/query",
            {
                "query": vector,
                "limit": limit,
                "with_payload": True,
                "with_vector": False,
                "filter": {
                    "must": [
                        {"key": "entity_id", "match": {"any": ids}},
                        {"key": "entity_type", "match": {"value": self.entity}},
                        {"key": "index_owner", "match": {"value": OWNER}},
                        {"key": "embedding_version", "match": {"value": EMBEDDING_VERSION}},
                    ],
                    "must_not": [{"has_id": [MANIFEST_ID]}],
                },
            },
        )
        if (
            not isinstance(result, dict)
            or not isinstance(result.get("points"), list)
            or len(result["points"]) > limit
        ):
            self.generation_verifier.invalidate()
            raise DependencyError("qdrant", "invalid_response")
        try:
            seen = set()
            for point in result["points"]:
                identity = point["id"]
                UUID(identity)
                self.validate_point(identity, point["payload"])
                if identity in seen or point["payload"]["entity_id"] not in ids:
                    raise ValueError("invalid_hit_identity")
                seen.add(identity)
                score = point["score"]
                if type(score) not in (int, float) or not math.isfinite(score):
                    raise ValueError("invalid_hit_score")
        except (ValueError, KeyError, TypeError, AttributeError):
            self.generation_verifier.invalidate()
            raise ValueError("invalid_search_hit") from None
        return result["points"]


class QdrantMaintenance(QdrantClient):
    def __init__(self, settings, *, build_id, isolated=False, test_recovery=False, **kwargs):
        parts = urlsplit(settings.qdrant_url)
        # No live override in Phase 2B.1. Also reject the usual local production port.
        if (
            not isolated
            or parts.hostname not in {"127.0.0.1", "::1"}
            or parts.port in {None, 6333}
            or not build_id.startswith("test_")
        ):
            raise ValueError("isolated_build_target_required")
        super().__init__(settings, build_id=build_id, **kwargs)
        self.test_recovery = test_recovery

    async def inactive(self):
        if any(a.get("collection_name") == self.collection for a in await self.aliases()):
            raise ValueError("active_collection_write_forbidden")

    async def writable(self):
        await self.inactive()
        if not self.test_recovery and await self.info() is not None:
            # Even a malformed completion marker is not a license to overwrite it.
            points = await self.call(
                "POST",
                "/points",
                {"ids": [MANIFEST_ID], "with_payload": True, "with_vector": False},
            )
            if not isinstance(points, list) or points:
                raise ValueError("sealed_generation_write_forbidden")
        self.generation_verifier.invalidate()

    async def create(self):
        await self.writable()
        if await self.info() is not None:
            raise ValueError("collection_already_exists")
        await self.call("PUT", "", {"vectors": {"size": 1024, "distance": "Cosine"}})

    async def upsert(self, points):
        await self.writable()
        if not 1 <= len(points) <= 2:
            raise ValueError("write_batch_limit")
        for point in points:
            UUID(point["id"])
            if point["id"] == MANIFEST_ID:
                raise ValueError("reserved_point")
            self.validate_point(point["id"], point["payload"])
        validate_vectors([p["vector"] for p in points], len(points))
        await self.call("PUT", "/points?wait=true", {"points": points})

    async def payload(self, identity, payload):
        await self.writable()
        if str(UUID(identity)) == MANIFEST_ID:
            raise ValueError("reserved_point")
        self.validate_point(identity, payload)
        await self.call(
            "PUT", "/points/payload?wait=true", {"points": [identity], "payload": payload}
        )

    async def delete(self, identities):
        await self.writable()
        for offset in range(0, len(identities), 64):
            batch = [str(UUID(i)) for i in identities[offset : offset + 64]]
            await self.call("POST", "/points/delete?wait=true", {"points": batch})

    async def write_manifest(self, manifest):
        await self.writable()
        points = await self.points()
        points.pop(MANIFEST_ID, None)
        manifest.verify(entity=self.entity, build_id=self.build_id, points=points)
        await self.call(
            "PUT",
            "/points?wait=true",
            {
                "points": [
                    {
                        "id": MANIFEST_ID,
                        "vector": [1.0] + [0.0] * 1023,
                        "payload": manifest.model_dump(mode="json"),
                    }
                ]
            },
        )

    def alias_switch(self, *args, **kwargs):
        raise ValueError("alias_switch_disabled_phase2b1")
