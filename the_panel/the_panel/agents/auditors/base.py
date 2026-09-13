from __future__ import annotations

from typing import Any

from ...schemas.audits import ContinuityReport, EarnedDeviceReport, EngagementReport, FeasibilityReport
from ..base import BaseAgent


class ContinuityAuditor(BaseAgent[ContinuityReport]):
    stage = "auditor"
    name = "audit_continuity"
    template = "P9_1_continuity"
    output_model = ContinuityReport

    def check(self, parsed: ContinuityReport, variables: dict[str, Any]) -> None:
        raise NotImplementedError("CP-6")


class FeasibilityAuditor(BaseAgent[FeasibilityReport]):
    stage = "auditor"
    name = "audit_feasibility"
    template = "P9_2_feasibility"
    output_model = FeasibilityReport

    def check(self, parsed: FeasibilityReport, variables: dict[str, Any]) -> None:
        raise NotImplementedError("CP-6")


class EarnedDeviceAuditor(BaseAgent[EarnedDeviceReport]):
    stage = "auditor"
    name = "audit_earned_device"
    template = "P9_3_earned_device"
    output_model = EarnedDeviceReport

    def check(self, parsed: EarnedDeviceReport, variables: dict[str, Any]) -> None:
        raise NotImplementedError("CP-6")


class EngagementAuditor(BaseAgent[EngagementReport]):
    stage = "auditor"
    name = "audit_engagement"
    template = "P9_4_engagement"
    output_model = EngagementReport

    def check(self, parsed: EngagementReport, variables: dict[str, Any]) -> None:
        raise NotImplementedError("CP-6")
