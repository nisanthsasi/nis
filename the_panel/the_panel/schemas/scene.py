"""Scene schemas: L1 parse skeletons and the L2 Scene Report Card.

The Scene schema deliberately has *no shot fields*: understanding precedes vision.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .common import (
    CostFlag,
    DayNight,
    IntExt,
    PleasureType,
    ProductionFlag,
    Rasa,
    Register,
    SetPieceKind,
    Verdict,
)


class DialogueBlock(BaseModel):
    model_config = ConfigDict(extra="forbid")

    character: str
    text: str = Field(description="verbatim, original script/language — never translated")
    parenthetical: str | None = None
    vo_os: str | None = Field(default=None, description="V.O. / O.S. / O.C. if present")
    dialogue_register: Register = Register.UNKNOWN
    region: str | None = Field(default=None, description="Kollam / Thrissur / Malabar / Trivandrum …")
    line_ref: int | None = Field(default=None, description="line number in the source text")


class MontageChild(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: str = Field(description="montage | series_of_shots | intercut")
    lines: list[str] = Field(default_factory=list)


class SongCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    marker: str = Field(description="the line that introduced the song block")
    lyrics: list[str] = Field(default_factory=list)
    line_ref: int | None = None


class SceneSkeleton(BaseModel):
    """L1 output — structure only, no interpretation."""

    model_config = ConfigDict(extra="forbid")

    id: str
    number: int
    slug: str
    int_ext: IntExt
    day_night: DayNight
    location_raw: str
    location_canonical: str
    page_start: float = Field(ge=0)
    page_eighths: int = Field(ge=1, description="1 page ≈ 8 eighths ≈ 55 lines")
    characters: list[str] = Field(default_factory=list)
    dialogue_blocks: list[DialogueBlock] = Field(default_factory=list)
    action_lines: list[str] = Field(default_factory=list)
    capitalised_items: list[str] = Field(default_factory=list)
    montage_children: list[MontageChild] = Field(default_factory=list)
    song_candidates: list[SongCandidate] = Field(default_factory=list)
    transitions: list[str] = Field(default_factory=list, description="transitions written in the scene (CUT TO:, FADE OUT.) — structure, not a cut decision")
    parse_warnings: list[str] = Field(default_factory=list)
    line_start: int | None = None
    line_end: int | None = None

    @property
    def text(self) -> str:
        parts: list[str] = [self.slug]
        parts.extend(self.action_lines)
        for d in self.dialogue_blocks:
            parts.append(f"{d.character}: {d.text}")
        return "\n".join(parts)


class Beat(BaseModel):
    model_config = ConfigDict(extra="forbid")

    n: int = Field(ge=1)
    action: str
    reaction: str
    tactic_shift: bool = False
    line_ref: str | None = None


class Turn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entry_value: str = Field(description="'+' or '-' (or '0' if no flip)")
    exit_value: str
    value_named: str = Field(description="the value that turns, e.g. trust, safety, freedom")

    @property
    def flips(self) -> bool:
        return self.entry_value != self.exit_value


class SceneAudits(BaseModel):
    model_config = ConfigDict(extra="forbid")

    late_entry_early_exit: bool = False
    conflict_named: bool = False
    exposition_under_pressure: bool = False
    someone_leaves_changed: bool = False
    subtext_present: bool = False
    plant_or_payoff: bool = False
    notes: list[str] = Field(default_factory=list, description="one line per audit, in order")


class RasaPair(BaseModel):
    model_config = ConfigDict(extra="forbid")

    primary: Rasa
    secondary: Rasa | None = None


class Scene(BaseModel):
    """The L2 Scene Report Card — writer's hat and director's hat, kept separate."""

    model_config = ConfigDict(extra="forbid")

    # identity (from L1)
    id: str
    number: int
    slug: str
    int_ext: IntExt
    day_night: DayNight
    location: str
    page_start: float = 0.0
    page_eighths: int = 1
    characters: list[str] = Field(default_factory=list)
    synopsis: str = ""

    # writer's hat
    whose_scene: str = ""
    objective: str = ""
    obstacle: str = ""
    tactics: list[str] = Field(default_factory=list)
    turn: Turn = Field(default_factory=lambda: Turn(entry_value="0", exit_value="0", value_named="unnamed"))
    story_function: str = ""
    beats: list[Beat] = Field(default_factory=list)
    audits: SceneAudits = Field(default_factory=SceneAudits)
    rasa: RasaPair = Field(default_factory=lambda: RasaPair(primary=Rasa.SHANTA))
    emotional_temperature: int = Field(default=5, ge=0, le=10)
    tension_curve: list[int] = Field(default_factory=list)
    subtext_notes: list[str] = Field(default_factory=list)
    plants: list[str] = Field(default_factory=list)
    payoffs: list[str] = Field(default_factory=list)
    motifs_present: list[str] = Field(default_factory=list)
    registers: list[Register] = Field(default_factory=list)

    # director's hat
    must_feel: str = Field(default="", description="the one thing the audience must feel at scene end")
    pleasure_type: PleasureType = PleasureType.NONE
    set_piece: bool = False
    set_piece_kind: SetPieceKind | None = None
    must_remember: str | None = Field(default=None, description="set-pieces only: what the audience tells a friend")
    energy_target: int = Field(default=5, ge=0, le=10, description="kinetic level; sequence plan may revise")
    load_bearing: bool = False
    sequence_id: str | None = None
    location_reuse: bool = False
    estimated_setups: int = Field(default=4, ge=1)
    special_requirements: list[str] = Field(default_factory=list)
    production_flags: list[ProductionFlag] = Field(default_factory=list)
    cost_flag: CostFlag = CostFlag.LOW
    cost_justification: str = ""

    writer_notes: list[str] = Field(default_factory=list)
    director_notes: list[str] = Field(default_factory=list)
    verdict: Verdict = Verdict.KEEP
    verdict_note: str = ""
    dialogue_excerpt: list[str] = Field(default_factory=list, description="verbatim quotes in original language")

    @model_validator(mode="after")
    def _set_piece_needs_memory(self) -> "Scene":
        if self.set_piece and not (self.must_remember and self.must_remember.strip()):
            raise ValueError("set_piece=True requires must_remember")
        if self.tension_curve:
            for v in self.tension_curve:
                if not 0 <= v <= 10:
                    raise ValueError("tension_curve values must be 0–10")
        return self

    @property
    def is_full_panel(self) -> bool:
        return self.load_bearing or self.set_piece or self.emotional_temperature >= 8

    def brief(self) -> dict[str, Any]:
        """Compact dict for neighbour summaries and headers."""
        return {
            "id": self.id,
            "slug": self.slug,
            "synopsis": self.synopsis,
            "turn": self.turn.model_dump(),
            "must_feel": self.must_feel,
            "pleasure_type": self.pleasure_type.value,
            "energy_target": self.energy_target,
        }


SHOT_FIELD_NAMES = frozenset({"shots", "shot_list", "lens_mm", "camera", "coverage_approach", "shot"})


def assert_no_shot_fields(model: type[BaseModel]) -> None:
    """Guard used by tests and the Showrunner: L2 output must carry no shot decisions."""
    offenders = SHOT_FIELD_NAMES.intersection(model.model_fields.keys())
    if offenders:
        raise ValueError(f"{model.__name__} carries shot fields: {sorted(offenders)}")


class ParsedScript(BaseModel):
    """L1 output wrapper (structured outputs need an object at the root)."""

    model_config = ConfigDict(extra="forbid")

    scenes: list[SceneSkeleton] = Field(default_factory=list)
    location_aliases: list[LocationAlias] = Field(default_factory=list)
    character_aliases: list[CharacterAlias] = Field(default_factory=list)
    parse_warnings: list[str] = Field(default_factory=list)
    source_format: str = ""
    total_pages: float = 0.0


class LocationAlias(BaseModel):
    model_config = ConfigDict(extra="forbid")

    alias: str
    canonical: str


class CharacterAlias(BaseModel):
    model_config = ConfigDict(extra="forbid")

    alias: str
    canonical: str
