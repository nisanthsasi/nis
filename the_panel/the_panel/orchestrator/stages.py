"""The pipeline's explicit state machine vocabulary."""
from __future__ import annotations

from enum import Enum


class Stage(str, Enum):
    L0_INGEST = "L0_ingest"
    L1_PARSE = "L1_parse"
    L2_UNDERSTAND = "L2_understand"
    L3_BREAKDOWN = "L3_breakdown"
    L4_STYLE_BIBLE = "L4_style_bible"
    HEADER_FROZEN = "header_frozen"
    L5_SEQUENCE_PANEL = "L5_sequence_panel"
    L5_SCENE_PANEL = "L5_scene_panel"
    L6_INTEGRATE = "L6_integrate"
    L7_DEPARTMENTS = "L7_departments"
    L8_AUDIT = "L8_audit"
    HUMAN_REVIEW = "human_review"
    PERSIST = "persist"


ORDER: tuple[Stage, ...] = tuple(Stage)


def requires(stage: Stage) -> tuple[Stage, ...]:
    """Stages that must be complete before ``stage`` may run."""
    idx = ORDER.index(stage)
    return ORDER[:idx]


class StageOrderError(RuntimeError):
    pass
