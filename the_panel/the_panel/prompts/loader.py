"""Lens-card loader and validator.

A lens is a constrained prior — conviction → decision rules → signature devices → refusals →
declared blind spots — never an impersonation. Cards live in ``prompts/lenses/<name>.yaml`` in
the §4.4 format; every roster name in :mod:`the_panel.prompts.registry` must have one. The lens
agents load a card here and hand it to P5 / P5s / P6 as ``lens_card``.
"""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .registry import (
    ALL_DIRECTING_LENSES,
    AUTEUR_EXTENSION_LENSES,
    AUTEUR_LENSES,
    COMMERCIAL_EXTENSION_LENSES,
    COMMERCIAL_LENSES,
    CRAFT_LENSES,
    DP_LENSES,
    LENSES_DIR,
)

LensBloc = Literal["auteur", "commercial", "dp", "craft"]

BASIS_PREFIX = "craft principles associated with"
NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")

# Text that would turn a prior into a costume: attributed quotes and anecdotes.
IMPERSONATION_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"once said", re.IGNORECASE),
    re.compile(r"\"\s*[—–-]{1,2}\s*[A-Z][a-z]+"),  # "…" — Name
    re.compile(r"\bas (?:he|she|they) (?:put it|would say|said)\b", re.IGNORECASE),
    re.compile(r"\bi remember\b", re.IGNORECASE),
)

ROSTER_BLOC: dict[str, LensBloc] = {
    **{n: "auteur" for n in AUTEUR_LENSES + AUTEUR_EXTENSION_LENSES},
    **{n: "commercial" for n in COMMERCIAL_LENSES + COMMERCIAL_EXTENSION_LENSES},
    **{n: "dp" for n in DP_LENSES},
    **{n: "craft" for n in CRAFT_LENSES},
}


class DecisionRule(BaseModel):
    """``when`` a dramatic situation arises, ``do`` this — the unit of a lens's prior."""

    model_config = ConfigDict(extra="forbid")

    when: str = Field(min_length=1)
    do: str = Field(min_length=1)


class LensCard(BaseModel):
    """The §4.4 card format. Directing lenses pair with a DP card; DP and craft cards carry ``principles``."""

    model_config = ConfigDict(extra="forbid")

    name: str
    bloc: LensBloc
    filmmaker_basis: str = Field(description="'craft principles associated with X's films' — principles, never biography")
    conviction: str = Field(min_length=1)
    decision_rules: list[DecisionRule] = Field(min_length=1)
    signature_devices: list[str] = Field(min_length=1)
    refusals: list[str] = Field(min_length=1)
    blind_spots: list[str] = Field(min_length=1)
    dp_pairing: str | None = Field(default=None, description="directing lenses only: a DP card name")
    best_for: list[str] = Field(min_length=1)
    posture_range: list[int] = Field(min_length=2, max_length=2, description="[lo, hi] postures at which this lens may be primary")
    principles: list[str] = Field(default_factory=list, description="DP and craft cards: the principles the lens applies")
    slate_fit: str | None = Field(default=None, description="which project on the slate this lens serves, if any")

    @field_validator("name")
    @classmethod
    def _snake_name(cls, v: str) -> str:
        if not NAME_RE.match(v):
            raise ValueError(f"card name '{v}' must be a snake_case id matching the roster")
        return v

    @field_validator("filmmaker_basis")
    @classmethod
    def _principles_not_biography(cls, v: str) -> str:
        if not v.lower().startswith(BASIS_PREFIX):
            raise ValueError(f"filmmaker_basis must begin '{BASIS_PREFIX} …' — principles, never a person")
        return v

    @field_validator("posture_range")
    @classmethod
    def _range_0_10(cls, v: list[int]) -> list[int]:
        lo, hi = v
        if not (0 <= lo <= 10 and 0 <= hi <= 10):
            raise ValueError("posture_range values must be 0–10")
        if lo > hi:
            raise ValueError("posture_range must be [lo, hi] with lo ≤ hi")
        return v

    @model_validator(mode="after")
    def _bloc_shape(self) -> "LensCard":
        directing = self.bloc in ("auteur", "commercial")
        if directing and not self.dp_pairing:
            raise ValueError(f"{self.name}: directing lenses must name a dp_pairing")
        if directing and self.dp_pairing not in DP_LENSES:
            raise ValueError(f"{self.name}: dp_pairing '{self.dp_pairing}' is not a DP card in the roster")
        if not directing and self.dp_pairing:
            raise ValueError(f"{self.name}: only directing lenses carry dp_pairing")
        if not directing and not self.principles:
            raise ValueError(f"{self.name}: DP and craft cards must list principles")
        for text in self._all_text():
            for pat in IMPERSONATION_PATTERNS:
                if pat.search(text):
                    raise ValueError(f"{self.name}: card text reads as an attributed quote or anecdote ({pat.pattern!r}) — a lens is a prior, not a costume")
        return self

    def _all_text(self) -> list[str]:
        out = [self.filmmaker_basis, self.conviction, *self.signature_devices, *self.refusals, *self.blind_spots, *self.best_for, *self.principles]
        out += [f"{r.when} {r.do}" for r in self.decision_rules]
        if self.slate_fit:
            out.append(self.slate_fit)
        return out

    @property
    def is_directing(self) -> bool:
        return self.bloc in ("auteur", "commercial")

    def may_be_primary_at(self, posture: int) -> bool:
        lo, hi = self.posture_range
        return lo <= posture <= hi


def card_path(name: str, lenses_dir: Path | None = None) -> Path:
    return (lenses_dir or LENSES_DIR) / f"{name}.yaml"


@lru_cache(maxsize=128)
def _read_card(path: str) -> LensCard:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"no lens card at {p}")
    with p.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    card = LensCard.model_validate(data)
    if card.name != p.stem:
        raise ValueError(f"lens card {p.name} declares name '{card.name}' — file stem and name must match")
    return card


def load_lens_card(name: str, *, with_dp_principles: bool = False, lenses_dir: Path | None = None) -> dict:
    """Load one card as the ``lens_card`` dict P5 / P5s / P6 render.

    With ``with_dp_principles`` a directing lens also carries ``dp_principles`` copied from its
    paired DP card, so the lens lights and moves by its cinematographer's principles.
    """
    card = _read_card(str(card_path(name, lenses_dir)))
    data = card.model_dump(mode="json")
    if with_dp_principles and card.dp_pairing:
        dp = _read_card(str(card_path(card.dp_pairing, lenses_dir)))
        data["dp_principles"] = list(dp.principles)
    return data


def load_all_lens_cards(*, lenses_dir: Path | None = None) -> dict[str, dict]:
    """Every card on disk, by name — the Showrunner's roster for panel sizing and affinity checks."""
    d = lenses_dir or LENSES_DIR
    return {p.stem: load_lens_card(p.stem, lenses_dir=d) for p in sorted(d.glob("*.yaml"))}


def validate_all_cards(*, lenses_dir: Path | None = None) -> dict[str, LensCard]:
    """Validate every roster name has a card whose bloc matches its roster; raise on the first failure."""
    problems: list[str] = []
    cards: dict[str, LensCard] = {}
    for name, bloc in ROSTER_BLOC.items():
        try:
            card = _read_card(str(card_path(name, lenses_dir)))
        except (FileNotFoundError, ValueError) as e:
            problems.append(str(e))
            continue
        if card.bloc != bloc:
            problems.append(f"{name}: roster says bloc '{bloc}', card says '{card.bloc}'")
        cards[name] = card
    for card in cards.values():
        if card.is_directing and card.dp_pairing not in cards:
            problems.append(f"{card.name}: dp_pairing '{card.dp_pairing}' has no card")
    if problems:
        raise ValueError("lens cards invalid:\n- " + "\n- ".join(problems))
    return cards


def directing_cards_for_posture(posture: int, *, lenses_dir: Path | None = None) -> list[str]:
    """Directing lenses whose posture_range admits ``posture`` as a primary — feeds P4's lens-affinity check."""
    cards = validate_all_cards(lenses_dir=lenses_dir)
    return [n for n in ALL_DIRECTING_LENSES if cards[n].may_be_primary_at(posture)]
