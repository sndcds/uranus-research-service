"""Differential execution against the untouched pinned Admin, same plans/data/clock."""

import asyncio
import json
import os
from copy import deepcopy
from pathlib import Path

import pytest

from tests.geography_fixtures import CATALOG, PLACES
from tests.integration.test_structured_queries import check_expected, run_cases
from tests.structured_fixtures import GOLDENS, envelope

pytestmark = [pytest.mark.integration, pytest.mark.parity]


def comparable(result):
    result = deepcopy(result)
    response = result["response"]
    # Nondeterministic transport/observation metadata only. No fact/result fields removed.
    response.pop("conversation_id", None)
    response.pop("observed_at", None)
    for key in ("planner_ms", "resolution_ms", "execution_ms", "total_ms"):
        response.get("diagnostics", {}).pop(key, None)
    return result


async def test_differential_admin_structured_execution(db_settings, postgres, tmp_path):
    admin = os.environ.get("ADMIN_PARITY_ROOT")
    if not admin:
        pytest.skip("ADMIN_PARITY_ROOT required for pinned cross-repository execution")
    root = await asyncio.to_thread(Path(admin).resolve)
    process = await asyncio.create_subprocess_exec(
        "git", "rev-parse", "HEAD", cwd=root, stdout=asyncio.subprocess.PIPE
    )
    stdout, _ = await process.communicate()
    assert (
        process.returncode == 0
        and stdout.decode().strip() == "340df4684611dbc4b8ec73a7702f1fad2ae1973c"
    )
    import hashlib

    for module in json.loads(
        await asyncio.to_thread(Path("docs/phase2-port-manifest.json").read_text)
    )["modules"]:
        assert (
            hashlib.sha256(
                await asyncio.to_thread((root / module["source"]).read_bytes)
            ).hexdigest()
            == module["source_sha256"]
        )
    catalog = tmp_path / "catalog.json"
    catalog.write_text(json.dumps(CATALOG))
    actual = await run_cases(db_settings, catalog)
    payload = dict(
        admin=str(root),
        source=postgres["source"],
        area=postgres["area"],
        catalog=str(catalog),
        places=PLACES,
        cases=[c | {"envelope": envelope(c["plan"])} for c in GOLDENS],
    )
    process = await asyncio.create_subprocess_exec(
        str(root / "backend/.venv/bin/python"),
        str(await asyncio.to_thread(Path("scripts/admin_parity_bridge.py").resolve)),
        cwd=root / "backend",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    async with asyncio.timeout(90):
        stdout, stderr = await process.communicate(json.dumps(payload).encode())
    if process.returncode:
        (tmp_path / "reference-error.txt").write_bytes(stderr)
        pytest.fail("Admin parity subprocess failed; inspect local reference-error.txt")
    reference = json.loads(stdout)
    assert len(actual) == len(reference) == len(GOLDENS)
    for case, left, right in zip(GOLDENS, actual, reference, strict=True):
        check_expected(case, right["response"])
        assert comparable(left) == comparable(right), case["id"]
