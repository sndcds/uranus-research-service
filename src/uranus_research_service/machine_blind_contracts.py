"""Closed blind-only inputs/outputs; no mapping, historical labels or ranking reads."""

import hashlib
import re
from pathlib import Path
from typing import Literal
from uuid import UUID

from pydantic import Field, StrictBool, StrictInt, model_validator

from uranus_research_service.blind_review import FIELDS, OCCURRENCE_FIELDS, Answer
from uranus_research_service.ground_truth import Eligibility
from uranus_research_service.ground_truth_snapshot import Closed, PublicEvent
from uranus_research_service.json_codec import decode
from uranus_research_service.semantic_manifest import digest

PACKET_SHA = "068bd7b58e0a1aa7749d93223df7cfadc9dd35d4a72116138c7fd714703f03bb"
META_SHA = "b7e22e115b0892446128062426deca538f2ce807b47d998a214ae555173cdd02"
PROMPT = Path("benchmark/review/lost-all-v1/machine/prompt-v1.txt")
PARAMETERS = {
    "temperature": 0,
    "seed": None,
    "reasoning_effort": "none",
    "max_output_tokens": 1200,
    "response_format": "responses.text.format:strict-json-schema",
    "store": False,
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read(path):
    return decode(Path(path).read_bytes())


class Candidate(Closed):
    annotation_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    query: str
    language: Literal["de", "da", "en"]
    reference_time: str
    eligibility: Eligibility
    event: dict
    eligible_occurrence_ids: list[UUID]
    rubric: str
    scale: dict[str, str]
    query_id: str
    event_id: UUID
    category: str
    intent_checks: list[str]

    @model_validator(mode="after")
    def evidence(self):
        require("id" not in self.event, "event_identity")
        event = PublicEvent.model_validate({"id": self.event_id, **self.event})
        require(
            set(self.eligible_occurrence_ids) <= {o.id for o in event.occurrences},
            "foreign_occurrence",
        )
        require(set(self.scale) == {"0", "1", "2", "3"}, "scale")
        return self


class MachineAnswer(Answer):
    state: Literal["graded", "uncertain", "needs_more_context"]
    grade: StrictInt | None = Field(ge=0, le=3)
    uncertain: StrictBool
    reason: str = Field(min_length=1, max_length=1200)
    supporting_fields: list[str] = Field(max_length=30)
    occurrence_ids: list[UUID] = Field(max_length=1000)

    @model_validator(mode="after")
    def machine(self):
        require(self.uncertain == (self.state != "graded"), "uncertainty_state")
        require(
            not re.search(
                r"\b(v[35]|rankings?|scores?|gates?|human.approved|human.reviewed|ground.truth)\b",
                self.reason,
                re.I,
            ),
            "non_evidence_reason",
        )
        return self


def schema():
    value = MachineAnswer.model_json_schema()
    value["properties"]["supporting_fields"]["items"] = {"type": "string", "enum": sorted(FIELDS)}
    require(set(value["required"]) == set(value["properties"]), "schema_required")
    return value


def load_packet(package):
    """The only evidence files read by the judging process. No operator package loader."""
    base = Path(package) / "reviewer"
    data = (base / "blind-candidates.jsonl").read_bytes()
    meta_bytes = (base / "annotation-package.json").read_bytes()
    require(sha(data) == PACKET_SHA and sha(meta_bytes) == META_SHA, "frozen_blind_input_changed")
    rows = [decode(line) for line in data.splitlines()]
    meta = decode(meta_bytes)
    require(
        len(rows) == len({r["annotation_id"] for r in rows}) == meta["count"] == 77, "packet_ids"
    )
    require(digest(rows) == meta["packet_sha256"], "packet_digest")
    for r in rows:
        Candidate.model_validate(r)
    return rows, meta


def validate_answer(raw, candidate):
    answer = MachineAnswer.model_validate(raw)
    require(answer.annotation_id == candidate["annotation_id"], "unknown_id")
    ids = {str(i) for i in answer.occurrence_ids}
    require(ids <= set(candidate["eligible_occurrence_ids"]), "foreign_occurrence")
    if answer.grade is not None and answer.grade > 0:
        require(ids, "positive_occurrence_required")
        occurrences = [o for o in candidate["event"]["occurrences"] if o["id"] in ids]
        for field in answer.supporting_fields:
            if field in OCCURRENCE_FIELDS:
                require(any(o[field] for o in occurrences), "empty_occurrence_field")
            elif field == "occurrences":
                require(occurrences, "occurrence_required")
            else:
                require(candidate["event"][field], "empty_supporting_field")
    return answer.model_dump(mode="json")


def payload(candidate, model, prompt):
    c = Candidate.model_validate(candidate).model_dump(mode="json")
    # Explicit allowlist: omit query/event IDs, category, all operator metadata.
    content = {
        "annotation_id": c["annotation_id"],
        "query": c["query"],
        "language": c["language"],
        "rubric": {
            "query_specific": c["rubric"],
            "scale": c["scale"],
            "intent_checks": c["intent_checks"],
        },
        "eligibility": {
            "requirements": c["eligibility"],
            "reference_time": c["reference_time"],
            "eligible_occurrence_ids": c["eligible_occurrence_ids"],
        },
        "evidence": c["event"],
    }
    from uranus_research_service.ground_truth_snapshot import canonical_bytes

    return {
        "model": model,
        "store": False,
        "instructions": prompt,
        "input": [{"role": "user", "content": canonical_bytes(content).decode()}],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "blind_machine_answer",
                "strict": True,
                "schema": schema(),
            }
        },
        "temperature": 0,
        "reasoning": {"effort": "none"},
        "max_output_tokens": 1200,
    }
