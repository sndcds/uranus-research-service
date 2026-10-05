"""Versioned v5 manifest; a reserved point is excluded from retrieval and corpus counts."""

import hashlib
import json
import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from uranus_research_service.research.semantic_contracts import COLLECTIONS, OWNER
from uranus_research_service.version import (
    CHUNK_VERSION,
    DIMENSIONS,
    EMBEDDING_VERSION,
    MODEL,
    MODEL_REVISION,
)

MANIFEST_ID = "00000000-0000-0000-0000-000000000001"
MANIFEST_OWNER = "uranus-research-service-manifest-v1"


def digest(value):
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
        ).encode()
    ).hexdigest()


def collection_name(entity, build_id=None):
    if entity not in COLLECTIONS:
        raise ValueError("unsupported_collection_role")
    if build_id is None:
        return COLLECTIONS[entity].name
    if not isinstance(build_id, str) or not re.fullmatch(r"[a-z0-9][a-z0-9_]{0,47}", build_id):
        raise ValueError("invalid_build_id")
    return COLLECTIONS[entity].name.removesuffix("v1") + "build_" + build_id


class Manifest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    manifest_owner: Literal["uranus-research-service-manifest-v1"]
    index_owner: Literal["kulturbytes-semantic-search-v1"]
    entity_type: Literal["event", "venue", "organization"]
    document_schema_version: str
    embedding_model: Literal["jina-v5"]
    embedding_version: Literal[EMBEDDING_VERSION]
    model_revision: Literal[MODEL_REVISION]
    dimensions: Literal[1024]
    distance: Literal["Cosine"]
    chunk_version: Literal[CHUNK_VERSION]
    build_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_]{0,47}$")
    created_at: str
    source_snapshot_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    corpus_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    document_count: int = Field(ge=0, le=10000)
    chunk_count: int = Field(ge=0, le=100000)
    complete: Literal[True]

    @classmethod
    def create(cls, **values):
        """Only the local builder supplies pins; untrusted manifests have required fields."""
        return cls(
            manifest_owner=MANIFEST_OWNER,
            index_owner=OWNER,
            embedding_model=MODEL,
            embedding_version=EMBEDDING_VERSION,
            model_revision=MODEL_REVISION,
            dimensions=DIMENSIONS,
            distance="Cosine",
            chunk_version=CHUNK_VERSION,
            complete=True,
            **values,
        )

    @model_validator(mode="before")
    @classmethod
    def exact_types(cls, value):
        if isinstance(value, dict) and (
            type(value.get("dimensions")) is not int or type(value.get("complete")) is not bool
        ):
            raise ValueError("manifest_pin_types")
        return value

    @model_validator(mode="after")
    def valid(self):
        if self.document_schema_version != COLLECTIONS[self.entity_type].document_version:
            raise ValueError("manifest_document_schema")
        if datetime.fromisoformat(self.created_at).tzinfo is None:
            raise ValueError("manifest_timestamp")
        return self

    def verify(self, *, entity, build_id, points):
        if self.entity_type != entity or self.build_id != build_id:
            raise ValueError("manifest_collection_identity")
        if self.chunk_count != len(points) or self.document_count != len(
            {p["entity_id"] for p in points.values()}
        ):
            raise ValueError("manifest_counts")
        if self.corpus_hash != digest(points):
            raise ValueError("manifest_corpus_hash")
