"""L3: production breakdown (P3) — the facts that make the panel honest.

One BreakdownRow per scene plus the film-level FilmBreakdown. The rows become the HARD
constraints of L5–L7 (setups × 1.25, cost flag, equipment, light window, CBFC notes); the
film's ≤ 5 feasibility facts ride into every scene's constraints and into P4.
"""
from __future__ import annotations

from collections import Counter
from typing import Any

from ..schemas.breakdown import BreakdownResult
from .analyst import enum_value, field_of, scene_ids_of
from .base import BaseAgent

FEASIBILITY_FACTS_MIN = 1
FEASIBILITY_FACTS_MAX = 5


class BreakdownAgent(BaseAgent[BreakdownResult]):
    """P3 — 1st AD / line producer. Routed to the fast model."""

    stage = "breakdown"
    name = "breakdown"
    template = "P3_breakdown"
    output_model = BreakdownResult
    uses_header = False

    def check(self, parsed: BreakdownResult, variables: dict[str, Any]) -> None:
        """One row per input scene and nothing else; every set-piece row is costed, with the
        cheapest staging that keeps its must_remember; the film carries 1–5 feasibility facts
        and the budget tier it was given. The schema itself caps cost drivers at 10 and setups
        at ≥ 1 (those reach the repair path as validation errors)."""
        scenes = variables["scenes"]
        scene_ids = scene_ids_of(scenes)
        set_piece_ids = {field_of(s, "id") for s in scenes if field_of(s, "set_piece")}
        problems: list[str] = []

        counts = Counter(r.scene_id for r in parsed.rows)
        missing = [sid for sid in scene_ids if sid not in counts]
        extra = sorted(sid for sid in counts if sid not in scene_ids)
        duplicated = sorted(sid for sid, n in counts.items() if n > 1)
        if missing or extra or duplicated:
            problems.append(f"rows must be exactly one per scene — missing {missing}, unknown {extra}, duplicated {duplicated}; scene ids are {scene_ids}")

        for row in parsed.rows:
            if row.scene_id not in set_piece_ids:
                continue
            if row.set_piece_costing is None:
                problems.append(f"{row.scene_id} is a set-piece and has no set_piece_costing — a set-piece without a cost line is not yet a set-piece")
            elif not row.set_piece_costing.cheapest_staging_keeping_must_remember.strip():
                problems.append(f"{row.scene_id}: set_piece_costing must name the cheapest staging that keeps the must_remember intact")

        facts = len(parsed.film.feasibility_facts)
        if not FEASIBILITY_FACTS_MIN <= facts <= FEASIBILITY_FACTS_MAX:
            problems.append(f"film.feasibility_facts must hold {FEASIBILITY_FACTS_MIN}–{FEASIBILITY_FACTS_MAX} facts the panel must respect (got {facts})")

        tier = enum_value(variables.get("budget_tier"))
        if tier and parsed.film.budget_tier != tier:
            problems.append(f"film.budget_tier is an input, not a diagnosis: it must be '{tier}'")

        if problems:
            raise ValueError("; ".join(problems))

    def _fake_hints(self, variables: dict[str, Any]) -> dict[str, Any]:
        """Offline: one example row per scene, set-pieces costed, the given budget tier."""
        hints = super()._fake_hints(variables)
        rows = []
        for s in variables["scenes"]:
            row: dict[str, Any] = {
                "scene_id": field_of(s, "id"),
                "location": field_of(s, "location"),
                "estimated_setups": field_of(s, "estimated_setups"),
                "page_eighths": field_of(s, "page_eighths"),
                "production_flags": list(field_of(s, "production_flags")),
                "cost_flag": field_of(s, "cost_flag"),
            }
            if field_of(s, "set_piece"):
                row["set_piece_costing"] = {"cheapest_staging_keeping_must_remember": f"keep the must_remember: {field_of(s, 'must_remember')}"}
            rows.append(row)
        hints["BreakdownResult.rows"] = rows
        tier = enum_value(variables.get("budget_tier"))
        if tier:
            hints["FilmBreakdown.budget_tier"] = tier
        return hints
