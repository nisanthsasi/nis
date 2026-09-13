"""L3: production breakdown (P3)."""
from __future__ import annotations

from typing import Any

from ..schemas.breakdown import BreakdownResult
from .base import BaseAgent


class BreakdownAgent(BaseAgent[BreakdownResult]):
    stage = "breakdown"
    name = "breakdown"
    template = "P3_breakdown"
    output_model = BreakdownResult
    uses_header = False

    def check(self, parsed: BreakdownResult, variables: dict[str, Any]) -> None:
        raise NotImplementedError("CP-4: one row per scene; set_piece rows carry set_piece_costing; ≤5 feasibility facts; ≤10 cost drivers")
