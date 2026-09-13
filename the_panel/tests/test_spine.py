"""Spine tests: schemas, posture, caps, header, base agent, fake LLM."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from the_panel.agents.base import AgentContext, BaseAgent, ValidationRejected
from the_panel.orchestrator.caps import CapLedger, OverCapError
from the_panel.orchestrator.header import build_film_brief_header, estimate_tokens
from the_panel.orchestrator.posture import policy_for, policy_for_posture
from the_panel.schemas import (
    Caps,
    DeviceUse,
    IntegratedScenePlan,
    ResonanceScore,
    Scene,
    SceneVision,
    Shot,
    StyleBible,
    assert_no_shot_fields,
)
from the_panel.testing import FakeLLM, build_example

from .conftest import make_film_brief, make_scene, make_style_bible


def test_scene_has_no_shot_fields():
    assert_no_shot_fields(Scene)


def test_set_piece_requires_must_remember():
    with pytest.raises(ValidationError):
        make_scene(set_piece=True, must_remember=None)
    s = make_scene(set_piece=True, must_remember="the barrier")
    assert s.is_full_panel


def test_shot_requires_beat_ref_and_device_requires_setup_ref():
    with pytest.raises(ValidationError):
        Shot(no=1, size="CU", angle="eye", height="eye", lens_mm=35, movement="static", duration_est_s=3, subject="Anju", action="looks", light_note="window")  # type: ignore[call-arg]
    with pytest.raises(ValidationError):
        DeviceUse(device="slow motion", setup_ref="  ")


def test_style_bible_max_three_signature_devices():
    with pytest.raises(ValidationError):
        make_style_bible(signature_devices=["a", "b", "c", "d"])


@pytest.mark.parametrize("posture,band,eng", [(0, "arthouse", 0.05), (3, "arthouse", 0.05), (4, "hybrid", 0.15), (6, "hybrid", 0.15), (7, "mass", 0.25), (10, "mass", 0.25)])
def test_posture_weights_by_band(posture, band, eng):
    pol = policy_for_posture(posture)
    assert pol.band == band
    assert pol.rubric_weights["engagement"] == eng
    assert abs(sum(pol.rubric_weights.values()) - 1.0) < 1e-9


def test_changing_posture_changes_caps_and_panel_mix_without_code_change():
    art, mass = policy_for_posture(2), policy_for_posture(9)
    assert art.caps.elevation_cues == 1 and mass.caps.elevation_cues == 5
    assert mass.caps.slow_motion is None  # unlimited, each earned
    assert art.panel_mix.primaries_auteur_min == 3 and mass.panel_mix.primaries_commercial_min == 2
    assert art.max_pleasure_gap_minutes is None and mass.max_pleasure_gap_minutes == 6


def test_policy_reads_caps_from_style_bible_not_presets():
    sb = make_style_bible(posture=5, caps=Caps(elevation_cues=1, slow_motion=0, needle_drops=0))
    pol = policy_for(sb)
    assert pol.caps.elevation_cues == 1 and "caps" in pol.overrides_applied


def test_unapproved_bible_cannot_drive_posture_when_required():
    sb = make_style_bible(approved=False)
    with pytest.raises(PermissionError):
        policy_for(sb, require_approved=True)


def test_weighted_total_and_tie_break():
    pol = policy_for_posture(8)
    a = ResonanceScore(dramatic_fidelity=8, emotional_impact=8, engagement=9, style_coherence=7, feasibility=8, earned_freshness=7)
    b = ResonanceScore(dramatic_fidelity=9, emotional_impact=8, engagement=6, style_coherence=7, feasibility=8, earned_freshness=7)
    pol.score(a), pol.score(b)
    assert pol.rank({"A": a, "B": b})[0] == "A"  # mass posture rewards engagement
    pol2 = policy_for_posture(2)
    pol2.score(a), pol2.score(b)
    assert pol2.rank({"A": a, "B": b})[0] == "B"  # arthouse rewards fidelity


def test_cap_ledger_never_spends_silently():
    ledger = CapLedger(Caps(elevation_cues=1, slow_motion=1, needle_drops=0))
    assert not ledger.would_exceed("bgm elevation")
    ledger.spend("bgm elevation", "S3", "beat 4")
    assert ledger.would_exceed("bgm elevation")
    with pytest.raises(OverCapError):
        ledger.spend("bgm elevation", "S5", "beat 2")
    assert ledger.would_exceed("needle drop")
    assert ledger.position("bgm elevation") == "1 of 1"
    ledger.release_scene("S3")
    assert not ledger.would_exceed("bgm elevation")


def test_header_fits_budget_and_is_stable():
    fb, sb = make_film_brief(), make_style_bible()
    h1 = build_film_brief_header(fb, sb, max_tokens=3000)
    h2 = build_film_brief_header(fb, sb, max_tokens=3000)
    assert h1.sha == h2.sha and h1.token_estimate <= 3000
    assert "posture 5/10" in h1.text and "KAITHA" in h1.text
    tiny = build_film_brief_header(fb, sb, max_tokens=120)
    assert tiny.token_estimate <= 120 and tiny.dropped_sections
    assert estimate_tokens("a" * 360) == 100


def test_example_builder_makes_valid_instances():
    v = build_example(SceneVision, {"lens": "kubrick", "scene_id": "S9"})
    assert v.lens == "kubrick" and v.scene_id == "S9" and 3 <= len(v.shots) <= 8
    p = build_example(IntegratedScenePlan, {"scene_id": "S9"})
    assert p.resonance_scores["A"].dramatic_fidelity >= 0
    build_example(StyleBible)


class _Agent(BaseAgent[SceneVision]):
    stage = "lens"
    name = "test_lens"
    template = "P5_lens"
    output_model = SceneVision

    def check(self, parsed, variables):
        if parsed.scene_id != variables["scene"].id:
            raise ValueError("scene_id mismatch")


async def test_base_agent_repairs_once_then_rejects(offline_ctx: AgentContext, scene, style_bible, sequence_plan):
    offline_ctx.client = FakeLLM(fail_first=1)
    res = await _Agent(offline_ctx).run(key="S1/test", lens_card={"name": "kubrick"}, scene=scene, sequence_plan=sequence_plan, scene_constraints={"scene_id": "S1"}, style_bible=style_bible)
    assert res.attempts == 2 and res.parsed.scene_id == "S1" and res.snapshot_path is not None
    offline_ctx.client = FakeLLM(fail_first=2)
    with pytest.raises(ValidationRejected):
        await _Agent(offline_ctx).run(key="S1/test", lens_card={"name": "kubrick"}, scene=scene, sequence_plan=sequence_plan, scene_constraints={"scene_id": "S1"}, style_bible=style_bible)


async def test_base_agent_rejects_impersonation(offline_ctx: AgentContext, scene, style_bible, sequence_plan):
    def responder(call):
        v = build_example(SceneVision, {"lens": "kubrick", "scene_id": "S1"})
        if not call.is_repair:
            v.governing_idea = "As I once said on the set of my film, symmetry is fear"
        return v

    offline_ctx.client = FakeLLM(responder)
    res = await _Agent(offline_ctx).run(key="S1/test", lens_card={"name": "kubrick"}, scene=scene, sequence_plan=sequence_plan, scene_constraints={"scene_id": "S1"}, style_bible=style_bible)
    assert res.attempts == 2 and "As I once said" not in res.parsed.governing_idea


async def test_base_agent_header_is_cached_system_block(offline_ctx_with_header: AgentContext, scene, style_bible, sequence_plan):
    ctx = offline_ctx_with_header
    await _Agent(ctx).run(key="S1/test", lens_card={"name": "kubrick"}, scene=scene, sequence_plan=sequence_plan, scene_constraints={"scene_id": "S1"}, style_bible=style_bible)
    call = ctx.client.last
    assert call.system[-1]["cache_control"]["type"] == "ephemeral" and "KAITHA" in call.system[-1]["text"]
    assert call.kwargs["output_config"]["effort"] == "high"


async def test_budget_flagging(offline_ctx: AgentContext, scene, style_bible, sequence_plan):
    offline_ctx.config = offline_ctx.config.model_copy(update={"budgets": offline_ctx.config.budgets.model_copy(update={"lens": 10})})
    res = await _Agent(offline_ctx).run(key="S1/test", lens_card={"name": "kubrick"}, scene=scene, sequence_plan=sequence_plan, scene_constraints={"scene_id": "S1"}, style_bible=style_bible)
    assert res.over_budget is True
    offline_ctx.config = offline_ctx.config.model_copy(update={"budgets": offline_ctx.config.budgets.model_copy(update={"lens": 10, "strict_budgets": True})})
    with pytest.raises(ValidationRejected):
        await _Agent(offline_ctx).run(key="S1/test", lens_card={"name": "kubrick"}, scene=scene, sequence_plan=sequence_plan, scene_constraints={"scene_id": "S1"}, style_bible=style_bible)
