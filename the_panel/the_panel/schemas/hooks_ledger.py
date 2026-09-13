"""Commercial Hooks Ledger — accumulates from approved scenes only."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class HookEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scene_id: str
    description: str
    kind: str = ""


class CommercialHooksLedger(BaseModel):
    model_config = ConfigDict(extra="forbid")

    trailer_shots: list[HookEntry] = Field(default_factory=list)
    poster_frames: list[HookEntry] = Field(default_factory=list)
    bgm_hooks: list[HookEntry] = Field(default_factory=list)
    song_slots: list[HookEntry] = Field(default_factory=list)
    teaser_scene_candidates: list[HookEntry] = Field(default_factory=list)
    interval_block: HookEntry | None = None
    shareable_moments: list[HookEntry] = Field(default_factory=list)
    approved_scene_ids: list[str] = Field(default_factory=list)

    def sections(self) -> dict[str, list[HookEntry]]:
        return {
            "trailer_shots": self.trailer_shots,
            "poster_frames": self.poster_frames,
            "bgm_hooks": self.bgm_hooks,
            "song_slots": self.song_slots,
            "teaser_scene_candidates": self.teaser_scene_candidates,
            "shareable_moments": self.shareable_moments,
        }
