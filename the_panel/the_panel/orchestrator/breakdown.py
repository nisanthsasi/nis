"""L3 stage runner: the production breakdown and the HARD constraints it hands to L5–L7."""
from __future__ import annotations

from typing import Any, Iterable

from ..agents.base import AgentContext
from ..agents.breakdown import BreakdownAgent
from ..schemas.breakdown import BreakdownResult, SceneConstraints
from ..schemas.common import BudgetTier, ReleaseTarget
from ..schemas.scene import Scene

FILM_KEY = "film"


async def run_breakdown(
    ctx: AgentContext,
    scenes: Iterable[Scene],
    *,
    budget_tier: BudgetTier | str,
    release_target: ReleaseTarget | str,
    budget_inr: float | None = None,
) -> BreakdownResult:
    """P3 over every analysed scene (set-pieces are costed because the Scene says set_piece)."""
    variables: dict[str, Any] = {
        "scenes": list(scenes),
        "budget_tier": BudgetTier(budget_tier).value,
        "release_target": ReleaseTarget(release_target).value,
    }
    if budget_inr is not None:
        variables["budget_inr"] = budget_inr
    result = await BreakdownAgent(ctx).run(key=FILM_KEY, **variables)
    return result.parsed


def scene_constraints_from(result: BreakdownResult) -> dict[str, SceneConstraints]:
    """The hard constraints per scene id: setups × 1.25 ceiling, cost flag, flags, equipment,
    light window, CBFC notes, plus the film's feasibility facts — what lenses, the Integrator
    and the departments may not contradict."""
    return {row.scene_id: SceneConstraints.from_row(row, result.film) for row in result.rows}
