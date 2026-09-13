"""Everything that depends on ``style_bible.commercial_posture`` is read here — never hardcoded.

The Showrunner, the Integrator, the panel sizer, the device audit and the departments all
call into this module with an approved Style Bible (or a bare posture int for tests).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from ..schemas.common import PostureBand, posture_band
from ..schemas.plan import RUBRIC_CRITERIA, ResonanceScore
from ..schemas.style_bible import Caps, DevicePermission, StyleBible

PRESETS_PATH = Path(__file__).resolve().parent.parent / "prompts" / "posture_presets.yaml"


@lru_cache(maxsize=4)
def load_presets(path: str | None = None) -> dict[str, Any]:
    p = Path(path) if path else PRESETS_PATH
    with p.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


@dataclass(frozen=True)
class PanelMix:
    primaries_auteur_min: int
    primaries_commercial_min: int
    secondaries_commercial_min: int
    secondaries_auteur_min: int


@dataclass
class PosturePolicy:
    """The resolved dials for one posture. Built from presets, then overridden by the Style Bible."""

    posture: int
    band: PostureBand
    rubric_weights: dict[str, float]
    tie_break: list[str]
    panel_mix: PanelMix
    caps: Caps
    device_permissions: list[DevicePermission]
    song_required_slots: int
    interval_required: bool
    interval_must_carry_reversal: bool
    first_hook_minute: dict[str, float]
    max_pleasure_gap_minutes: float | None
    must_remember_per_act: int
    star_entry: str
    colour_energy_default: str
    comedy: str
    consensus_device_share: float
    consensus_device_penalty: float
    lone_engagement_carry_threshold: float
    full_panel_temperature_threshold: int = 8
    reduced_panel_size: int = 3
    overrides_applied: list[str] = field(default_factory=list)

    # --- scoring -----------------------------------------------------------------
    def weighted_total(self, score: ResonanceScore) -> float:
        total = sum(self.rubric_weights[c] * float(getattr(score, c)) for c in RUBRIC_CRITERIA)
        total -= self.rubric_weights["earned_freshness"] * score.consensus_device_penalty
        return round(total, 4)

    def score(self, score: ResonanceScore) -> ResonanceScore:
        score.weighted_total = self.weighted_total(score)
        return score

    def rank(self, scored: dict[str, ResonanceScore]) -> list[str]:
        """Rank option labels by weighted total, then the posture's tie-break order."""

        def key(label: str) -> tuple[float, ...]:
            s = scored[label]
            return (s.weighted_total or self.weighted_total(s), *[float(getattr(s, c)) for c in self.tie_break])

        return sorted(scored.keys(), key=key, reverse=True)

    # --- devices -----------------------------------------------------------------
    def permits(self, device: str) -> bool:
        d = device.strip().lower()
        return any(p.device.strip().lower() == d for p in self.device_permissions)

    def cap_for(self, device: str) -> int | None:
        return self.caps.limit_for(device)

    def is_capped_device(self, device: str) -> bool:
        from ..schemas.style_bible import DEVICE_TO_CAP

        return device.strip().lower() in DEVICE_TO_CAP

    # --- panel -------------------------------------------------------------------
    def requires_full_panel(self, *, load_bearing: bool, set_piece: bool, temperature: int) -> bool:
        return load_bearing or set_piece or temperature >= self.full_panel_temperature_threshold


def _mix(d: dict[str, int]) -> PanelMix:
    return PanelMix(**{k: int(v) for k, v in d.items()})


def policy_for_posture(posture: int, presets_path: str | None = None) -> PosturePolicy:
    """Resolve the preset dials for a bare posture (no Style Bible overrides)."""
    if not 0 <= posture <= 10:
        raise ValueError("commercial_posture must be 0–10")
    p = load_presets(presets_path)
    band = posture_band(posture)
    caps_raw = p["caps"][band]
    caps = Caps(
        elevation_cues=caps_raw.get("elevation_cues"),
        slow_motion=caps_raw.get("slow_motion"),
        needle_drops=caps_raw.get("needle_drops"),
    )
    interval = p["interval_block"][band]
    return PosturePolicy(
        posture=posture,
        band=band,
        rubric_weights=dict(p["rubric_weights"][band]),
        tie_break=list(p["tie_break"][band]),
        panel_mix=_mix(p["panel_mix"][band]),
        caps=caps,
        device_permissions=[DevicePermission(**d) for d in p["device_permissions"][band]],
        song_required_slots=int(p["song_policy"][band]["required_slots"]),
        interval_required=bool(interval.get("required", interval.get("required_if_theatrical", False))),
        interval_must_carry_reversal=bool(interval.get("must_carry_reversal", False)),
        first_hook_minute={k: float(v) for k, v in p["first_hook_minute"][band].items()},
        max_pleasure_gap_minutes=p["max_pleasure_gap_minutes"][band],
        must_remember_per_act=int(p["must_remember_per_act"][band]),
        star_entry=p["star_entry"][band],
        colour_energy_default=p["colour_energy_default"][band],
        comedy=p["comedy"][band],
        consensus_device_share=float(p["anti_groupthink"]["consensus_device_share"]),
        consensus_device_penalty=float(p["anti_groupthink"]["consensus_device_penalty"]),
        lone_engagement_carry_threshold=float(p["anti_groupthink"]["lone_engagement_carry_threshold"]),
        full_panel_temperature_threshold=int(p["engagement_audit"]["full_panel_temperature_threshold"]),
        reduced_panel_size=int(p["engagement_audit"]["reduced_panel_size"]),
    )


def policy_for(style_bible: StyleBible, presets_path: str | None = None, *, require_approved: bool = False) -> PosturePolicy:
    """The policy the pipeline actually uses: presets for the Bible's posture, overridden by the Bible."""
    if require_approved and not style_bible.is_approved:
        raise PermissionError("Style Bible is not approved; posture cannot be read from a pending constitution")
    pol = policy_for_posture(style_bible.commercial_posture, presets_path)
    # caps: the Bible's caps win outright (they are per-film decisions)
    pol.caps = style_bible.caps
    pol.overrides_applied.append("caps")
    if style_bible.device_permissions:
        pol.device_permissions = list(style_bible.device_permissions)
        pol.overrides_applied.append("device_permissions")
    if style_bible.structural_hooks.first_hook_minute:
        m = float(style_bible.structural_hooks.first_hook_minute)
        pol.first_hook_minute = {"theatrical": m, "ott": m}
        pol.overrides_applied.append("first_hook_minute")
    return pol


def default_caps_for(posture: int) -> Caps:
    return policy_for_posture(posture).caps


def default_permissions_for(posture: int) -> list[DevicePermission]:
    return policy_for_posture(posture).device_permissions
