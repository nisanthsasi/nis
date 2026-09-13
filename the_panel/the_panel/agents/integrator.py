"""L6: the Integrator — scene-level (P7) and sequence-level (P7s)."""
from __future__ import annotations

from typing import Any

from ..schemas.plan import IntegratedScenePlan
from ..schemas.sequence_plan import SequencePlan
from .base import BaseAgent


class IntegratorAgent(BaseAgent[IntegratedScenePlan]):
    stage = "integrator"
    name = "integrator"
    template = "P7_integrator"
    output_model = IntegratedScenePlan

    def check(self, parsed: IntegratedScenePlan, variables: dict[str, Any]) -> None:
        raise NotImplementedError("CP-5: scene_id matches; both options' shots carry beat_refs; contributions attribute lenses that exist; pleasure 'none' justified; the_shot_it_cannot_live_without exists in the recommended option")


class SequenceIntegratorAgent(BaseAgent[SequencePlan]):
    stage = "integrator"
    name = "sequence_integrator"
    template = "P7s_sequence_integrator"
    output_model = SequencePlan

    def check(self, parsed: SequencePlan, variables: dict[str, Any]) -> None:
        raise NotImplementedError("CP-5: sequence_id matches; one entry per scene; energy/pleasure consistent with the pleasure map")
