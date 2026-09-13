"""P10: the one push-back on a human override (prose); the rules live in orchestrator/review.py."""
from __future__ import annotations

from typing import Any

from ..schemas.decisions import Pushback
from .base import BaseAgent


class PushbackAgent(BaseAgent[Pushback]):
    stage = "integrator"
    name = "pushback"
    template = "P10_pushback"
    output_model = Pushback

    def check(self, parsed: Pushback, variables: dict[str, Any]) -> None:
        raise NotImplementedError("CP-7")
