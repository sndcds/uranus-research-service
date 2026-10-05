"""Generate only this service's schemas. Upstream snapshots require explicit source review."""

import asyncio
import json
from pathlib import Path

from uranus_research_service.app import create_app
from uranus_research_service.config import Settings
from uranus_research_service.contracts import (
    HealthResponse,
    QueryRequest,
    QueryResponse,
    ReadyResponse,
    VersionResponse,
)
from uranus_research_service.errors import ErrorResponse

ROOT = Path(__file__).resolve().parents[1]


def canonical(value):
    if isinstance(value, dict):
        return {k: sorted(v) if k == "enum" else canonical(v) for k, v in value.items()}
    if isinstance(value, list):
        return [canonical(v) for v in value]
    return value


class NoDependency:
    async def close(self):
        pass


async def generate():
    target = ROOT / "contracts/service"
    target.mkdir(exist_ok=True)
    for model in (
        HealthResponse,
        QueryRequest,
        QueryResponse,
        ReadyResponse,
        VersionResponse,
        ErrorResponse,
    ):
        (target / (model.__name__ + ".json")).write_text(
            json.dumps(canonical(model.model_json_schema()), indent=2, sort_keys=True) + "\n"
        )
    app = create_app(
        Settings(api_key="schema-generation-only-key-0123456789"),
        planner=NoDependency(),
        database=NoDependency(),
        areas=NoDependency(),
    )
    (target / "openapi.json").write_text(
        json.dumps(canonical(app.openapi()), indent=2, sort_keys=True) + "\n"
    )


if __name__ == "__main__":
    asyncio.run(generate())
