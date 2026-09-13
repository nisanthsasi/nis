"""CP-5 — the Panel: lenses, critique, integrator, resonance scoring, anti-groupthink, panel sizing, caps.

Offline throughout: FakeLLM with a scripted responder (so ids, beat_refs and lens names line
up the way a real panel's would), the stub templates, the conftest factories and a small
injected lens-card dict — nothing here depends on the prompt files.
"""
from __future__ import annotations

import re
from typing import Any, Callable

import pytest
from pydantic import ValidationError

from the_panel.agents.base import AgentContext, ValidationRejected
from the_panel.agents.integrator import IntegratorAgent
from the_panel.agents.lens import CritiqueAgent, LensAgent, SequenceLensAgent
from the_panel.orchestrator.caps import CapLedger
from the_panel.orchestrator.lenses import LensRoster
from the_panel.orchestrator.panel import Panel
from the_panel.orchestrator.posture import policy_for, policy_for_posture
from the_panel.orchestrator.scoring import (
    apply_consensus_penalty,
    detect_consensus_devices,
    lone_high_engagement,
    lone_high_fidelity,
    needs_human_question,
    prescore_panel,
    prescore_vision,
    recommend,
    score_options,
)
from the_panel.orchestrator.stages import StageOrderError
from the_panel.schemas import (
    Caps,
    Contribution,
    Critique,
    DepartmentHandoff,
    DeviceUse,
    EnergyCheck,
    IntegratedScenePlan,
    LensAffinity,
    PlanOption,
    ResonanceScore,
    SceneConstraints,
    SceneVision,
    SequencePlan,
    SequenceSceneEntry,
    SequenceVision,
    Shot,
    ShotItCannotLiveWithout,
    Steal,
)
from the_panel.schemas.style_bible import ExcludedLens
from the_panel.store.db import ARTIFACT_PLAN, PanelDB
from the_panel.testing import FakeLLM

from .conftest import make_film_brief, make_scene, make_sequence_plan, make_style_bible

# ------------------------------------------------------------------ injected lens cards


def _card(name: str, bloc: str, posture_range: list[int], dp: str | None = None, principles: list[str] | None = None) -> dict[str, Any]:
    card: dict[str, Any] = {
        "name": name,
        "bloc": bloc,
        "filmmaker_basis": f"craft principles associated with the {name} films",
        "conviction": f"{name}: the frame knows the turn",
        "decision_rules": [{"when": "pressure", "do": "hold the frame"}],
        "signature_devices": ["the held frame"],
        "refusals": ["coverage-by-default"],
        "blind_spots": ["pace"],
        "best_for": ["pressure"],
        "posture_range": posture_range,
    }
    if dp:
        card["dp_pairing"] = dp
    if principles:
        card["principles"] = principles
    return card


CARDS: dict[str, dict[str, Any]] = {
    "inarritu": _card("inarritu", "auteur", [1, 8], dp="lubezki"),
    "ray_adoor": _card("ray_adoor", "auteur", [0, 8], dp="sivan_mohanan_mitra"),
    "malayalam_new_wave": _card("malayalam_new_wave", "commercial", [3, 10], dp="shyju_khalid_anend_sameer"),
    "bergman": _card("bergman", "auteur", [0, 5], dp="nykvist"),
    "bong_joon_ho": _card("bong_joon_ho", "commercial", [3, 10], dp="hong_kyung_pyo"),
    "kubrick": _card("kubrick", "auteur", [0, 7], dp="deakins"),
    "rajamouli": _card("rajamouli", "commercial", [4, 10], dp="kk_senthil_kumar"),
    "lubezki": _card("lubezki", "dp", [0, 10], principles=["natural light", "very wide lenses", "continuous takes"]),
    "murch": _card("murch", "craft", [0, 10], principles=["emotion 51%"]),
}
PRIMARIES = ["inarritu", "ray_adoor", "malayalam_new_wave"]
SECONDARIES = ["bergman", "bong_joon_ho"]
SEQ_SCENES = ("S1", "S2", "S3")
LENS_RE = re.compile(r'"lens":\s*"([a-z_]+)"')


@pytest.fixture
def roster() -> LensRoster:
    return LensRoster(CARDS)


# ------------------------------------------------------------------ builders


def _shot(no: int, beat_ref: int) -> Shot:
    return Shot(no=no, size="CU", angle="eye-level", height="eye", lens_mm=35, movement="static", duration_est_s=4, subject="Anju", action="holds the ledger", beat_ref=beat_ref, light_note="sodium through the window")


def _vision(lens: str, scene_id: str, *, beat_refs: tuple[int, ...] = (1, 2, 3), energy: int = 4, devices: tuple[str, ...] = (), pleasure: str = "the held breath before the lie breaks", colour: str = "sodium against teal marks the lie", governing_idea: str | None = None, conflicts: tuple[str, ...] = ()) -> SceneVision:
    return SceneVision(
        lens=lens,
        scene_id=scene_id,
        governing_idea=governing_idea or f"{lens}: the room closes on Anju until the floor goes",
        key_image=f"{lens}: Anju's face in the doorway, Ravi a silhouette behind",
        coverage_approach="oner",
        shots=[_shot(i + 1, b) for i, b in enumerate(beat_refs)],
        blocking_note="Ravi keeps the door; Anju must cross him to leave",
        pleasure_offer=pleasure,
        energy_level=energy,
        colour_note=colour,
        devices_used=[DeviceUse(device=d, setup_ref="beat 2") for d in devices],
        style_bible_conflicts=list(conflicts),
    )


def _score(**kw: float) -> ResonanceScore:
    base: dict[str, float] = dict(dramatic_fidelity=7, emotional_impact=7, engagement=7, style_coherence=7, feasibility=7, earned_freshness=7)
    base.update(kw)
    return ResonanceScore(**base)


def _option(label: str, lenses: list[str], *, devices: tuple[str, ...] = (), idea: str | None = None) -> PlanOption:
    return PlanOption(label=label, governing_idea=idea or f"option {label}: the room closes on Anju", shots=[_shot(1, 1), _shot(2, 2)], blocking="Ravi keeps the door", rationale=f"option {label} keeps the turn on Anju's face", source_lenses=lenses, devices_used=[DeviceUse(device=d, setup_ref="beat 2") for d in devices])


def _plan(scene_id: str, lenses: list[str], *, devices_a: tuple[str, ...] = (), devices_b: tuple[str, ...] = (), idea_a: str | None = None, idea_b: str | None = None, score_a: ResonanceScore | None = None, score_b: ResonanceScore | None = None, recommended: str = "A", shot_no: int = 1, contributions: list[str] | None = None, tensions: tuple[str, ...] = ()) -> IntegratedScenePlan:
    a = _option("A", lenses[:1], devices=devices_a, idea=idea_a)
    b = _option("B", lenses[1:2] or lenses[:1], devices=devices_b, idea=idea_b)
    chosen = a if recommended == "A" else b
    return IntegratedScenePlan(
        scene_id=scene_id,
        governing_idea=chosen.governing_idea,
        directors_note="Anju already knows; play the not-knowing.",
        option_A=a,
        option_B=b,
        contributions=[Contribution(element="the doorway frame", lens=n) for n in (contributions if contributions is not None else lenses[:1])],
        unresolved_tensions=list(tensions),
        pleasure_beat="the barrier lifts and the crowd turns",
        trailer_shot="Anju at the barrier, the witness behind her",
        must_remember_delivery="the choice lands on her face before the crowd reacts",
        energy_check=EnergyCheck(asl_target_s=4, camera_velocity="with breath", cut_rate="slow", sequence_energy_target=7, plan_energy=7),
        devices_used=list(chosen.devices_used),
        resonance_A=score_a or _score(),
        resonance_B=score_b or _score(),
        department_handoff=DepartmentHandoff(colour_stance="sodium marks the lie", music_stance="silence until the barrier", sound_stance="Anju's ears", design_stance="the ledger on the table", performance_stance="low tempo, Kochi colloquial"),
        the_shot_it_cannot_live_without=ShotItCannotLiveWithout(shot_no=shot_no, why="the turn is on her face"),
        recommended=recommended,
    )


def _lenses_in(prompt: str) -> list[str]:
    seen: dict[str, None] = {}
    for m in LENS_RE.finditer(prompt):
        seen.setdefault(m.group(1), None)
    return list(seen)


def panel_responder(
    *,
    scene_ids: tuple[str, ...] = SEQ_SCENES,
    set_piece_scene: str | None = "S3",
    seq_human_questions: tuple[str, ...] = (),
    vision_for: Callable[[str, str], SceneVision] | None = None,
    plan_for: Callable[[str, list[str]], IntegratedScenePlan] | None = None,
):
    """Scripted panel outputs keyed on the requested schema, with ids taken from the fake's hints."""

    def entries() -> list[SequenceSceneEntry]:
        return [SequenceSceneEntry(scene_id=s, energy_target=3 + 2 * i, pleasure_type="thrill" if s == set_piece_scene else "dread", set_piece=(s == set_piece_scene), asl_target_s=8.0 - 2 * i) for i, s in enumerate(scene_ids)]

    def respond(call):
        h, fmt = call.hints, call.output_format
        if fmt is SequenceVision:
            return SequenceVision(lens=h["lens"], sequence_id=h["sequence_id"], escalation_strategy="each scene removes one exit", key_image="Anju lit by a passing sodium lamp", scenes=entries(), set_piece_scene_id=set_piece_scene, temperature_curve=[4, 6, 9][: len(scene_ids)])
        if fmt is SequencePlan:
            return SequencePlan(sequence_id=h["sequence_id"], function="the smuggling begins", key_image="Anju lit by a passing sodium lamp", escalation_strategy="each scene removes one exit", scenes=entries(), oner_placement=scene_ids[-1], silence_placement=scene_ids[0], temperature_curve=[4, 6, 9][: len(scene_ids)], human_questions=list(seq_human_questions))
        if fmt is SceneVision:
            return vision_for(h["lens"], h["scene_id"]) if vision_for else _vision(h["lens"], h["scene_id"])
        if fmt is Critique:
            other = next(n for n in _lenses_in(call.prompt) if n != h["lens"])
            return Critique(lens=h["lens"], scene_id=h["scene_id"], steal=Steal(from_lens=other, idea="the doorway frame", how_it_improves_mine="gives the oner a threshold"), risk="the oner flattens the turn")
        if fmt is IntegratedScenePlan:
            lenses = _lenses_in(call.prompt)
            return plan_for(h["scene_id"], lenses) if plan_for else _plan(h["scene_id"], lenses)
        return None

    return respond


def _panel(ctx: AgentContext, roster: LensRoster, bible=None, **kw: Any) -> Panel:
    bible = bible or make_style_bible(5)
    return Panel(ctx, bible, roster=roster, **kw)


def _scenes() -> list:
    return [make_scene("S1", 1), make_scene("S2", 2), make_scene("S3", 3, set_piece=True, set_piece_kind="action", must_remember="Anju's choice at the barrier", load_bearing=True, pleasure_type="thrill", energy_target=7, emotional_temperature=8)]


def _calls(fake: FakeLLM, model: type) -> list:
    return [c for c in fake.calls if c.output_format is model]


SEQ1 = make_film_brief().sequences[0]
CONSTRAINTS = SceneConstraints(scene_id="S3", estimated_setups=6, max_setups=8)


async def _run_seq_and_scene(ctx: AgentContext, roster: LensRoster, scene_index: int, bible=None, **kw: Any) -> tuple[Panel, IntegratedScenePlan]:
    panel = _panel(ctx, roster, bible, **kw)
    scenes = _scenes()
    await panel.run_sequence(SEQ1, scenes)
    scene = scenes[scene_index]
    plan = await panel.run_scene(scene, SceneConstraints(scene_id=scene.id, estimated_setups=6, max_setups=8))
    return panel, plan


# ------------------------------------------------------------------ schema guards


def test_shot_without_beat_ref_fails_schema():
    with pytest.raises(ValidationError):
        Shot(no=1, size="CU", angle="eye", height="eye", lens_mm=35, movement="static", duration_est_s=3, subject="Anju", action="looks", light_note="window")  # type: ignore[call-arg]


def test_device_without_setup_ref_fails_schema():
    with pytest.raises(ValidationError):
        DeviceUse(device="slow motion")  # type: ignore[call-arg]
    with pytest.raises(ValidationError):
        DeviceUse(device="slow motion", setup_ref="   ")


# ------------------------------------------------------------------ agent checks


def _lens_vars(scene, **over: Any) -> dict[str, Any]:
    v = dict(lens_card=CARDS["kubrick"], scene=scene, sequence_plan=make_sequence_plan(), scene_constraints=SceneConstraints(scene_id=scene.id), style_bible=make_style_bible(5))
    v.update(over)
    return v


async def test_lens_agent_rejects_beat_ref_outside_scene_beats(offline_ctx: AgentContext, scene):
    offline_ctx.client = FakeLLM(lambda call: _vision("kubrick", "S1", beat_refs=(1, 2, 9)))
    with pytest.raises(ValidationRejected) as e:
        await LensAgent(offline_ctx).run(key="S1/kubrick", **_lens_vars(scene))
    assert "beat_ref" in str(e.value) and len(offline_ctx.client.calls) == 2 and offline_ctx.client.calls[1].is_repair


async def test_lens_agent_rejects_mismatched_lens(offline_ctx: AgentContext, scene):
    offline_ctx.client = FakeLLM(lambda call: _vision("kurosawa", "S1"))
    with pytest.raises(ValidationRejected) as e:
        await LensAgent(offline_ctx).run(key="S1/kubrick", **_lens_vars(scene))
    assert "lens must be 'kubrick'" in str(e.value) and len(offline_ctx.client.calls) == 2


async def test_lens_agent_requires_reason_for_no_pleasure_and_beat_1_when_no_beats(offline_ctx: AgentContext):
    bare = make_scene("S1", beats=0, tension_curve=[])
    offline_ctx.client = FakeLLM(lambda call: _vision("kubrick", "S1", beat_refs=(1, 1, 1), pleasure="None"))
    with pytest.raises(ValidationRejected) as e:
        await LensAgent(offline_ctx).run(key="S1/kubrick", **_lens_vars(bare))
    assert "pleasure_offer 'none'" in str(e.value)
    offline_ctx.client = FakeLLM(lambda call: _vision("kubrick", "S1", beat_refs=(1, 1, 2), pleasure="none — connective tissue between the two confrontations"))
    with pytest.raises(ValidationRejected) as e:
        await LensAgent(offline_ctx).run(key="S1/kubrick", **_lens_vars(bare))
    assert "[1]" in str(e.value)
    offline_ctx.client = FakeLLM(lambda call: _vision("kubrick", "S1", beat_refs=(1, 1, 1), pleasure="none — connective tissue between the two confrontations"))
    res = await LensAgent(offline_ctx).run(key="S1/kubrick", **_lens_vars(bare))
    assert res.attempts == 1


async def test_sequence_lens_check_requires_one_entry_per_scene_and_no_shots(offline_ctx: AgentContext, style_bible):
    def short(call):
        return SequenceVision(lens="kubrick", sequence_id="SEQ1", escalation_strategy="each scene removes one exit", key_image="the corridor", scenes=[SequenceSceneEntry(scene_id="S1", energy_target=3, pleasure_type="dread")])

    offline_ctx.client = FakeLLM(short)
    variables = dict(lens_card=CARDS["kubrick"], sequence=SEQ1, pleasure_map_entry=style_bible.pleasure_map[0], style_bible=style_bible, release_target="both")
    with pytest.raises(ValidationRejected) as e:
        await SequenceLensAgent(offline_ctx).run(key="SEQ1/kubrick", **variables)
    assert "missing ['S2', 'S3']" in str(e.value)

    def shots(call):
        return SequenceVision(lens="kubrick", sequence_id="SEQ1", escalation_strategy="open on a 24mm corridor, then shot 2 pushes in", key_image="the corridor", scenes=[SequenceSceneEntry(scene_id=s, energy_target=3, pleasure_type="dread") for s in SEQ_SCENES])

    offline_ctx.client = FakeLLM(shots)
    with pytest.raises(ValidationRejected) as e:
        await SequenceLensAgent(offline_ctx).run(key="SEQ1/kubrick", **variables)
    assert "shot-level content" in str(e.value)


async def test_critique_check_rejects_self_steal_and_multi_element_revision(offline_ctx: AgentContext, scene, style_bible):
    others = [_vision("kurosawa", "S1"), _vision("bergman", "S1")]
    variables = dict(lens_card=CARDS["kubrick"], own_vision=_vision("kubrick", "S1"), other_visions=others, scene=scene, style_bible=style_bible)
    offline_ctx.client = FakeLLM(lambda call: Critique(lens="kubrick", scene_id="S1", steal=Steal(from_lens="kubrick", idea="x", how_it_improves_mine="y"), risk="z"))
    with pytest.raises(ValidationRejected) as e:
        await CritiqueAgent(offline_ctx).run(key="S1/critique/kubrick", **variables)
    assert "own vision" in str(e.value)
    offline_ctx.client = FakeLLM(lambda call: Critique(lens="kubrick", scene_id="S1", steal=Steal(from_lens="kurosawa", idea="x", how_it_improves_mine="y"), risk="z", revised_element="light, shots", revised_value="all of it"))
    with pytest.raises(ValidationRejected) as e:
        await CritiqueAgent(offline_ctx).run(key="S1/critique/kubrick", **variables)
    assert "exactly ONE" in str(e.value)
    offline_ctx.client = FakeLLM(lambda call: Critique(lens="kubrick", scene_id="S1", steal=Steal(from_lens="bergman", idea="the double face", how_it_improves_mine="the oner gets a second face"), risk="z", revised_element="light", revised_value="single window source"))
    res = await CritiqueAgent(offline_ctx).run(key="S1/critique/kubrick", **variables)
    assert res.attempts == 1


async def test_integrator_check_rejects_shot_outside_recommended_option_and_stranger_lens(offline_ctx: AgentContext, style_bible):
    scene = _scenes()[2]
    visions = [_vision(n, "S3") for n in PRIMARIES]
    variables = dict(visions=visions, critiques=[], scene=scene, sequence_plan=make_sequence_plan(), style_bible=style_bible, scene_constraints=CONSTRAINTS, caps_used_so_far={}, rubric_weights=policy_for(style_bible).rubric_weights)
    offline_ctx.client = FakeLLM(lambda call: _plan("S3", PRIMARIES, shot_no=99))
    with pytest.raises(ValidationRejected) as e:
        await IntegratorAgent(offline_ctx).run(key="S3", **variables)
    assert "the_shot_it_cannot_live_without" in str(e.value)
    offline_ctx.client = FakeLLM(lambda call: _plan("S3", PRIMARIES, contributions=["rajamouli"]))
    with pytest.raises(ValidationRejected) as e:
        await IntegratorAgent(offline_ctx).run(key="S3", **variables)
    assert "rajamouli" in str(e.value)
    offline_ctx.client = FakeLLM(lambda call: _plan("S3", PRIMARIES))
    res = await IntegratorAgent(offline_ctx).run(key="S3", **variables)
    assert res.parsed.scene_id == "S3" and res.attempts == 1


# ------------------------------------------------------------------ order, sizing, rounds


async def test_run_scene_before_run_sequence_raises_stage_order_error(offline_ctx: AgentContext, roster: LensRoster):
    offline_ctx.client = FakeLLM(panel_responder())
    panel = _panel(offline_ctx, roster)
    with pytest.raises(StageOrderError):
        await panel.run_scene(_scenes()[2], CONSTRAINTS)
    assert offline_ctx.client.calls == []


async def test_full_panel_runs_every_round_with_the_expected_calls(offline_ctx: AgentContext, roster: LensRoster):
    offline_ctx.client = FakeLLM(panel_responder())
    fake = offline_ctx.client
    panel, plan = await _run_seq_and_scene(offline_ctx, roster, 2)
    assert panel.panel_size_for(_scenes()[2]) == "full" and panel.active_lenses(_scenes()[2]) == PRIMARIES + SECONDARIES
    assert len(_calls(fake, SequenceVision)) == 5 and len(_calls(fake, SequencePlan)) == 1
    assert len(_calls(fake, SceneVision)) == 5 and len(_calls(fake, Critique)) == 5 and len(_calls(fake, IntegratedScenePlan)) == 1
    assert plan.scene_id == "S3" and plan.recommended in ("A", "B") and plan.resonance_A.weighted_total is not None
    assert set(panel.visions["S3"]) == set(PRIMARIES + SECONDARIES) and set(panel.critiques["S3"]) == set(PRIMARIES + SECONDARIES)
    # no lens saw another's output in Round 1; Round 2 saw exactly the others
    for call in _calls(fake, SceneVision):
        assert "other_visions" not in call.prompt
    for call in _calls(fake, Critique):
        assert len(_lenses_in(call.prompt)) == 5
    assert panel.usage["S3"].output_tokens > 0 and panel.usage["SEQ1"].output_tokens > 0
    # persisted under the agreed keys
    store = offline_ctx.store
    assert store.latest("lens", "S3/inarritu") and store.latest("critique", "S3/critique/inarritu") and store.latest("integrator", "S3")
    assert store.latest("plan", "S3")["parsed"]["recommended"] == plan.recommended and store.latest("sequence_plan", "SEQ1")


async def test_reduced_panel_is_three_primaries(offline_ctx: AgentContext, roster: LensRoster):
    offline_ctx.client = FakeLLM(panel_responder())
    fake = offline_ctx.client
    panel, plan = await _run_seq_and_scene(offline_ctx, roster, 0)
    assert panel.panel_size_for(_scenes()[0]) == "reduced" and panel.active_lenses(_scenes()[0]) == PRIMARIES
    assert len(_calls(fake, SceneVision)) == 3 and len(_calls(fake, Critique)) == 3 and len(_calls(fake, IntegratedScenePlan)) == 1
    assert plan.scene_id == "S1"


def test_panel_selection_honours_excluded_lenses_and_temperature(roster: LensRoster):
    bible = make_style_bible(5, lens_affinity=LensAffinity(primary=PRIMARIES, secondary=SECONDARIES, excluded=[ExcludedLens(lens="bergman", reason="no chamber intimacy in a chase")]))
    policy = policy_for(bible)
    hot = make_scene("S2", 2, emotional_temperature=8)
    assert roster.select_panel(hot, bible, policy) == PRIMARIES + ["bong_joon_ho"]
    warm = make_scene("S2", 2, emotional_temperature=7)
    assert roster.select_panel(warm, bible, policy) == PRIMARIES
    # an excluded primary never sits, even on the reduced panel
    bible2 = make_style_bible(5, lens_affinity=LensAffinity(primary=PRIMARIES + ["kubrick"], secondary=SECONDARIES, excluded=[ExcludedLens(lens="ray_adoor", reason="pace")]))
    assert roster.select_panel(warm, bible2, policy_for(bible2)) == ["inarritu", "malayalam_new_wave", "kubrick"]
    assert roster.select_panel(hot, bible2, policy_for(bible2)) == ["inarritu", "malayalam_new_wave", "kubrick"] + SECONDARIES
    # a primary outside its posture_range yields its reduced seat and is warned about
    mass = make_style_bible(9, lens_affinity=LensAffinity(primary=["bergman", "malayalam_new_wave", "bong_joon_ho", "rajamouli"], secondary=["inarritu"]))
    roster.warnings.clear()
    assert roster.select_panel(warm, mass, policy_for(mass)) == ["malayalam_new_wave", "bong_joon_ho", "rajamouli"]
    assert roster.warnings and "bergman" in roster.warnings[0]


def test_validate_affinity_reports_panel_mix_violations(roster: LensRoster):
    hybrid = make_style_bible(5)
    assert roster.validate_affinity(hybrid, policy_for(hybrid)) == []
    mass = make_style_bible(9)
    problems = roster.validate_affinity(mass, policy_for(mass))
    assert any("commercial lenses among primaries" in p for p in problems)
    assert any("inarritu" in p and "posture_range" in p for p in problems)
    odd = make_style_bible(2, lens_affinity=LensAffinity(primary=["kubrick", "murch", "ghost"], secondary=["kubrick"], excluded=[ExcludedLens(lens="kubrick", reason="x")]))
    problems = roster.validate_affinity(odd, policy_for(odd))
    assert any("'ghost' has no card" in p for p in problems) and any("'murch' is a craft card" in p for p in problems)
    assert any("both primary and excluded" in p for p in problems) and any("both primary and secondary" in p for p in problems)
    assert any("commercial lenses among secondaries" in p for p in problems)


def test_attach_dp_merges_paired_principles(roster: LensRoster):
    card = roster.attach_dp(roster.card("inarritu"))
    assert card["dp_principles"] == ["natural light", "very wide lenses", "continuous takes"] and "dp_principles" not in roster.card("inarritu")
    assert "dp_principles" not in roster.attach_dp(roster.card("kubrick"))  # deakins is not on this small roster
    with pytest.raises(KeyError):
        roster.card("ghost")


async def test_run_sequence_applies_plan_and_never_flips_a_set_piece_without_must_remember(offline_ctx: AgentContext, roster: LensRoster):
    offline_ctx.client = FakeLLM(panel_responder(set_piece_scene="S2", seq_human_questions=["HQ: the lenses argue for S2; the map says S3 — (1) keep S3 (2) move to S2"]))
    panel = _panel(offline_ctx, roster)
    scenes = [make_scene("S1", 1), make_scene("S2", 2), make_scene("S3", 3, must_remember="Anju's choice at the barrier")]
    plan = await panel.run_sequence(SEQ1, scenes)
    assert panel.sequence_plans["SEQ1"] is plan
    assert [s.energy_target for s in scenes] == [3, 5, 7] and scenes[1].pleasure_type == "thrill"
    assert scenes[1].set_piece is False and any("S2" in q and "must_remember" in q for q in plan.human_questions)
    offline_ctx.client = FakeLLM(panel_responder(set_piece_scene="S3"))
    plan = await panel.run_sequence(SEQ1, scenes)
    assert scenes[2].set_piece is True and scenes[2].must_remember == "Anju's choice at the barrier"


# ------------------------------------------------------------------ scoring & anti-groupthink


def test_weights_come_from_posture_not_code():
    a = _score(dramatic_fidelity=8, emotional_impact=8, engagement=9, style_coherence=7, feasibility=8, earned_freshness=7)
    b = _score(dramatic_fidelity=9, emotional_impact=8, engagement=6, style_coherence=7, feasibility=8, earned_freshness=7)
    plan = _plan("S3", PRIMARIES, score_a=a, score_b=b)
    assert recommend(plan, policy_for(make_style_bible(8))) == "A" and plan.recommended == "A"
    assert recommend(plan, policy_for(make_style_bible(2))) == "B" and plan.recommended == "B"
    assert plan.resonance_A.weighted_total == policy_for_posture(2).weighted_total(a)


def test_consensus_device_detection_and_penalty():
    visions = [_vision("inarritu", "S1", devices=("slow motion",)), _vision("ray_adoor", "S1", devices=("Slow Motion", "drone")), _vision("malayalam_new_wave", "S1")]
    policy = policy_for(make_style_bible(5))
    assert detect_consensus_devices(visions, policy.consensus_device_share) == ["slow motion"]
    assert detect_consensus_devices(visions, 0.7) == []
    plan = _plan("S1", PRIMARIES, devices_a=("slow motion",))
    score_options(plan, policy)
    clean_total = plan.resonance_A.weighted_total
    apply_consensus_penalty(plan, ["slow motion"], policy.consensus_device_penalty, policy)
    assert plan.resonance_A.consensus_device_penalty == 2.0 and plan.resonance_B.consensus_device_penalty == 0.0
    assert plan.resonance_A.weighted_total == pytest.approx(clean_total - policy.rubric_weights["earned_freshness"] * 2.0)
    assert recommend(plan, policy) == "B"


async def test_consensus_device_penalised_inside_the_panel(offline_ctx: AgentContext, roster: LensRoster):
    def vision_for(lens: str, scene_id: str) -> SceneVision:
        return _vision(lens, scene_id, devices=("slow motion",) if lens != "malayalam_new_wave" else ())

    offline_ctx.client = FakeLLM(panel_responder(vision_for=vision_for, plan_for=lambda sid, lenses: _plan(sid, lenses, devices_a=("slow motion",))))
    panel, plan = await _run_seq_and_scene(offline_ctx, roster, 0)
    assert plan.resonance_A.consensus_device_penalty == 2.0 and plan.resonance_B.consensus_device_penalty == 0.0 and plan.recommended == "B"
    assert "consensus_devices" in offline_ctx.client.calls_for("STUB TEMPLATE P7_integrator")[0].prompt


def test_prescore_is_a_bounded_deterministic_hint(scene):
    policy = policy_for(make_style_bible(5))
    full = prescore_vision(_vision("inarritu", "S1", beat_refs=(1, 2, 3, 4), energy=4, governing_idea="the floor goes from under Anju"), scene, policy, SequenceSceneEntry(scene_id="S1", energy_target=4, pleasure_type="tears"))
    thin = prescore_vision(_vision("bergman", "S1", beat_refs=(1, 1, 1), energy=0, pleasure="none — connective", colour="", conflicts=("score under dialogue",)), scene, policy)
    assert full.dramatic_fidelity > thin.dramatic_fidelity and full.engagement > thin.engagement and full.style_coherence > thin.style_coherence
    assert full.emotional_impact == 10 and thin.style_coherence == 8 and full.weighted_total is not None
    assert all(0 <= getattr(full, c) <= 10 for c in ("dramatic_fidelity", "emotional_impact", "engagement", "style_coherence", "feasibility", "earned_freshness"))
    assert prescore_vision(_vision("inarritu", "S1"), scene, policy) == prescore_vision(_vision("inarritu", "S1"), scene, policy)
    assert all(j.note.startswith("hint:") for j in full.justifications)


def test_lone_high_fidelity_and_engagement(scene):
    policy = policy_for(make_style_bible(5))
    entry = SequenceSceneEntry(scene_id="S1", energy_target=4, pleasure_type="tears")
    visions = [_vision("inarritu", "S1", beat_refs=(1, 2, 3, 4)), _vision("ray_adoor", "S1", beat_refs=(1, 1, 1), energy=0, pleasure="none — connective", colour=""), _vision("bergman", "S1", beat_refs=(1, 1, 2), energy=0, pleasure="none — connective", colour="")]
    scores = prescore_panel(visions, scene, policy, entry)
    assert lone_high_fidelity(scores) == "inarritu"
    carried = lone_high_engagement(scores, visions, policy.lone_engagement_carry_threshold)
    assert carried and carried["lens"] == "inarritu" and carried["pleasure_offer"] == visions[0].pleasure_offer
    tie = prescore_panel([_vision("inarritu", "S1"), _vision("bergman", "S1")], scene, policy, entry)
    assert lone_high_fidelity(tie) is None and lone_high_engagement(tie, visions, policy.lone_engagement_carry_threshold) is None
    # a Round-2 revision of ONE element feeds the pre-score
    revised = prescore_panel(visions, scene, policy, entry, critiques=[Critique(lens="ray_adoor", scene_id="S1", steal=Steal(from_lens="inarritu", idea="x", how_it_improves_mine="y"), risk="z", revised_element="energy_level", revised_value="4")])
    assert revised["ray_adoor"].engagement > scores["ray_adoor"].engagement


async def test_lone_high_engagement_pleasure_beat_reaches_the_integrator_prompt(offline_ctx: AgentContext, roster: LensRoster):
    def vision_for(lens: str, scene_id: str) -> SceneVision:
        if lens == "malayalam_new_wave":
            return _vision(lens, scene_id, energy=7, pleasure="the group-reaction frame when the barrier lifts")
        return _vision(lens, scene_id, energy=1, pleasure="none — this lens keeps the scene connective", colour="")

    offline_ctx.client = FakeLLM(panel_responder(vision_for=vision_for))
    panel, plan = await _run_seq_and_scene(offline_ctx, roster, 2)
    prompt = _calls(offline_ctx.client, IntegratedScenePlan)[0].prompt
    hint = prompt.split("lone_high_engagement:")[1].split("lone_high_fidelity_lens:")[0]
    assert '"lens": "malayalam_new_wave"' in hint and "group-reaction frame" in hint
    assert '"malayalam_new_wave"' in prompt.split("lone_high_fidelity_lens:")[1]
    # the Integrator's plan (option A from inarritu, B from ray_adoor) drops both protected visions: recorded, not rewritten
    tensions = " ".join(plan.unresolved_tensions)
    assert "anti-groupthink" in tensions and "malayalam_new_wave" in tensions
    assert plan.option_A.source_lenses == ["inarritu"]


async def test_lone_fidelity_preserved_as_option_b_raises_no_tension(offline_ctx: AgentContext, roster: LensRoster):
    def vision_for(lens: str, scene_id: str) -> SceneVision:
        return _vision(lens, scene_id, beat_refs=(1, 2, 3, 4) if lens == "ray_adoor" else (1, 1, 1))

    offline_ctx.client = FakeLLM(panel_responder(vision_for=vision_for, plan_for=lambda sid, lenses: _plan(sid, ["inarritu", "ray_adoor"])))
    panel, plan = await _run_seq_and_scene(offline_ctx, roster, 0)
    assert not any("ray_adoor" in t for t in plan.unresolved_tensions)


def test_needs_human_question_on_governing_idea_split_and_amendment():
    policy = policy_for(make_style_bible(5))
    ledger = CapLedger(policy.caps)
    same = _plan("S3", PRIMARIES, idea_a="the room closes on Anju", idea_b="The room closes on Anju.")
    assert needs_human_question(same, policy, ledger) == []
    split = _plan("S3", PRIMARIES, idea_a="the room closes on Anju", idea_b="Anju was never trapped", tensions=("Option B needs an amendment: score under dialogue in Act 1",))
    qs = needs_human_question(split, policy, ledger, conflicts=["uses a drone the Bible must amend to permit"])
    assert [q.id for q in qs] == ["HQ-S3-1", "HQ-S3-2"] and all(len(q.options) == 2 for q in qs)
    assert "governing idea" in qs[0].question and qs[0].conservative_option == 0
    assert "amendment" in qs[1].question and qs[1].conservative_option == 1 and "score under dialogue" in qs[1].options[0]


# ------------------------------------------------------------------ caps


async def test_over_cap_device_raises_human_question_and_does_not_spend(offline_ctx: AgentContext, roster: LensRoster):
    bible = make_style_bible(5, caps=Caps(elevation_cues=1, slow_motion=3, needle_drops=0))
    ledger = CapLedger(bible.caps)
    ledger.spend("bgm elevation", "S1", "beat 2")
    offline_ctx.client = FakeLLM(panel_responder(plan_for=lambda sid, lenses: _plan(sid, lenses, devices_a=("bgm elevation", "drone"))))
    panel, plan = await _run_seq_and_scene(offline_ctx, roster, 2, bible, ledger=ledger)
    questions = [q for q in plan.human_questions if "bgm elevation" in q.question]
    assert questions and "exceed the film cap" in questions[0].question and len(questions[0].options) == 2 and questions[0].conservative_option == 0
    assert any("drone" in q.question and "not in the Style Bible's device_permissions" in q.question for q in plan.human_questions)
    assert ledger.used("bgm elevation") == 1 and all(s.scene_id == "S1" for s in ledger.spends["elevation_cues"])
    assert ledger.status()["elevation_cues"] == "1 of 1"


async def test_permitted_under_cap_device_is_spent_and_released_on_rerun(offline_ctx: AgentContext, roster: LensRoster):
    offline_ctx.client = FakeLLM(panel_responder(plan_for=lambda sid, lenses: _plan(sid, lenses, devices_a=("slow motion",))))
    db = PanelDB(":memory:")
    panel, plan = await _run_seq_and_scene(offline_ctx, roster, 2, db=db)
    assert panel.ledger.used("slow motion") == 1 and panel.ledger.spends["slow_motion"][0].scene_id == "S3"
    assert not any("slow motion" in q.question for q in plan.human_questions)
    scene = _scenes()[2]
    await panel.run_scene(scene, CONSTRAINTS)
    assert panel.ledger.used("slow motion") == 1 and panel.ledger.position("slow motion") == "1 of 3"
    assert db.load_artifact(ARTIFACT_PLAN, "S3", IntegratedScenePlan).scene_id == "S3" and db.cap_ledger_load(panel.policy.caps).used("slow motion") == 1
    assert len(db.calls()) == 6 + 11 + 11


# ------------------------------------------------------------------ token budgets


async def test_output_token_budget_is_flagged_then_enforced(offline_ctx: AgentContext, roster: LensRoster):
    offline_ctx.client = FakeLLM(panel_responder())
    offline_ctx.config = offline_ctx.config.model_copy(update={"budgets": offline_ctx.config.budgets.model_copy(update={"lens": 10})})
    panel, plan = await _run_seq_and_scene(offline_ctx, roster, 0)
    assert panel.over_budget_calls and all(c.startswith("lens:S1/") for c in panel.over_budget_calls) and len(panel.over_budget_calls) == 3
    assert panel.usage["S1"].output_tokens > 10 and panel.total_usage().output_tokens == panel.usage["S1"].output_tokens + panel.usage["SEQ1"].output_tokens
    offline_ctx.config = offline_ctx.config.model_copy(update={"budgets": offline_ctx.config.budgets.model_copy(update={"lens": 10, "strict_budgets": True})})
    with pytest.raises(ValidationRejected):
        await panel.run_scene(_scenes()[0], SceneConstraints(scene_id="S1"))
