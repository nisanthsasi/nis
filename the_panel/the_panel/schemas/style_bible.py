"""The Style Bible — the film's constitution (L4)."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .common import PleasureType, posture_band


class Form(BaseModel):
    model_config = ConfigDict(extra="forbid")

    genre_contract: str
    tone: str = Field(description="one adjective pair, e.g. 'austere-tender'")
    narrative_stance: str = Field(description="observational | immersive | lyrical | classical-invisible | propulsive")
    pov_strategy: str
    audience_relationship: str = Field(description="complicit | witness | participant")


class ActRhythm(BaseModel):
    model_config = ConfigDict(extra="forbid")

    act: str
    rhythm: str = Field(description="where duration is spent, where speed")
    asl_target_s: float | None = None


class Structure(BaseModel):
    model_config = ConfigDict(extra="forbid")

    time_organisation: str = Field(description="linear | elliptical | braided | looped")
    sequence_architecture: str
    rhythm_plan_by_act: list[ActRhythm] = Field(default_factory=list)
    ellipsis_policy: str = ""
    where_it_breathes: str = ""


class StructuralHooks(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cold_open: str | None = None
    first_hook_minute: float = 8
    interval_block_scene: str | None = None
    interval_detonates: str = ""
    act_break_cliffhangers: list[str] = Field(default_factory=list)
    finale_promise: str = ""


class PleasureMapEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sequence_id: str
    pleasure_type: PleasureType
    set_piece_scene_id: str | None = None
    reason_if_none: str | None = None


class SongSlot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slot: str
    type: str = Field(description="montage | situational | duet | dance | anthem")
    narrative_job: str
    camera_grammar: str = ""
    scene_id: str | None = None


class ActPalette(BaseModel):
    model_config = ConfigDict(extra="forbid")

    act: str
    palette: str


class MotifColour(BaseModel):
    model_config = ConfigDict(extra="forbid")

    motif: str
    colour: str
    carriers: str = Field(default="", description="costume, prop, practical light …")


class Style(BaseModel):
    model_config = ConfigDict(extra="forbid")

    camera_grammar: str
    lens_policy: str
    movement_policy: str
    light_policy: str
    color_arc: list[ActPalette] = Field(default_factory=list, description="palette per act")
    motif_colours: list[MotifColour] = Field(default_factory=list)
    colour_energy: str = ""
    colour_set_pieces: list[str] = Field(default_factory=list)
    editing_grammar: str
    sound_philosophy: str
    music_philosophy: str
    bgm_policy: str = ""
    song_plan: list[SongSlot] = Field(default_factory=list)
    song_plan_reason_if_none: str | None = None
    mise_en_scene_rules: str
    performance_style: str


class DevicePermission(BaseModel):
    model_config = ConfigDict(extra="forbid")

    device: str
    must_pay_off: str


class Caps(BaseModel):
    """Film-wide caps. ``None`` means unlimited (each use still must be earned)."""

    model_config = ConfigDict(extra="forbid")

    elevation_cues: int | None = 3
    slow_motion: int | None = 3
    needle_drops: int | None = 2

    def limit_for(self, device: str) -> int | None:
        key = DEVICE_TO_CAP.get(device.strip().lower())
        if key is None:
            return None
        return getattr(self, key)


DEVICE_TO_CAP: dict[str, str] = {
    "bgm elevation": "elevation_cues",
    "bgm elevation cue": "elevation_cues",
    "elevation": "elevation_cues",
    "elevation cue": "elevation_cues",
    "earned elevation": "elevation_cues",
    "slow motion": "slow_motion",
    "slow-motion": "slow_motion",
    "slow_motion": "slow_motion",
    "slomo": "slow_motion",
    "speed ramp": "slow_motion",
    "needle drop": "needle_drops",
    "needle_drop": "needle_drops",
    "needle drops": "needle_drops",
}


class GoverningReference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    film: str
    borrowed: str
    refused: str


class ExcludedLens(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lens: str
    reason: str


class LensAffinity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    primary: list[str] = Field(default_factory=list)
    secondary: list[str] = Field(default_factory=list)
    excluded: list[ExcludedLens] = Field(default_factory=list)


class Amendment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scene_id: str | None
    change: str
    reason: str
    approved: bool = False
    affected_scene_ids: list[str] = Field(default_factory=list)


class StyleBible(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: str = "1.0"
    approved_by: str = "pending"
    form: Form
    audience_promise: list[PleasureType] = Field(default_factory=list, description="ranked pleasures the film sells")
    commercial_posture: int = Field(ge=0, le=10)
    posture_defence: str = ""
    structure: Structure
    structural_hooks: StructuralHooks = Field(default_factory=StructuralHooks)
    pleasure_map: list[PleasureMapEntry] = Field(default_factory=list)
    style: Style
    signature_devices: list[str] = Field(default_factory=list, max_length=3)
    device_permissions: list[DevicePermission] = Field(default_factory=list)
    caps: Caps = Field(default_factory=Caps)
    refusals: list[str] = Field(default_factory=list)
    governing_references: list[GoverningReference] = Field(default_factory=list, max_length=3)
    lens_affinity: LensAffinity = Field(default_factory=LensAffinity)
    malayalam_grounding: str = ""
    amendments: list[Amendment] = Field(default_factory=list)
    manifesto: str = ""
    digest: str = Field(default="", description="≤600 tokens; joins the Film Brief Header")
    human_questions: list[str] = Field(default_factory=list)

    @field_validator("signature_devices")
    @classmethod
    def _max_three(cls, v: list[str]) -> list[str]:
        if len(v) > 3:
            raise ValueError("a device used more than three times is a tic — max 3 signature devices")
        return v

    @model_validator(mode="after")
    def _pleasure_map_none_needs_reason(self) -> "StyleBible":
        for e in self.pleasure_map:
            if e.pleasure_type == PleasureType.NONE and not e.reason_if_none:
                raise ValueError(f"sequence {e.sequence_id} carries 'none' without a reason")
        return self

    @property
    def band(self) -> str:
        return posture_band(self.commercial_posture)

    @property
    def is_approved(self) -> bool:
        return self.approved_by not in ("", "pending")

    def permits(self, device: str) -> bool:
        d = device.strip().lower()
        return any(p.device.strip().lower() == d for p in self.device_permissions)

    def permission_for(self, device: str) -> DevicePermission | None:
        d = device.strip().lower()
        for p in self.device_permissions:
            if p.device.strip().lower() == d:
                return p
        return None
