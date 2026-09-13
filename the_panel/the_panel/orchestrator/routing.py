"""Model routing: parse/breakdown → fast; understanding, lenses, integrator, auditors → reasoning."""
from __future__ import annotations

from ..config import PanelConfig

STAGES = (
    "parser",
    "analyst_film",
    "analyst_scene",
    "breakdown",
    "style_bible",
    "sequence_lens",
    "lens",
    "critique",
    "integrator",
    "department",
    "auditor",
    "judge",
)


def model_for(config: PanelConfig, stage: str) -> str:
    if stage not in STAGES:
        raise KeyError(f"unknown stage '{stage}'")
    return config.model_for_stage(stage)


def max_tokens_for(config: PanelConfig, stage: str) -> int:
    return config.budgets.max_tokens_for(stage)


def budget_for(config: PanelConfig, stage: str) -> int:
    return config.budgets.budget_for(stage)


def request_kwargs(config: PanelConfig, stage: str) -> dict:
    """Extra Messages-API kwargs for a stage. Thinking is adaptive on reasoning tiers; omitted otherwise."""
    kwargs: dict = {}
    tier = config.routing.get(stage, "reasoning")
    if tier in ("reasoning", "judge") and config.request.thinking == "adaptive":
        kwargs["thinking"] = {"type": "adaptive"}
    kwargs["output_config"] = {"effort": config.request.effort}
    return kwargs
