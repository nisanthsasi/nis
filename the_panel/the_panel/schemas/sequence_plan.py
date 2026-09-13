"""Sequence-level deliberation (Round 0): shape before shots."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from .common import CoverageTier, MusicPermission, PleasureType


class SequenceSceneEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scene_id: str
    energy_target: int = Field(ge=0, le=10)
    pleasure_type: PleasureType
    set_piece: bool = False
    coverage_tier: CoverageTier = CoverageTier.FULL
    music_permission: MusicPermission = MusicPermission.SILENCE
    transition_out: str = "cut"
    asl_target_s: float | None = Field(default=None, description="average shot length target, seconds")


class Contribution(BaseModel):
    model_config = ConfigDict(extra="forbid")

    element: str
    lens: str


class SequenceVision(BaseModel):
    """One lens's proposal for the SHAPE of a sequence. No shots."""

    model_config = ConfigDict(extra="forbid")

    lens: str
    sequence_id: str
    escalation_strategy: str
    key_image: str
    duration_spent_on: list[str] = Field(default_factory=list, description="scene ids where duration is spent")
    speed_on: list[str] = Field(default_factory=list, description="scene ids that move fast")
    oner_placement: str | None = None
    silence_placement: str | None = None
    breath_placement: str | None = None
    laugh_placement: str | None = None
    scenes: list[SequenceSceneEntry] = Field(default_factory=list)
    set_piece_scene_id: str | None = None
    build_to_set_piece: str = ""
    transitions_as_meaning: list[str] = Field(default_factory=list)
    temperature_curve: list[int] = Field(default_factory=list)
    carries_interval_block: bool = False
    carries_cold_open: bool = False
    carries_act_break: bool = False
    rationale: str = ""


class SequencePlan(BaseModel):
    """The Integrator's merge of SequenceVisions — the contract scene-level work inherits."""

    model_config = ConfigDict(extra="forbid")

    sequence_id: str
    function: str = ""
    key_image: str = ""
    escalation_strategy: str = ""
    scenes: list[SequenceSceneEntry] = Field(default_factory=list)
    oner_placement: str | None = None
    silence_placement: str | None = None
    breath_placement: str | None = None
    laugh_placement: str | None = None
    temperature_curve: list[int] = Field(default_factory=list)
    carries_interval_block: bool = False
    carries_cold_open: bool = False
    carries_act_break: bool = False
    contributions: list[Contribution] = Field(default_factory=list, description="element → lens")
    human_questions: list[str] = Field(default_factory=list)
    approved: bool = False

    @property
    def asl_target_by_scene(self) -> dict[str, float]:
        return {e.scene_id: e.asl_target_s for e in self.scenes if e.asl_target_s is not None}

    def entry_for(self, scene_id: str) -> SequenceSceneEntry | None:
        for e in self.scenes:
            if e.scene_id == scene_id:
                return e
        return None
