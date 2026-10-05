"""Single reviewed v5 space; legacy models are benchmark artifacts only."""

from dataclasses import dataclass

from uranus_research_service.version import DIMENSIONS, EMBEDDING_VERSION, MODEL, MODEL_REVISION


@dataclass(frozen=True)
class Model:
    name: str = MODEL
    revision: str = MODEL_REVISION
    dimensions: int = DIMENSIONS
    version: str = EMBEDDING_VERSION


V5 = Model()
