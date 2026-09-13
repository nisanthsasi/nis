"""L1 model-assisted parse pass (register detection, canonicalisation warnings). Rule-based ingest is in ``the_panel.ingest``."""
from __future__ import annotations

from typing import Any

from ..schemas.scene import ParsedScript
from .base import BaseAgent


class ParserAgent(BaseAgent[ParsedScript]):
    stage = "parser"
    name = "parser"
    template = "P1_parse"
    output_model = ParsedScript
    uses_header = False

    def check(self, parsed: ParsedScript, variables: dict[str, Any]) -> None:
        raise NotImplementedError("CP-2: implement ParserAgent.check (ids unique, dialogue verbatim, no interpretation fields)")
