"""L2 stage runners: the film is understood before any scene is read closely.

``run_film_analysis`` runs P2a once and returns the FilmBrief. ``run_scene_analysis`` then runs
P2b per scene in chunks of ``config.pipeline.scene_chunk_size``: inside a chunk the scenes run
concurrently under a semaphore, each seeing a compact summary of its neighbours — the analysed
report card (``Scene.brief()``) when the neighbour was read in an earlier chunk, the L1 skeleton
otherwise — and every P2b call carries a provisional, prompt-cached Film Brief Header built from
the brief alone (the Style Bible does not exist yet; the frozen header replaces it at Gate 1).
After each call the flags the brief owns (load_bearing, sequence_id) are applied in code.
No shot is decided in this layer.
"""
from __future__ import annotations

import asyncio
from typing import Any

from ..agents.analyst import FilmAnalystAgent, SceneAnalystAgent, apply_film_flags
from ..agents.base import AgentContext, AgentResult
from ..schemas.common import BudgetTier, ReleaseTarget
from ..schemas.film_brief import FilmBrief
from ..schemas.scene import ParsedScript, Scene, SceneSkeleton
from .header import FilmBriefHeader, build_film_brief_header

FILM_KEY = "film"
SKELETON_SUMMARY_ACTION_LINES = 2


def neighbour_summary(item: SceneSkeleton | Scene | None) -> dict[str, Any] | None:
    """The compact view a scene analyst gets of a neighbouring scene.

    An already-analysed neighbour contributes its report-card brief (synopsis, turn, must_feel,
    pleasure, energy); an unread one contributes structure only — id, slug, characters and the
    first two action lines — so the analyst reads continuity, not a rival interpretation.
    """
    if item is None:
        return None
    if isinstance(item, Scene):
        return item.brief()
    return {
        "id": item.id,
        "slug": item.slug,
        "characters": list(item.characters),
        "action": list(item.action_lines[:SKELETON_SUMMARY_ACTION_LINES]),
    }


def provisional_header(ctx: AgentContext, film_brief: FilmBrief) -> FilmBriefHeader:
    """Cache a provisional Film Brief Header for L2 — built from the brief alone, unfrozen.

    A frozen header (Gate 1 has passed) is never replaced, so re-running scenes after approval
    directs them within the constitution; anything else is rebuilt from this brief.
    """
    if ctx.header is None or not ctx.header.frozen:
        ctx.header = build_film_brief_header(film_brief, None, max_tokens=ctx.config.pipeline.header_max_tokens, frozen=False)
    return ctx.header


async def run_film_analysis(
    ctx: AgentContext,
    parsed: ParsedScript,
    *,
    release_target: ReleaseTarget | str,
    mechanism_notes: str | None = None,
    cast_notes: str | None = None,
    budget_tier: BudgetTier | str | None = None,
) -> AgentResult[FilmBrief]:
    """P2a over the whole parsed script. NFE mechanism notes and confirmed cast are optional inputs;
    release target (interval block vs. cold open expectations) is not."""
    variables: dict[str, Any] = {"scenes": list(parsed.scenes), "release_target": ReleaseTarget(release_target).value}
    if mechanism_notes:
        variables["mechanism_notes"] = mechanism_notes
    if cast_notes:
        variables["cast_notes"] = cast_notes
    if budget_tier:
        variables["budget_tier"] = BudgetTier(budget_tier).value
    return await FilmAnalystAgent(ctx).run(key=FILM_KEY, **variables)


async def run_scene_analysis(
    ctx: AgentContext,
    parsed: ParsedScript,
    film_brief: FilmBrief,
    *,
    chunk_size: int | None = None,
    concurrency: int = 4,
) -> list[Scene]:
    """P2b per scene, chunked and bounded, returned in script order with the brief's flags applied."""
    size = ctx.config.pipeline.scene_chunk_size if chunk_size is None else chunk_size
    if size < 1 or concurrency < 1:
        raise ValueError("chunk_size and concurrency must be ≥ 1")
    provisional_header(ctx, film_brief)
    skeletons = list(parsed.scenes)
    threshold = ctx.config.pipeline.full_panel_temperature_threshold
    agent = SceneAnalystAgent(ctx)
    semaphore = asyncio.Semaphore(concurrency)
    analysed: dict[str, Scene] = {}

    async def analyse(skeleton: SceneSkeleton, prev: dict[str, Any] | None, nxt: dict[str, Any] | None) -> Scene:
        async with semaphore:
            result = await agent.run(key=skeleton.id, scene=skeleton, prev_scene_summary=prev, next_scene_summary=nxt)
        return apply_film_flags(result.parsed, film_brief, temperature_threshold=threshold)

    for start in range(0, len(skeletons), size):
        jobs = []
        for i in range(start, min(start + size, len(skeletons))):
            prev = None if i == 0 else analysed.get(skeletons[i - 1].id, skeletons[i - 1])
            nxt = skeletons[i + 1] if i + 1 < len(skeletons) else None
            jobs.append(analyse(skeletons[i], neighbour_summary(prev), neighbour_summary(nxt)))
        for scene in await asyncio.gather(*jobs):
            analysed[scene.id] = scene
    return [analysed[s.id] for s in skeletons]
