"""L5: lenses — sequence-level (P5s), scene-level (P5), cross-critique (P6)."""
from __future__ import annotations

from typing import Any

from ..schemas.sequence_plan import SequenceVision
from ..schemas.vision import Critique, SceneVision
from .base import BaseAgent


class SequenceLensAgent(BaseAgent[SequenceVision]):
    stage = "sequence_lens"
    name = "sequence_lens"
    template = "P5s_sequence_lens"
    output_model = SequenceVision

    def check(self, parsed: SequenceVision, variables: dict[str, Any]) -> None:
        raise NotImplementedError("CP-5: lens == card name; sequence_id matches; every scene of the sequence gets an entry; no shots")


class LensAgent(BaseAgent[SceneVision]):
    stage = "lens"
    name = "lens"
    template = "P5_lens"
    output_model = SceneVision

    def check(self, parsed: SceneVision, variables: dict[str, Any]) -> None:
        raise NotImplementedError("CP-5: lens == card name; scene_id matches; 3–8 shots each with beat_ref ∈ scene beats; devices have setup_ref; pleasure 'none' justified")


class CritiqueAgent(BaseAgent[Critique]):
    stage = "critique"
    name = "critique"
    template = "P6_critique"
    output_model = Critique

    def check(self, parsed: Critique, variables: dict[str, Any]) -> None:
        raise NotImplementedError("CP-5: steal names another lens present in other_visions; at most one revised element")
