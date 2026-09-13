"""Shared enums and small value types used across every layer.

Every stage speaks schema: these are the words the pipeline agrees on.
"""
from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StrEnum(str, Enum):
    def __str__(self) -> str:  # pragma: no cover - trivial
        return str(self.value)


class IntExt(StrEnum):
    INT = "INT"
    EXT = "EXT"
    INT_EXT = "INT/EXT"


class DayNight(StrEnum):
    DAY = "DAY"
    NIGHT = "NIGHT"
    DAWN = "DAWN"
    DUSK = "DUSK"
    CONTINUOUS = "CONTINUOUS"
    LATER = "LATER"
    UNKNOWN = "UNKNOWN"


class Rasa(StrEnum):
    """The nine rasas of the Natyashastra — the film's emotional taxonomy."""

    SHRINGARA = "shringara"  # love / beauty
    HASYA = "hasya"  # laughter
    KARUNA = "karuna"  # sorrow / compassion
    RAUDRA = "raudra"  # fury
    VEERA = "veera"  # heroism
    BHAYANAKA = "bhayanaka"  # terror
    BIBHATSA = "bibhatsa"  # disgust
    ADBHUTA = "adbhuta"  # wonder
    SHANTA = "shanta"  # peace


class PleasureType(StrEnum):
    THRILL = "thrill"
    LAUGHTER = "laughter"
    TEARS = "tears"
    AWE = "awe"
    ROMANCE = "romance"
    ELEVATION = "elevation"
    DREAD = "dread"
    WONDER = "wonder"
    NONE = "none"


class CostFlag(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class StructureModel(StrEnum):
    THREE_ACT = "three_act"
    FIVE_ACT = "five_act"
    EIGHT_SEQUENCE = "eight_sequence"
    KISHOTENKETSU = "kishotenketsu"
    BRAIDED = "braided"
    OTHER = "other"


class ReleaseTarget(StrEnum):
    THEATRICAL = "theatrical"
    OTT = "ott"
    BOTH = "both"


class BudgetTier(StrEnum):
    MICRO = "micro"
    LOW = "low"
    MID = "mid"
    STUDIO = "studio"


class CoverageTier(StrEnum):
    FULL = "full"
    TWO_SHOT = "two_shot"
    MONTAGE = "montage"


class CoverageApproach(StrEnum):
    ONER = "oner"
    MASTER_COVERAGE = "master+coverage"
    MONTAGE = "montage"
    HYBRID = "hybrid"


class MusicPermission(StrEnum):
    SCORE = "score"
    DIEGETIC_ONLY = "diegetic_only"
    SILENCE = "silence"
    BGM_ELEVATION = "bgm_elevation"
    SONG = "song"


class ShotSize(StrEnum):
    ECU = "ECU"
    CU = "CU"
    MCU = "MCU"
    MS = "MS"
    MLS = "MLS"
    LS = "LS"
    WS = "WS"
    EWS = "EWS"
    TWO_SHOT = "2S"
    OTS = "OTS"
    INSERT = "INSERT"


class ProductionFlag(StrEnum):
    RAIN = "rain"
    NIGHT_EXT = "night_ext"
    CROWD = "crowd"
    STUNT = "stunt"
    VFX = "vfx"
    MINOR = "minor"
    ANIMAL = "animal"
    VEHICLE = "vehicle"
    SONG = "song"
    CHOREOGRAPHY = "choreography"
    WATER = "water"
    HEIGHT = "height"
    WEATHER = "weather"


class Register(StrEnum):
    LITERARY = "literary"
    COLLOQUIAL = "colloquial"
    REGIONAL = "regional"
    CODE_SWITCHED = "code_switched"
    UNKNOWN = "unknown"


class Severity(StrEnum):
    BLOCK = "BLOCK"
    WARN = "WARN"
    NOTE = "NOTE"


class RAG(StrEnum):
    RED = "RED"
    AMBER = "AMBER"
    GREEN = "GREEN"


class DeviceVerdict(StrEnum):
    EARNED = "EARNED"
    UNEARNED = "UNEARNED"
    OVER_CAP = "OVER_CAP"
    NOT_PERMITTED = "NOT_PERMITTED"


class Bloc(StrEnum):
    AUTEUR = "auteur"
    COMMERCIAL = "commercial"


class SetPieceKind(StrEnum):
    HERO_ENTRY = "hero_entry"
    ACTION = "action"
    COMEDY_RUN = "comedy_run"
    SONG = "song"
    INTERVAL = "interval"
    TEARJERKER = "tearjerker"
    ELEVATION = "elevation"
    OTHER = "other"


class Verdict(StrEnum):
    KEEP = "KEEP"
    TRIM = "TRIM"
    MERGE = "MERGE"
    REWRITE = "REWRITE"
    CUT = "CUT"


class Department(StrEnum):
    CINEMATOGRAPHY = "cinematography"
    EDITING = "editing"
    COLOUR = "colour"
    MUSIC = "music"
    SOUND = "sound"
    DESIGN = "design"
    PERFORMANCE = "performance"


PostureBand = Literal["arthouse", "hybrid", "mass"]


def posture_band(posture: int) -> PostureBand:
    """0–3 arthouse · 4–6 hybrid · 7–10 mass."""
    if posture <= 3:
        return "arthouse"
    if posture <= 6:
        return "hybrid"
    return "mass"


class HumanQuestion(BaseModel):
    """Raised whenever an agent must not guess. Two concrete options; continue with the conservative one."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(description="Stable id, e.g. HQ-<scene>-<n>")
    scene_id: str | None = None
    raised_by: str = Field(description="agent/lens/stage that raised it")
    question: str
    options: list[str] = Field(min_length=2, max_length=2)
    conservative_option: int = Field(ge=0, le=1, description="index of the option the system proceeds with")
    rationale: str = ""


class Usage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0

    def __add__(self, other: "Usage") -> "Usage":
        return Usage(
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            cache_creation_input_tokens=self.cache_creation_input_tokens + other.cache_creation_input_tokens,
            cache_read_input_tokens=self.cache_read_input_tokens + other.cache_read_input_tokens,
        )
