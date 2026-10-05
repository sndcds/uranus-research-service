"""Incremental embedding reuse and explicit reconciliation against a complete snapshot."""

import math
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from uranus_research_service.research.semantic_contracts import (
    COLLECTIONS,
    OWNER,
    EntityType,
    SemanticDocument,
    semantic_point_id,
)
from uranus_research_service.research.semantic_documents import is_public_text
from uranus_research_service.research.vector_documents import (
    Chunk,
    content_hash,
)
from uranus_research_service.research.vector_models import V5, Model

MAX_POINTS = 100_000

_COORDINATE_PATHS = frozenset(
    {
        ("latitude",),
        ("longitude",),
        ("effective_latitude",),
        ("effective_longitude",),
        ("effective_locations", "[]", "effective_latitude"),
        ("effective_locations", "[]", "effective_longitude"),
    }
)


def payloads_equal(desired: Any, stored: Any, path: tuple[str, ...] = ()) -> bool:
    """Compare every field, allowing only binary64 round-trip noise in coordinates."""
    if desired == stored:
        return True
    if isinstance(desired, dict) and isinstance(stored, dict):
        return desired.keys() == stored.keys() and all(
            payloads_equal(value, stored[key], (*path, key)) for key, value in desired.items()
        )
    if isinstance(desired, list) and isinstance(stored, list):
        return len(desired) == len(stored) and all(
            payloads_equal(left, right, (*path, "[]"))
            for left, right in zip(desired, stored, strict=True)
        )
    # Qdrant's JSON float parser can round decimal coordinates to a neighboring
    # binary64 value. One ULP covers the observed drift (under 3e-14 degrees
    # across valid coordinates), without rounding source values or payload writes.
    # No tolerance applies to hashes, versions, IDs, dates or other numeric fields.
    return (
        path in _COORDINATE_PATHS
        and isinstance(desired, float)
        and isinstance(stored, float)
        and math.isfinite(desired)
        and math.isfinite(stored)
        and abs(desired - stored) <= max(math.ulp(desired), math.ulp(stored))
    )


@dataclass
class Plan:
    desired: dict[str, tuple[Chunk, dict[str, Any]]]
    entity: EntityType | None = None
    embed: list[str] = field(default_factory=list)
    metadata: list[str] = field(default_factory=list)
    delete: list[str] = field(default_factory=list)
    new: int = 0
    unchanged: int = 0

    def counts(self) -> dict[str, int]:
        return {
            "chunks": len(self.desired),
            "new": self.new,
            "updated": len(self.embed) - self.new,
            "metadata_updated": len(self.metadata),
            "unchanged": self.unchanged,
            "deleted": len(self.delete),
        }


def plan_changes(
    documents: Sequence[SemanticDocument],
    chunks: dict[str, list[Chunk]],
    existing: dict[str, dict[str, Any]],
    model: Model,
    *,
    complete: bool,
    entity: EntityType | None = None,
) -> Plan:
    if entity not in COLLECTIONS:
        raise ValueError("semantic_collection_required")
    if entity is not None:
        if model != V5:
            raise ValueError("semantic_model_mismatch")
        if any(not isinstance(d, SemanticDocument) or d.entity_type != entity for d in documents):
            raise ValueError("collection_document_mismatch")
        if any(
            p.get("entity_type") != entity
            or p.get("index_owner") != OWNER
            or p.get("embedding_version") != model.version
            or p.get("embedding_model") != model.name
            or p.get("document_schema_version") != COLLECTIONS[entity].document_version
            for p in existing.values()
        ):
            raise ValueError("foreign_collection_points")
    if len({d.entity_id for d in documents}) != len(documents):
        raise ValueError("duplicate_document")
    desired: dict[str, tuple[Chunk, dict[str, Any]]] = {}
    for document in documents:
        for chunk in chunks[str(document.entity_id)]:
            if (
                not is_public_text(chunk.text)
                or chunk.content_hash != content_hash(chunk.text)
                or chunk.token_count > 480
                or chunk.text not in "\n\n".join(s.text for s in document.sections)
            ):
                raise ValueError("unsafe_or_unmatched_chunk")
            if document.entity_type == "event":
                expected_contexts = {
                    s.context
                    for s in document.sections
                    if s.kind == chunk.chunk_kind and chunk.text in s.text
                }
                if (
                    not chunk.contexts
                    or None in expected_contexts
                    or not set(chunk.contexts).issubset(expected_contexts)
                ):
                    raise ValueError("unsafe_or_unmatched_chunk_context")
            identifier = semantic_point_id(document, chunk)
            payload = document.payload.model_dump(mode="json")
            if identifier in desired:
                raise ValueError("duplicate_document_chunk")
            desired[identifier] = (
                chunk,
                {
                    **payload,
                    "chunk_text": chunk.text,
                    **(
                        {"evidence_contexts": [c.model_dump(mode="json") for c in chunk.contexts]}
                        if document.entity_type == "event"
                        else {}
                    ),
                    "chunk_index": chunk.chunk_index,
                    "chunk_kind": chunk.chunk_kind,
                    "content_hash": chunk.content_hash,
                    "embedding_model": model.name,
                    "embedding_version": model.version,
                },
            )
    if len(desired) > MAX_POINTS:
        raise ValueError("collection_point_limit")
    plan = Plan(desired, entity=entity)
    selected = {str(d.entity_id) for d in documents}
    for identifier, (_chunk, payload) in desired.items():
        old = existing.get(identifier)
        if old is None:
            plan.new += 1
            plan.embed.append(identifier)
        elif any(
            old.get(key) != payload.get(key)
            for key in (
                "content_hash",
                "embedding_model",
                "embedding_version",
                "document_schema_version",
            )
        ):
            plan.embed.append(identifier)
        elif not payloads_equal(payload, old):
            plan.metadata.append(identifier)
        else:
            plan.unchanged += 1
    plan.delete = sorted(
        identifier
        for identifier, old in existing.items()
        if identifier not in desired and (complete or old.get("entity_id") in selected)
    )
    return plan
