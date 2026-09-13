"""L4: the Style Bible (P4) — the film's constitution, proposed once and approved by the human.

Form, structure and style are decided at film level; the commercial posture on the bible is
the dial every later layer reads. This agent checks that the proposal is committed (three
governing references, a defended posture, a digest that can join the header) and that the lens
affinity seats the blocs the posture's panel mix demands.
"""
from __future__ import annotations

from collections import Counter
from typing import Any

from ..orchestrator.header import estimate_tokens
from ..orchestrator.posture import policy_for_posture
from ..prompts.loader import load_lens_card
from ..prompts.registry import (
    ALL_DIRECTING_LENSES,
    AUTEUR_EXTENSION_LENSES,
    AUTEUR_LENSES,
    COMMERCIAL_EXTENSION_LENSES,
    COMMERCIAL_LENSES,
)
from ..schemas.common import Bloc
from ..schemas.film_brief import FilmBrief
from ..schemas.style_bible import LensAffinity, StyleBible
from .analyst import field_of
from .base import BaseAgent

AUTEUR_BLOC: frozenset[str] = frozenset(AUTEUR_LENSES + AUTEUR_EXTENSION_LENSES)
COMMERCIAL_BLOC: frozenset[str] = frozenset(COMMERCIAL_LENSES + COMMERCIAL_EXTENSION_LENSES)
GOVERNING_REFERENCES = 3
PRIMARY_LENSES = 3
SECONDARY_LENSES = 2
DIGEST_MAX_TOKENS = 600

# Offline example affinities per band — satisfy the preset panel mix and every card's posture_range.
OFFLINE_AFFINITY: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "arthouse": (("ray_adoor", "bergman", "kubrick"), ("malayalam_new_wave", "wong_kar_wai")),
    "hybrid": (("inarritu", "ray_adoor", "malayalam_new_wave"), ("bergman", "bong_joon_ho")),
    "mass": (("rajamouli", "malayalam_new_wave", "spielberg"), ("ray_adoor", "mani_ratnam")),
}


def bloc_of(lens: str) -> Bloc | None:
    """Which bloc a directing lens sits in; None for a name that is not on the directing roster."""
    if lens in AUTEUR_BLOC:
        return Bloc.AUTEUR
    if lens in COMMERCIAL_BLOC:
        return Bloc.COMMERCIAL
    return None


def panel_mix_problems(affinity: LensAffinity, posture: int) -> list[str]:
    """Why a lens affinity does not seat the panel this posture demands — empty when it does.

    Reads the panel mix from the posture presets (never hardcoded), the spec's two sentence
    rules (posture ≥ 5: a commercial primary; posture ≤ 3: a commercial secondary, so the mass
    grammar still argues) and each primary card's ``posture_range``.
    """
    policy = policy_for_posture(posture)
    mix, band = policy.panel_mix, policy.band
    primary, secondary = list(affinity.primary), list(affinity.secondary)
    excluded = [e.lens for e in affinity.excluded]
    problems: list[str] = []

    unknown = sorted({n for n in primary + secondary + excluded if n not in ALL_DIRECTING_LENSES})
    if unknown:
        problems.append(f"unknown lens ids {unknown}; use roster ids only: {list(ALL_DIRECTING_LENSES)}")
    if len(primary) != PRIMARY_LENSES:
        problems.append(f"lens_affinity.primary must name exactly {PRIMARY_LENSES} lenses (got {len(primary)})")
    if len(secondary) != SECONDARY_LENSES:
        problems.append(f"lens_affinity.secondary must name exactly {SECONDARY_LENSES} lenses (got {len(secondary)})")
    repeated = sorted(n for n, c in Counter(primary + secondary + excluded).items() if c > 1)
    if repeated:
        problems.append(f"a lens sits in one seat only — repeated across primary/secondary/excluded: {repeated}")

    p_auteur = sum(1 for n in primary if n in AUTEUR_BLOC)
    p_commercial = sum(1 for n in primary if n in COMMERCIAL_BLOC)
    s_auteur = sum(1 for n in secondary if n in AUTEUR_BLOC)
    s_commercial = sum(1 for n in secondary if n in COMMERCIAL_BLOC)
    if p_auteur < mix.primaries_auteur_min:
        problems.append(f"{band} posture {posture} needs ≥ {mix.primaries_auteur_min} auteur primaries (have {p_auteur})")
    if p_commercial < mix.primaries_commercial_min:
        problems.append(f"{band} posture {posture} needs ≥ {mix.primaries_commercial_min} commercial/energy primaries (have {p_commercial})")
    if s_auteur < mix.secondaries_auteur_min:
        problems.append(f"{band} posture {posture} needs ≥ {mix.secondaries_auteur_min} auteur secondaries (have {s_auteur})")
    if s_commercial < mix.secondaries_commercial_min:
        problems.append(f"{band} posture {posture} needs ≥ {mix.secondaries_commercial_min} commercial/energy secondaries (have {s_commercial})")
    if posture >= 5 and p_commercial < 1:
        problems.append(f"posture {posture} ≥ 5 requires at least one commercial/energy lens among the primaries")
    if posture <= 3 and s_commercial < 1:
        problems.append(f"posture {posture} ≤ 3 requires at least one commercial/energy lens among the secondaries, so the mass grammar still argues")

    for n in primary:
        if n in ALL_DIRECTING_LENSES:
            lo, hi = load_lens_card(n)["posture_range"]
            if not lo <= posture <= hi:
                problems.append(f"'{n}' may not be a primary at posture {posture} (its card admits {lo}–{hi})")
    return problems


def _sequence_map(film_brief: Any) -> dict[str, list[str]]:
    sequences = field_of(film_brief, "sequences")
    return {field_of(q, "sequence_id"): list(field_of(q, "scene_ids")) for q in sequences}


def pleasure_map_problems(bible: StyleBible, film_brief: FilmBrief | dict[str, Any]) -> list[str]:
    """The pleasure map must assign every sequence of the brief exactly once, and a sequence's
    set-piece must be one of its own scenes. (A 'none' without a reason is refused by the schema.)"""
    sequences = _sequence_map(film_brief)
    if not sequences:
        return []
    problems: list[str] = []
    counts = Counter(e.sequence_id for e in bible.pleasure_map)
    missing = [sid for sid in sequences if sid not in counts]
    unknown = sorted(sid for sid in counts if sid not in sequences)
    repeated = sorted(sid for sid, n in counts.items() if n > 1)
    if missing or unknown or repeated:
        problems.append(f"pleasure_map must carry one entry per sequence — missing {missing}, unknown {unknown}, repeated {repeated}; sequences are {list(sequences)}")
    for e in bible.pleasure_map:
        if e.set_piece_scene_id and e.sequence_id in sequences and e.set_piece_scene_id not in sequences[e.sequence_id]:
            problems.append(f"{e.sequence_id}: set-piece scene {e.set_piece_scene_id} is not in that sequence ({sequences[e.sequence_id]})")
    return problems


class StyleBibleAgent(BaseAgent[StyleBible]):
    """P4 — the Form–Structure–Style architect. Output is v1.0, approved_by 'pending' until Gate 1."""

    stage = "style_bible"
    name = "style_bible"
    template = "P4_style_bible"
    output_model = StyleBible
    uses_header = False

    def check(self, parsed: StyleBible, variables: dict[str, Any]) -> None:
        """Three governing references; a defended posture; a lens affinity that seats the
        posture's panel mix; a pleasure map over the brief's sequences; a digest that states the
        posture and the caps and fits the header (≤ 600 tokens). The schema refuses more than
        three signature devices and a pleasure-map 'none' without a reason."""
        problems: list[str] = []
        if len(parsed.governing_references) != GOVERNING_REFERENCES:
            problems.append(f"exactly {GOVERNING_REFERENCES} governing references, each with the one thing borrowed and what is refused (got {len(parsed.governing_references)})")
        if not parsed.posture_defence.strip():
            problems.append("posture_defence is required: one sentence defending the commercial_posture number")
        problems += panel_mix_problems(parsed.lens_affinity, parsed.commercial_posture)
        film_brief = variables.get("film_brief")
        if film_brief is not None:
            problems += pleasure_map_problems(parsed, film_brief)
        digest = parsed.digest.strip()
        if not digest:
            problems.append("digest is required — it joins the cached Film Brief Header")
        else:
            tokens = estimate_tokens(digest)
            if tokens > DIGEST_MAX_TOKENS:
                problems.append(f"digest is ~{tokens} tokens; keep it ≤ {DIGEST_MAX_TOKENS}")
            if str(parsed.commercial_posture) not in digest:
                problems.append(f"digest must state the posture number ({parsed.commercial_posture})")
            if "cap" not in digest.lower():
                problems.append("digest must state the caps (elevation cues, slow motion, needle drops)")
        if problems:
            raise ValueError("; ".join(problems))

    def _fake_hints(self, variables: dict[str, Any]) -> dict[str, Any]:
        """Offline: a committed example bible at the hinted posture (default 5) whose affinity,
        references, caps, pleasure map and digest pass the check."""
        hints = super()._fake_hints(variables)
        hint = variables.get("posture_hint")
        posture = int(hint) if isinstance(hint, int) else 5
        policy = policy_for_posture(posture)
        primary, secondary = OFFLINE_AFFINITY[policy.band]
        caps = policy.caps
        film_brief = variables.get("film_brief")
        sequences = _sequence_map(film_brief) if film_brief is not None else {}
        hints.update(
            {
                "StyleBible.commercial_posture": posture,
                "StyleBible.approved_by": "pending",
                "LensAffinity.primary": list(primary),
                "LensAffinity.secondary": list(secondary),
                "LensAffinity.excluded": [],
                "StyleBible.governing_references": [{"film": f"reference film {i}", "borrowed": "one thing", "refused": "one thing"} for i in range(1, GOVERNING_REFERENCES + 1)],
                "StyleBible.caps": caps,
                "StyleBible.device_permissions": list(policy.device_permissions),
                "StyleBible.pleasure_map": [{"sequence_id": sid, "pleasure_type": "thrill", "set_piece_scene_id": ids[0] if ids else None} for sid, ids in sequences.items()],
                "StyleBible.digest": (
                    f"posture {posture}/10 ({policy.band}); caps: elevation {caps.elevation_cues}, slow motion {caps.slow_motion}, "
                    f"needle drops {caps.needle_drops}; permissions: {', '.join(p.device for p in policy.device_permissions)}; "
                    f"pleasure map: {', '.join(f'{sid} thrill' for sid in sequences)}"
                ),
            }
        )
        return hints
