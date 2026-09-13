"""Prompt templates and lens cards.

Every registry template renders with the real environment (StrictUndefined) from realistic
variables built with the conftest factories, carries its SPEC phrases and names every field of
its output schema in the contract. Every roster lens has a card that validates as a prior —
decision rules, devices, refusals, declared blind spots — and never reads as an impersonation.
"""
from __future__ import annotations

import re
from typing import Any

import jinja2
import pytest
from pydantic import BaseModel, ValidationError

from the_panel.agents.base import AgentContext, BaseAgent
from the_panel.orchestrator.caps import CapLedger
from the_panel.orchestrator.header import build_film_brief_header
from the_panel.orchestrator.posture import policy_for
from the_panel.prompts import registry
from the_panel.prompts.loader import (
    ROSTER_BLOC,
    LensCard,
    directing_cards_for_posture,
    load_all_lens_cards,
    load_lens_card,
    validate_all_cards,
)
from the_panel.prompts.registry import (
    ALL_DIRECTING_LENSES,
    AUTEUR_EXTENSION_LENSES,
    AUTEUR_LENSES,
    COMMERCIAL_EXTENSION_LENSES,
    COMMERCIAL_LENSES,
    CRAFT_LENSES,
    DP_LENSES,
    LENSES_DIR,
    PROMPTS_DIR,
    TEMPLATES,
)
from the_panel.schemas import (
    BreakdownResult,
    BreakdownRow,
    ContinuityReport,
    Critique,
    Department,
    DepartmentDirective,
    DepartmentOutput,
    DialogueBlock,
    EarnedDeviceReport,
    EngagementReport,
    FeasibilityReport,
    FilmBreakdown,
    FilmBrief,
    IntegratedScenePlan,
    JudgeVerdict,
    ParsedScript,
    Pushback,
    Scene,
    SceneConstraints,
    SceneSkeleton,
    SceneVision,
    SequencePlan,
    SequenceVision,
    StarCastEntry,
    StyleBible,
)
from the_panel.testing import build_example

from .conftest import make_film_brief, make_plan, make_scene, make_sequence_plan, make_style_bible, make_vision

LENS = "inarritu"
OTHER_LENSES = ("ray_adoor", "malayalam_new_wave")
SCENE_ID = "S3"

DEPT_BRIEFS: dict[Department, str] = {
    Department.CINEMATOGRAPHY: "P8.1 CINEMATOGRAPHY — final numbered shot list; lighting plan per setup; lens set; coverage order; one previz prompt per shot.",
    Department.EDITING: "P8.2 EDITING — cut philosophy; rhythm map; cut points keyed to beats; J/L-cut plan; the shot the scene cannot live without.",
    Department.COLOUR: "P8.3 COLOUR / GRADE — palette inside the act's colour arc; motif colours and carriers; colour energy; the colour sentence.",
    Department.MUSIC: "P8.4 MUSIC / BGM & SONG — permission; cue sheet with in-beat/out-beat; silence windows; elevation with cap accounting; song brief.",
    Department.SOUND: "P8.5 SOUND DESIGN — ambience beds; perspective plan; hero sound; silence events; impact design for mass beats.",
    Department.DESIGN: "P8.6 PRODUCTION DESIGN — blocking map; the one meaningful object; costume colour and class register; Kerala authenticity checklist.",
    Department.PERFORMANCE: "P8.7 PERFORMANCE — per character: objective, action verbs per beat, subtext line, what NOT to play; the Director's Note verbatim.",
}


# ------------------------------------------------------------------ realistic variables


def _dump(v: Any) -> Any:
    """Mirror BaseAgent.prepare: templates receive JSON-serialisable dicts, never models."""
    if isinstance(v, BaseModel):
        return v.model_dump(mode="json")
    if isinstance(v, list):
        return [_dump(x) for x in v]
    if isinstance(v, dict):
        return {k: _dump(x) for k, x in v.items()}
    return v


def _skeleton(scene_id: str = "S1", number: int = 1) -> SceneSkeleton:
    return SceneSkeleton(
        id=scene_id,
        number=number,
        slug="INT. KOCHI FLAT - NIGHT",
        int_ext="INT",
        day_night="NIGHT",
        location_raw="KOCHI FLAT",
        location_canonical="APARTMENT, KOCHI",
        page_start=float(number),
        page_eighths=8,
        characters=["ANJU", "RAVI"],
        dialogue_blocks=[DialogueBlock(character="ANJU", text="പണം എവിടെ, രവി?", dialogue_register="colloquial", region="Kochi", line_ref=12)],
        action_lines=["Anju slams the LEDGER on the table."],
        capitalised_items=["LEDGER"],
    )


def _set_piece_scene() -> Scene:
    return make_scene(SCENE_ID, 3, set_piece=True, set_piece_kind="action", must_remember="Anju's choice at the barrier", load_bearing=True, pleasure_type="thrill", energy_target=7, emotional_temperature=8)


def _plan(scene_id: str = SCENE_ID) -> IntegratedScenePlan:
    """A plan as the Integrator ships it: recommended is A or B; chosen is the human's and still null."""
    return make_plan(scene_id, recommended="A", chosen=None)


def _ledger(sb: StyleBible) -> CapLedger:
    ledger = CapLedger(sb.caps)
    ledger.spend("bgm elevation", "S1", "beat 2")
    return ledger


def _policy_dict(sb: StyleBible) -> dict[str, Any]:
    pol = policy_for(sb)
    return {
        "max_pleasure_gap_minutes": pol.max_pleasure_gap_minutes,
        "first_hook_minute": pol.first_hook_minute,
        "must_remember_per_act": pol.must_remember_per_act,
        "star_entry": pol.star_entry,
        "comedy": pol.comedy,
    }


def variables_for(key: str, *, optionals: bool = True) -> dict[str, Any]:
    """Realistic variables for every registry key, built from the conftest factories."""
    sb = make_style_bible(5)
    fb = make_film_brief()
    scene = _set_piece_scene()
    seq_plan = make_sequence_plan()
    plan = _plan()
    card = load_lens_card(LENS, with_dp_principles=True)
    ledger = _ledger(sb)
    pol = policy_for(sb)
    plans = [_plan("S1"), _plan("S2"), plan]
    constraints = SceneConstraints(scene_id=SCENE_ID, estimated_setups=6, max_setups=8, cost_flag="HIGH", production_flags=["night_ext", "stunt"], feasibility_facts=["no more than six night exteriors"])
    required: dict[str, Any]
    optional: dict[str, Any] = {}
    match key:
        case "P0_showrunner":
            required = {}
            optional = {"film_brief_header": build_film_brief_header(fb, sb).text}
        case "P1_parse":
            required = {"raw_text": "INT. KOCHI FLAT - NIGHT\n\nAnju slams the LEDGER on the table.\n\nANJU\nപണം എവിടെ, രവി?\n"}
            optional = {"format_hint": "fountain", "location_aliases": [{"alias": "KOCHI FLAT", "canonical": "APARTMENT, KOCHI"}]}
        case "P2a_film":
            required = {"scenes": [_skeleton("S1", 1), _skeleton("S2", 2)], "release_target": "both"}
            optional = {"mechanism_notes": "mechanism family: the carried body; transposition: a witness instead of a corpse", "cast_notes": "ANJU is played by a star; the script gives her an entry in S1", "budget_tier": "low"}
        case "P2b_scene":
            required = {"scene": _skeleton("S2", 2), "prev_scene_summary": make_scene("S1").brief(), "next_scene_summary": None}
        case "P3_breakdown":
            required = {"scenes": [make_scene("S1"), scene], "budget_tier": "low", "release_target": "both"}
            optional = {"budget_inr": 30_000_000}
        case "P4_style_bible":
            required = {"film_brief": fb, "feasibility_facts": ["no more than six night exteriors", "one company move"], "release_target": "both"}
            optional = {"director_intent": "a single-take noir that owes the audience thrill and colour", "references": [{"film": "Kammatipaadam", "why": "Kochi as a moral map"}], "posture_hint": 5}
        case "P5s_sequence_lens":
            required = {"lens_card": card, "sequence": fb.sequences[0], "pleasure_map_entry": sb.pleasure_map[0], "style_bible": sb, "release_target": "both"}
        case "P5_lens":
            required = {"lens_card": card, "sequence_plan": seq_plan, "scene": scene, "scene_constraints": constraints, "style_bible": sb}
        case "P6_critique":
            required = {"lens_card": card, "own_vision": make_vision(LENS, SCENE_ID), "other_visions": [make_vision(l, SCENE_ID) for l in OTHER_LENSES], "scene": scene, "style_bible": sb}
        case "P7_integrator":
            visions = [make_vision(l, SCENE_ID) for l in (LENS, *OTHER_LENSES)]
            critiques = [build_example(Critique, {"lens": v.lens, "scene_id": SCENE_ID}) for v in visions]
            required = {"visions": visions, "critiques": critiques, "scene": scene, "sequence_plan": seq_plan, "style_bible": sb, "scene_constraints": constraints, "caps_used_so_far": ledger.to_dict(), "rubric_weights": pol.rubric_weights}
            optional = {"consensus_devices": ["slow motion"], "lone_high_fidelity_lens": "ray_adoor", "lone_high_engagement": {"lens": "malayalam_new_wave", "pleasure_offer": "the group-reaction frame when the barrier lifts"}}
        case "P7s_sequence_integrator":
            required = {"sequence_visions": [build_example(SequenceVision, {"lens": l, "sequence_id": "SEQ1"}) for l in (LENS, *OTHER_LENSES)], "sequence": fb.sequences[0], "style_bible": sb, "pleasure_map_entry": sb.pleasure_map[0]}
        case "P8_department":
            required = {"dept": "colour", "dept_brief": DEPT_BRIEFS[Department.COLOUR], "plan": plan, "scene": scene, "style_bible": sb, "breakdown_row": BreakdownRow(scene_id=SCENE_ID, estimated_setups=6, production_flags=["night_ext"])}
            optional = {"caps_status": ledger.status()}
        case "P9_1_continuity":
            directive = DepartmentDirective(dept="colour", scene_id="S1", governing_idea=plans[0].governing_idea, pleasure_beat=plans[0].pleasure_beat, directive={"palette": "sodium and teal"}, must_not=["teal-orange"])
            required = {"plans": plans, "directives": [directive], "ledgers": {"motifs": {"the ledger": ["S1", "S3"]}, "key_images": {"S1": plans[0].option_A.shots[0].subject}, "signature_device_counts": {"the participant oner": 2}, "cap_ledger": ledger.status(), "asl_trajectory": [8.0, 6.0, 4.0]}}
        case "P9_2_feasibility":
            required = {"plans": plans, "breakdown_rows": [BreakdownRow(scene_id=p.scene_id, estimated_setups=5) for p in plans], "film_breakdown": FilmBreakdown(budget_tier="low", night_ext_count=4, feasibility_facts=["no more than six night exteriors"]), "budget_tier": "low"}
        case "P9_3_earned_device":
            required = {"plans": plans, "device_permissions": sb.device_permissions, "caps": sb.caps, "caps_used_so_far": ledger.to_dict(), "recent_devices": [{"scene_id": "S1", "device": "bgm elevation"}]}
        case "P9_4_engagement":
            required = {"plans": plans, "scenes": [make_scene("S1"), make_scene("S2", 2), scene], "sequence_plans": [seq_plan], "style_bible": sb, "posture_policy": _policy_dict(sb), "release_target": "both"}
            optional = {"star_cast": [StarCastEntry(actor="a star", character="ANJU", entry_scene_id="S1")]}
        case "P10_review":
            required = {"plan": plan, "scene": scene, "audit_flags": {"continuity": ["S3: eyeline flips across the barrier"], "earned_device": []}, "caps_status": ledger.status()}
        case "P10_pushback":
            required = {"plan": plan, "scene": scene, "override": {"chosen": "custom", "custom_text": "add a drone over the barrier and a second slow-motion", "overrides": ["drone", "slow motion"], "human_note": "I want scale here"}, "style_bible": sb}
        case "P11_judge":
            required = {"plan": plan, "scene": scene, "ideal": {"governing_idea": "Anju's loyalty becomes a physical burden she chooses to carry", "must_feel": scene.must_feel, "pleasure_beat": "the barrier lifting a beat too late"}, "rubric_weights": pol.rubric_weights, "style_bible": sb}
        case _:
            raise KeyError(key)
    spec = TEMPLATES[key]
    assert set(required) == set(spec.required), f"{key}: test variables drifted from the registry's required list"
    assert set(optional) <= set(spec.optional), f"{key}: test optionals not in the registry's optional list"
    variables = dict(required)
    if optionals:
        variables.update(optional)
    return _dump(variables)


def render(key: str, env: jinja2.Environment, *, optionals: bool = True) -> str:
    return registry.render(key, env, **variables_for(key, optionals=optionals))


# ------------------------------------------------------------------ templates exist and render


def test_every_registry_template_file_exists_and_no_orphans():
    for spec in TEMPLATES.values():
        assert (PROMPTS_DIR / spec.file).exists(), spec.file
    assert set(registry.template_files()) == {s.file for s in TEMPLATES.values()}


@pytest.mark.parametrize("key", sorted(TEMPLATES))
def test_template_has_front_matter(key: str):
    first = (PROMPTS_DIR / TEMPLATES[key].file).read_text(encoding="utf-8").splitlines()[0]
    assert first.startswith("{#") and "v2.0" in first and "output:" in first, f"{key}: {first}"


@pytest.mark.parametrize("key", sorted(TEMPLATES))
@pytest.mark.parametrize("optionals", [True, False], ids=["full", "required-only"])
def test_template_renders_with_realistic_variables(real_env, key: str, optionals: bool):
    text = render(key, real_env, optionals=optionals)
    assert len(text) > 200
    assert "{{" not in text and "{%" not in text
    if key == "P10_review":
        assert "JSON only" not in text  # rendered for the human, not a model
    elif key != "P0_showrunner":
        assert "JSON only" in text and "OUTPUT CONTRACT" in text


def test_no_line_ends_with_an_inline_block_tag_that_swallows_its_newline():
    """make_env sets trim_blocks: a line ending in an inline {% endif %} loses its newline and fuses with
    the next line (two bullets become one). Such tags must be written `+%}` so the newline survives."""
    for spec in TEMPLATES.values():
        for i, line in enumerate((PROMPTS_DIR / spec.file).read_text(encoding="utf-8").splitlines(), 1):
            s = line.strip()
            if s.startswith(("{%", "{#")) or not s.endswith("%}"):
                continue
            assert s.endswith("+%}"), f"{spec.file}:{i} ends with an inline block tag — write it '+%}}' so the newline survives"


def test_missing_required_variable_raises(real_env):
    variables = variables_for("P5_lens")
    variables.pop("scene")
    with pytest.raises(KeyError):
        registry.render("P5_lens", real_env, **variables)
    with pytest.raises(jinja2.UndefinedError):  # StrictUndefined, not silent blanks
        real_env.get_template(TEMPLATES["P5_lens"].file).render(**variables)


def test_optional_variables_render_only_when_present(real_env):
    with_hint = render("P4_style_bible", real_env, optionals=True)
    without = render("P4_style_bible", real_env, optionals=False)
    assert "POSTURE HINT" in with_hint and "POSTURE HINT" not in without
    with_header = render("P0_showrunner", real_env, optionals=True)
    without_header = render("P0_showrunner", real_env, optionals=False)
    assert "KAITHA" in with_header and "not yet frozen" in without_header


# ------------------------------------------------------------------ SPEC phrases and contracts


SPEC_PHRASES: list[tuple[str, str]] = [
    ("P0_showrunner", "The human director is sovereign"),
    ("P0_showrunner", "never hardcoded"),
    ("P1_parse", "never transliterate or translate"),
    ("P2a_film", "as a doctor, not a fan"),
    ("P2b_scene", "No shot suggestions here"),
    ("P3_breakdown", "A set-piece without a cost line is not yet a set-piece"),
    ("P4_style_bible", "hedging here poisons every downstream scene"),
    ("P4_style_bible", "posture ≥ 5 requires at least one commercial"),
    ("P5_lens", "never invent quotes"),
    ("P5_lens", "A shot without beat_ref is rejected"),
    ("P5_lens", "Budget ≤ 750 tokens"),
    ("P5s_sequence_lens", "Do NOT propose shots"),
    ("P5s_sequence_lens", "Budget ≤ 450 tokens"),
    ("P6_critique", "no defending, no flattery"),
    ("P6_critique", "Budget ≤ 200 tokens"),
    ("P7_integrator", "never average"),
    ("P7_integrator", "what it ADDS"),
    ("P7_integrator", "never spend a cap silently"),
    ("P7_integrator", "Budget ≤ 1600 tokens"),
    ("P7s_sequence_integrator", "No shots"),
    ("P8_department", "You DERIVE; you do not re-decide"),
    ("P8_department", "must_not always includes the Style Bible refusals"),
    ("P8_department", "Never restate or alter the governing idea or the pleasure beat"),
    ("P8_department", "Budget ≤ 850 tokens"),
    ("P9_1_continuity", "screen direction and 180°"),
    ("P9_2_feasibility", "ranked by dramatic cost"),
    ("P9_3_earned_device", "Devices are not clichés; unearned devices are"),
    ("P9_4_engagement", "Pleasure is engineered"),
    ("P9_4_engagement", "page_eighths / 8"),
    ("P10_pushback", "push back ONCE"),
    ("P11_judge", "never reward a device by pedigree"),
]


@pytest.mark.parametrize("key,phrase", SPEC_PHRASES, ids=[f"{k}:{p[:24]}" for k, p in SPEC_PHRASES])
def test_spec_phrase_present(real_env, key: str, phrase: str):
    assert phrase in " ".join(render(key, real_env).split())  # whitespace-insensitive: templates wrap lines


OUTPUT_MODELS: list[tuple[str, type[BaseModel]]] = [
    ("P1_parse", ParsedScript),
    ("P2a_film", FilmBrief),
    ("P2b_scene", Scene),
    ("P3_breakdown", BreakdownResult),
    ("P4_style_bible", StyleBible),
    ("P5s_sequence_lens", SequenceVision),
    ("P5_lens", SceneVision),
    ("P6_critique", Critique),
    ("P7_integrator", IntegratedScenePlan),
    ("P7s_sequence_integrator", SequencePlan),
    ("P8_department", DepartmentOutput),
    ("P9_1_continuity", ContinuityReport),
    ("P9_2_feasibility", FeasibilityReport),
    ("P9_3_earned_device", EarnedDeviceReport),
    ("P9_4_engagement", EngagementReport),
    ("P10_pushback", Pushback),
    ("P11_judge", JudgeVerdict),
]


@pytest.mark.parametrize("key,model", OUTPUT_MODELS, ids=[k for k, _ in OUTPUT_MODELS])
def test_output_contract_names_every_schema_field(real_env, key: str, model: type[BaseModel]):
    text = render(key, real_env)
    contract = text[text.rindex("OUTPUT CONTRACT") :]
    missing = [f for f in model.model_fields if not re.search(rf"\b{re.escape(f)}\b", contract)]
    assert not missing, f"{key}: contract omits {missing}"
    assert model.__name__ in contract


def test_no_task_template_renders_the_header_inline(real_env):
    """The Film Brief Header is a cached system block; only P0 (the Showrunner's own prompt) may render it."""
    for key, spec in TEMPLATES.items():
        source = (PROMPTS_DIR / spec.file).read_text(encoding="utf-8")
        if key != "P0_showrunner":
            assert "film_brief_header" not in source, key


# ------------------------------------------------------------------ per-template specifics


def test_p5_carries_lens_identity_beats_and_scene_targets(real_env):
    text = render("P5_lens", real_env)
    card = load_lens_card(LENS, with_dp_principles=True)
    scene = _set_piece_scene()
    assert "THE INARRITU LENS" in text and card["conviction"] in text and card["decision_rules"][0]["do"] in text
    assert card["dp_pairing"] in text and card["dp_principles"][0] in text and card["slate_fit"] in text
    for b in scene.beats:
        assert re.search(rf"^- beat {b.n}: ", text, re.M), f"beat {b.n} must start its own line"
    assert scene.must_feel in text and scene.must_remember in text and "thrill / 7" in text
    assert "Posture 5/10 (hybrid)" in text and "max_setups" in text
    assert 'lens = "inarritu"' in text and 'scene_id = "S3"' in text
    assert "energy_target 7" in text  # the sequence-plan entry for S3 is obeyed


def test_p5_flags_a_scene_missing_from_the_sequence_plan(real_env):
    variables = variables_for("P5_lens")
    variables["scene"]["id"] = "S9"
    text = registry.render("P5_lens", real_env, **variables)
    assert "no entry for S9 in sequence plan SEQ1" in text


def test_p5s_has_no_shots_and_serves_the_pleasure_map(real_env):
    text = render("P5s_sequence_lens", real_env)
    assert "shots[" not in text and "SequenceVision" in text and '"set_piece_scene_id": "S3"' in text
    assert "carries the interval block" in text and "cold open" in text


def test_p6_shows_own_and_other_visions_with_one_revision_rule(real_env):
    text = render("P6_critique", real_env)
    assert "YOUR OWN VISION" in text and "THE OTHER VISIONS" in text
    assert "revise ONE element" in text and "may\nnot rewrite it" in text.replace("may not rewrite it", "may\nnot rewrite it")
    for lens in OTHER_LENSES:
        assert f'"lens": "{lens}"' in text


def test_p7_reads_weights_from_posture_and_applies_anti_groupthink(real_env):
    text = render("P7_integrator", real_env)
    pol = policy_for(make_style_bible(5))
    for criterion, weight in pol.rubric_weights.items():
        assert f"- {criterion}: {weight}" in text
    assert "Dramatic Fidelity — posture < 7" in text
    assert "ray_adoor as that lone vision" in text
    assert "the group-reaction frame when the barrier lifts" in text
    assert "consensus devices in this round: slow motion" in text
    assert "\nSTYLE BIBLE REFUSALS:" in text and "\nCAP LEDGER" in text  # inline lists do not fuse with the next line
    assert "Option B" in text and "the_shot_it_cannot_live_without" in text and "conservative_option" in text
    mass = registry.render("P7_integrator", real_env, **{**variables_for("P7_integrator"), "style_bible": make_style_bible(8).model_dump(mode="json")})
    assert "Engagement — posture ≥ 7" in mass


def test_p7s_merges_sequence_visions_into_a_plan(real_env):
    text = render("P7s_sequence_integrator", real_env)
    assert "SequencePlan" in text and "contributions[{element, lens}]" in text and "approved = false" in text
    assert "interval block scene S3" not in text  # the fixture bible sets no interval scene
    assert "interval block scene not set" in text


@pytest.mark.parametrize("dept", list(Department), ids=[d.value for d in Department])
def test_p8_shell_renders_for_every_department(real_env, dept: Department):
    variables = variables_for("P8_department")
    variables["dept"] = dept.value
    variables["dept_brief"] = DEPT_BRIEFS[dept]
    text = registry.render("P8_department", real_env, **variables)
    plan = IntegratedScenePlan.model_validate(variables["plan"])
    assert f"You are the {dept.value.upper()} HEAD" in text and DEPT_BRIEFS[dept] in text
    assert plan.governing_idea in text and plan.pleasure_beat in text and plan.directors_note in text
    stance = {
        Department.COLOUR: plan.department_handoff.colour_stance,
        Department.MUSIC: plan.department_handoff.music_stance,
        Department.SOUND: plan.department_handoff.sound_stance,
        Department.DESIGN: plan.department_handoff.design_stance,
        Department.PERFORMANCE: plan.department_handoff.performance_stance,
    }.get(dept)
    if stance:
        assert f"your stance: {stance}" in text
    assert "cap ledger status" in text and '"elevation_cues": "1 of 3"' in text
    assert "\n- refusals (must_not[]" in text and "\n- energy check:" in text
    for refusal in make_style_bible(5).refusals:
        assert refusal in text
    assert 'under\n"directive"' in text or 'under "directive"' in text.replace("\n", " ")


def test_p9_4_renders_the_posture_policy_not_a_constant(real_env):
    hybrid = render("P9_4_engagement", real_env)
    assert "~10 screen minutes" in hybrid and "must_remember per act: ≥ 1" in hybrid
    assert "theatrical ≤ 8.0 · ott ≤ 8.0" in hybrid and "the Bible wins" in hybrid  # the Bible's first_hook_minute overrides the preset
    assert "\n- first hook by minute:" in hybrid and "\n- must_remember per act" in hybrid
    assert "STAR CAST (their entries must be designed" in hybrid
    variables = variables_for("P9_4_engagement")
    sb2 = make_style_bible(2)
    variables["style_bible"] = sb2.model_dump(mode="json")
    variables["posture_policy"] = _policy_dict(sb2)
    arthouse = registry.render("P9_4_engagement", real_env, **variables)
    assert "not audited at this posture" in arthouse and "POSTURE 2/10 (arthouse)" in arthouse


def test_p10_review_is_the_one_screen_in_pitch_voice(real_env):
    text = render("P10_review", real_env)
    plan = _plan()
    for heading in ("**Must-feel:**", "**Governing idea:**", "**Pleasure beat:**", "## Option A", "## Option B", "## The shot it cannot live without", "## Department stances", "## Audit flags", "## Cap ledger", "## HUMAN_QUESTIONS"):
        assert heading in text, heading
    for stance in ("Colour", "Music", "Sound", "Design", "Performance"):
        assert f"- **{stance}:**" in text
    assert "S3: eyeline flips across the barrier" in text and "elevation_cues: 1 of 3" in text
    assert plan.human_questions[0].question in text and "Decide: **A** | **B** | **custom**" in text
    assert "## Option A — recommended\n1. **Governing idea:**" in text and "## Option B\n1. **Governing idea:**" in text
    assert "\n**Energy:**" in text and "\n  - _" in text  # the human question's rationale sits on its own line


def test_p10_pushback_is_warranted_only_for_bible_turn_or_cap(real_env):
    text = render("P10_pushback", real_env)
    assert "Style Bible" in text and "TURN" in text and "cap" in text and "Taste disagreement is NOT a warrant" in text
    assert "Pushback" in text and "proposed_amendment" in text and "Never re-run silently" in text


def test_p11_judges_against_the_human_ideal_at_posture(real_env):
    text = render("P11_judge", real_env)
    assert "Anju's loyalty becomes a physical burden" in text and "governing_idea_match" in text and "cap_discipline" in text
    assert "POSTURE 5/10 (hybrid)" in text and "quote the plan's fields, never a filmmaker" in text


def test_p4_lists_the_full_directing_roster_and_the_panel_mix_rule(real_env):
    text = render("P4_style_bible", real_env)
    for name in ALL_DIRECTING_LENSES:
        assert re.search(rf"\b{name}\b", text), name
    for name in DP_LENSES + CRAFT_LENSES:
        assert not re.search(rf"\b{name}\b", text.split("LENS ROSTER")[1].split("RULE:")[0]), f"{name} is not a panel lens"
    assert "digest (≤ 600 tokens" in text and "manifesto" in text and "pleasure map" in text


def test_p2b_renders_dict_neighbour_summaries_as_json(real_env):
    text = render("P2b_scene", real_env)
    assert '"must_feel": "the floor has gone from under Anju"' in text
    assert "NEXT SCENE: none — this is the last scene" in text


class _RealTemplateLens(BaseAgent[SceneVision]):
    stage = "lens"
    name = "lens_real_template"
    template = "P5_lens"
    output_model = SceneVision


async def test_real_p5_template_runs_through_base_agent_offline(offline_ctx_real_templates: AgentContext):
    """The shipped template, the loader's card and BaseAgent.prepare agree on variable shapes."""
    sb = make_style_bible(5)
    res = await _RealTemplateLens(offline_ctx_real_templates).run(
        key=f"{SCENE_ID}/{LENS}",
        lens_card=load_lens_card(LENS, with_dp_principles=True),
        sequence_plan=make_sequence_plan(),
        scene=_set_piece_scene(),
        scene_constraints=SceneConstraints(scene_id=SCENE_ID),
        style_bible=sb,
    )
    prompt = offline_ctx_real_templates.client.last.prompt
    assert res.parsed.lens == LENS and res.parsed.scene_id == SCENE_ID
    assert "THE INARRITU LENS" in prompt and "never invent quotes" in prompt


# ------------------------------------------------------------------ lens cards


ROSTER = AUTEUR_LENSES + AUTEUR_EXTENSION_LENSES + COMMERCIAL_LENSES + COMMERCIAL_EXTENSION_LENSES + DP_LENSES + CRAFT_LENSES


def test_roster_sizes_match_the_spec():
    assert len(AUTEUR_LENSES) == 7 and len(AUTEUR_EXTENSION_LENSES) == 5
    assert len(COMMERCIAL_LENSES) == 7 and len(COMMERCIAL_EXTENSION_LENSES) == 6
    assert len(DP_LENSES) == 13 and len(CRAFT_LENSES) == 9
    assert len(set(ROSTER)) == len(ROSTER) == 47


@pytest.mark.parametrize("name", ROSTER)
def test_every_roster_name_has_a_valid_card(name: str):
    assert (LENSES_DIR / f"{name}.yaml").exists()
    card = LensCard.model_validate(load_lens_card(name))
    assert card.name == name and card.bloc == ROSTER_BLOC[name]
    assert card.filmmaker_basis.lower().startswith("craft principles associated with")
    assert len(card.decision_rules) >= 3 and all(r.when and r.do for r in card.decision_rules)
    assert card.signature_devices and card.refusals and card.blind_spots and card.best_for


def test_validate_all_cards_and_no_orphan_cards():
    cards = validate_all_cards()
    assert set(cards) == set(ROSTER)
    assert set(load_all_lens_cards()) == set(ROSTER), "every card on disk must be a roster lens"


@pytest.mark.parametrize("name", AUTEUR_LENSES + AUTEUR_EXTENSION_LENSES + COMMERCIAL_LENSES + COMMERCIAL_EXTENSION_LENSES)
def test_directing_cards_pair_with_a_dp_and_fit_their_bloc(name: str):
    card = LensCard.model_validate(load_lens_card(name))
    assert card.is_directing and card.dp_pairing in DP_LENSES
    lo, hi = card.posture_range
    if card.bloc == "commercial":
        assert hi >= 7, f"{name}: a commercial lens must reach the mass band"
    else:
        assert lo <= 3, f"{name}: an auteur lens must reach the arthouse band"


@pytest.mark.parametrize("name", DP_LENSES + CRAFT_LENSES)
def test_dp_and_craft_cards_carry_principles_and_serve_every_posture(name: str):
    card = LensCard.model_validate(load_lens_card(name))
    assert not card.is_directing and card.dp_pairing is None
    assert card.principles and card.posture_range == [0, 10]


QUOTE_ATTRIBUTION = re.compile(r"\"[^\"\n]*\"\s*[—–-]{1,2}\s*[A-Z][a-z]+")
ANECDOTE = re.compile(r"\bonce said\b|\bas (?:he|she|they) (?:put it|would say|said)\b|\bI remember\b|\bwould say\b", re.IGNORECASE)


@pytest.mark.parametrize("name", ROSTER)
def test_card_text_is_a_prior_not_a_costume(name: str):
    raw = (LENSES_DIR / f"{name}.yaml").read_text(encoding="utf-8")
    assert not QUOTE_ATTRIBUTION.search(raw), f"{name}: attributed quote"
    assert not ANECDOTE.search(raw), f"{name}: anecdote or first-person filmmaker voice"


def test_lens_card_validator_rejects_bad_cards():
    good = load_lens_card("rajamouli")
    with pytest.raises(ValidationError):
        LensCard.model_validate({**good, "posture_range": [4, 11]})
    with pytest.raises(ValidationError):
        LensCard.model_validate({**good, "posture_range": [8, 4]})
    with pytest.raises(ValidationError):
        LensCard.model_validate({**good, "bloc": "editor"})
    with pytest.raises(ValidationError):
        LensCard.model_validate({**good, "decision_rules": [{"when": "elevation"}]})
    with pytest.raises(ValidationError):
        LensCard.model_validate({**good, "dp_pairing": "murch"})
    with pytest.raises(ValidationError):
        LensCard.model_validate({**good, "filmmaker_basis": "the life and times of S.S. Rajamouli"})
    with pytest.raises(ValidationError):
        LensCard.model_validate({**good, "conviction": "as he once said, spectacle is emotion"})
    with pytest.raises(ValidationError):
        LensCard.model_validate({**good, "unknown_field": 1})
    craft = load_lens_card("murch")
    with pytest.raises(ValidationError):
        LensCard.model_validate({**craft, "principles": []})


def test_load_lens_card_attaches_dp_principles_and_posture_gate():
    card = load_lens_card("kubrick", with_dp_principles=True)
    assert card["dp_pairing"] == "deakins" and "one motivated source" in card["dp_principles"]
    assert "dp_principles" not in load_lens_card("kubrick")
    assert "dp_principles" not in load_lens_card("murch", with_dp_principles=True)
    mass, arthouse = directing_cards_for_posture(9), directing_cards_for_posture(1)
    assert "rajamouli" in mass and "tarkovsky" not in mass
    assert "kubrick" in arthouse and "rajamouli" not in arthouse and "ray_adoor" in arthouse
    with pytest.raises(FileNotFoundError):
        load_lens_card("nobody")
