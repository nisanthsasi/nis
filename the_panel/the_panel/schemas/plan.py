"""The Integrator's output: one plan, two options, scored."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from .common import HumanQuestion
from .sequence_plan import Contribution
from .vision import DeviceUse, Shot

RUBRIC_CRITERIA: tuple[str, ...] = (
    "dramatic_fidelity",
    "emotional_impact",
    "engagement",
    "style_coherence",
    "feasibility",
    "earned_freshness",
)


class Justification(BaseModel):
    model_config = ConfigDict(extra="forbid")

    criterion: str
    note: str


class ResonanceScore(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dramatic_fidelity: float = Field(ge=0, le=10)
    emotional_impact: float = Field(ge=0, le=10)
    engagement: float = Field(ge=0, le=10)
    style_coherence: float = Field(ge=0, le=10)
    feasibility: float = Field(ge=0, le=10)
    earned_freshness: float = Field(ge=0, le=10)
    justifications: list[Justification] = Field(default_factory=list, description="one line per criterion")
    weighted_total: float | None = Field(default=None, description="filled by the orchestrator from posture weights")
    consensus_device_penalty: float = 0.0

    def as_dict(self) -> dict[str, float]:
        return {c: float(getattr(self, c)) for c in RUBRIC_CRITERIA}


class PlanOption(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str = Field(description="A | B")
    governing_idea: str = ""
    shots: list[Shot] = Field(min_length=1)
    blocking: str
    rationale: str
    source_lenses: list[str] = Field(default_factory=list)
    reduced_coverage_variant: str | None = None
    devices_used: list[DeviceUse] = Field(default_factory=list)


class EnergyCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asl_target_s: float
    camera_velocity: str
    cut_rate: str
    sequence_energy_target: int = Field(ge=0, le=10)
    plan_energy: int = Field(ge=0, le=10)
    matches: bool = True
    note: str = ""


class DepartmentHandoff(BaseModel):
    model_config = ConfigDict(extra="forbid")

    colour_stance: str
    music_stance: str
    sound_stance: str
    design_stance: str
    performance_stance: str


class ShotItCannotLiveWithout(BaseModel):
    model_config = ConfigDict(extra="forbid")

    shot_no: int
    why: str


class IntegratedScenePlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scene_id: str
    governing_idea: str
    directors_note: str = Field(description="one plain paragraph for the actors — no camera talk")
    option_A: PlanOption
    option_B: PlanOption
    contributions: list[Contribution] = Field(default_factory=list, description="element → lens; every stolen element attributed")
    unresolved_tensions: list[str] = Field(default_factory=list)
    pleasure_beat: str
    pleasure_none_reason: str | None = None
    trailer_shot: str | None = None
    must_remember_delivery: str | None = None
    energy_check: EnergyCheck
    devices_used: list[DeviceUse] = Field(default_factory=list)
    resonance_A: ResonanceScore
    resonance_B: ResonanceScore
    department_handoff: DepartmentHandoff
    the_shot_it_cannot_live_without: ShotItCannotLiveWithout
    human_questions: list[HumanQuestion] = Field(default_factory=list)
    digest: str = Field(default="", description="≤150 words, pitch voice")
    recommended: str = "A"
    chosen: str | None = None

    @property
    def resonance_scores(self) -> dict[str, ResonanceScore]:
        return {"A": self.resonance_A, "B": self.resonance_B}

    def option(self, label: str) -> PlanOption:
        return self.option_A if label == "A" else self.option_B

    def chosen_option(self) -> PlanOption:
        label = self.chosen or self.recommended
        return self.option_A if label == "A" else self.option_B


class JudgeVerdict(BaseModel):
    """CP-8 judge-model grading of an IntegratedScenePlan against a human-written ideal."""

    model_config = ConfigDict(extra="forbid")

    scene_id: str
    scores: ResonanceScore
    governing_idea_match: float = Field(ge=0, le=10)
    must_feel_match: float = Field(ge=0, le=10)
    pleasure_beat_match: float = Field(ge=0, le=10)
    style_bible_adherence: float = Field(ge=0, le=10)
    cap_discipline: bool = True
    notes: list[str] = Field(default_factory=list)
