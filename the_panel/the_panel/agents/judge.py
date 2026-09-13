"""CP-8: judge-model grading against a human-written ideal."""
from __future__ import annotations

from typing import Any

from ..schemas.plan import JudgeVerdict
from .base import BaseAgent


class JudgeAgent(BaseAgent[JudgeVerdict]):
    stage = "judge"
    name = "judge"
    template = "P11_judge"
    output_model = JudgeVerdict

    def check(self, parsed: JudgeVerdict, variables: dict[str, Any]) -> None:
        raise NotImplementedError("CP-8")
