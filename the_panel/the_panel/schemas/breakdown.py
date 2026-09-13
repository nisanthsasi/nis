"""L3 production breakdown — the facts the panel must respect."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from .common import CostFlag, ProductionFlag, RAG


class SetPieceCosting(BaseModel):
    model_config = ConfigDict(extra="forbid")

    extra_shoot_days: float = 0
    rehearsal_days: float = 0
    playback_lipsync: bool = False
    crowd_count: int = 0
    high_speed_days: float = 0
    vfx_plates: int = 0
    star_windows: list[str] = Field(default_factory=list)
    cheapest_staging_keeping_must_remember: str = ""


class BreakdownRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scene_id: str
    cast_speaking: list[str] = Field(default_factory=list)
    cast_non_speaking: list[str] = Field(default_factory=list)
    background_count: int = 0
    location: str = ""
    location_new: bool = True
    company_move: bool = False
    props: list[str] = Field(default_factory=list)
    set_dressing: list[str] = Field(default_factory=list)
    wardrobe_notes: list[str] = Field(default_factory=list)
    makeup_sfx: list[str] = Field(default_factory=list)
    vehicles: list[str] = Field(default_factory=list)
    animals: list[str] = Field(default_factory=list)
    minors: list[str] = Field(default_factory=list)
    stunts: list[str] = Field(default_factory=list)
    vfx: list[str] = Field(default_factory=list)
    special_equipment: list[str] = Field(default_factory=list)
    light_window: str = ""
    schedule_critical: bool = False
    estimated_setups: int = Field(default=4, ge=1)
    page_eighths: int = Field(default=1, ge=1)
    production_flags: list[ProductionFlag] = Field(default_factory=list)
    cost_flag: CostFlag = CostFlag.LOW
    set_piece_costing: SetPieceCosting | None = None
    cbfc_notes: list[str] = Field(default_factory=list)


class CostDriver(BaseModel):
    model_config = ConfigDict(extra="forbid")

    driver: str
    scene_ids: list[str] = Field(default_factory=list)
    cheaper_alternative: str = ""


class CbfcFlag(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scene_id: str
    category: str = Field(description="violence | language | sexual | religion | real_institution | other")
    likely_band: str = Field(default="U/A", description="U | U/A | A")
    safer_staging: str = ""
    dramatic_cost: str = ""


class LocationGroup(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    scene_ids: list[str] = Field(default_factory=list)
    group: str = Field(default="", description="company-move grouping")
    reuse_count: int = 1


class CastDays(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    days: float
    is_star: bool = False


class FilmBreakdown(BaseModel):
    model_config = ConfigDict(extra="forbid")

    budget_tier: str = ""
    budget_inr: float | None = None
    locations: list[LocationGroup] = Field(default_factory=list)
    cast_days: list[CastDays] = Field(default_factory=list)
    night_ext_count: int = 0
    crowd_scene_ids: list[str] = Field(default_factory=list)
    weather_dependent_ids: list[str] = Field(default_factory=list)
    song_choreography_days: float = 0
    cbfc_flags: list[CbfcFlag] = Field(default_factory=list)
    likely_certificate: str = "U/A"
    cost_drivers: list[CostDriver] = Field(default_factory=list, max_length=10)
    feasibility_facts: list[str] = Field(default_factory=list, description="≤5 facts the panel must respect")
    digest: str = ""


class SceneConstraints(BaseModel):
    """Hard constraints derived from the breakdown for one scene; injected into L5–L7."""

    model_config = ConfigDict(extra="forbid")

    scene_id: str
    estimated_setups: int = 4
    max_setups: int = Field(default=5, description="estimated_setups × 1.25, rounded up")
    cost_flag: CostFlag = CostFlag.LOW
    production_flags: list[ProductionFlag] = Field(default_factory=list)
    special_equipment: list[str] = Field(default_factory=list)
    light_window: str = ""
    cbfc_notes: list[str] = Field(default_factory=list)
    feasibility_facts: list[str] = Field(default_factory=list)
    budget_tier: str = ""

    @classmethod
    def from_row(cls, row: BreakdownRow, film: FilmBreakdown | None = None) -> "SceneConstraints":
        import math

        return cls(
            scene_id=row.scene_id,
            estimated_setups=row.estimated_setups,
            max_setups=math.ceil(row.estimated_setups * 1.25),
            cost_flag=row.cost_flag,
            production_flags=list(row.production_flags),
            special_equipment=list(row.special_equipment),
            light_window=row.light_window,
            cbfc_notes=list(row.cbfc_notes),
            feasibility_facts=list(film.feasibility_facts) if film else [],
            budget_tier=film.budget_tier if film else "",
        )


class FeasibilityStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scene_id: str
    rag: RAG = RAG.GREEN
    issues: list[str] = Field(default_factory=list)
    fixes_ranked_by_dramatic_cost: list[str] = Field(default_factory=list)


class BreakdownResult(BaseModel):
    """P3 output: per-scene rows + the film-level breakdown."""

    model_config = ConfigDict(extra="forbid")

    rows: list[BreakdownRow] = Field(default_factory=list)
    film: FilmBreakdown = Field(default_factory=FilmBreakdown)
