"""Configuration loading for THE PANEL.

Model IDs, routing, budgets and paths live in ``config.yaml``. Nothing here decides
posture, weights, caps or permissions — those are read from the approved Style Bible
(see :mod:`the_panel.orchestrator.posture`).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config.yaml"

ModelTier = Literal["fast", "reasoning", "judge"]


class ModelsConfig(BaseModel):
    fast: str = "claude-sonnet-5"
    reasoning: str = "claude-opus-5"
    judge: str = "claude-opus-5"

    def for_tier(self, tier: str) -> str:
        return getattr(self, tier)


class BudgetsConfig(BaseModel):
    slack: float = 2.0
    strict_budgets: bool = False
    parser: int = 8000
    analyst_film: int = 6000
    analyst_scene: int = 2500
    breakdown: int = 6000
    style_bible: int = 6000
    sequence_lens: int = 450
    lens: int = 750
    critique: int = 200
    integrator: int = 1600
    department: int = 850
    auditor: int = 600
    judge: int = 800

    def budget_for(self, stage: str) -> int:
        return int(getattr(self, stage))

    def max_tokens_for(self, stage: str) -> int:
        return int(self.budget_for(stage) * self.slack)


class RequestConfig(BaseModel):
    thinking: Literal["adaptive", "none"] = "adaptive"
    effort: Literal["low", "medium", "high", "xhigh", "max"] = "high"
    cache_ttl: Literal["5m", "1h"] = "1h"
    timeout_s: float = 600.0
    max_retries: int = 2


class PipelineConfig(BaseModel):
    scene_chunk_size: int = 12
    full_panel_temperature_threshold: int = 8
    reduced_panel_size: int = 3
    header_max_tokens: int = 3000
    batch_mode: bool = False


class PathsConfig(BaseModel):
    prompts: str = "the_panel/prompts"
    lenses: str = "the_panel/prompts/lenses"
    store: str = ".panel/state.sqlite"
    snapshots: str = ".panel/snapshots"
    vault: str = "vault"
    exports: str = "exports"

    def resolve(self, key: str, root: Path | None = None) -> Path:
        root = root or PROJECT_ROOT
        p = Path(getattr(self, key))
        return p if p.is_absolute() else root / p


class PanelConfig(BaseModel):
    models: ModelsConfig = Field(default_factory=ModelsConfig)
    routing: dict[str, ModelTier] = Field(
        default_factory=lambda: {
            "parser": "fast",
            "breakdown": "fast",
            "analyst_film": "reasoning",
            "analyst_scene": "reasoning",
            "style_bible": "reasoning",
            "lens": "reasoning",
            "sequence_lens": "reasoning",
            "critique": "reasoning",
            "integrator": "reasoning",
            "department": "reasoning",
            "auditor": "reasoning",
            "judge": "judge",
        }
    )
    budgets: BudgetsConfig = Field(default_factory=BudgetsConfig)
    request: RequestConfig = Field(default_factory=RequestConfig)
    pipeline: PipelineConfig = Field(default_factory=PipelineConfig)
    paths: PathsConfig = Field(default_factory=PathsConfig)
    project_root: Path = Field(default=PROJECT_ROOT, exclude=True)

    def model_for_stage(self, stage: str) -> str:
        tier = self.routing.get(stage, "reasoning")
        return self.models.for_tier(tier)

    def path(self, key: str) -> Path:
        return self.paths.resolve(key, self.project_root)


def load_config(path: str | Path | None = None, overrides: dict[str, Any] | None = None) -> PanelConfig:
    """Load ``config.yaml`` (or *path*), applying shallow ``overrides`` per top-level section."""
    cfg_path = Path(path) if path else DEFAULT_CONFIG_PATH
    data: dict[str, Any] = {}
    if cfg_path.exists():
        with cfg_path.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
    if overrides:
        for section, values in overrides.items():
            if isinstance(values, dict) and isinstance(data.get(section), dict):
                data[section] = {**data[section], **values}
            else:
                data[section] = values
    cfg = PanelConfig.model_validate(data)
    cfg.project_root = cfg_path.resolve().parent if cfg_path.exists() else PROJECT_ROOT
    return cfg
