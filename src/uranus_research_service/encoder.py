"""Pinned encoder metadata consumer. Model weights never enter this process."""

from uranus_research_service.clients import InternalClient
from uranus_research_service.errors import DependencyError
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
        ):
            raise DependencyError("encoder", "incompatible")

    async def ready(self):
        self.compatible(await self.get("/version"))
        health = await self.get("/ready")
        self.compatible(health, readiness=True)
        if health.get("status") != "ready":
            raise DependencyError("encoder", "unavailable")
