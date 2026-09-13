"""L2: film-level (P2a) and scene-level (P2b) dramatic analysis.

Understanding precedes vision. P2a reads the whole script as a doctor and writes the FilmBrief
(structure model, load-bearing beats, sequence map, character engine, set-piece candidates,
pleasure gaps); P2b fills one Scene Report Card per scene — the must_feel the panel directs
toward, the pleasure it delivers, a set-piece's must_remember, the load-bearing flag that sizes
the panel. Neither carries a shot decision: the Scene schema is guarded at import.
"""
from __future__ import annotations

from collections import Counter
from typing import Any

from pydantic import BaseModel

from ..schemas.common import PleasureType
from ..schemas.film_brief import FilmBrief
from ..schemas.scene import Scene, assert_no_shot_fields
from .base import BaseAgent

assert_no_shot_fields(Scene)

HUMAN_DIGEST_MAX_WORDS = 250
LOAD_BEARING_TEMPERATURE = 8  # P2b: temperature ≥ 8 is load-bearing; the stage runner passes config's threshold


def field_of(item: Any, name: str) -> Any:
    """Read a field from a schema instance or its dumped dict — agents see whatever the caller passed."""
    return item[name] if isinstance(item, dict) else getattr(item, name)


def enum_value(v: Any) -> Any:
    """The string behind an enum member (or the string itself)."""
    return getattr(v, "value", v)


def scene_ids_of(scenes: Any) -> list[str]:
    """Ids of the scenes an agent was given — a ParsedScript, a list of models or of dumped dicts."""
    if isinstance(scenes, BaseModel) and hasattr(scenes, "scenes"):
        scenes = scenes.scenes
    elif isinstance(scenes, dict) and "scenes" in scenes:
        scenes = scenes["scenes"]
    return [field_of(s, "id") for s in scenes]


class FilmAnalystAgent(BaseAgent[FilmBrief]):
    """P2a — the dramaturg's whole-script diagnosis, the FilmBrief every later layer reads."""

    stage = "analyst_film"
    name = "analyst_film"
    template = "P2a_film"
    output_model = FilmBrief
    uses_header = False

    def check(self, parsed: FilmBrief, variables: dict[str, Any]) -> None:
        """Every scene id the brief points at must exist; sequences must partition the script;
        the theme audit is mandatory; a set-piece candidate names its pleasure; the digest is
        ≤ 250 words; release target and budget tier are inputs, not diagnoses."""
        scene_ids = scene_ids_of(variables["scenes"])
        valid = set(scene_ids)
        problems: list[str] = []

        referenced: list[tuple[str, str | None]] = [(f"load_bearing_beats[{b.name}]", b.scene_id) for b in parsed.load_bearing_beats]
        referenced += [(f"set_piece_candidates[{c.kind.value}]", c.scene_id) for c in parsed.set_piece_candidates]
        referenced += [(f"sequences[{q.sequence_id}]", sid) for q in parsed.sequences for sid in q.scene_ids]
        if parsed.mechanism is not None:
            referenced += [("mechanism.execution_scene_ids", sid) for sid in parsed.mechanism.execution_scene_ids]
        referenced += [(f"plants_payoffs[{p.item}]", sid) for p in parsed.plants_payoffs for sid in (p.plant_scene_id, p.payoff_scene_id)]
        referenced += [(f"star_cast[{s.character}]", s.entry_scene_id) for s in parsed.star_cast]
        referenced += [("pleasure_gaps", sid) for g in parsed.pleasure_gaps for sid in (g.from_scene_id, g.to_scene_id)]
        dangling = sorted({f"{where}→{sid}" for where, sid in referenced if sid is not None and sid not in valid})
        if dangling:
            problems.append(f"scene ids that do not exist in the script: {dangling}; the only valid ids are {scene_ids}")

        counts = Counter(sid for q in parsed.sequences for sid in q.scene_ids)
        missing = [sid for sid in scene_ids if sid not in counts]
        repeated = sorted(sid for sid, n in counts.items() if n > 1 and sid in valid)
        if missing or repeated:
            problems.append(f"sequences must cover every scene exactly once — not covered {missing}, covered twice {repeated}")
        seq_ids = [q.sequence_id for q in parsed.sequences]
        if len(set(seq_ids)) != len(seq_ids):
            problems.append(f"sequence_id values must be unique (got {seq_ids})")

        audit = parsed.theme_audit
        if not (audit.dramatised or audit.silent or audit.preaches):
            problems.append("theme_audit is mandatory: say where the theme is dramatised, where it goes silent, where it preaches")

        for c in parsed.set_piece_candidates:
            if c.pleasure_type == PleasureType.NONE:
                problems.append(f"set-piece candidate {c.scene_id} ({c.kind.value}) must name the pleasure it offers — a set-piece with 'none' is not a set-piece")

        words = len(parsed.human_digest.split())
        if words > HUMAN_DIGEST_MAX_WORDS:
            problems.append(f"human_digest is {words} words; keep it ≤ {HUMAN_DIGEST_MAX_WORDS}")

        release = enum_value(variables.get("release_target"))
        if release and parsed.release_target.value != release:
            problems.append(f"release_target is an input, not a diagnosis: it must be '{release}'")
        tier = enum_value(variables.get("budget_tier"))
        if tier and parsed.budget_tier.value != tier:
            problems.append(f"budget_tier is an input, not a diagnosis: it must be '{tier}'")

        if problems:
            raise ValueError("; ".join(problems))

    def _fake_hints(self, variables: dict[str, Any]) -> dict[str, Any]:
        """Offline: every id the example brief points at is a real scene, so the check passes."""
        hints = super()._fake_hints(variables)
        ids = scene_ids_of(variables["scenes"])
        if ids:
            hints.update(
                {
                    "scene_id": ids[0],
                    "SequenceEntry.scene_ids": list(ids),
                    "Mechanism.execution_scene_ids": [ids[0]],
                    "PlantPayoff.plant_scene_id": ids[0],
                    "PlantPayoff.payoff_scene_id": ids[-1],
                    "StarCastEntry.entry_scene_id": ids[0],
                    "PleasureGap.from_scene_id": ids[0],
                    "PleasureGap.to_scene_id": ids[-1],
                }
            )
        release = enum_value(variables.get("release_target"))
        if release:
            hints["FilmBrief.release_target"] = release
        tier = enum_value(variables.get("budget_tier"))
        if tier:
            hints["FilmBrief.budget_tier"] = tier
        return hints


class SceneAnalystAgent(BaseAgent[Scene]):
    """P2b — one Scene Report Card, writer's hat and director's hat kept separate, no shots."""

    stage = "analyst_scene"
    name = "analyst_scene"
    template = "P2b_scene"
    output_model = Scene
    uses_header = True

    def check(self, parsed: Scene, variables: dict[str, Any]) -> None:
        """Identity is unchanged from the skeleton; beats are 1..n with one tension value each;
        rasa and must_feel are present; a set-piece names its kind and its pleasure (the schema
        already refuses a set-piece without must_remember, which reaches the repair path as a
        validation error)."""
        skeleton = variables["scene"]
        sid, number = field_of(skeleton, "id"), field_of(skeleton, "number")
        problems: list[str] = []
        if parsed.id != sid or parsed.number != number:
            problems.append(f"id and number must be unchanged from the skeleton: id '{sid}', number {number} (got '{parsed.id}', {parsed.number})")
        numbering = [b.n for b in parsed.beats]
        if numbering != list(range(1, len(numbering) + 1)):
            problems.append(f"beats must be numbered 1..{len(numbering)} consecutively without gaps (got {numbering})")
        if parsed.beats and parsed.tension_curve and len(parsed.tension_curve) != len(parsed.beats):
            problems.append(f"tension_curve needs exactly one 0–10 value per beat ({len(parsed.beats)} beats, {len(parsed.tension_curve)} values)")
        if "rasa" not in parsed.model_fields_set:
            problems.append("rasa is required: primary (and secondary) from the Natyashastra nine")
        if not parsed.must_feel.strip():
            problems.append("must_feel is required — the one sentence the panel will direct toward")
        if parsed.set_piece:
            if parsed.set_piece_kind is None:
                problems.append("a set-piece names its set_piece_kind (hero_entry | action | comedy_run | song | interval | tearjerker | elevation | other)")
            if parsed.pleasure_type == PleasureType.NONE:
                problems.append("a set-piece delivers a pleasure; pleasure_type cannot be 'none' when set_piece is true")
        if problems:
            raise ValueError("; ".join(problems))

    def _fake_hints(self, variables: dict[str, Any]) -> dict[str, Any]:
        """Offline: the example report card keeps the skeleton's identity."""
        hints = super()._fake_hints(variables)
        skeleton = variables.get("scene")
        if skeleton is not None:
            hints.update({"Scene.id": field_of(skeleton, "id"), "Scene.number": field_of(skeleton, "number"), "Scene.slug": field_of(skeleton, "slug")})
        return hints


def apply_film_flags(scene: Scene, film_brief: FilmBrief, *, temperature_threshold: int = LOAD_BEARING_TEMPERATURE) -> Scene:
    """Make a Scene Report Card agree with the film-level facts P2b cannot see.

    P2b runs with only the cached header, so the flags the FilmBrief owns are enforced here,
    after the call: ``load_bearing`` is True when the scene is a load-bearing beat, a
    mechanism-execution scene, or its emotional temperature reaches the full-panel threshold;
    ``sequence_id`` comes from the brief's sequence map. A set-piece candidate the scene
    analyst did not confirm is raised to the human as a director note (the panel sizes on
    ``set_piece``) — never flipped silently. Mutates and returns ``scene``.
    """
    if scene.id in film_brief.load_bearing_scene_ids() or scene.emotional_temperature >= temperature_threshold:
        scene.load_bearing = True
    sequence_id = film_brief.sequence_for(scene.id)
    if sequence_id is not None:
        scene.sequence_id = sequence_id
    candidate = next((c for c in film_brief.set_piece_candidates if c.scene_id == scene.id), None)
    if candidate is not None and not scene.set_piece:
        note = (
            f"HUMAN_QUESTION: film-level analysis lists this scene as a {candidate.kind.value} set-piece candidate "
            f"({candidate.pleasure_type.value}) but scene analysis did not confirm set_piece — "
            f"(a) confirm it as a set-piece: full panel, must_remember, costed; (b) keep it a {scene.pleasure_type.value} scene. Proceeding with (b)."
        )
        if note not in scene.director_notes:
            scene.director_notes.append(note)
    return scene
