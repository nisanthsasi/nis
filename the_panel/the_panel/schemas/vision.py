"""Lens outputs: Shot, SceneVision, Critique."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .common import CoverageApproach, ShotSize


class Shot(BaseModel):
    """A shot without beat_ref is not a shot, it is a wish."""

    model_config = ConfigDict(extra="forbid")

    no: int = Field(ge=1)
    size: ShotSize
    angle: str = Field(description="eye-level | low | high | dutch | overhead | POV | profile …")
    height: str = Field(description="camera height: floor | knee | waist | eye | overhead …")
    lens_mm: int = Field(ge=8, le=1200)
    movement: str = Field(description="static | pan | tilt | dolly | track | Steadicam | hand-held | crane | zoom …")
    movement_motivation: str = ""
    duration_est_s: float = Field(gt=0)
    subject: str
    action: str
    beat_ref: int = Field(ge=1, description="the scene beat this shot exists for")
    light_note: str = Field(description="source, direction, quality")
    sound_note: str = ""
    transition_in: str = "cut"
    transition_out: str = "cut"
    frame_rate: int | None = None


class DeviceUse(BaseModel):
    """Every device names the beat that earns it."""

    model_config = ConfigDict(extra="forbid")

    device: str
    setup_ref: str = Field(min_length=1, description="beat n / earlier scene id that sets it up")
    pays: str = ""

    @field_validator("setup_ref")
    @classmethod
    def _non_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("a device without setup_ref is unearned by construction")
        return v


class SceneVision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lens: str
    scene_id: str
    governing_idea: str
    key_image: str
    coverage_approach: CoverageApproach
    coverage_why: str = ""
    shots: list[Shot] = Field(min_length=3, max_length=8)
    blocking_note: str
    movement: str = ""
    light: str = ""
    sound_stance: str = ""
    music_stance: str = ""
    edit_rhythm: str = ""
    asl_target_s: float | None = None
    pleasure_offer: str = Field(description="'none' only with a reason")
    energy_level: int = Field(ge=0, le=10)
    colour_note: str = ""
    devices_used: list[DeviceUse] = Field(default_factory=list)
    refusals: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list, max_length=4)
    style_bible_conflicts: list[str] = Field(default_factory=list)

    @property
    def device_names(self) -> set[str]:
        return {d.device.strip().lower() for d in self.devices_used}


class Steal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    from_lens: str
    idea: str
    how_it_improves_mine: str


class Critique(BaseModel):
    """Round-2 cross-critique: steal / risk / conflict. ≤200 tokens. No defending, no flattery."""

    model_config = ConfigDict(extra="forbid")

    lens: str
    scene_id: str
    steal: Steal
    risk: str
    conflict: str = "none"
    revised_element: str | None = Field(default=None, description="ONE element revised; never a rewrite")
    revised_value: str | None = None
