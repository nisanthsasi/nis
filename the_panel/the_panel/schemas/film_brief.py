"""Film-level understanding (L2a) and the cached Film Brief Header."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from .common import BudgetTier, PleasureType, Register, ReleaseTarget, SetPieceKind, StructureModel


class ArcState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    act: str
    state: str


class ValueArcEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    act: str
    value: str = Field(description="'+' or '-'")


class Character(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    want: str = ""
    need: str = ""
    flaw: str = ""
    wound: str = ""
    lie: str = ""
    thematic_answer: str = ""
    arc_map: list[ArcState] = Field(default_factory=list, description="state at each act boundary")
    dialogue_register: Register = Register.UNKNOWN
    is_antagonist: bool = False
    antagonist_argument: str | None = Field(default=None, description="the protagonist's argument made flesh")


class StarCastEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    actor: str
    character: str
    entry_scene_id: str | None = None
    entry_note: str = ""


class Mechanism(BaseModel):
    model_config = ConfigDict(extra="forbid")

    family: str
    transposition_premise: str = ""
    one_sentence: str = ""
    execution_scene_ids: list[str] = Field(default_factory=list)


class LoadBearingBeat(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(description="inciting | lock_in | midpoint | low_point | decision | climax")
    scene_id: str
    turns_central_value: bool = True
    note: str = ""


class SequenceEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sequence_id: str
    scene_ids: list[str]
    function: str
    rhythm: str = Field(default="sustaining", description="accelerating | sustaining | releasing")
    act: str = ""


class PlantPayoff(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item: str
    plant_scene_id: str
    payoff_scene_id: str | None = None


class ThemeAudit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dramatised: list[str] = Field(default_factory=list)
    silent: list[str] = Field(default_factory=list)
    preaches: list[str] = Field(default_factory=list)


class SetPieceCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scene_id: str
    kind: SetPieceKind
    pleasure_type: PleasureType
    earning_beat: str = ""
    interval_candidate: bool = False


class PleasureGap(BaseModel):
    model_config = ConfigDict(extra="forbid")

    from_scene_id: str
    to_scene_id: str
    approx_screen_minutes: float


class FilmBrief(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    logline: str
    dramatic_question: str
    controlling_idea: str
    mechanism: Mechanism | None = None
    structure_model: StructureModel = StructureModel.THREE_ACT
    load_bearing_beats: list[LoadBearingBeat] = Field(default_factory=list)
    sequences: list[SequenceEntry] = Field(default_factory=list)
    characters: list[Character] = Field(default_factory=list)
    star_cast: list[StarCastEntry] = Field(default_factory=list)
    image_systems: list[str] = Field(default_factory=list)
    motifs: list[str] = Field(default_factory=list)
    plants_payoffs: list[PlantPayoff] = Field(default_factory=list)
    theme_audit: ThemeAudit = Field(default_factory=ThemeAudit)
    value_arc: list[ValueArcEntry] = Field(default_factory=list, description="central value per act")
    set_piece_candidates: list[SetPieceCandidate] = Field(default_factory=list)
    pleasure_gaps: list[PleasureGap] = Field(default_factory=list)
    release_target: ReleaseTarget = ReleaseTarget.BOTH
    budget_tier: BudgetTier = BudgetTier.LOW
    cbfc_posture: str = ""
    language_mix: str = ""
    exemplars: list[str] = Field(default_factory=list, description="craft-note exemplar films, Malayalam first")
    writer_notes: list[str] = Field(default_factory=list)
    style_bible_digest: str | None = None
    human_digest: str = ""

    def load_bearing_scene_ids(self) -> set[str]:
        ids = {b.scene_id for b in self.load_bearing_beats}
        if self.mechanism:
            ids.update(self.mechanism.execution_scene_ids)
        return ids

    def sequence_for(self, scene_id: str) -> str | None:
        for s in self.sequences:
            if scene_id in s.scene_ids:
                return s.sequence_id
        return None
