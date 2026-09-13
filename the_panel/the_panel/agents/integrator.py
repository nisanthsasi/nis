"""L6: the Integrator — scene-level (P7) and sequence-level (P7s).

``check`` holds the Integrator to the deliberation protocol: the plan is for the scene it was
asked about, both options' shots are beat-tethered, every stolen element is attributed to a
lens that actually sat on the panel, a 'none' pleasure beat is justified, a set-piece names
its trailer shot and how must_remember lands, and the shot the scene cannot live without
exists in the recommended option. Shape-level constraints the schema already enforces (two
options per human question, non-blank setup_refs, scores present, energy 0–10) are not
re-checked here — Pydantic rejects them before ``check`` runs.
"""
from __future__ import annotations

from typing import Any

from ..schemas.plan import IntegratedScenePlan, PlanOption
from ..schemas.scene import Scene
from ..schemas.sequence_plan import SequencePlan
from .base import BaseAgent
from .lens import valid_beat_refs


def _lens_of(vision: Any) -> str:
    return str(vision["lens"] if isinstance(vision, dict) else getattr(vision, "lens"))


def _device_names(option: PlanOption) -> set[str]:
    return {d.device.strip().lower() for d in option.devices_used}


class IntegratorAgent(BaseAgent[IntegratedScenePlan]):
    stage = "integrator"
    name = "integrator"
    template = "P7_integrator"
    output_model = IntegratedScenePlan

    def check(self, parsed: IntegratedScenePlan, variables: dict[str, Any]) -> None:
        scene: Scene = variables["scene"]
        if parsed.scene_id != scene.id:
            raise ValueError(f"scene_id must be '{scene.id}', not '{parsed.scene_id}'")
        if parsed.option_A.label != "A" or parsed.option_B.label != "B":
            raise ValueError("option_A.label must be 'A' and option_B.label must be 'B'")
        if parsed.recommended not in ("A", "B"):
            raise ValueError(f"recommended must be 'A' or 'B', not '{parsed.recommended}'")
        beats = valid_beat_refs(scene)
        for option in (parsed.option_A, parsed.option_B):
            bad = [(s.no, s.beat_ref) for s in option.shots if s.beat_ref not in beats]
            if bad:
                raise ValueError(f"option_{option.label}: every shot.beat_ref must be one of the scene's beats {sorted(beats)}; offending (shot no, beat_ref): {bad}")
        panel = {_lens_of(v) for v in variables["visions"]}
        strangers = sorted({c.lens for c in parsed.contributions} - panel)
        if strangers:
            raise ValueError(f"contributions may only attribute lenses that sat on this panel {sorted(panel)}; unknown: {strangers}")
        if parsed.pleasure_beat.strip().lower().startswith("none") and not (parsed.pleasure_none_reason or "").strip():
            raise ValueError("pleasure_beat 'none' requires pleasure_none_reason justified against the pleasure map")
        if scene.set_piece and not ((parsed.trailer_shot or "").strip() and (parsed.must_remember_delivery or "").strip()):
            raise ValueError(f"{scene.id} is a set-piece: name trailer_shot and must_remember_delivery (how '{scene.must_remember}' lands)")
        recommended = parsed.option(parsed.recommended)
        shot_nos = {s.no for s in recommended.shots}
        if parsed.the_shot_it_cannot_live_without.shot_no not in shot_nos:
            raise ValueError(f"the_shot_it_cannot_live_without.shot_no must be a shot of the recommended option {parsed.recommended} {sorted(shot_nos)}, not {parsed.the_shot_it_cannot_live_without.shot_no}")
        plan_devices = {d.device.strip().lower() for d in parsed.devices_used}
        option_devices = _device_names(recommended)
        if plan_devices != option_devices:
            raise ValueError(f"devices_used must carry exactly the recommended option's devices {sorted(option_devices)} (with their setup refs), got {sorted(plan_devices)}")


class SequenceIntegratorAgent(BaseAgent[SequencePlan]):
    stage = "integrator"
    name = "sequence_integrator"
    template = "P7s_sequence_integrator"
    output_model = SequencePlan

    def check(self, parsed: SequencePlan, variables: dict[str, Any]) -> None:
        sequence = variables["sequence"]
        sequence_id = str(sequence["sequence_id"] if isinstance(sequence, dict) else sequence.sequence_id)
        scene_ids = [str(s) for s in (sequence["scene_ids"] if isinstance(sequence, dict) else sequence.scene_ids)]
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
        set_pieces = [e.scene_id for e in parsed.scenes if e.set_piece]
        if len(set_pieces) > 1:
            raise ValueError(f"a sequence builds to ONE set-piece; {set_pieces} are all flagged — keep the pleasure map's and raise a human_question for the rest")
        entry = variables.get("pleasure_map_entry")
        mapped = entry["set_piece_scene_id"] if isinstance(entry, dict) else getattr(entry, "set_piece_scene_id", None)
        if mapped in scene_ids and mapped not in set_pieces and not parsed.human_questions:
            raise ValueError(f"the pleasure map designates {mapped} as this sequence's set-piece: flag it set_piece=true, or keep the map and raise a human_question explaining the lens that argued otherwise")
        if parsed.temperature_curve and len(parsed.temperature_curve) != len(scene_ids):
            raise ValueError(f"temperature_curve must carry one value per scene ({len(scene_ids)}), got {len(parsed.temperature_curve)}")
