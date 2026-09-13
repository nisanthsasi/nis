"""The cap ledger — a cap is never spent silently."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from ..schemas.style_bible import DEVICE_TO_CAP, Caps


@dataclass
class CapSpend:
    scene_id: str
    device: str
    setup_ref: str


@dataclass
class CapLedger:
    caps: Caps
    spends: dict[str, list[CapSpend]] = field(default_factory=lambda: defaultdict(list))

    @staticmethod
    def cap_key(device: str) -> str | None:
        return DEVICE_TO_CAP.get(device.strip().lower())

    def used(self, device: str) -> int:
        key = self.cap_key(device)
        return len(self.spends[key]) if key else 0

    def limit(self, device: str) -> int | None:
        key = self.cap_key(device)
        return getattr(self.caps, key) if key else None

    def remaining(self, device: str) -> int | None:
        lim = self.limit(device)
        if lim is None:
            return None
        return max(0, lim - self.used(device))

    def would_exceed(self, device: str, *, scene_id: str | None = None) -> bool:
        key = self.cap_key(device)
        if key is None:
            return False
        lim = getattr(self.caps, key)
        if lim is None:
            return False
        already_here = sum(1 for s in self.spends[key] if scene_id and s.scene_id == scene_id)
        return (self.used(device) - already_here) + 1 > lim

    def spend(self, device: str, scene_id: str, setup_ref: str) -> "CapSpend | None":
        """Record a spend. Raises if over cap — callers must check ``would_exceed`` first and raise HUMAN_QUESTION."""
        key = self.cap_key(device)
        if key is None:
            return None
        if self.would_exceed(device, scene_id=None):
            raise OverCapError(device, self.limit(device) or 0)
        spend = CapSpend(scene_id=scene_id, device=device, setup_ref=setup_ref)
        self.spends[key].append(spend)
        return spend

    def release_scene(self, scene_id: str) -> None:
        """Remove spends for a scene (used when a scene is re-run)."""
        for key in list(self.spends.keys()):
            self.spends[key] = [s for s in self.spends[key] if s.scene_id != scene_id]

    def position(self, device: str) -> str:
        lim = self.limit(device)
        return f"{self.used(device)} of {'∞' if lim is None else lim}"

    def status(self) -> dict[str, str]:
        return {k: f"{len(self.spends[k])} of {'∞' if getattr(self.caps, k) is None else getattr(self.caps, k)}" for k in ("elevation_cues", "slow_motion", "needle_drops")}

    def to_dict(self) -> dict[str, list[dict[str, str]]]:
        return {k: [s.__dict__ for s in v] for k, v in self.spends.items()}

    @classmethod
    def from_dict(cls, caps: Caps, data: dict[str, list[dict[str, str]]]) -> "CapLedger":
        ledger = cls(caps=caps)
        for k, v in data.items():
            ledger.spends[k] = [CapSpend(**s) for s in v]
        return ledger


class OverCapError(RuntimeError):
    def __init__(self, device: str, limit: int):
        super().__init__(f"device '{device}' exceeds the film cap of {limit}")
        self.device = device
        self.limit = limit
