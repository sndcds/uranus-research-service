import asyncio
import hashlib
import json
import os
from pathlib import Path

import pytest

from tests.integration.test_semantic_index import NOW
from uranus_research_service.database import ResearchDatabase
from uranus_research_service.repositories.semantic_source import SemanticSource

pytestmark = [pytest.mark.integration, pytest.mark.parity]


async def test_admin_public_document_differential(db_settings, postgres):
    admin = os.environ.get("ADMIN_PARITY_ROOT")
    if not admin:
        pytest.skip("ADMIN_PARITY_ROOT required")
    root = Path(admin)
    provenance = json.loads(
        await asyncio.to_thread(Path("docs/phase2b1-port-manifest.json").read_text)
    )
    p = await asyncio.create_subprocess_exec(
        "git", "rev-parse", "HEAD", cwd=root, stdout=asyncio.subprocess.PIPE
    )
    out, _ = await p.communicate()
    assert out.decode().strip() == provenance["admin_commit"]
    for module in provenance["modules"].values():
        assert (
            hashlib.sha256((root / "backend/app" / module["source"]).read_bytes()).hexdigest()
            == module["sha256"]
        )
    db, areas = ResearchDatabase(db_settings), ResearchDatabase(db_settings, "area")
    try:
        docs, total = await SemanticSource(db, areas, db_settings).snapshot(now=NOW)
    finally:
        await db.close()
        await areas.close()
    p = await asyncio.create_subprocess_exec(
        str(root / "backend/.venv/bin/python"),
        str(await asyncio.to_thread(Path("scripts/semantic_parity_bridge.py").resolve)),
        cwd=root / "backend",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    async with asyncio.timeout(60):
        out, _ = await p.communicate(
            json.dumps(
                {
                    "admin": admin,
                    "source": postgres["source"],
                    "area": postgres["area"],
                    "now": NOW.isoformat(),
                }
            ).encode()
        )
    assert p.returncode == 0, "Pinned Admin semantic extractor failed"
    assert json.loads(out) == {
        "total": total,
        "documents": [d.model_dump(mode="json") for d in docs],
    }
