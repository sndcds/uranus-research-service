"""Human-maintained judgments and blinded candidate pools; never model verdicts."""

import csv
import io
import math
import re
import unicodedata
from collections import Counter
from datetime import date, datetime
from difflib import SequenceMatcher
from typing import Literal
from uuid import UUID

from pydantic import Field, StrictBool, StrictInt, model_validator

from uranus_research_service.ground_truth_snapshot import Closed
from uranus_research_service.semantic_manifest import digest

Category = Literal[
    "accessibility",
    "atmosphere",
    "music",
    "theatre",
    "exhibition",
    "family",
    "venue",
    "location",
    "genre",
    "cultural_style",
    "combined",
    "paraphrase",
    "ambiguous",
    "multiple_results",
    "no_hit",
    "workshops",
    "readings",
    "outdoor",
]
CORE_CATEGORIES = {
    "accessibility",
    "atmosphere",
    "music",
    "theatre",
    "exhibition",
    "family",
    "venue",
    "location",
    "genre",
    "cultural_style",
    "combined",
    "paraphrase",
    "ambiguous",
    "multiple_results",
    "no_hit",
}
Hash = str


def normalized_query(text):
    return " ".join(re.findall(r"\w+", unicodedata.normalize("NFKC", text).casefold()))


class Eligibility(Closed):
    contract: Literal["public-snapshot-eligibility-v1"] = "public-snapshot-eligibility-v1"
    date_from: date | None = None
    date_to: date | None = None
    city: str | None = Field(default=None, min_length=1, max_length=2000)
    venue_id: UUID | None = None
    weekdays: list[StrictInt] = Field(default_factory=list, max_length=7)

    @model_validator(mode="after")
    def valid(self):
        if self.city is not None and not normalized_query(self.city):
            raise ValueError("empty_city")
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise ValueError("invalid_date_range")
        if len(set(self.weekdays)) != len(self.weekdays) or any(
            x not in range(1, 8) for x in self.weekdays
        ):
            raise ValueError("invalid_weekdays")
        return self

    def accepts(self, event):
        if not any((self.date_from, self.date_to, self.city, self.venue_id, self.weekdays)):
            return True
        # All hard predicates must hold on ONE occurrence, never unrelated dates/venues.
        return any(
            (self.date_from is None or d.start_date >= self.date_from)
            and (self.date_to is None or d.start_date <= self.date_to)
            and (self.city is None or normalized_query(d.city) == normalized_query(self.city))
            and (self.venue_id is None or d.venue_id == self.venue_id)
            and (not self.weekdays or d.start_date.isoweekday() in self.weekdays)
            for d in event.occurrences
        )


class QueryProposal(Closed):
    id: str = Field(pattern=r"^[a-z0-9_-]{1,100}$")
    query: str = Field(min_length=3, max_length=1000)
    language: Literal["de", "da", "en"]
    category: Category
    query_group: str = Field(pattern=r"^[a-z0-9_-]{1,100}$")
    eligibility: Eligibility = Field(default_factory=Eligibility)
    notes: str = Field(default="", max_length=2000)
    purpose: Literal["calibration", "evaluation"] | None = None


class Judgment(Closed):
    event_id: UUID
    document_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    relevance: StrictInt | None = Field(default=None, ge=0, le=3)
    reason: str = Field(default="", max_length=2000)
    supporting_fields: list[
        Literal[
            "title",
            "subtitle",
            "summary",
            "description",
            "event_types",
            "venue_accessibility",
            "space_accessibility",
            "accessibility_info",
            "venue",
            "city",
            "occurrences",
            "price_type",
        ]
    ] = Field(default_factory=list)
    reviewer_a: str | None = Field(default=None, min_length=1, max_length=100)
    relevance_a: StrictInt | None = Field(default=None, ge=0, le=3)
    reviewer_b: str | None = Field(default=None, min_length=1, max_length=100)
    relevance_b: StrictInt | None = Field(default=None, ge=0, le=3)
    adjudicated_relevance: StrictInt | None = Field(default=None, ge=0, le=3)

    @model_validator(mode="after")
    def valid(self):
        for reviewer, score in (
            (self.reviewer_a, self.relevance_a),
            (self.reviewer_b, self.relevance_b),
        ):
            if (reviewer is None) != (score is None):
                raise ValueError("reviewer_score_pair_required")
        if self.reviewer_b is not None and self.reviewer_a == self.reviewer_b:
            raise ValueError("independent_reviewers_required")
        if self.relevance is not None:
            if not self.reason.strip() or self.reviewer_a is None:
                raise ValueError("human_judgment_reason_required")
            if self.relevance_b is not None and self.relevance_a != self.relevance_b:
                if self.adjudicated_relevance is None:
                    raise ValueError("adjudication_required")
            final = (
                self.adjudicated_relevance
                if self.adjudicated_relevance is not None
                else self.relevance_a
            )
            if self.relevance != final:
                raise ValueError("judgment_disagrees_with_review")
            if self.relevance > 0 and not self.supporting_fields:
                raise ValueError("positive_evidence_required")
        return self


class GroundTruthCase(QueryProposal):
    schema_version: Literal["retrieval-ground-truth-v1"] = "retrieval-ground-truth-v1"
    source_snapshot_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    reference_time: datetime
    judgments: list[Judgment] = Field(max_length=10000)
    expected_no_hit: StrictBool | None = None
    no_hit_review_scope: Literal["full_eligible_corpus"] | None = None
    review_status: Literal["generated", "reviewed", "approved"] = "generated"
    approved_by: str | None = Field(default=None, min_length=1, max_length=100)
    approved_at: datetime | None = None

    @model_validator(mode="after")
    def valid_case(self):
        if self.reference_time.tzinfo is None:
            raise ValueError("aware_reference_required")
        ids = [j.event_id for j in self.judgments]
        if len(set(ids)) != len(ids):
            raise ValueError("duplicate_event_judgment")
        positive = any(j.relevance is not None and j.relevance > 0 for j in self.judgments)
        if self.expected_no_hit is False and not positive:
            raise ValueError("positive_judgment_required")
        if self.expected_no_hit is True and positive:
            raise ValueError("no_hit_inconsistent")
        if self.review_status in {"reviewed", "approved"}:
            if not self.judgments or any(j.relevance is None for j in self.judgments):
                raise ValueError("complete_human_judgments_required")
            if self.expected_no_hit is None or self.expected_no_hit == positive:
                raise ValueError("relevance_expectation_inconsistent")
        if self.review_status == "approved":
            if not self.approved_by or not self.approved_at or self.approved_at.tzinfo is None:
                raise ValueError("human_approval_required")
            if self.expected_no_hit and self.no_hit_review_scope != "full_eligible_corpus":
                raise ValueError("no_hit_requires_corpus_review")
        elif self.approved_by is not None or self.approved_at is not None:
            raise ValueError("approval_status_mismatch")
        return self


def validate_cases(cases, manifest, rows):
    if not 1 <= len(cases) <= 1000 or len({c.id for c in cases}) != len(cases):
        raise ValueError("duplicate_or_invalid_case_count")
    queries = set()
    for case in cases:
        key = normalized_query(case.query)
        if key in queries:
            raise ValueError("duplicate_query")
        queries.add(key)
        if (
            case.source_snapshot_hash != manifest.source_snapshot_hash
            or case.reference_time != manifest.reference_time
        ):
            raise ValueError("case_snapshot_mismatch")
        for j in case.judgments:
            if j.event_id not in rows or rows[j.event_id].document_hash != j.document_hash:
                raise ValueError("judgment_document_hash_mismatch")
            if not case.eligibility.accepts(rows[j.event_id].event):
                raise ValueError("judgment_outside_eligibility")
    return cases


def event_text(event):
    return "\n".join(
        [
            event.title,
            event.subtitle,
            event.summary,
            event.description,
            *(t.type_name + " " + t.genre_name for t in event.event_types),
            *(
                " ".join(
                    (
                        o.venue,
                        o.city,
                        o.space,
                        o.venue_accessibility,
                        o.space_accessibility,
                        o.accessibility_info,
                    )
                )
                for o in event.occurrences
            ),
        ]
    )


def prepare_pool(proposals, manifest, rows, historical=None, manual=None, *, size=20):
    if not 10 <= size <= 30:
        raise ValueError("pool_size_10_to_30")
    historical, manual = historical or {}, manual or {}
    tokens = {i: Counter(normalized_query(event_text(r.event)).split()) for i, r in rows.items()}
    frequencies = Counter(t for terms in tokens.values() for t in terms)
    cases, audit = [], []
    for q in proposals:
        eligible = {i for i, r in rows.items() if q.eligibility.accepts(r.event)}
        terms = set(normalized_query(q.query).split())
        scores = {
            i: sum(
                (1 + math.log(tokens[i][t])) * math.log(1 + len(rows) / (1 + frequencies[t]))
                for t in terms
                if tokens[i][t]
            )
            for i in eligible
        }
        lexical = sorted(eligible, key=lambda i: (-scores[i], str(i)))
        diverse = sorted(eligible, key=lambda i: digest([q.id, str(i), "diversity"]))
        # Historical rankings/scores are discarded before pooling and ordering.
        old = sorted(
            {UUID(str(i)) for i in historical.get(q.id, []) if UUID(str(i)) in eligible}, key=str
        )
        seeds = sorted({UUID(str(i)) for i in manual.get(q.id, [])}, key=str)
        if not set(seeds) <= eligible or len(seeds) > size:
            raise ValueError("invalid_manual_candidates")
        historical_overlap = len(old)
        pool = list(seeds)
        sources = [lexical, old, diverse]
        while len(pool) < min(size, len(eligible)):
            progress = False
            for source in sources:
                while source and source[0] in pool:
                    source.pop(0)
                if source and len(pool) < size:
                    pool.append(source.pop(0))
                    progress = True
            if not progress:
                break
        pool.sort(
            key=lambda i: digest([manifest.source_snapshot_hash, q.id, str(i), "blind-order-v1"])
        )
        cases.append(
            GroundTruthCase(
                **q.model_dump(),
                source_snapshot_hash=manifest.source_snapshot_hash,
                reference_time=manifest.reference_time,
                judgments=[Judgment(event_id=i, document_hash=rows[i].document_hash) for i in pool],
            )
        )
        audit.append(
            {
                "case_id": q.id,
                "eligible_count": len(eligible),
                "historical_overlap": historical_overlap,
                "manual_count": len(seeds),
                "pool_count": len(pool),
            }
        )
    return validate_cases(cases, manifest, rows), audit


def coverage(cases):
    approved = [c for c in cases if c.review_status == "approved"]

    def stats(values):
        judged = [j for c in values for j in c.judgments if j.relevance is not None]
        positive = [j for j in judged if j.relevance > 0]
        counts = Counter(str(j.event_id) for j in positive)
        top_three = {identity for identity, _ in counts.most_common(3)}
        concentrated = sum(
            any(
                j.relevance is not None and j.relevance > 0 and str(j.event_id) in top_three
                for j in c.judgments
            )
            for c in values
        ) / max(1, len(values))
        return {
            "total_queries": len(values),
            "queries_per_language": dict(Counter(c.language for c in values)),
            "queries_per_category": dict(Counter(c.category for c in values)),
            "no_hit_count": sum(c.expected_no_hit is True for c in values),
            "multi_relevant_count": sum(
                sum(j.relevance is not None and j.relevance > 0 for j in c.judgments) > 1
                for c in values
            ),
            "mean_judged_candidates_per_query": len(judged) / max(1, len(values)),
            "relevance_distribution": dict(
                sorted(Counter(str(j.relevance) for j in judged).items())
            ),
            "unique_relevant_events": len(counts),
            "unique_events_judged": len({j.event_id for j in judged}),
            "top_three_event_query_incidence": concentrated,
        }

    a = stats(approved)
    gates = {
        "all_cases_approved": bool(cases) and len(approved) == len(cases),
        "languages": all(
            a["queries_per_language"].get(lang, 0) >= 5 for lang in ("de", "da", "en")
        ),
        "core_categories": CORE_CATEGORIES <= set(a["queries_per_category"]),
        "no_hit": a["no_hit_count"] >= 3,
        "multi_hit": a["multi_relevant_count"] >= 5,
        "diverse_events": a["unique_relevant_events"] >= 30,
        "concentration": bool(approved) and a["top_three_event_query_incidence"] <= 0.5,
        "query_count": len(approved) >= 50,
    }
    similar = []
    for i, c in enumerate(cases):
        for other in cases[:i]:
            if (
                c.language == other.language
                and SequenceMatcher(
                    None, normalized_query(c.query), normalized_query(other.query)
                ).ratio()
                >= 0.85
            ):
                similar.append(
                    {
                        "case_a": other.id,
                        "case_b": c.id,
                        "grouped": other.query_group == c.query_group,
                    }
                )
    gates["paraphrase_review"] = all(p["grouped"] for p in similar)
    return {
        "schema_version": "ground-truth-coverage-v1",
        "dataset_status": "approved" if all(gates.values()) else "draft",
        "total_queries": len(cases),
        "pool_candidate_count": sum(len(c.judgments) for c in cases),
        "unique_pool_events": len({j.event_id for c in cases for j in c.judgments}),
        "queries_with_pool_below_10": sum(len(c.judgments) < 10 for c in cases),
        "approved_queries": len(approved),
        "all_cases": stats(cases),
        "approved": a,
        "coverage_gates": gates,
        "similar_query_pairs": similar,
        "query_groups": {
            g: [c.id for c in cases if c.query_group == g]
            for g in sorted({c.query_group for c in cases})
        },
    }


def safe_csv(value):
    value = str(value)
    return "'" + value if value.lstrip().startswith(("=", "+", "-", "@", "\t", "\r")) else value


def annotation_csv(cases, rows):
    out = io.StringIO(newline="")
    fields = [
        "case_id",
        "query",
        "language",
        "category",
        "query_group",
        "eligibility",
        "event_id",
        "document_hash",
        "event_title",
        "event_summary_excerpt",
        "venue",
        "date_context",
        "relevance",
        "reason",
        "supporting_fields",
        "reviewer_a",
        "relevance_a",
        "reviewer_b",
        "relevance_b",
        "adjudicated_relevance",
        "review_status",
    ]
    writer = csv.DictWriter(out, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for c in cases:
        for j in c.judgments:
            e = rows[j.event_id].event
            values = {
                **c.model_dump(mode="json"),
                **j.model_dump(mode="json"),
                "case_id": c.id,
                "eligibility": str(c.eligibility.model_dump(mode="json", exclude_none=True)),
                "event_title": e.title,
                "event_summary_excerpt": (e.summary or e.description)[:1200],
                "venue": "; ".join(sorted({o.venue + " / " + o.space for o in e.occurrences})),
                "date_context": "; ".join(
                    o.start_date.isoformat() + " " + o.start_time + " " + o.city + " " + o.venue
                    for o in e.occurrences
                ),
                "supporting_fields": ";".join(j.supporting_fields),
            }
            writer.writerow(
                {k: safe_csv(values.get(k) if values.get(k) is not None else "") for k in fields}
            )
    return out.getvalue()


def import_annotations(cases, rows, csv_text):
    """Import human edits only. Never approve or advance case status automatically."""
    expected = list(csv.DictReader(io.StringIO(annotation_csv(cases, rows))))
    actual = list(csv.DictReader(io.StringIO(csv_text)))

    def key(r):
        return r["case_id"], r["event_id"]

    if len(actual) != len(expected) or len({key(r) for r in actual}) != len(actual):
        raise ValueError("annotation_rows_mismatch")
    by_key = {key(r): r for r in actual}
    editable = {
        "relevance",
        "reason",
        "supporting_fields",
        "reviewer_a",
        "relevance_a",
        "reviewer_b",
        "relevance_b",
        "adjudicated_relevance",
    }
    judgments = {}
    for before in expected:
        after = by_key.get(key(before))
        if (
            after is None
            or set(after) != set(before)
            or any(after[k] != before[k] for k in before if k not in editable)
        ):
            raise ValueError("annotation_evidence_changed")
        values = {k: after[k] for k in editable}
        for name in ("relevance", "relevance_a", "relevance_b", "adjudicated_relevance"):
            if values[name] not in ("", "0", "1", "2", "3"):
                raise ValueError("invalid_annotation_grade")
            values[name] = int(values[name]) if values[name] else None
        for name in ("reviewer_a", "reviewer_b"):
            values[name] = values[name] or None
        values["supporting_fields"] = [s for s in values["supporting_fields"].split(";") if s]
        judgments[key(before)] = Judgment(
            event_id=before["event_id"], document_hash=before["document_hash"], **values
        )
    output = []
    for case in cases:
        if case.review_status != "generated":
            raise ValueError("import_requires_generated_draft")
        value = case.model_dump(mode="json")
        value["judgments"] = [
            judgments[(case.id, str(j.event_id))].model_dump(mode="json") for j in case.judgments
        ]
        output.append(GroundTruthCase.model_validate(value))
    return output


def evidence_markdown(rows):
    """Complete blinded public evidence; the CSV excerpt alone is insufficient for review."""
    out = [
        "# Frozen public evidence\n\nUse the event UUID and document hash to locate evidence. "
        "Missing information is unknown.\n"
    ]
    for identity, row in sorted(rows.items(), key=lambda item: str(item[0])):
        e = row.event
        out.append(f"\n## {identity}\n\nDocument SHA256: {row.document_hash}\n\n")
        # Fenced JSON keeps source prose from injecting Markdown links or headings.
        data = e.model_dump(mode="json")
        import json

        value = json.dumps(data, ensure_ascii=False, indent=2)
        fence = "`" * (max([len(m[0]) for m in re.finditer(r"`+", value)] + [2]) + 1)
        out.append(f"{fence}json\n{value}\n{fence}\n")
    return "".join(out)


def coverage_markdown(report, manifest):
    a = report["approved"]
    all_cases = report["all_cases"]
    lines = [
        "# Retrieval ground truth v1 — " + report["dataset_status"],
        "",
        "Generated from validated artifacts. Counts are not model-quality metrics.",
        "",
        f"Snapshot: `{manifest.snapshot_id}`; {manifest.public_event_count} public events.",
        f"Source SHA256: `{manifest.source_snapshot_hash}`.",
        f"Reference time: `{manifest.reference_time.isoformat()}`.",
        f"Timezone: `{manifest.timezone}`.",
        "",
        f"Queries: {report['total_queries']}; approved: {report['approved_queries']}.",
        f"Pool entries: {report['pool_candidate_count']}.",
        f"Distinct pooled events: {report['unique_pool_events']}.",
        f"Pools below ten candidates: {report['queries_with_pool_below_10']}.",
        "Hard eligibility is never relaxed to fill a pool.",
        "",
        "| Language | Proposed | Approved |",
        "| --- | ---: | ---: |",
    ]
    for lang in ("de", "da", "en"):
        n = all_cases["queries_per_language"].get(lang, 0)
        approved = a["queries_per_language"].get(lang, 0)
        lines.append(f"| {lang} | {n} | {approved} |")
    lines.extend(["", "| Category | Proposed | Approved |", "| --- | ---: | ---: |"])
    for cat, n in sorted(all_cases["queries_per_category"].items()):
        lines.append(f"| {cat} | {n} | {a['queries_per_category'].get(cat, 0)} |")
    lines.extend(
        [
            "",
            "## Human judgments",
            "",
            f"Confirmed no-hit: {a['no_hit_count']}; multi-relevant: {a['multi_relevant_count']}.",
            f"Unique relevant events: {a['unique_relevant_events']}.",
            f"Unique judged events: {a['unique_events_judged']}.",
            f"Mean judged candidates/query: {a['mean_judged_candidates_per_query']}.",
            f"Relevance distribution: `{a['relevance_distribution']}`.",
            "",
            "## Coverage gates",
            "",
        ]
    )
    lines.extend(
        "- " + k + ": " + ("pass" if v else "not met")
        for k, v in sorted(report["coverage_gates"].items())
    )
    lines.extend(
        [
            "",
            "No-hit/multiple-results categories are proposals, not confirmed outcomes.",
            "Unjudged is unknown, never relevance 0. Official evaluation requires human approval",
            "and passing coverage gates.",
            "See [annotation guidelines](retrieval-annotation-guidelines.md)",
            "and [workflow](phase2b2b-ground-truth.md).",
            "",
        ]
    )
    return "\n".join(lines)
