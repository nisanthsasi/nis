"""Department directives (L7). Departments derive; they do not reinvent.

Typed bodies per department are what the agents parse (structured outputs need closed
schemas — no free-form dicts). The DepartmentDirective wrapper is built in code.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .common import Department
from .vision import Shot


class DeptFlag(BaseModel):
    model_config = ConfigDict(extra="forbid")

    issue: str
    cheapest_fix: str


class DepartmentOutput(BaseModel):
    """Common tail every department returns (subclasses add a typed ``directive``)."""

    model_config = ConfigDict(extra="forbid")

    deliverables: list[str] = Field(default_factory=list)
    references: list[str] = Field(default_factory=list)
    must_not: list[str] = Field(default_factory=list)
    dept_flags: list[DeptFlag] = Field(default_factory=list)
    digest: str = Field(default="", description="≤120 words")


class DepartmentDirective(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dept: Department
    scene_id: str
    governing_idea: str = Field(description="copied verbatim from the plan; departments may not alter it")
    pleasure_beat: str = Field(default="", description="copied verbatim from the plan")
    directive: dict[str, Any] = Field(default_factory=dict, description="the typed department body, dumped")
    deliverables: list[str] = Field(default_factory=list)
    references: list[str] = Field(default_factory=list)
    must_not: list[str] = Field(default_factory=list)
    dept_flags: list[DeptFlag] = Field(default_factory=list)
    digest: str = Field(default="", description="≤120 words")

    def body(self) -> BaseModel:
        return DEPARTMENT_BODIES[self.dept].model_validate(self.directive)

    @classmethod
    def from_output(cls, dept: Department, scene_id: str, governing_idea: str, pleasure_beat: str, output: "DepartmentOutput") -> "DepartmentDirective":
        body = getattr(output, "directive")
        return cls(
            dept=dept,
            scene_id=scene_id,
            governing_idea=governing_idea,
            pleasure_beat=pleasure_beat,
            directive=body.model_dump(mode="json") if isinstance(body, BaseModel) else dict(body),
            deliverables=list(output.deliverables),
            references=list(output.references),
            must_not=list(output.must_not),
            dept_flags=list(output.dept_flags),
            digest=output.digest,
        )


# ---------------------------------------------------------------- P8.1 cinematography


class CinematographyShot(Shot):
    filtration: str | None = None
    aspect_ratio: str | None = None
    camera_height_cm: int | None = None
    previz_prompt: str = Field(default="", description="plain description of frame, light, lens, movement")


class LightingSetup(BaseModel):
    model_config = ConfigDict(extra="forbid")

    setup: str
    key: str = ""
    fill: str = ""
    back: str = ""
    source_type: str = ""
    colour_temperature_k: int | None = None
    contrast_ratio: str = ""
    practicals_in_frame: list[str] = Field(default_factory=list)


class ShotFrameRate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    shot_no: int
    fps: int
    earned_by: str = ""


class CinematographyBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    shot_list: list[CinematographyShot] = Field(min_length=1)
    aspect_ratio: str = "2.39:1"
    base_frame_rate: int = 24
    lighting_plan: list[LightingSetup] = Field(default_factory=list)
    lens_set: list[int] = Field(default_factory=list)
    equipment: list[str] = Field(default_factory=list)
    coverage_order: list[str] = Field(default_factory=list, description="setups grouped by light direction and window")
    camera_velocity_plan: str = ""
    slow_motion_frame_rates: list[ShotFrameRate] = Field(default_factory=list)
    song_or_crowd_coverage: str | None = None
    star_entry_framing: str | None = None
    safety_continuity: list[str] = Field(default_factory=list)


class CinematographyOutput(DepartmentOutput):
    directive: CinematographyBody


# ---------------------------------------------------------------- P8.2 editing


class CutPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    beat: int
    cut: str
    why: str


class EditingBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cut_philosophy: str
    rhythm_map: str = ""
    asl_target_s: float | None = None
    cut_points: list[CutPoint] = Field(default_factory=list)
    jl_cut_plan: list[str] = Field(default_factory=list)
    transition_in: str = "cut"
    transition_out: str = "cut"
    transitions_as_meaning: str = ""
    montage_or_intercut: str | None = None
    energy_and_comedy: str = ""
    assembly_note: str = ""
    protect_in_takes: str = ""
    temp_music_guidance: str = ""


class EditingOutput(DepartmentOutput):
    directive: EditingBody


# ---------------------------------------------------------------- P8.3 colour


class MotifColourCarrier(BaseModel):
    model_config = ConfigDict(extra="forbid")

    motif: str
    colour: str
    carrier: str = ""


class ColourBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    palette: str
    contrast_saturation_position: str = ""
    skin_tone_protection: str = ""
    motif_colours: list[MotifColourCarrier] = Field(default_factory=list)
    colour_energy: str = ""
    is_colour_set_piece: bool = False
    what_colour_does: str = ""
    costume_design_pops: list[str] = Field(default_factory=list)
    show_lut: str = ""
    day_night_rules: str = ""
    grade_transitions: str = ""
    colour_sentence: str = ""


class ColourOutput(DepartmentOutput):
    directive: ColourBody


# ---------------------------------------------------------------- P8.4 music / BGM & song


class Cue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cue_id: str
    in_beat: int
    out_beat: int
    function: str
    motif: str = ""
    instrumentation: str = ""
    tempo_vs_cut_rate: str = ""
    key_mode_or_raga: str = ""
    rasa: str = ""
    dynamics: str = ""


class ElevationPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    setup_beat: str
    build: str
    drop: str
    cap_position: str = Field(description="n of N for the film")


class SongBrief(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str
    narrative_job: str
    lyric_to_image: list[str] = Field(default_factory=list)
    camera_edit_grammar: str = ""
    playback_lipsync: str = ""
    register_shift: str = ""


class MusicBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    permission: str
    cue_sheet: list[Cue] = Field(default_factory=list)
    silence_windows: list[str] = Field(default_factory=list)
    diegetic_sources: list[str] = Field(default_factory=list)
    elevation: ElevationPlan | None = None
    theme_hooks: list[str] = Field(default_factory=list)
    song_brief: SongBrief | None = None
    spotting_note: str = ""
    must_not_do: list[str] = Field(default_factory=list)


class MusicOutput(DepartmentOutput):
    directive: MusicBody


# ---------------------------------------------------------------- P8.5 sound


class BeatPriority(BaseModel):
    model_config = ConfigDict(extra="forbid")

    beat: int
    priority: str


class SoundBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ambience_beds: list[str] = Field(default_factory=list)
    perspective_plan: str = ""
    hero_sound: str = ""
    key_foley: list[str] = Field(default_factory=list)
    designed_sounds: list[str] = Field(default_factory=list)
    dialogue_treatment: str = ""
    pre_post_laps: list[str] = Field(default_factory=list)
    silence_events: list[str] = Field(default_factory=list)
    subjective_moments: list[str] = Field(default_factory=list)
    mix_priority_per_beat: list[BeatPriority] = Field(default_factory=list)
    impact_design: str | None = None
    song_handover: str | None = None
    location_risks: list[str] = Field(default_factory=list)
    worldizing: str = ""


class SoundOutput(DepartmentOutput):
    directive: SoundBody


# ---------------------------------------------------------------- P8.6 design


class CostumeNote(BaseModel):
    model_config = ConfigDict(extra="forbid")

    character: str
    colour: str
    class_register: str = ""


class DesignBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    blocking_map: str
    set_dressing: list[str] = Field(default_factory=list)
    the_one_meaningful_object: str = ""
    props_tracking: list[str] = Field(default_factory=list)
    costume_colour_class: list[CostumeNote] = Field(default_factory=list)
    spatial_hierarchy: str = ""
    frames_within_frames: list[str] = Field(default_factory=list)
    colour_set_piece_dressing: str | None = None
    star_entry_environment: str | None = None
    kerala_authenticity: list[str] = Field(default_factory=list)
    continuity_flags: list[str] = Field(default_factory=list)


class DesignOutput(DepartmentOutput):
    directive: DesignBody


# ---------------------------------------------------------------- P8.7 performance


class BeatVerb(BaseModel):
    model_config = ConfigDict(extra="forbid")

    beat: int
    verb: str


class PerformanceNote(BaseModel):
    model_config = ConfigDict(extra="forbid")

    character: str
    objective: str
    action_verbs_per_beat: list[BeatVerb] = Field(default_factory=list)
    subtext_line: str = ""
    tempo: str = ""
    physical_life: str = ""
    dialogue_register: str = ""
    what_not_to_play: str = ""
    moment_of_change: str = ""


class PerformanceBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    notes: list[PerformanceNote] = Field(default_factory=list)
    star_handling: str | None = None
    comedy_playing: str | None = None
    ensemble_energy: str = ""
    rehearsal_note: str = ""
    non_actor_handling: str = ""
    directors_note_verbatim: str = ""


class PerformanceOutput(DepartmentOutput):
    directive: PerformanceBody


DEPARTMENT_BODIES: dict[Department, type[BaseModel]] = {
    Department.CINEMATOGRAPHY: CinematographyBody,
    Department.EDITING: EditingBody,
    Department.COLOUR: ColourBody,
    Department.MUSIC: MusicBody,
    Department.SOUND: SoundBody,
    Department.DESIGN: DesignBody,
    Department.PERFORMANCE: PerformanceBody,
}

DEPARTMENT_OUTPUTS: dict[Department, type[DepartmentOutput]] = {
    Department.CINEMATOGRAPHY: CinematographyOutput,
    Department.EDITING: EditingOutput,
    Department.COLOUR: ColourOutput,
    Department.MUSIC: MusicOutput,
    Department.SOUND: SoundOutput,
    Department.DESIGN: DesignOutput,
    Department.PERFORMANCE: PerformanceOutput,
}
