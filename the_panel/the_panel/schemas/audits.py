"""Auditor outputs (L8) — the cross-scene passes."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from .common import DeviceVerdict, Severity
from .breakdown import FeasibilityStatus


class ContinuityIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scene_id: str
    severity: Severity
    issue: str
    fix: str
    category: str = Field(default="", description="screen_direction | eyeline | geography | motif | colour | music | device | asl | echo | light | costume")


class ContinuityReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    issues: list[ContinuityIssue] = Field(default_factory=list)
    ledger_notes: list[str] = Field(default_factory=list)


class FeasibilityReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    statuses: list[FeasibilityStatus] = Field(default_factory=list)
    top_fixes_ranked_by_dramatic_cost: list[str] = Field(default_factory=list)


class DeviceFlag(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scene_id: str
    device: str
    verdict: DeviceVerdict
    earned_by: str | None = None
    cap_position: str | None = Field(default=None, description="n of N")
    repeated_recently: bool = False
    alternative: str = ""


class EarnedDeviceReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    flags: list[DeviceFlag] = Field(default_factory=list)
    template_coverage_warnings: list[str] = Field(default_factory=list)
    fits_any_scene_warnings: list[str] = Field(default_factory=list)


class EngagementPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scene_id: str
    approx_minute: float
    pleasure_delivered: str
    energy: int = Field(ge=0, le=10)
    colour_energy: str = ""


class EngagementGap(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: str = Field(description="pleasure_gap | first_hook | cold_open | interval | act_break | colour_monotone | bgm_density | energy_flat | energy_never_rests | comedy_placement | set_piece_spacing | must_remember | star_entry")
    scene_ids: list[str] = Field(default_factory=list)
    detail: str
    fix: str
    dramatic_cost: str = Field(default="low", description="low | medium | high")


class EngagementReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    engagement_curve: list[EngagementPoint] = Field(default_factory=list)
    gaps: list[EngagementGap] = Field(default_factory=list)


class AuditBundle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    continuity: ContinuityReport = Field(default_factory=ContinuityReport)
    feasibility: FeasibilityReport = Field(default_factory=FeasibilityReport)
    earned_device: EarnedDeviceReport = Field(default_factory=EarnedDeviceReport)
    engagement: EngagementReport = Field(default_factory=EngagementReport)

    def blocking(self) -> list[str]:
        out = [f"{i.scene_id}: {i.issue}" for i in self.continuity.issues if i.severity == Severity.BLOCK]
        out += [f"{f.scene_id}: {f.device} {f.verdict.value}" for f in self.earned_device.flags if f.verdict != DeviceVerdict.EARNED]
        return out
