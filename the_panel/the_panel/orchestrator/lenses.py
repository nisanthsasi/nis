"""The lens roster — who sits at the panel for a given scene, read from the Style Bible.

A lens card (``prompts/lenses/<name>.yaml``, SPEC §4.4) is a constrained prior: conviction →
decision rules → signature devices → refusals → declared blind spots. The roster holds the
cards and answers the Showrunner's two panel questions:

* **panel sizing** — full panel (primary + secondary lenses of ``style_bible.lens_affinity``)
  on load-bearing scenes, set-pieces and scenes at or above the posture's temperature
  threshold; otherwise the reduced panel — the first ``policy.reduced_panel_size`` primaries;
* **panel mix** — whether the Bible's affinity honours the posture's mix rule (SPEC §10) and
  each primary's ``posture_range``.

Cards are injectable (a dict of name → card dict) so tests never depend on the prompt files
that ship alongside; :meth:`LensRoster.from_disk` loads whatever cards exist.
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from ..prompts.loader import load_all_lens_cards
from ..schemas.scene import Scene
from ..schemas.style_bible import StyleBible
from .posture import PosturePolicy

DIRECTING_BLOCS: frozenset[str] = frozenset({"auteur", "commercial"})


class LensRoster:
    """The cards on the table and the rules for seating them."""

    def __init__(self, cards: dict[str, dict[str, Any]]):
        self.cards: dict[str, dict[str, Any]] = {name: dict(card) for name, card in cards.items()}
        self.warnings: list[str] = []

    @classmethod
    def from_disk(cls, lenses_dir: str | Path | None = None) -> "LensRoster":
        """Load every card under ``lenses_dir`` (default: the shipped ``prompts/lenses``). A missing directory is an empty roster."""
        d = Path(lenses_dir) if lenses_dir else None
        if d is not None and not d.exists():
            return cls({})
        return cls(load_all_lens_cards(lenses_dir=d))

    # --- cards -------------------------------------------------------------------
    def __contains__(self, name: str) -> bool:
        return name in self.cards

    def names(self) -> list[str]:
        return list(self.cards)

    def card(self, name: str) -> dict[str, Any]:
        """The card dict P5 / P5s / P6 render as ``lens_card``."""
        try:
            return self.cards[name]
        except KeyError:
            raise KeyError(f"lens '{name}' has no card in the roster (known: {sorted(self.cards)})") from None

    def bloc(self, name: str) -> str:
        return str(self.card(name)["bloc"])

    def is_directing(self, name: str) -> bool:
        return self.bloc(name) in DIRECTING_BLOCS

    def may_be_primary_at(self, name: str, posture: int) -> bool:
        lo, hi = self.card(name).get("posture_range", [0, 10])
        return int(lo) <= posture <= int(hi)

    def attach_dp(self, card: dict[str, Any]) -> dict[str, Any]:
        """A copy of ``card`` carrying its paired DP's ``principles`` as ``dp_principles`` (when the DP card is on the roster).

        A directing lens lights and moves by its cinematographer; the P5 template renders
        ``dp_principles`` when present and simply omits the line when it is not.
        """
        out = dict(card)
        pairing = card.get("dp_pairing")
        if pairing and pairing in self.cards:
            out["dp_principles"] = list(self.cards[pairing].get("principles", []))
        return out

    # --- panel sizing ------------------------------------------------------------
    def select_panel(self, scene: Scene, bible: StyleBible, policy: PosturePolicy) -> list[str]:
        """The active lenses for ``scene``: full panel on load-bearing scenes, set-pieces and hot scenes; reduced elsewhere."""
        full = policy.requires_full_panel(load_bearing=scene.load_bearing, set_piece=scene.set_piece, temperature=scene.emotional_temperature)
        return self.panel(bible, policy, full=full)

    def panel(self, bible: StyleBible, policy: PosturePolicy, *, full: bool) -> list[str]:
        """Full panel = primary + secondary lenses of the Bible's affinity; reduced = the first ``policy.reduced_panel_size`` primaries.

        Excluded lenses are never seated. A primary whose ``posture_range`` does not admit the
        Bible's posture keeps its seat on the full panel (the Bible is the constitution) but is
        recorded in :attr:`warnings` and yields its reduced-panel seat to in-range primaries.
        """
        excluded = {e.lens for e in bible.lens_affinity.excluded}
        primaries = self._seatable(bible.lens_affinity.primary, excluded, role="primary")
        secondaries = self._seatable(bible.lens_affinity.secondary, excluded, role="secondary")
        in_range = [n for n in primaries if self.may_be_primary_at(n, policy.posture)]
        out_of_range = [n for n in primaries if n not in in_range]
        for n in out_of_range:
            self.warnings.append(f"primary lens '{n}' posture_range {self.card(n).get('posture_range')} does not admit posture {policy.posture}")
        if full:
            return _dedupe(primaries + secondaries)
        return _dedupe(in_range + out_of_range)[: policy.reduced_panel_size]

    def _seatable(self, names: list[str], excluded: set[str], *, role: str) -> list[str]:
        seated: list[str] = []
        for name in names:
            if name in excluded:
                continue
            card = self.card(name)
            if card["bloc"] not in DIRECTING_BLOCS:
                raise ValueError(f"{role} lens '{name}' is a {card['bloc']} card — only auteur/commercial lenses sit at the panel")
            seated.append(name)
        return seated

    # --- panel mix ---------------------------------------------------------------
    def validate_affinity(self, bible: StyleBible, policy: PosturePolicy) -> list[str]:
        """Panel-mix violations in the Bible's ``lens_affinity`` for its posture (empty list = the affinity is sound).

        Checks: unknown or non-directing lenses; a lens both seated and excluded, or both primary
        and secondary; fewer primaries than the reduced panel needs; primaries outside their
        ``posture_range``; and the §10 bloc minimums (auteur/commercial among primaries and
        secondaries) resolved by :mod:`the_panel.orchestrator.posture`.
        """
        aff = bible.lens_affinity
        problems: list[str] = []
        excluded = {e.lens for e in aff.excluded}
        for role, names in (("primary", aff.primary), ("secondary", aff.secondary)):
            for n in names:
                if n not in self.cards:
                    problems.append(f"{role} lens '{n}' has no card in the roster")
                elif not self.is_directing(n):
                    problems.append(f"{role} lens '{n}' is a {self.bloc(n)} card, not a directing lens")
                if n in excluded:
                    problems.append(f"lens '{n}' is both {role} and excluded")
        for n in set(aff.primary) & set(aff.secondary):
            problems.append(f"lens '{n}' is both primary and secondary")
        known_primaries = [n for n in aff.primary if n in self.cards and self.is_directing(n) and n not in excluded]
        known_secondaries = [n for n in aff.secondary if n in self.cards and self.is_directing(n) and n not in excluded]
        if len(known_primaries) < policy.reduced_panel_size:
            problems.append(f"{len(known_primaries)} seatable primaries; the reduced panel needs {policy.reduced_panel_size}")
        for n in known_primaries:
            if not self.may_be_primary_at(n, policy.posture):
                problems.append(f"primary lens '{n}' posture_range {self.card(n).get('posture_range')} does not admit posture {policy.posture}")
        prim = Counter(self.bloc(n) for n in known_primaries)
        sec = Counter(self.bloc(n) for n in known_secondaries)
        mix = policy.panel_mix
        for label, have, need in (
            ("auteur lenses among primaries", prim["auteur"], mix.primaries_auteur_min),
            ("commercial lenses among primaries", prim["commercial"], mix.primaries_commercial_min),
            ("auteur lenses among secondaries", sec["auteur"], mix.secondaries_auteur_min),
            ("commercial lenses among secondaries", sec["commercial"], mix.secondaries_commercial_min),
        ):
            if have < need:
                problems.append(f"posture {policy.posture} ({policy.band}) needs ≥ {need} {label}; the Bible seats {have}")
        return problems


def _dedupe(names: list[str]) -> list[str]:
    seen: dict[str, None] = {}
    for n in names:
        seen.setdefault(n, None)
    return list(seen)
