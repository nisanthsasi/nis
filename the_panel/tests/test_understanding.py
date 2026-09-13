"""CP-3 understanding tests: P2a film analysis, chunked P2b scene analysis, flags from the brief, goldens.

Everything runs offline through FakeLLM with the stub templates; responders build their answers
from the five-scene ParsedScript so ids line up (or deliberately do not).
"""
from __future__ import annotations

import json
from typing import Any

import pytest

from the_panel.agents.analyst import FilmAnalystAgent, SceneAnalystAgent, apply_film_flags, scene_ids_of
from the_panel.agents.base import AgentContext, ValidationRejected
from the_panel.orchestrator.header import build_film_brief_header
from the_panel.orchestrator.understand import neighbour_summary, provisional_header, run_film_analysis, run_scene_analysis
from the_panel.schemas import (
    Beat,
    DayNight,
    FilmBrief,
    IntExt,
    LoadBearingBeat,
    ParsedScript,
    PleasureType,
    ReleaseTarget,
    Scene,
    SceneSkeleton,
    SequenceEntry,
    SetPieceCandidate,
    ThemeAudit,
    assert_no_shot_fields,
)
from the_panel.testing import FakeLLM
from the_panel.testing.fake_llm import FakeCall

from .conftest import GOLDEN_DIR, make_film_brief, make_scene

ANNOTATIONS: dict[str, Any] = json.loads((GOLDEN_DIR / "understanding_annotations.json").read_text(encoding="utf-8"))["five_scene_pilot"]
IDS: list[str] = ANNOTATIONS["scene_ids"]

SLUGS: dict[str, tuple[str, IntExt, DayNight, str]] = {
    "S1": ("EXT. VYPIN JETTY - NIGHT", IntExt.EXT, DayNight.NIGHT, "VYPIN JETTY"),
    "S2": ("INT. AMBULANCE - CONTINUOUS", IntExt.INT, DayNight.CONTINUOUS, "AMBULANCE"),
    "S3": ("EXT. GOSHREE BRIDGE CHECKPOINT - NIGHT", IntExt.EXT, DayNight.NIGHT, "GOSHREE BRIDGE CHECKPOINT"),
    "S4": ("INT. KOCHI FLAT - LATER", IntExt.INT, DayNight.LATER, "KOCHI FLAT"),
    "S5": ("INT. KOCHI FLAT - DAWN", IntExt.INT, DayNight.DAWN, "KOCHI FLAT"),
}


# ------------------------------------------------------------------ fixtures & responders


def make_skeleton(scene_id: str) -> SceneSkeleton:
    slug, int_ext, day_night, location = SLUGS[scene_id]
    number = int(scene_id[1:])
    return SceneSkeleton(
        id=scene_id,
        number=number,
        slug=slug,
        int_ext=int_ext,
        day_night=day_night,
        location_raw=location,
        location_canonical=location,
        page_start=float(number),
        page_eighths=6,
        characters=["ANJU", "RAVI"] if number % 2 else ["ANJU", "AMMACHI"],
        action_lines=[f"Action line one of {scene_id}.", f"Action line two of {scene_id}.", f"Action line three of {scene_id} must not be summarised."],
        line_start=number * 40,
        line_end=number * 40 + 30,
    )


def make_parsed() -> ParsedScript:
    return ParsedScript(scenes=[make_skeleton(sid) for sid in IDS], source_format="fountain", total_pages=5)


def brief_from_annotations(**overrides: Any) -> FilmBrief:
    ann = ANNOTATIONS
    base: dict[str, Any] = dict(
        title=ann["title"],
        load_bearing_beats=[LoadBearingBeat(**b) for b in ann["load_bearing_beats"]],
        sequences=[SequenceEntry(**q) for q in ann["sequences"]],
        set_piece_candidates=[SetPieceCandidate(**c) for c in ann["set_piece_candidates"]],
        theme_audit=ThemeAudit(dramatised=["S3 — the choice at the barrier"], silent=["S2"], preaches=[]),
        release_target=ann["release_target"],
        human_digest="A night, an ambulance, a debt: the pilot sequence closes every exit on Anju until the locket comes home.",
    )
    base.update(overrides)
    return make_film_brief(**base)


def scene_from_annotation(scene_id: str, **overrides: Any) -> Scene:
    """The scene analyst's answer for one scene — flags the brief owns are left unset on purpose."""
    sk = make_skeleton(scene_id)
    a = ANNOTATIONS["scenes"][scene_id]
    base: dict[str, Any] = dict(
        slug=sk.slug,
        int_ext=sk.int_ext,
        day_night=sk.day_night,
        location=sk.location_canonical,
        characters=list(sk.characters),
        emotional_temperature=a["emotional_temperature"],
        set_piece=a["set_piece"],
        set_piece_kind=a.get("set_piece_kind"),
        must_remember=a.get("must_remember"),
        pleasure_type=PleasureType(a["pleasure_type"]),
        load_bearing=False,
        sequence_id=None,
    )
    base.update(overrides)
    return make_scene(scene_id, sk.number, **base)


def golden_responder(call: FakeCall) -> Any:
    if call.output_format is FilmBrief:
        return brief_from_annotations()
    return scene_from_annotation(call.hints["scene_id"])


def _neighbour_sections(prompt: str) -> tuple[str, str]:
    """The stub template prints ``prev_scene_summary: <json>`` then ``next_scene_summary: <json>``."""
    _, rest = prompt.split("prev_scene_summary:", 1)
    prev, nxt = rest.split("next_scene_summary:", 1)
    return prev.strip(), nxt.strip()


def _scene_calls(fake_llm: FakeLLM) -> dict[str, FakeCall]:
    return {c.hints["scene_id"]: c for c in fake_llm.calls if c.output_format is Scene}


# ------------------------------------------------------------------ schema guard


def test_scene_report_card_carries_no_shot_fields():
    assert_no_shot_fields(Scene)
    assert not [f for f in Scene.model_fields if "shot" in f.lower()]


# ------------------------------------------------------------------ film analysis (P2a)


async def test_film_analysis_ids_reference_real_scenes(offline_ctx: AgentContext, fake_llm: FakeLLM):
    parsed = make_parsed()
    fake_llm.responder = golden_responder
    res = await run_film_analysis(offline_ctx, parsed, release_target=ReleaseTarget.BOTH, cast_notes="Anju — confirmed lead")
    brief = res.parsed
    valid = set(scene_ids_of(parsed))
    assert res.attempts == 1 and res.stage == "analyst_film" and res.snapshot_path is not None
    assert {b.scene_id for b in brief.load_bearing_beats} <= valid
    assert {c.scene_id for c in brief.set_piece_candidates} <= valid
    assert sorted(sid for q in brief.sequences for sid in q.scene_ids) == IDS
    assert brief.load_bearing_scene_ids() == {"S1", "S3", "S5"}
    prompt = fake_llm.last.prompt
    assert all(f'"id": "{sid}"' in prompt for sid in IDS) and "release_target: \"both\"" in prompt and "Anju — confirmed lead" in prompt
    assert fake_llm.last.system[-1]["text"].startswith("You are one specialist")  # L2a: no header yet


async def test_film_analysis_default_offline_example_is_valid(offline_ctx: AgentContext):
    parsed = make_parsed()
    res = await run_film_analysis(offline_ctx, parsed, release_target="ott", budget_tier="low")
    assert res.attempts == 1 and res.parsed.release_target == ReleaseTarget.OTT and res.parsed.budget_tier.value == "low"
    FilmAnalystAgent(offline_ctx).check(res.parsed, {"scenes": parsed.scenes, "release_target": "ott", "budget_tier": "low"})


async def test_dangling_scene_id_triggers_repair_then_rejection(offline_ctx: AgentContext, fake_llm: FakeLLM):
    fake_llm.responder = lambda call: brief_from_annotations(load_bearing_beats=[LoadBearingBeat(name="inciting", scene_id="S99")])
    with pytest.raises(ValidationRejected) as exc:
        await run_film_analysis(offline_ctx, make_parsed(), release_target="both")
    assert "S99" in exc.value.error
    assert len(fake_llm.calls) == 2 and fake_llm.calls[1].is_repair and "S99" in fake_llm.calls[1].prompt


@pytest.mark.parametrize(
    "overrides,needle",
    [
        ({"sequences": [SequenceEntry(sequence_id="SEQ1", scene_ids=["S1", "S2", "S3"], function="f")]}, "cover every scene exactly once"),
        ({"sequences": [SequenceEntry(sequence_id="SEQ1", scene_ids=["S1", "S2", "S3"], function="f"), SequenceEntry(sequence_id="SEQ2", scene_ids=["S3", "S4", "S5"], function="g")]}, "covered twice \\['S3'\\]"),
        ({"set_piece_candidates": [SetPieceCandidate(scene_id="S3", kind="action", pleasure_type="none")]}, "not a set-piece"),
        ({"theme_audit": ThemeAudit()}, "theme_audit is mandatory"),
        ({"human_digest": "word " * 251}, "≤ 250"),
        ({"release_target": "theatrical"}, "release_target is an input"),
    ],
)
def test_film_analyst_check_rules(offline_ctx: AgentContext, overrides: dict[str, Any], needle: str):
    agent = FilmAnalystAgent(offline_ctx)
    variables = {"scenes": make_parsed().scenes, "release_target": "both"}
    agent.check(brief_from_annotations(), variables)
    with pytest.raises(ValueError, match=needle):
        agent.check(brief_from_annotations(**overrides), variables)


# ------------------------------------------------------------------ scene analysis (P2b)


async def test_scene_analysis_is_chunked_in_order_with_neighbour_summaries(offline_ctx: AgentContext, fake_llm: FakeLLM):
    parsed, brief = make_parsed(), brief_from_annotations()
    fake_llm.responder = golden_responder
    scenes = await run_scene_analysis(offline_ctx, parsed, brief, chunk_size=2, concurrency=2)
    assert [s.id for s in scenes] == IDS and [s.number for s in scenes] == [1, 2, 3, 4, 5]
    calls = _scene_calls(fake_llm)
    assert list(calls) == IDS  # one P2b call per scene
    sections = {sid: _neighbour_sections(c.prompt) for sid, c in calls.items()}
    for i, sid in enumerate(IDS):
        prev, nxt = sections[sid]
        assert prev == "null" if i == 0 else f'"id": "{IDS[i - 1]}"' in prev
        assert nxt == "null" if i == len(IDS) - 1 else f'"id": "{IDS[i + 1]}"' in nxt
        assert "must not be summarised" not in prev + nxt  # skeleton summaries carry only two action lines
    # chunks [S1,S2] [S3,S4] [S5]: a neighbour read in an earlier chunk contributes its report card, a same-chunk one its skeleton
    assert '"must_feel"' in sections["S3"][0] and '"must_feel"' in sections["S5"][0]
    assert '"action"' in sections["S2"][0] and '"action"' in sections["S4"][0]
    assert all('"action"' in nxt for _, nxt in list(sections.values())[:-1])  # the next scene is never analysed yet


async def test_scene_analysis_applies_flags_from_the_brief(offline_ctx: AgentContext, fake_llm: FakeLLM):
    parsed, brief = make_parsed(), brief_from_annotations()
    fake_llm.responder = golden_responder
    scenes = {s.id: s for s in await run_scene_analysis(offline_ctx, parsed, brief)}
    assert scenes["S1"].load_bearing and scenes["S3"].load_bearing and scenes["S5"].load_bearing  # beats in the brief
    assert scenes["S4"].load_bearing and scenes["S4"].emotional_temperature == 8  # temperature ≥ 8 alone
    assert not scenes["S2"].load_bearing
    assert {sid: s.sequence_id for sid, s in scenes.items()} == {"S1": "SEQ1", "S2": "SEQ1", "S3": "SEQ1", "S4": "SEQ2", "S5": "SEQ2"}
    assert scenes["S3"].is_full_panel and scenes["S4"].is_full_panel and not scenes["S2"].is_full_panel


async def test_scene_analysis_caches_a_provisional_header(offline_ctx: AgentContext, fake_llm: FakeLLM):
    parsed, brief = make_parsed(), brief_from_annotations()
    fake_llm.responder = golden_responder
    assert offline_ctx.header is None
    await run_scene_analysis(offline_ctx, parsed, brief, chunk_size=5)
    assert offline_ctx.header is not None and not offline_ctx.header.frozen and offline_ctx.header.token_estimate <= 3000
    block = _scene_calls(fake_llm)["S1"].system[-1]
    assert block["cache_control"]["type"] == "ephemeral" and ANNOTATIONS["title"] in block["text"] and "inciting→S1" in block["text"]
    frozen = build_film_brief_header(brief, None, frozen=True)
    offline_ctx.header = frozen
    assert provisional_header(offline_ctx, make_film_brief(title="OTHER")) is frozen  # a frozen header is never replaced


async def test_default_offline_example_scene_passes_the_check(offline_ctx: AgentContext):
    parsed, brief = make_parsed(), brief_from_annotations()
    scenes = await run_scene_analysis(offline_ctx, parsed, brief, chunk_size=3)
    assert [s.id for s in scenes] == IDS and all(s.sequence_id == brief.sequence_for(s.id) for s in scenes)
    assert [s.slug for s in scenes] == [SLUGS[sid][0] for sid in IDS]


async def test_set_piece_without_must_remember_is_rejected(offline_ctx: AgentContext, fake_llm: FakeLLM):
    sk = make_skeleton("S3")

    def responder(call: FakeCall) -> dict[str, Any]:
        return {"id": "S3", "number": 3, "slug": sk.slug, "int_ext": "EXT", "day_night": "NIGHT", "location": sk.location_canonical, "must_feel": "the barrier is gone", "rasa": {"primary": "veera"}, "set_piece": True, "set_piece_kind": "action", "pleasure_type": "thrill"}

    fake_llm.responder = responder
    with pytest.raises(ValidationRejected, match="must_remember"):
        await run_scene_analysis(offline_ctx, ParsedScript(scenes=[sk]), brief_from_annotations())
    assert len(fake_llm.calls) == 2 and fake_llm.calls[1].is_repair


@pytest.mark.parametrize(
    "overrides,needle",
    [
        ({"id": "S9"}, "unchanged from the skeleton"),
        ({"number": 4}, "unchanged from the skeleton"),
        ({"beats": [Beat(n=1, action="a", reaction="r"), Beat(n=3, action="a", reaction="r")], "tension_curve": [2, 4]}, "numbered 1..2 consecutively"),
        ({"tension_curve": [1, 2, 3]}, "one 0–10 value per beat"),
        ({"must_feel": "  "}, "must_feel is required"),
        ({"set_piece": True, "must_remember": "the barrier", "set_piece_kind": None}, "set_piece_kind"),
        ({"set_piece": True, "must_remember": "the barrier", "set_piece_kind": "action", "pleasure_type": "none"}, "cannot be 'none'"),
    ],
)
def test_scene_analyst_check_rules(offline_ctx: AgentContext, overrides: dict[str, Any], needle: str):
    agent, sk = SceneAnalystAgent(offline_ctx), make_skeleton("S3")
    variables = {"scene": sk, "prev_scene_summary": None, "next_scene_summary": None}
    scene = scene_from_annotation("S3")
    agent.check(scene, variables)
    with pytest.raises(ValueError, match=needle):
        agent.check(scene.model_copy(update=overrides), variables)


def test_scene_analyst_requires_rasa_to_be_stated(offline_ctx: AgentContext):
    data = make_scene("S3", 3).model_dump()
    del data["rasa"]  # a card whose rasa was never stated would silently fall back to the default
    scene = Scene.model_validate(data)
    assert "rasa" not in scene.model_fields_set
    with pytest.raises(ValueError, match="rasa is required"):
        SceneAnalystAgent(offline_ctx).check(scene, {"scene": make_skeleton("S3")})


def test_apply_film_flags_rules():
    brief = brief_from_annotations()
    cold = apply_film_flags(scene_from_annotation("S2", emotional_temperature=7), brief)
    assert not cold.load_bearing and cold.sequence_id == "SEQ1"
    hot = apply_film_flags(scene_from_annotation("S2", emotional_temperature=8), brief)
    assert hot.load_bearing
    strict = apply_film_flags(scene_from_annotation("S2", emotional_temperature=8), brief, temperature_threshold=9)
    assert not strict.load_bearing
    beat = apply_film_flags(scene_from_annotation("S1", emotional_temperature=3), brief)
    assert beat.load_bearing  # in the brief's load-bearing beats
    unconfirmed = apply_film_flags(scene_from_annotation("S3", set_piece=False, set_piece_kind=None, must_remember=None), brief)
    assert not unconfirmed.set_piece and any(n.startswith("HUMAN_QUESTION") and "action set-piece candidate" in n for n in unconfirmed.director_notes)
    apply_film_flags(unconfirmed, brief)
    assert sum(n.startswith("HUMAN_QUESTION") for n in unconfirmed.director_notes) == 1  # idempotent
    confirmed = apply_film_flags(scene_from_annotation("S3"), brief)
    assert confirmed.set_piece and not confirmed.director_notes


def test_neighbour_summary_shapes():
    sk = make_skeleton("S2")
    summary = neighbour_summary(sk)
    assert summary == {"id": "S2", "slug": sk.slug, "characters": ["ANJU", "AMMACHI"], "action": sk.action_lines[:2]}
    analysed = neighbour_summary(scene_from_annotation("S2"))
    assert analysed is not None and analysed["id"] == "S2" and "must_feel" in analysed and "action" not in analysed
    assert neighbour_summary(None) is None


async def test_scene_analysis_guards_its_bounds(offline_ctx: AgentContext):
    with pytest.raises(ValueError):
        await run_scene_analysis(offline_ctx, make_parsed(), brief_from_annotations(), chunk_size=0)
    with pytest.raises(ValueError):
        await run_scene_analysis(offline_ctx, make_parsed(), brief_from_annotations(), concurrency=0)


# ------------------------------------------------------------------ golden annotations


async def test_golden_flags_match_annotations(offline_ctx: AgentContext, fake_llm: FakeLLM):
    parsed = make_parsed()
    fake_llm.responder = golden_responder
    brief = (await run_film_analysis(offline_ctx, parsed, release_target=ANNOTATIONS["release_target"])).parsed
    assert [q.sequence_id for q in brief.sequences] == [q["sequence_id"] for q in ANNOTATIONS["sequences"]]
    scenes = await run_scene_analysis(offline_ctx, parsed, brief, chunk_size=2)
    assert len(scenes) == len(ANNOTATIONS["scenes"])
    for scene in scenes:
        expected = ANNOTATIONS["scenes"][scene.id]
        assert scene.load_bearing == expected["load_bearing"], scene.id
        assert scene.set_piece == expected["set_piece"], scene.id
        assert scene.sequence_id == expected["sequence_id"], scene.id
        assert scene.pleasure_type.value == expected["pleasure_type"], scene.id
        if expected["set_piece"]:
            assert scene.must_remember == expected["must_remember"] and scene.set_piece_kind.value == expected["set_piece_kind"]
    candidates = {c.scene_id for c in brief.set_piece_candidates}
    assert candidates == {s.id for s in scenes if s.set_piece}
    assert all(not s.director_notes for s in scenes)  # every candidate confirmed: no HUMAN_QUESTION raised
