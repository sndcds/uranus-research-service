"""Pinned synthetic plans, not live-planner or retrieval quality results."""

import json
from pathlib import Path

GOLDENS = json.loads(Path("tests/fixtures/structured_goldens.json").read_text())
SOCIAL = [
    c
    for c in json.loads(Path("tests/fixtures/conversation_v13.json").read_text())
    if "conversation" in c["plan"]["interaction"]
]


def envelope(plan):
    return dict(
        schema_version="research-query-plan-v13",
        prompt_version="research-planner-v19",
        model="fixture",
        plan=plan,
        reference_date="2026-10-04",
        timezone="Europe/Berlin",
        diagnostics=dict(
            request_id="a" * 32,
            interaction_kind=plan["interaction"]["kind"],
            validation_stage="validated",
            planner_model="fixture",
            planner_prompt_version="research-planner-v19",
            planner_ms=1,
            total_ms=1,
        ),
    )
