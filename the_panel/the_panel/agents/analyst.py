"""L2: film-level (P2a) and scene-level (P2b) dramatic analysis."""
from __future__ import annotations

from typing import Any

from ..schemas.film_brief import FilmBrief
from ..schemas.scene import Scene
from .base import BaseAgent


class FilmAnalystAgent(BaseAgent[FilmBrief]):
    stage = "analyst_film"
    name = "analyst_film"
    template = "P2a_film"
    output_model = FilmBrief
    uses_header = False

    def check(self, parsed: FilmBrief, variables: dict[str, Any]) -> None:
        raise NotImplementedError("CP-3: load-bearing beats reference real scene ids; set-piece candidates carry pleasure; theme audit present")


class SceneAnalystAgent(BaseAgent[Scene]):
    stage = "analyst_scene"
    name = "analyst_scene"
    template = "P2b_scene"
    output_model = Scene
    uses_header = True

    def check(self, parsed: Scene, variables: dict[str, Any]) -> None:
        raise NotImplementedError("CP-3: scene id matches; beats numbered 1..n; tension_curve len == beats; set_piece ⇒ must_remember; no shot fields")
