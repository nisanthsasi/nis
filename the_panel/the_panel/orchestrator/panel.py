"""The Panel — Rounds 0–3 of the deliberation protocol (SPEC §5 P6), sequence-level then scene-level.

Round 0 shapes a sequence (SequenceVisions → SequencePlan): energy curve, pleasure placement,
set-piece designation, coverage tiers. Only then may a scene be directed: Round 1 runs the
active lenses in parallel with no lens seeing another's output; Round 2 lets each lens steal,
declare its risk and name a conflict; Round 3 hands the Integrator the visions, the critiques,
the posture's rubric weights, the cap ledger and the anti-groupthink hints. The Panel then
weights the scores, applies the consensus-device penalty, ranks A and B, raises the
HUMAN_QUESTIONs Gate 3 needs, and spends caps — never silently. Never the reverse order:
:class:`StageOrderError` guards it.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from ..agents.base import AgentContext, AgentResult
from ..agents.integrator import IntegratorAgent, SequenceIntegratorAgent
from ..agents.lens import CritiqueAgent, LensAgent, SequenceLensAgent
from ..schemas.breakdown import SceneConstraints
from ..schemas.common import ReleaseTarget, Usage
from ..schemas.film_brief import SequenceEntry
from ..schemas.plan import IntegratedScenePlan, ResonanceScore
from ..schemas.scene import Scene
from ..schemas.sequence_plan import SequencePlan
from ..schemas.style_bible import PleasureMapEntry, StyleBible
from ..schemas.vision import Critique, SceneVision
from ..store.db import ARTIFACT_CRITIQUE, ARTIFACT_PLAN, ARTIFACT_SEQUENCE_PLAN, ARTIFACT_VISION, PanelDB
from .caps import CapLedger
from .lenses import LensRoster
from .posture import PosturePolicy, policy_for
from .scoring import (
    apply_consensus_penalty,
    blocked_devices,
    detect_consensus_devices,
    lone_high_engagement,
    lone_high_fidelity,
    needs_human_question,
    normalise_device,
    normalise_text,
    prescore_panel,
    recommend,
)
from .stages import StageOrderError

log = logging.getLogger("the_panel.orchestrator.panel")

SNAPSHOT_SEQUENCE_PLAN = "sequence_plan"
SNAPSHOT_PLAN = "plan"


class Panel:
    """The deliberation over one film's Style Bible: lenses, critiques, integrator, scoring, caps.

    ``ctx`` carries the model client, the cached Film Brief Header and the snapshot store;
    ``bible`` is the constitution every dial is read from (``policy`` defaults to
    :func:`policy_for` on it); ``roster`` defaults to the shipped lens cards; ``ledger`` to a
    fresh cap ledger on the Bible's caps; ``db`` mirrors calls, artifacts and the ledger when given.

    Token accounting: ``usage[<scene or sequence id>]`` sums every lens, critique and integrator
    call of that run; ``over_budget_calls`` lists ``"<agent>:<key>"`` for calls whose output
    tokens exceeded the stage budget in ``config.yaml`` (``strict_budgets`` makes them raise).
    """

    def __init__(
        self,
        ctx: AgentContext,
        bible: StyleBible,
        *,
        policy: PosturePolicy | None = None,
        roster: LensRoster | None = None,
        ledger: CapLedger | None = None,
        db: PanelDB | None = None,
        release_target: ReleaseTarget | str = ReleaseTarget.BOTH,
    ):
        self.ctx = ctx
        self.bible = bible
        self.policy = policy or policy_for(bible)
        self.roster = roster or LensRoster.from_disk(ctx.config.path("lenses"))
        self.ledger = ledger or CapLedger(self.policy.caps)
        self.db = db
        self.release_target = ReleaseTarget(release_target)
        self.sequence_plans: dict[str, SequencePlan] = {}
        self.visions: dict[str, dict[str, SceneVision]] = {}
        self.critiques: dict[str, dict[str, Critique]] = {}
        self.prescores: dict[str, dict[str, ResonanceScore]] = {}
        self.plans: dict[str, IntegratedScenePlan] = {}
        self.usage: dict[str, Usage] = {}
        self.over_budget_calls: list[str] = []

    # --- panel sizing ------------------------------------------------------------
    def panel_size_for(self, scene: Scene) -> str:
        """``"full"`` on load-bearing scenes, set-pieces and hot scenes (posture threshold); ``"reduced"`` elsewhere."""
        full = self.policy.requires_full_panel(load_bearing=scene.load_bearing, set_piece=scene.set_piece, temperature=scene.emotional_temperature)
        return "full" if full else "reduced"

    def active_lenses(self, scene: Scene) -> list[str]:
        return self.roster.select_panel(scene, self.bible, self.policy)

    def active_lenses_for_sequence(self, scenes: list[Scene], pleasure_map_entry: PleasureMapEntry) -> list[str]:
        """Round 0 seats the full panel when any scene of the sequence would, or when the pleasure map places a set-piece here."""
        full = any(self.panel_size_for(s) == "full" for s in scenes) or pleasure_map_entry.set_piece_scene_id in {s.id for s in scenes}
        return self.roster.panel(self.bible, self.policy, full=full)

    # --- Round 0 ---------------------------------------------------------------
    async def run_sequence(self, sequence: SequenceEntry, scenes: list[Scene], pleasure_map_entry: PleasureMapEntry | None = None) -> SequencePlan:
        """Round 0: SequenceVisions from every active lens in parallel, merged by the sequence Integrator into the SequencePlan.

        The plan's energy_target, pleasure_type and set_piece are applied back onto the Scene
        objects — a set-piece without a must_remember is not flipped but raised as a human
        question on the plan. The plan is remembered so scene-level work may begin.
        """
        by_id = {s.id: s for s in scenes}
        missing = [sid for sid in sequence.scene_ids if sid not in by_id]
        if missing:
            raise ValueError(f"run_sequence({sequence.sequence_id}): Scene objects missing for {missing}")
        seq_scenes = [by_id[sid] for sid in sequence.scene_ids]
        entry = pleasure_map_entry or next((e for e in self.bible.pleasure_map if e.sequence_id == sequence.sequence_id), None)
        if entry is None:
            raise ValueError(f"sequence {sequence.sequence_id} has no pleasure map entry in the Style Bible — P4 assigns every sequence a pleasure (or 'none' with a reason)")
        active = self.active_lenses_for_sequence(seq_scenes, entry)
        common = dict(sequence=sequence, pleasure_map_entry=entry, style_bible=self.bible, release_target=self.release_target.value)
        vision_results: list[AgentResult[Any]] = list(
            await asyncio.gather(*(SequenceLensAgent(self.ctx).run(key=f"{sequence.sequence_id}/{lens}", lens_card=self.roster.attach_dp(self.roster.card(lens)), **common) for lens in active))
        )
        merge = await SequenceIntegratorAgent(self.ctx).run(
            key=sequence.sequence_id,
            sequence_visions=[r.parsed for r in vision_results],
            sequence=sequence,
            style_bible=self.bible,
            pleasure_map_entry=entry,
        )
        plan: SequencePlan = merge.parsed
        self._apply_sequence_plan(plan, by_id)
        self.sequence_plans[sequence.sequence_id] = plan
        self._account(sequence.sequence_id, [*vision_results, merge])
        if self.ctx.store is not None:
            self.ctx.store.save(SNAPSHOT_SEQUENCE_PLAN, sequence.sequence_id, plan, meta={"lenses": active, "usage": self.usage[sequence.sequence_id].model_dump()})
        if self.db is not None:
            for r in [*vision_results, merge]:
                self.db.record_call(r)
            self.db.save_artifact(ARTIFACT_SEQUENCE_PLAN, sequence.sequence_id, plan)
        return plan

    def _apply_sequence_plan(self, plan: SequencePlan, by_id: dict[str, Scene]) -> None:
        for e in plan.scenes:
            scene = by_id[e.scene_id]
            scene.energy_target = e.energy_target
            scene.pleasure_type = e.pleasure_type
            if e.set_piece and not scene.set_piece:
                if scene.must_remember and scene.must_remember.strip():
                    scene.set_piece = True
                else:
                    plan.human_questions.append(
                        f"HQ: the sequence plan makes {scene.id} the set-piece but the scene has no must_remember. "
                        f"(1) Write the must_remember — the moment the audience will describe to a friend — and flag {scene.id}; "
                        f"(2) keep {scene.id} unflagged and place the set-piece elsewhere. Proceeding with (2)."
                    )
            elif scene.set_piece and not e.set_piece:
                plan.human_questions.append(
                    f"HQ: scene analysis flags {scene.id} as a set-piece ('{scene.must_remember}') but the sequence plan does not. "
                    f"(1) Keep {scene.id} as a set-piece; (2) drop the flag and let the sequence build elsewhere. Proceeding with (1)."
                )

    # --- Rounds 1–3 ------------------------------------------------------------
    async def run_scene(self, scene: Scene, constraints: SceneConstraints) -> IntegratedScenePlan:
        """Rounds 1–3 for one scene, then scoring, human questions and cap spends. Requires its sequence plan."""
        seq_plan = self._sequence_plan_for(scene)
        seq_entry = seq_plan.entry_for(scene.id)
        if constraints.scene_id != scene.id:
            raise ValueError(f"constraints are for {constraints.scene_id}, not {scene.id} — the breakdown row must match the scene")
        active = self.active_lenses(scene)
        cards = {lens: self.roster.attach_dp(self.roster.card(lens)) for lens in active}

        # Round 1 — independent visions; no lens sees another's output.
        vision_results: list[AgentResult[Any]] = list(
            await asyncio.gather(*(LensAgent(self.ctx).run(key=f"{scene.id}/{lens}", lens_card=cards[lens], sequence_plan=seq_plan, scene=scene, scene_constraints=constraints, style_bible=self.bible) for lens in active))
        )
        visions: dict[str, SceneVision] = {r.parsed.lens: r.parsed for r in vision_results}

        # Round 2 — cross-critique: steal / risk / conflict. A lone lens has nobody to steal from.
        critique_results: list[AgentResult[Any]] = []
        if len(active) > 1:
            critique_results = list(
                await asyncio.gather(
                    *(
                        CritiqueAgent(self.ctx).run(key=f"{scene.id}/critique/{lens}", lens_card=cards[lens], own_vision=visions[lens], other_visions=[visions[o] for o in active if o != lens], scene=scene, style_bible=self.bible)
                        for lens in active
                    )
                )
            )
        critiques: dict[str, Critique] = {r.parsed.lens: r.parsed for r in critique_results}

        # Anti-groupthink hints for the Integrator.
        consensus = detect_consensus_devices(visions.values(), self.policy.consensus_device_share)
        prescores = prescore_panel(visions.values(), scene, self.policy, seq_entry, critiques=critiques.values(), consensus_devices=consensus, max_setups=constraints.max_setups)
        lone_fidelity = lone_high_fidelity(prescores)
        lone_engagement = lone_high_engagement(prescores, visions.values(), self.policy.lone_engagement_carry_threshold)

        # Round 3 — the Integrator.
        integration = await IntegratorAgent(self.ctx).run(
            key=scene.id,
            visions=list(visions.values()),
            critiques=list(critiques.values()),
            scene=scene,
            sequence_plan=seq_plan,
            style_bible=self.bible,
            scene_constraints=constraints,
            caps_used_so_far=self.ledger.status(),
            rubric_weights=self.policy.rubric_weights,
            consensus_devices=consensus,
            lone_high_fidelity_lens=lone_fidelity,
            lone_high_engagement=lone_engagement,
        )
        plan: IntegratedScenePlan = integration.parsed

        # Collapse: consensus penalty (re-weights both options from posture), then rank.
        apply_consensus_penalty(plan, consensus, self.policy.consensus_device_penalty, self.policy)
        recommend(plan, self.policy)
        self._enforce_anti_groupthink(plan, visions, lone_fidelity, lone_engagement)

        # The human gate: governing-idea split, amendments, caps and permissions.
        conflicts = [c for v in visions.values() for c in v.style_bible_conflicts]
        asked = {q.question for q in plan.human_questions}
        for q in needs_human_question(plan, self.policy, self.ledger, conflicts=conflicts):
            if q.question not in asked:
                plan.human_questions.append(q)
                asked.add(q.question)
        self._spend_caps(plan, scene)

        results = [*vision_results, *critique_results, integration]
        self.visions[scene.id], self.critiques[scene.id], self.prescores[scene.id], self.plans[scene.id] = visions, critiques, prescores, plan
        self._account(scene.id, results)
        meta = {"panel": active, "consensus_devices": consensus, "lone_high_fidelity": lone_fidelity, "lone_high_engagement": lone_engagement, "usage": self.usage[scene.id].model_dump()}
        if self.ctx.store is not None:
            self.ctx.store.save(SNAPSHOT_PLAN, scene.id, plan, meta=meta)
        if self.db is not None:
            for r in results:
                self.db.record_call(r)
            for lens, v in visions.items():
                self.db.save_artifact(ARTIFACT_VISION, f"{scene.id}/{lens}", v)
            for lens, c in critiques.items():
                self.db.save_artifact(ARTIFACT_CRITIQUE, f"{scene.id}/{lens}", c)
            self.db.save_artifact(ARTIFACT_PLAN, scene.id, plan)
            self.db.cap_ledger_save(self.ledger)
        return plan

    def _sequence_plan_for(self, scene: Scene) -> SequencePlan:
        if not scene.sequence_id:
            raise StageOrderError(f"scene {scene.id} belongs to no sequence — sequence-level deliberation runs before scene-level, never the reverse")
        plan = self.sequence_plans.get(scene.sequence_id)
        if plan is None:
            raise StageOrderError(f"no SequencePlan for {scene.sequence_id}: run_sequence({scene.sequence_id}) before run_scene({scene.id}) — sequence-level before scene-level, never the reverse")
        if plan.entry_for(scene.id) is None:
            raise StageOrderError(f"SequencePlan {scene.sequence_id} carries no entry for scene {scene.id}; re-run the sequence with the scene included")
        return plan

    def _enforce_anti_groupthink(self, plan: IntegratedScenePlan, visions: dict[str, SceneVision], lone_fidelity: str | None, lone_engagement: dict[str, Any] | None) -> None:
        """Record — never rewrite — where the Integrator dropped a protected lone vision."""
        options = (plan.option_A, plan.option_B)
        if lone_fidelity and lone_fidelity in visions:
            idea = visions[lone_fidelity].governing_idea
            preserved = any(lone_fidelity in o.source_lenses or normalise_text(o.governing_idea) == normalise_text(idea) for o in options)
            if not preserved:
                plan.unresolved_tensions.append(f"anti-groupthink: {lone_fidelity} held the lone highest Dramatic Fidelity in Round 1 ('{idea}') but neither option preserves its governing idea — Option B should carry it even at a lower total")
        if lone_engagement:
            lens, offer = lone_engagement["lens"], normalise_text(str(lone_engagement["pleasure_offer"]))
            carried = any(lens in o.source_lenses for o in options) or (offer and offer in normalise_text(plan.pleasure_beat))
            if not carried:
                plan.unresolved_tensions.append(f"anti-groupthink: {lens} alone offered a pleasure beat scoring Engagement ≥ {self.policy.lone_engagement_carry_threshold:g} ('{lone_engagement['pleasure_offer']}') and neither option carries it — energy is not allowed to die in committee")

    def _spend_caps(self, plan: IntegratedScenePlan, scene: Scene) -> None:
        """Spend the recommended option's capped devices; blocked devices (over cap / not permitted) already carry a HUMAN_QUESTION and are never spent."""
        option = plan.option(plan.recommended)
        blocked = blocked_devices(option, self.ledger, self.policy, scene.id)
        self.ledger.release_scene(scene.id)
        for d in option.devices_used:
            name = normalise_device(d.device)
            if name in blocked:
                log.info("%s: '%s' blocked (over cap or not permitted) — raised, not spent", scene.id, name)
                continue
            self.ledger.spend(name, scene.id, d.setup_ref)

    # --- token accounting ----------------------------------------------------------
    def _account(self, key: str, results: list[AgentResult[Any]]) -> None:
        total = Usage()
        for r in results:
            total = total + r.usage
            if r.over_budget:
                self.over_budget_calls.append(f"{r.agent}:{r.key}")
        self.usage[key] = total

    def total_usage(self) -> Usage:
        total = Usage()
        for u in self.usage.values():
            total = total + u
        return total
