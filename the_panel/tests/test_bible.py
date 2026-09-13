"""CP-4 tests: the breakdown's check rules and hard constraints; the Style Bible's check rules,
Gate-1 approval (posture set by the human, caps re-derived), the frozen header and posture policy."""
from __future__ import annotations

import math
from typing import Any

import pytest

from the_panel.agents.base import AgentContext, ValidationRejected
from the_panel.agents.breakdown import BreakdownAgent
from the_panel.agents.style_bible import StyleBibleAgent, bloc_of, panel_mix_problems, pleasure_map_problems
from the_panel.orchestrator.bible import approve_style_bible, bible_gate_summary, freeze_header, run_style_bible
from the_panel.orchestrator.breakdown import run_breakdown, scene_constraints_from
from the_panel.orchestrator.posture import policy_for, policy_for_posture
from the_panel.schemas import (
    Bloc,
    BreakdownResult,
    BreakdownRow,
    Caps,
    FilmBreakdown,
    GoverningReference,
    LensAffinity,
    PleasureMapEntry,
    ProductionFlag,
    Scene,
    SetPieceCosting,
    StyleBible,
)
from the_panel.testing import FakeLLM
from the_panel.testing.fake_llm import FakeCall

from .conftest import make_film_brief, make_scene, make_style_bible

# ------------------------------------------------------------------ breakdown fixtures


def _scenes() -> list[Scene]:
    return [
        make_scene("S1", 1, estimated_setups=5),
        make_scene("S2", 2, estimated_setups=4, production_flags=[ProductionFlag.NIGHT_EXT]),
        make_scene("S3", 3, estimated_setups=8, set_piece=True, set_piece_kind="action", must_remember="the barrier", pleasure_type="thrill", production_flags=[ProductionFlag.NIGHT_EXT, ProductionFlag.STUNT]),
    ]


FACTS = ["no more than 12 setups on any night", "one company move in the whole schedule", "S3 needs a road closure: one night only"]


def _row(scene: Scene, **overrides: Any) -> BreakdownRow:
    base: dict[str, Any] = dict(scene_id=scene.id, estimated_setups=scene.estimated_setups, page_eighths=scene.page_eighths, production_flags=list(scene.production_flags), cost_flag=scene.cost_flag, special_equipment=["Steadicam"] if scene.set_piece else [], light_window="blue hour" if scene.set_piece else "", cbfc_notes=["stunt violence, aftermath only"] if scene.set_piece else [])
    if scene.set_piece:
        base["set_piece_costing"] = SetPieceCosting(extra_shoot_days=1, rehearsal_days=1, cheapest_staging_keeping_must_remember="one lane, one police jeep, the barrier practical")
    base.update(overrides)
    return BreakdownRow(**base)


def _breakdown(scenes: list[Scene], rows: list[BreakdownRow] | None = None, **film: Any) -> BreakdownResult:
    film_base: dict[str, Any] = dict(budget_tier="low", feasibility_facts=list(FACTS), digest="three scenes, one night, one closure")
    film_base.update(film)
    return BreakdownResult(rows=rows if rows is not None else [_row(s) for s in scenes], film=FilmBreakdown(**film_base))


BREAKDOWN_VARS = {"budget_tier": "low", "release_target": "both"}


# ------------------------------------------------------------------ breakdown checks


def test_breakdown_check_accepts_a_complete_breakdown(offline_ctx: AgentContext):
    scenes = _scenes()
    BreakdownAgent(offline_ctx).check(_breakdown(scenes), {"scenes": scenes, **BREAKDOWN_VARS})


@pytest.mark.parametrize(
    "mutate,needle",
    [
        (lambda scenes: _breakdown(scenes, rows=[_row(s) for s in scenes[:2]]), "missing \\['S3'\\]"),
        (lambda scenes: _breakdown(scenes, rows=[_row(s) for s in scenes] + [_row(scenes[0], scene_id="S9")]), "unknown \\['S9'\\]"),
        (lambda scenes: _breakdown(scenes, rows=[_row(s) for s in scenes] + [_row(scenes[0])]), "duplicated \\['S1'\\]"),
        (lambda scenes: _breakdown(scenes, rows=[_row(s, set_piece_costing=None) for s in scenes]), "no set_piece_costing"),
        (lambda scenes: _breakdown(scenes, rows=[_row(s, set_piece_costing=SetPieceCosting()) if s.set_piece else _row(s) for s in scenes]), "cheapest staging"),
        (lambda scenes: _breakdown(scenes, feasibility_facts=[f"fact {i}" for i in range(6)]), "1–5 facts"),
        (lambda scenes: _breakdown(scenes, feasibility_facts=[]), "1–5 facts"),
        (lambda scenes: _breakdown(scenes, budget_tier="studio"), "budget_tier is an input"),
    ],
)
def test_breakdown_check_rules(offline_ctx: AgentContext, mutate, needle: str):
    scenes = _scenes()
    with pytest.raises(ValueError, match=needle):
        BreakdownAgent(offline_ctx).check(mutate(scenes), {"scenes": scenes, **BREAKDOWN_VARS})


async def test_run_breakdown_repairs_once_then_rejects_a_missing_row(offline_ctx: AgentContext, fake_llm: FakeLLM):
    scenes = _scenes()
    fake_llm.responder = lambda call: _breakdown(scenes, rows=[_row(s) for s in scenes[:2]])
    with pytest.raises(ValidationRejected, match="missing"):
        await run_breakdown(offline_ctx, scenes, budget_tier="low", release_target="both", budget_inr=2.5e7)
    assert len(fake_llm.calls) == 2 and fake_llm.calls[1].is_repair
    assert "budget_inr: 25000000.0" in fake_llm.calls[0].prompt and fake_llm.calls[0].model == offline_ctx.config.models.fast


async def test_run_breakdown_too_many_facts_is_rejected(offline_ctx: AgentContext, fake_llm: FakeLLM):
    scenes = _scenes()
    fake_llm.responder = lambda call: _breakdown(scenes, feasibility_facts=[f"fact {i}" for i in range(6)])
    with pytest.raises(ValidationRejected, match="1–5 facts"):
        await run_breakdown(offline_ctx, scenes, budget_tier="low", release_target="both")


async def test_run_breakdown_offline_example_covers_every_scene(offline_ctx: AgentContext):
    scenes = _scenes()
    result = await run_breakdown(offline_ctx, scenes, budget_tier="mid", release_target="theatrical")
    assert [r.scene_id for r in result.rows] == ["S1", "S2", "S3"]
    assert result.rows[2].set_piece_costing is not None and "the barrier" in result.rows[2].set_piece_costing.cheapest_staging_keeping_must_remember
    assert result.film.budget_tier == "mid" and 1 <= len(result.film.feasibility_facts) <= 5


def test_scene_constraints_carry_setup_ceiling_flags_and_facts():
    scenes = _scenes()
    constraints = scene_constraints_from(_breakdown(scenes))
    assert list(constraints) == ["S1", "S2", "S3"]
    for scene in scenes:
        c = constraints[scene.id]
        assert c.estimated_setups == scene.estimated_setups and c.max_setups == math.ceil(scene.estimated_setups * 1.25)
        assert c.production_flags == list(scene.production_flags) and c.feasibility_facts == FACTS and c.budget_tier == "low"
    assert (constraints["S1"].max_setups, constraints["S2"].max_setups, constraints["S3"].max_setups) == (7, 5, 10)
    assert constraints["S3"].special_equipment == ["Steadicam"] and constraints["S3"].light_window == "blue hour" and constraints["S3"].cbfc_notes


# ------------------------------------------------------------------ style bible fixtures


REFS = [GoverningReference(film=f, borrowed="one thing", refused="one thing") for f in ("Kammatipaadam", "Birdman", "Elippathayam")]
ARTHOUSE = (["kubrick", "bergman", "ray_adoor"], ["bong_joon_ho", "ozu"])
HYBRID = (["inarritu", "ray_adoor", "malayalam_new_wave"], ["bergman", "bong_joon_ho"])
MASS = (["rajamouli", "malayalam_new_wave", "kurosawa"], ["ray_adoor", "mani_ratnam"])
BIBLE_VARS = {"film_brief": make_film_brief(), "feasibility_facts": FACTS, "release_target": "both"}


def _digest(posture: int, caps: Caps) -> str:
    return f"posture {posture}/10; caps: elevation {caps.elevation_cues}, slow-mo {caps.slow_motion}, needle drops {caps.needle_drops}; pleasure map SEQ1 thrill@S3, SEQ2 tears@S5"


def _bible(posture: int, primary: list[str], secondary: list[str], **overrides: Any) -> StyleBible:
    caps = overrides.get("caps", policy_for_posture(posture).caps)
    base: dict[str, Any] = dict(governing_references=list(REFS), lens_affinity=LensAffinity(primary=list(primary), secondary=list(secondary)), caps=caps, digest=_digest(posture, caps), manifesto="One night, one ambulance, no cut until the body changes state.")
    base.update(overrides)
    return make_style_bible(posture, approved=False, **base)


# ------------------------------------------------------------------ style bible checks


def test_bloc_classification():
    assert bloc_of("ray_adoor") == Bloc.AUTEUR and bloc_of("tarkovsky") == Bloc.AUTEUR
    assert bloc_of("rajamouli") == Bloc.COMMERCIAL and bloc_of("lokesh_kanagaraj") == Bloc.COMMERCIAL
    assert bloc_of("deakins") is None and bloc_of("nobody") is None


@pytest.mark.parametrize("posture,primary,secondary", [(2, *ARTHOUSE), (3, *ARTHOUSE), (5, *HYBRID), (4, *HYBRID), (8, *MASS), (7, *MASS)])
def test_valid_affinities_pass_the_panel_mix(offline_ctx: AgentContext, posture: int, primary: list[str], secondary: list[str]):
    assert panel_mix_problems(LensAffinity(primary=primary, secondary=secondary), posture) == []
    StyleBibleAgent(offline_ctx).check(_bible(posture, primary, secondary), BIBLE_VARS)


@pytest.mark.parametrize(
    "posture,primary,secondary,needle",
    [
        (2, ["kubrick", "bergman", "ray_adoor"], ["tarkovsky", "ozu"], "posture 2 ≤ 3 requires at least one commercial"),
        (2, ["kubrick", "bergman", "bong_joon_ho"], ["ray_adoor", "ozu"], "needs ≥ 3 auteur primaries"),
        (5, ["kubrick", "bergman", "ray_adoor"], ["bong_joon_ho", "ozu"], "needs ≥ 1 commercial/energy primaries"),
        (5, ["kubrick", "bergman", "ray_adoor"], ["bong_joon_ho", "ozu"], "posture 5 ≥ 5 requires at least one commercial"),
        (8, ["rajamouli", "kurosawa", "ray_adoor"], ["spielberg", "mani_ratnam"], "needs ≥ 2 commercial/energy primaries"),
        (8, ["rajamouli", "malayalam_new_wave", "scorsese"], ["mani_ratnam", "boyle"], "needs ≥ 1 auteur secondaries"),
        (5, ["inarritu", "ray_adoor", "nobody"], ["bergman", "bong_joon_ho"], "unknown lens ids \\['nobody'\\]"),
        (5, ["inarritu", "ray_adoor"], ["bergman", "bong_joon_ho"], "exactly 3 lenses"),
        (5, ["inarritu", "ray_adoor", "malayalam_new_wave"], ["bergman"], "exactly 2 lenses"),
        (5, ["inarritu", "ray_adoor", "malayalam_new_wave"], ["ray_adoor", "bong_joon_ho"], "one seat only"),
        (9, ["rajamouli", "malayalam_new_wave", "kurosawa"], ["ray_adoor", "mani_ratnam"], "'kurosawa' may not be a primary at posture 9"),
    ],
)
def test_panel_mix_violations_are_rejected(offline_ctx: AgentContext, posture: int, primary: list[str], secondary: list[str], needle: str):
    problems = panel_mix_problems(LensAffinity(primary=primary, secondary=secondary), posture)
    assert any(needle.replace("\\", "") in p for p in problems), problems
    with pytest.raises(ValueError, match=needle):
        StyleBibleAgent(offline_ctx).check(_bible(posture, primary, secondary), BIBLE_VARS)


@pytest.mark.parametrize(
    "overrides,needle",
    [
        ({"governing_references": REFS[:2]}, "exactly 3 governing references"),
        ({"posture_defence": " "}, "posture_defence is required"),
        ({"digest": ""}, "digest is required"),
        ({"digest": "posture 5; caps stated; " + "word " * 700}, "keep it ≤ 600"),
        ({"digest": "caps: elevation three, slow-mo three, needle drops two"}, "state the posture number"),
        ({"digest": "posture 5/10 hybrid; elevation 3, slow-mo 3"}, "state the caps"),
        ({"pleasure_map": [PleasureMapEntry(sequence_id="SEQ1", pleasure_type="thrill", set_piece_scene_id="S3")]}, "missing \\['SEQ2'\\]"),
        ({"pleasure_map": [PleasureMapEntry(sequence_id="SEQ1", pleasure_type="thrill", set_piece_scene_id="S5"), PleasureMapEntry(sequence_id="SEQ2", pleasure_type="tears")]}, "S5 is not in that sequence"),
        ({"pleasure_map": [PleasureMapEntry(sequence_id="SEQ1", pleasure_type="thrill"), PleasureMapEntry(sequence_id="SEQ2", pleasure_type="tears"), PleasureMapEntry(sequence_id="SEQ9", pleasure_type="none", reason_if_none="x")]}, "unknown \\['SEQ9'\\]"),
    ],
)
def test_style_bible_check_rules(offline_ctx: AgentContext, overrides: dict[str, Any], needle: str):
    with pytest.raises(ValueError, match=needle):
        StyleBibleAgent(offline_ctx).check(_bible(5, *HYBRID, **overrides), BIBLE_VARS)


def test_pleasure_map_problems_without_sequences_is_empty():
    assert pleasure_map_problems(_bible(5, *HYBRID), make_film_brief(sequences=[])) == []


async def test_run_style_bible_returns_pending_and_renders_inputs(offline_ctx: AgentContext, fake_llm: FakeLLM):
    def responder(call: FakeCall) -> StyleBible:
        return _bible(5, *HYBRID, approved_by="the model")

    fake_llm.responder = responder
    bible = await run_style_bible(offline_ctx, make_film_brief(), FACTS, release_target="theatrical", director_intent="one take per scene", references=["Birdman"], posture_hint=5)
    assert bible.approved_by == "pending" and not bible.is_approved and bible.version == "1.0"
    prompt = fake_llm.last.prompt
    assert "one take per scene" in prompt and '"Birdman"' in prompt and "posture_hint: 5" in prompt and FACTS[0] in prompt and 'release_target: "theatrical"' in prompt
    assert fake_llm.last.model == offline_ctx.config.models.reasoning


@pytest.mark.parametrize("posture", [2, 5, 8])
async def test_run_style_bible_offline_example_seats_the_posture(offline_ctx: AgentContext, posture: int):
    bible = await run_style_bible(offline_ctx, make_film_brief(), FACTS, release_target="both", posture_hint=posture)
    assert bible.commercial_posture == posture and bible.approved_by == "pending"
    assert panel_mix_problems(bible.lens_affinity, posture) == [] and bible.caps == policy_for_posture(posture).caps
    assert {e.sequence_id for e in bible.pleasure_map} == {"SEQ1", "SEQ2"} and len(bible.governing_references) == 3


async def test_run_style_bible_rejects_a_bible_that_breaks_the_mix(offline_ctx: AgentContext, fake_llm: FakeLLM):
    fake_llm.responder = lambda call: _bible(8, *HYBRID)
    with pytest.raises(ValidationRejected, match="commercial/energy primaries"):
        await run_style_bible(offline_ctx, make_film_brief(), FACTS, release_target="both")
    assert len(fake_llm.calls) == 2


# ------------------------------------------------------------------ Gate 1: approval


def test_approve_sets_approver_and_rederives_preset_caps_on_posture_change():
    proposed = _bible(5, *HYBRID, device_permissions=list(policy_for_posture(5).device_permissions))
    approved = approve_style_bible(proposed, "nisanth", posture=8, edits={"lens_affinity": {"primary": MASS[0], "secondary": MASS[1]}})
    assert approved.is_approved and approved.approved_by == "nisanth" and approved.commercial_posture == 8 and approved.band == "mass"
    assert approved.caps == policy_for_posture(8).caps and approved.caps.slow_motion is None
    assert approved.device_permissions == policy_for_posture(8).device_permissions and approved.permits("freeze frame")
    assert "P4 proposed 5" in approved.posture_defence and "nisanth" in approved.posture_defence
    assert proposed.approved_by == "pending" and proposed.commercial_posture == 5  # the proposal is untouched


def test_approve_keeps_caps_and_permissions_that_were_chosen_with_a_reason():
    chosen_caps = Caps(elevation_cues=1, slow_motion=0, needle_drops=0)
    proposed = _bible(5, *HYBRID, caps=chosen_caps, device_permissions=list(policy_for_posture(5).device_permissions))
    approved = approve_style_bible(proposed, "nisanth", posture=8, edits={"lens_affinity": {"primary": MASS[0], "secondary": MASS[1]}})
    assert approved.caps == chosen_caps  # not the hybrid preset, so the human's/P4's reasoned cap survives the posture change
    assert approved.device_permissions == policy_for_posture(8).device_permissions  # still the preset → re-derived


def test_approve_edits_win_outright():
    proposed = _bible(5, *HYBRID)
    approved = approve_style_bible(proposed, "nisanth", posture=8, edits={"caps": {"elevation_cues": 2, "slow_motion": 2, "needle_drops": 1}, "lens_affinity": {"primary": MASS[0], "secondary": MASS[1]}, "refusals": ["an interval block without a reversal"]})
    assert approved.caps == Caps(elevation_cues=2, slow_motion=2, needle_drops=1) and approved.refusals == ["an interval block without a reversal"]


def test_approve_without_posture_change_keeps_the_proposal():
    proposed = _bible(5, *HYBRID, caps=Caps(elevation_cues=2, slow_motion=1, needle_drops=1))
    approved = approve_style_bible(proposed, "nisanth")
    assert approved.commercial_posture == 5 and approved.caps == proposed.caps and approved.device_permissions == proposed.device_permissions
    assert approved.posture_defence == proposed.posture_defence and approved.is_approved
    same = approve_style_bible(proposed, "nisanth", posture=5)
    assert same.caps == proposed.caps and "at approval" not in same.posture_defence


def test_approve_refuses_an_affinity_that_no_longer_seats_the_posture():
    with pytest.raises(ValueError, match="panel mix for posture 8"):
        approve_style_bible(_bible(5, *HYBRID), "nisanth", posture=8)


@pytest.mark.parametrize("approver", ["", "  ", "pending"])
def test_approve_requires_a_named_human(approver: str):
    with pytest.raises(ValueError, match="approved_by"):
        approve_style_bible(_bible(5, *HYBRID), approver)


def test_approve_refuses_posture_through_edits():
    with pytest.raises(ValueError, match="'posture' argument"):
        approve_style_bible(_bible(5, *HYBRID), "nisanth", edits={"commercial_posture": 8})


# ------------------------------------------------------------------ the frozen header and the posture policy


def test_freeze_header_is_frozen_within_budget_and_carries_posture_and_caps():
    brief = make_film_brief()
    approved = approve_style_bible(_bible(8, *MASS), "nisanth")
    header = freeze_header(brief, approved, 3000)
    assert header.frozen and header.token_estimate <= 3000 and not header.dropped_sections
    assert "posture 8/10 (mass)" in header.text and "Caps: elevation 5, slow-mo ∞, needle drops 4" in header.text and "approved by" not in header.text
    assert "(nisanth)" in header.text and approved.digest in header.text and brief.style_bible_digest == approved.digest
    assert header.system_block("1h")["cache_control"] == {"type": "ephemeral", "ttl": "1h"}


def test_freeze_header_requires_approval():
    with pytest.raises(PermissionError):
        freeze_header(make_film_brief(), _bible(5, *HYBRID), 3000)


def test_policy_for_approved_bible_reads_its_caps_and_band():
    chosen = Caps(elevation_cues=2, slow_motion=None, needle_drops=1)
    approved = approve_style_bible(_bible(8, *MASS, caps=chosen), "nisanth")
    policy = policy_for(approved, require_approved=True)
    assert policy.caps == chosen and policy.cap_for("slow motion") is None and policy.cap_for("bgm elevation") == 2
    assert policy.band == "mass" and policy.rubric_weights["engagement"] == 0.25 and policy.panel_mix.primaries_commercial_min == 2
    assert "caps" in policy.overrides_applied and "device_permissions" in policy.overrides_applied


# ------------------------------------------------------------------ the Gate-1 screen


def test_gate_summary_shows_everything_the_human_decides_on():
    bible = _bible(5, *HYBRID, human_questions=["Cold open at the jetty or at the flat?"])
    text = bible_gate_summary(bible)
    for needle in (
        "pending approval",
        "HOW WE SHOOT THIS FILM",
        bible.manifesto,
        "COMMERCIAL POSTURE: 5/10 (hybrid)",
        f"Defence: {bible.posture_defence}",
        "Audience promise: thrill, tears, dread",
        "- SEQ1: thrill — set-piece S3",
        "- SEQ2: tears — set-piece S5",
        "elevation cues: 3 · slow motion: 3 · needle drops: 2",
        "- slow motion → must pay off: Anju's decision at the barrier",
        "- primary: inarritu, ray_adoor, malayalam_new_wave",
        "- secondary: bergman, bong_joon_ho",
        "- score under dialogue in Act 1",
        "HUMAN QUESTIONS",
        "Cold open at the jetty or at the flat?",
    ):
        assert needle in text, needle
    approved = approve_style_bible(_bible(8, *MASS, pleasure_map=[PleasureMapEntry(sequence_id="SEQ1", pleasure_type="thrill", set_piece_scene_id="S3"), PleasureMapEntry(sequence_id="SEQ2", pleasure_type="none", reason_if_none="the price is paid in silence")]), "nisanth")
    text = bible_gate_summary(approved)
    assert "approved by nisanth" in text and "slow motion: unlimited (each earned)" in text and "- SEQ2: none (reason: the price is paid in silence)" in text
