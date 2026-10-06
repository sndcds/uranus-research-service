"""Human-only annotation import, disagreement and approval gates for Phase 2D.

This validates declared provenance, not a person's identity. No automatic judgments.
"""

from collections import Counter
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, StrictInt, model_validator

from uranus_research_service.controlled_evaluation import require
from uranus_research_service.ground_truth_snapshot import Closed
from uranus_research_service.semantic_manifest import digest

Grade = StrictInt | None
FIELDS = {
    "title",
    "subtitle",
    "summary",
    "description",
    "event_types",
    "tags",
    "languages",
    "price_type",
    "occurrences",
    "venue",
    "city",
    "space",
    "venue_accessibility",
    "space_accessibility",
    "accessibility_info",
}
OCCURRENCE_FIELDS = {
    "venue",
    "city",
    "space",
    "venue_accessibility",
    "space_accessibility",
    "accessibility_info",
}


class Answer(Closed):
    annotation_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    state: Literal["pending", "graded", "uncertain", "needs_more_context"]
    grade: Grade = Field(default=None, ge=0, le=3)
    reason: str = Field(default="", max_length=4000)
    supporting_fields: list[str] = Field(default_factory=list, max_length=30)
    occurrence_ids: list[UUID] = Field(default_factory=list, max_length=1000)

    @model_validator(mode="after")
    def consistent(self):
        require((self.state == "graded") == (self.grade is not None), "state_grade_mismatch")
        if self.state != "pending":
            require(self.reason.strip(), "reason_required")
        require(set(self.supporting_fields) <= FIELDS, "supporting_field_unknown")
        require(len(set(self.supporting_fields)) == len(self.supporting_fields), "duplicate_field")
        require(len(set(self.occurrence_ids)) == len(self.occurrence_ids), "duplicate_occurrence")
        if self.grade is not None and self.grade > 0:
            require(self.supporting_fields, "positive_evidence_required")
        return self


class ReviewBatch(Closed):
    schema_version: Literal["phase2d-human-annotations-v1"]
    package_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    annotator: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,80}$")
    provenance: Literal["human-independent"]
    answers: list[Answer] = Field(max_length=10000)


class Adjudication(Closed):
    schema_version: Literal["phase2d-human-adjudication-v1"]
    package_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    review_inputs_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    adjudicator: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,80}$")
    provenance: Literal["human-adjudication"]
    answers: list[Answer] = Field(max_length=10000)


class Approval(Closed):
    schema_version: Literal["phase2d-human-approval-v1"]
    draft_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    approved_at: datetime
    approval_reference: str = Field(min_length=5, max_length=1000)
    authorized_by: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,80}$")
    authorization: Literal["explicit-human-approval"]
    rubric_decisions: dict[str, str]

    @model_validator(mode="after")
    def aware(self):
        require(self.approved_at.tzinfo is not None, "approval_time_timezone")
        require(self.approval_reference.strip(), "approval_reference")
        return self


def validate_answers(answers, bundle, packet):
    mapping = {r["annotation_id"]: r for r in bundle["mapping"]}
    evidence = {r["annotation_id"]: r for r in packet}
    ids = [a.annotation_id for a in answers]
    require(len(ids) == len(set(ids)), "duplicate_answer")
    require(set(ids) <= mapping.keys(), "unknown_annotation")
    for a in answers:
        p = evidence[a.annotation_id]
        ids = {str(x) for x in a.occurrence_ids}
        require(ids <= set(p["eligible_occurrence_ids"]), "occurrence_not_eligible")
        occurrences = [o for o in p["event"]["occurrences"] if o["id"] in ids]
        for field in a.supporting_fields:
            if field in OCCURRENCE_FIELDS:
                require(any(o[field] for o in occurrences), "missing_occurrence_evidence")
            elif field == "occurrences":
                require(occurrences, "occurrence_evidence_required")
            else:
                require(p["event"][field], "empty_evidence_field")
        if a.grade is not None and a.grade > 0 and mapping[a.annotation_id]["occurrence_sensitive"]:
            require(ids, "occurrence_sensitive_positive")
    return {a.annotation_id: a for a in answers}


def validate_batch(raw, bundle, packet):
    batch = ReviewBatch.model_validate(raw)
    require(batch.package_sha256 == digest(bundle), "annotation_package_mismatch")
    validate_answers(batch.answers, bundle, packet)
    return batch


def import_batch(raw, bundle, packet):
    batch = validate_batch(raw, bundle, packet)
    mapping = {r["annotation_id"]: r for r in bundle["mapping"]}
    return {
        "status": "draft",
        "package_sha256": digest(bundle),
        "annotator": batch.annotator,
        "provenance": batch.provenance,
        "answers": [
            {**a.model_dump(mode="json"), **mapping[a.annotation_id]} for a in batch.answers
        ],
    }


def review_inputs_hash(a, b):
    return digest([a.model_dump(mode="json"), b.model_dump(mode="json")])


def agreement(a, b, bundle, packet):
    require(a.annotator != b.annotator, "independent_annotators_required")
    require(a.package_sha256 == b.package_sha256 == digest(bundle), "annotation_package_mismatch")
    aa, bb = (validate_answers(x.answers, bundle, packet) for x in (a, b))
    matrix = [[0 for _ in range(4)] for _ in range(4)]
    counts = Counter()
    for pair in bundle["mapping"]:
        x, y = aa.get(pair["annotation_id"]), bb.get(pair["annotation_id"])
        if x is None or y is None:
            counts["missing_pair"] += 1
        elif x.state != "graded" or y.state != "graded":
            counts["unresolved_pair"] += 1
        else:
            matrix[x.grade][y.grade] += 1
    n = sum(map(sum, matrix))
    observed = sum(matrix[i][i] for i in range(4)) / n if n else None
    rows, cols = [sum(r) for r in matrix], [sum(r[i] for r in matrix) for i in range(4)]
    expected = sum(rows[i] * cols[i] for i in range(4)) / n**2 if n else None
    weighted_loss = sum(matrix[i][j] * ((i - j) / 3) ** 2 for i in range(4) for j in range(4))
    expected_loss = sum(rows[i] * cols[j] * ((i - j) / 3) ** 2 for i in range(4) for j in range(4))
    return {
        "status": "draft",
        "graded_pairs": n,
        **counts,
        "confusion_matrix_0_3": matrix,
        "raw_agreement": observed,
        "quadratic_weighted_agreement": 1 - weighted_loss / n if n else None,
        "cohen_kappa": (observed - expected) / (1 - expected) if n and expected < 1 else None,
        "quadratic_weighted_kappa": 1 - weighted_loss * n / expected_loss
        if expected_loss
        else None,
        "disagreements": n - sum(matrix[i][i] for i in range(4)),
        "limitation": "Declared independent humans; identity cannot be authenticated by this tool. "
        "Missing/uncertain excluded, never zero. "
        "Class imbalance can make kappa misleading/undefined.",
    }


def conflicts(a, b, bundle, packet, old):
    require(a.annotator != b.annotator, "independent_annotators_required")
    require(a.package_sha256 == b.package_sha256 == digest(bundle), "annotation_package_mismatch")
    aa, bb = (validate_answers(x.answers, bundle, packet) for x in (a, b))
    result = []
    for pair in bundle["mapping"]:
        key = pair["annotation_id"]
        x, y = aa.get(key), bb.get(key)
        prior = old[pair["case_id"]].get(pair["event_id"])
        reason = None
        if x is None or y is None or x.state != "graded" or y.state != "graded":
            reason = "missing_or_unresolved_independent_review"
        elif x.grade != y.grade:
            reason = "human_disagreement"
        elif prior is not None and x.grade != prior:
            reason = "existing_draft_judgment_conflict"
        if reason:
            result.append(
                {
                    **pair,
                    "old_grade": prior,
                    "grade_a": x.grade if x else None,
                    "grade_b": y.grade if y else None,
                    "reason_a": x.reason if x else None,
                    "reason_b": y.reason if y else None,
                    "reason": reason,
                    "adjudication_required": True,
                    "provenance": {
                        "old": "frozen-draft-machine-proposal",
                        "a": a.annotator,
                        "b": b.annotator,
                    },
                }
            )
    return result


def prepare_freeze(a, b, adjudication, bundle, packet, old):
    """Produces a draft only. Complete independent judgments are mandatory."""
    disputed = conflicts(a, b, bundle, packet, old)
    require(
        not any(r["reason"] == "missing_or_unresolved_independent_review" for r in disputed),
        "incomplete_human_reviews",
    )
    ad = Adjudication.model_validate(adjudication)
    require(ad.package_sha256 == digest(bundle), "adjudication_package_mismatch")
    require(ad.review_inputs_sha256 == review_inputs_hash(a, b), "adjudication_inputs_changed")
    resolved = validate_answers(ad.answers, bundle, packet)
    require(set(resolved) == {r["annotation_id"] for r in disputed}, "open_or_unknown_adjudication")
    require(all(r.state == "graded" for r in resolved.values()), "unresolved_adjudication")
    answers = {r.annotation_id: r for r in a.answers}
    values = []
    for pair in bundle["mapping"]:
        key = pair["annotation_id"]
        answer = resolved.get(key, answers[key])
        prior = old[pair["case_id"]].get(pair["event_id"])
        values.append(
            {
                **pair,
                **answer.model_dump(mode="json"),
                "previous_grade": prior,
                "provenance": "human-adjudicated" if key in resolved else "two-independent-humans",
            }
        )
    return {
        "schema_version": "phase2d-judgments-v2",
        "status": "draft",
        "package_sha256": digest(bundle),
        "input_manifest_sha256": bundle["input_manifest_sha256"],
        "review_inputs_sha256": review_inputs_hash(a, b),
        "annotators": [a.annotator, b.annotator],
        "adjudicator": ad.adjudicator,
        "adjudication_sha256": digest(ad.model_dump(mode="json")),
        "adjudication_status": "complete",
        "open_conflict_count": 0,
        "conflicts": [
            {
                **r,
                "resolution_status": "resolved",
                "adjudicated_grade": resolved[r["annotation_id"]].grade,
                "resolution_reason": resolved[r["annotation_id"]].reason,
            }
            for r in disputed
        ],
        "judgments": values,
        "rubric_questions": bundle["rubric_questions"],
    }


def freeze(draft, approval):
    """Called only with externally supplied explicit human authorization, never by export."""
    approval = Approval.model_validate(approval)
    require(draft["status"] == "draft", "already_frozen")
    require(
        draft.get("adjudication_status") == "complete"
        and draft.get("open_conflict_count") == 0
        and all(r.get("resolution_status") == "resolved" for r in draft["conflicts"]),
        "open_conflicts",
    )
    require(approval.draft_sha256 == digest(draft), "approval_draft_mismatch")
    for question in draft["rubric_questions"]:
        # Changing the historical scoring interpretation requires a separately versioned
        # protocol, not an arbitrary approval string that silently changes the rubric.
        require(
            approval.rubric_decisions.get(question) == "confirm-existing-single-event-rubric",
            "rubric_clarification_required",
        )
    return {**draft, "status": "frozen", "approval": approval.model_dump(mode="json")}
