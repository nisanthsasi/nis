"""Human sovereignty: decisions, overrides, amendments."""
from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field

from .style_bible import Amendment


class DecisionLogEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scene_id: str
    chosen: str = Field(description="A | B | custom")
    human_note: str = ""
    custom_text: str | None = None
    overrides: list[str] = Field(default_factory=list)
    pushback_given: bool = False
    pushback_reason: str | None = None
    style_bible_amendment: Amendment | None = None
    rerun_scene_ids: list[str] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    gate: str = Field(default="scene", description="style_bible | sequence | scene")


class Pushback(BaseModel):
    """The one push-back the Showrunner may give on a human override — then it complies."""

    model_config = ConfigDict(extra="forbid")

    warranted: bool
    reason: str = ""
    cost: str = Field(default="", description="what the override costs: the TURN, the Style Bible, a cap")
    breaks: list[str] = Field(default_factory=list, description="style_bible | turn | cap | none")
    amendment_needed: bool = False
    proposed_amendment: Amendment | None = None
