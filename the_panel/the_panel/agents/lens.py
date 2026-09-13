"""L5: lenses — sequence-level (P5s), scene-level (P5), cross-critique (P6).

Each agent's ``check`` turns a lens's schema-valid output into a *panel-valid* one: the lens
speaks as its own card, for the scene or sequence it was asked about, every shot is tethered to
a real scene beat, every device names the beat that earns it, and a steal names a lens that is
actually at the table. A failed check is a repair instruction, retried once by ``BaseAgent``.
"""
from __future__ import annotations

import re
from typing import Any

from ..schemas.scene import Scene
from ..schemas.sequence_plan import SequenceVision
from ..schemas.vision import Critique, SceneVision
from .base import BaseAgent

# Sequence-level lenses propose shape, never shots: focal lengths and numbered shots are the tell.
SHOT_LIKE = re.compile(r"(\b\d{1,4}\s?mm\b|\bshot\s*(?:no\.?|#|\d+)\b|\bshot list\b)", re.IGNORECASE)


def card_name(variables: dict[str, Any]) -> str:
    """The lens name on the ``lens_card`` variable (a card dict, or an object with ``name``)."""
    card = variables["lens_card"]
    return str(card["name"] if isinstance(card, dict) else getattr(card, "name"))


def _field(obj: Any, name: str) -> Any:
    return obj[name] if isinstance(obj, dict) else getattr(obj, name)


def valid_beat_refs(scene: Scene) -> set[int]:
    """The beat numbers a shot may be tethered to; a scene with no beat ledger admits only beat 1."""
    return {b.n for b in scene.beats} or {1}


class SequenceLensAgent(BaseAgent[SequenceVision]):
    stage = "sequence_lens"
    name = "sequence_lens"
    template = "P5s_sequence_lens"
    output_model = SequenceVision

    def check(self, parsed: SequenceVision, variables: dict[str, Any]) -> None:
        lens = card_name(variables)
        if parsed.lens != lens:
            raise ValueError(f"lens must be '{lens}' (the card you were given), not '{parsed.lens}'")
        sequence = variables["sequence"]
        sequence_id = str(_field(sequence, "sequence_id"))
        scene_ids = [str(s) for s in _field(sequence, "scene_ids")]
        if parsed.sequence_id != sequence_id:
            raise ValueError(f"sequence_id must be '{sequence_id}', not '{parsed.sequence_id}'")
        got = [e.scene_id for e in parsed.scenes]
        missing = [s for s in scene_ids if s not in got]
        extras = [s for s in got if s not in scene_ids]
        duplicates = sorted({s for s in got if got.count(s) > 1})
        if missing or extras or duplicates:
            raise ValueError(
                f"scenes[] must carry exactly one entry per scene of sequence {sequence_id} {scene_ids}: "
                f"missing {missing}, not in sequence {extras}, duplicated {duplicates}"
            )
        for label, text in (("escalation_strategy", parsed.escalation_strategy), ("key_image", parsed.key_image), ("build_to_set_piece", parsed.build_to_set_piece), ("rationale", parsed.rationale), *[("transitions_as_meaning", t) for t in parsed.transitions_as_meaning]):
            m = SHOT_LIKE.search(text)
            if m:
                raise ValueError(f"{label} contains shot-level content ('{m.group(0)}'): Round 0 proposes the sequence's SHAPE, never shots or focal lengths")


class LensAgent(BaseAgent[SceneVision]):
    stage = "lens"
    name = "lens"
    template = "P5_lens"
    output_model = SceneVision

    def check(self, parsed: SceneVision, variables: dict[str, Any]) -> None:
        lens = card_name(variables)
        if parsed.lens != lens:
            raise ValueError(f"lens must be '{lens}' (the card you were given), not '{parsed.lens}'")
        scene: Scene = variables["scene"]
        if parsed.scene_id != scene.id:
            raise ValueError(f"scene_id must be '{scene.id}', not '{parsed.scene_id}'")
        if not 3 <= len(parsed.shots) <= 8:
            raise ValueError(f"shots must number 3–8, got {len(parsed.shots)}")
        beats = valid_beat_refs(scene)
        bad = [(s.no, s.beat_ref) for s in parsed.shots if s.beat_ref not in beats]
        if bad:
            raise ValueError(f"every shot.beat_ref must be one of the scene's beats {sorted(beats)}; offending (shot no, beat_ref): {bad}")
        unearned = [d.device for d in parsed.devices_used if not d.setup_ref.strip()]
        if unearned:
            raise ValueError(f"devices_used must each name the beat that earns them (setup_ref): {unearned}")
        offer = parsed.pleasure_offer.strip()
        if offer.lower().startswith("none") and len(offer) <= 10:
            raise ValueError("pleasure_offer 'none' is allowed only with a reason — write 'none — <why this connective scene offers no pleasure>'")
        if any(not c.strip() for c in parsed.style_bible_conflicts):
            raise ValueError("style_bible_conflicts entries must be non-empty conflict statements (use an empty list for no conflict)")


class CritiqueAgent(BaseAgent[Critique]):
    stage = "critique"
    name = "critique"
    template = "P6_critique"
    output_model = Critique

    def check(self, parsed: Critique, variables: dict[str, Any]) -> None:
        lens = card_name(variables)
        if parsed.lens != lens:
            raise ValueError(f"lens must be '{lens}' (the card you were given), not '{parsed.lens}'")
        scene: Scene = variables["scene"]
        if parsed.scene_id != scene.id:
            raise ValueError(f"scene_id must be '{scene.id}', not '{parsed.scene_id}'")
        others = {str(_field(v, "lens")) for v in variables["other_visions"]}
        if parsed.steal.from_lens == lens:
            raise ValueError("steal.from_lens must name another lens — you may not steal from your own vision")
        if parsed.steal.from_lens not in others:
            raise ValueError(f"steal.from_lens must be a lens whose vision you were shown {sorted(others)}, not '{parsed.steal.from_lens}'")
        if parsed.revised_element is not None:
            element = parsed.revised_element.strip()
            if re.search(r"[,;/&]|\band\b", element) or element not in SceneVision.model_fields:
                raise ValueError(f"revised_element must name exactly ONE SceneVision field (one of {sorted(SceneVision.model_fields)}), not '{parsed.revised_element}' — you may revise one element, never rewrite")
            if parsed.revised_value is None or not str(parsed.revised_value).strip():
                raise ValueError("revised_element is set, so revised_value must carry the new value")
