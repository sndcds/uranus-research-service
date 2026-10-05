"""Internal event retrieval only. The public query coordinator does not import this path."""

from time import perf_counter

from pydantic import BaseModel, ConfigDict, Field

from uranus_research_service.research.semantic_evidence import (
    contextualize_event_hit,
    semantic_hits,
)
from uranus_research_service.research.semantic_explanations import explain
from uranus_research_service.research.semantic_limits import semantic_relevance_threshold
from uranus_research_service.research.vector_models import V5
from uranus_research_service.schemas.research import SemanticResearchRecord
from uranus_research_service.schemas.research_execution import (
    ExecutionSemanticFilters,
)


class RetrievalResult(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    items: list[SemanticResearchRecord] = Field(default_factory=list, max_length=50)
    candidate_count: int = 0
    returned_count: int = 0
    best_score: float | None = None
    latency: float = 0
    embedding_latency: float = 0
    qdrant_latency: float = 0
    rehydration_latency: float = 0
    eligibility_hash: str = ""


async def retrieve(
    source, encoder, qdrant, filters: ExecutionSemanticFilters, *, area=None, now=None
):
    from uranus_research_service.semantic_manifest import digest

    if not isinstance(filters, ExecutionSemanticFilters) or qdrant.entity != "event":
        raise ValueError("validated_event_filters_required")
    started = perf_counter()
    # Preserve all resolved hard constraints, including excluded internal place metadata.
    hard = filters.model_copy(update={"q": ""})
    allowed = await source.eligible(hard, area)
    result = RetrievalResult(eligibility_hash=digest(sorted(map(str, allowed))))
    if not allowed:
        result.latency = perf_counter() - started
        return result
    before = perf_counter()
    vector = (await encoder.embed([filters.q], kind="query"))[0]
    result.embedding_latency = perf_counter() - before
    before = perf_counter()
    raw = await qdrant.search(vector, entity_ids=allowed, limit=50)
    result.qdrant_latency = perf_counter() - before
    hits = semantic_hits(raw, set(allowed), V5, entity="event", limit=50)
    result.candidate_count = len(hits)
    if hits:
        before = perf_counter()
        page, documents = await source.rehydrate(
            filters, [h.entity_id for h in hits], now=now, area=area
        )
        by_id = {h.entity_id: h for h in hits}
        for item in page.items:
            if item.entity_key not in by_id or item.entity_key not in documents:
                raise ValueError("rehydration_identity_mismatch")
            hit, document = by_id[item.entity_key], documents[item.entity_key]
            # Payload hashes alone prove self-consistency, not freshness. Match current
            # public sections AND their exact contexts from the rehydration snapshot.
            chunks = [
                c
                for c in hit.candidate_chunks
                if all(
                    any(
                        s.kind == c.chunk_kind and c.chunk_text in s.text and s.context == context
                        for s in document.sections
                    )
                    for context in c.contexts
                )
            ]
            hit = hit.model_copy(
                update={"candidate_chunks": chunks, "display_name": document.display_name}
            )
            hit = contextualize_event_hit(
                hit,
                venue_id=item.venue_id,
                space_id=item.space_id,
                occurrence_id=page.occurrence_ids.get(item.entity_key),
            )
            if hit is not None:
                result.items.append(
                    SemanticResearchRecord(**item.model_dump(), semantic=explain(hit))
                )
        result.rehydration_latency = perf_counter() - before
    scores = [i.semantic.score for i in result.items]
    threshold = semantic_relevance_threshold(scores)
    result.best_score = max(scores, default=None)
    if threshold is not None:
        result.items = [i for i in result.items if i.semantic.score >= threshold]
    result.items.sort(key=lambda i: (-i.semantic.score, str(i.entity_key)))
    result.items = result.items[: filters.page_size]
    result.returned_count = len(result.items)
    result.latency = perf_counter() - started
    return result


async def retrieve_plan(response, resolver, source, encoder, qdrant, *, location_context=None):
    """Internal v13 entrypoint; never installed in the public query coordinator."""
    from uranus_research_service.research.context import ResearchExecutionContext
    from uranus_research_service.research.normalize_v12 import normalize_v12
    from uranus_research_service.research.wire.research_v13_schema import (
        PlanResponseV13,
        ResearchInteractionV13,
    )
    from uranus_research_service.services.research_plan_execution import execution_filters

    # Re-run the original closed validators even if a caller used model_construct.
    validated = PlanResponseV13.model_validate_json(response.model_dump_json())
    interaction = validated.plan.interaction
    if not isinstance(interaction, ResearchInteractionV13):
        raise ValueError("semantic_research_plan_required")
    wire = interaction.research_plan
    if wire.semantic is None or wire.clarification != "none":
        raise ValueError("resolved_semantic_plan_required")
    plan = normalize_v12(wire, allow_semantic=True)
    context = ResearchExecutionContext(
        reference_date=validated.reference_date,
        timezone=validated.timezone,
        original_query=validated.plan.original_query,
        location_context=location_context,
    )
    if context.timezone != source.settings.event_timezone:
        raise ValueError("semantic_timezone_mismatch")
    resolution = await resolver.resolve(plan, context)
    if resolution.clarification is not None:
        raise ValueError("semantic_resolution_required")
    hard = execution_filters(plan, context, resolution)
    filters = ExecutionSemanticFilters(
        place=hard.place,
        **{k: v for k, v in hard.model_dump().items() if k not in {"q", "sort"}},
        q="\n".join(dict.fromkeys(t for t in (plan.semantic.query, plan.semantic.focus) if t)),
    )
    return await retrieve(source, encoder, qdrant, filters, area=resolution.area)
