"""L4: the Style Bible (P4)."""
from __future__ import annotations

from typing import Any

from ..schemas.style_bible import StyleBible
from .base import BaseAgent


class StyleBibleAgent(BaseAgent[StyleBible]):
    stage = "style_bible"
    name = "style_bible"
    template = "P4_style_bible"
    output_model = StyleBible
    uses_header = False

    def check(self, parsed: StyleBible, variables: dict[str, Any]) -> None:
        raise NotImplementedError("CP-4: 3 governing references; posture defended; lens affinity satisfies the posture's panel mix; every pleasure-map 'none' has a reason; digest ≤600 tokens")
