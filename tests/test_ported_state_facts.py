"""Pure state/facts regressions ported from Admin test_research_v13, same assertions."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from uranus_research_service.errors import APIError
from uranus_research_service.research.answer_facts import (
    AnswerFacts,
    render_conversation,
    render_facts,
)
from uranus_research_service.research.conversation_state import ConversationStore
from uranus_research_service.research.wire.research_v13_schema import ConversationV13
from uranus_research_service.schemas.research_conversation_v12 import ResearchPlanSummaryV12

CONTEXT = json.loads(Path("tests/fixtures/modern_v12_context.json").read_text())


def test_memory_is_bounded_expires_and_is_session_bound():
    now = [0]
    store = ConversationStore(ttl=30, capacity=2, per_session=1, clock=lambda: now[0])
    with store.turn("session-a", None) as (token, state, expired):
        assert not expired
        state.language = "da"
        with pytest.raises(APIError):
            with store.turn("session-a", token):
                pass
    with store.turn("session-b", token) as (other, new, expired):
        assert expired and other != token and new.language == "de"
    with store.turn("session-a", token) as (_, old, expired):
        assert not expired and old.language == "da"
    now[0] = 31
    with store.turn("session-a", token) as (replacement, _, expired):
        assert expired and replacement != token
    assert len(store.entries) == 1
    summary = ResearchPlanSummaryV12.model_validate(CONTEXT["previous_turns"][0])
    for _ in range(9):
        state.remember(summary)
    assert len(state.summaries) == 4
    state.remember(None)
    assert state.context() is None


@pytest.mark.parametrize(
    "language,noun", [("de", "Termine"), ("da", "forekomster"), ("en", "occurrences")]
)
def test_answers_are_grounded_localized_and_bounded(language, noun):
    facts = AnswerFacts(kind="count", metric="occurrence_count", value=7, shown=0)
    text = render_facts(facts, language)
    assert "7" in text and noun in text
    explanation = render_conversation(
        ConversationV13(act="explain_previous", reason=None), language, facts=facts
    )
    assert text in explanation and len(explanation) <= 1000
    with pytest.raises(ValidationError):
        AnswerFacts.model_validate({**facts.model_dump(), "sql": "private"})


def test_fact_projection_discards_keys_and_preserves_displayed_scope():
    from uranus_research_service.research.answer_facts import project_answer_facts
    from uranus_research_service.research.plan import InternalResearchPlan
    from uranus_research_service.schemas.research_execution import (
        ExecutionProvenance,
        GroupedResult,
    )

    result = GroupedResult.model_validate(
        {
            "kind": "grouped",
            "metric": "occurrence_count",
            "dimensions": ["month"],
            "ordering": "desc",
            "limit": 20,
            "items": [
                {
                    "coordinates": [{"dimension": "month", "key": "PRIVATE-ID", "name": "09"}],
                    "value": 7,
                }
            ],
        }
    )
    facts = project_answer_facts(
        InternalResearchPlan(
            intent="aggregate", entity_type="event", metric="occurrence_count", groupings=("month",)
        ),
        result,
        ExecutionProvenance(),
    )
    assert "PRIVATE-ID" not in facts.model_dump_json()
    assert "September" in render_facts(facts, "de")
    assert "angezeigten Daten" in render_facts(facts, "de")
    assert "displayed data" in render_facts(facts, "en")


def test_ties_and_semantic_matches_are_not_global_or_unique_claims():
    from uranus_research_service.research.answer_facts import AnswerCell

    facts = AnswerFacts(
        kind="grouped",
        metric="occurrence_count",
        shown=2,
        ordering="desc",
        cells=[
            AnswerCell(labels=["A"], dimensions=["event_type"], value=7),
            AnswerCell(labels=["B"], dimensions=["event_type"], value=7),
        ],
    )
    text = render_facts(facts, "de")
    assert "2 Gruppen" in text and "höchste angezeigte Wert" in text
    assert "„A“" not in text
    facts = AnswerFacts(kind="records", shown=1, semantic=True)
    assert "keine vollständige Zählung" in render_facts(facts, "de")
    assert "not a complete count" in render_facts(facts, "en")
    assert "ikke en fuldstændig optælling" in render_facts(facts, "da")
