"""Process-local trust established only by full validation of immutable generations."""

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
from time import monotonic

from uranus_research_service.semantic_manifest import digest

VALIDATION_TTL_SECONDS = 600


@dataclass(frozen=True)
class VerifiedSemanticGeneration:
    entity_type: str
    collection_name: str
    build_id: str
    manifest_digest: str
    corpus_hash: str
    source_snapshot_hash: str
    embedding_model: str
    embedding_version: str
    model_revision: str
    dimensions: int
    distance: str
    chunk_version: str
    document_schema_version: str
    index_owner: str
    point_count: int
    validated_at: datetime


class SemanticGenerationVerifier:
    def __init__(self, client, *, clock=monotonic):
        self.client = client
        self.clock = clock
        self.generation = None
        self._expires_at = 0.0
        self._lock = asyncio.Lock()
        self.full_validation_count = 0
        self.manifest_check_count = 0
        self.generation_invalidation_count = 0

    @property
    def is_verified(self):
        return self.generation is not None and self.clock() < self._expires_at

    def invalidate(self):
        if self.generation is not None:
            self.generation_invalidation_count += 1
        self.generation = None
        self._expires_at = 0.0

    async def _check(self, verified):
        self.manifest_check_count += 1
        if (
            verified.collection_name != self.client.collection
            or verified.entity_type != self.client.entity
            or verified.build_id != self.client.build_id
        ):
            raise ValueError("generation_identity_mismatch")
        info = await self.client.info()
        if info is None:
            raise ValueError("missing_collection")
        manifest = await self.client.get_manifest()
        if (
            digest(manifest.model_dump(mode="json")) != verified.manifest_digest
            or type(info.get("points_count")) is not int
            or info["points_count"] != verified.point_count
        ):
            raise ValueError("generation_changed")

    async def verify_generation_current(self):
        """Request boundary: never call full validation, even on expiry or mismatch."""
        async with self._lock:
            try:
                if not self.is_verified:
                    raise ValueError("generation_verification_required")
                await self._check(self.generation)
                # A slow check must not extend the full-validation lifetime.
                if not self.is_verified:
                    raise ValueError("generation_verification_expired")
                return self.generation
            except BaseException:
                self.invalidate()
                raise

    async def _full(self):
        self.invalidate()
        self.full_validation_count += 1
        try:
            manifest = await self.client._validate_full()
            values = manifest.model_dump(mode="json")
            verified = VerifiedSemanticGeneration(
                **{
                    k: values[k]
                    for k in (
                        "entity_type",
                        "build_id",
                        "corpus_hash",
                        "source_snapshot_hash",
                        "embedding_model",
                        "embedding_version",
                        "model_revision",
                        "dimensions",
                        "distance",
                        "chunk_version",
                        "document_schema_version",
                        "index_owner",
                    )
                },
                collection_name=self.client.collection,
                manifest_digest=digest(values),
                point_count=manifest.chunk_count + 1,
                validated_at=datetime.now(UTC),
            )
            # Detect identity/count changes during the full scan before publishing trust.
            await self._check(verified)
            self.generation = verified
            self._expires_at = self.clock() + VALIDATION_TTL_SECONDS
            return manifest
        except BaseException:
            self.invalidate()
            raise

    async def validate(self):
        """Explicit operator/build validation always performs the full scan."""
        async with self._lock:
            return await self._full()

    async def ready(self):
        """Concurrent readiness calls share one full validation, then cheap checks."""
        async with self._lock:
            if not self.is_verified:
                await self._full()
            else:
                try:
                    await self._check(self.generation)
                    if not self.is_verified:
                        raise ValueError("generation_verification_expired")
                except BaseException:
                    self.invalidate()
                    raise
            return self.generation
