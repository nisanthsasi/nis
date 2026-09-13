"""The template registry: every prompt the pipeline renders, by name, with the variables it needs.

Templates live in ``the_panel/prompts/*.md.j2``. Agents render by registry key, never by
literal path, so a missing template or a missing variable fails loudly at render time.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import jinja2

PROMPTS_DIR = Path(__file__).resolve().parent
LENSES_DIR = PROMPTS_DIR / "lenses"


@dataclass(frozen=True)
class TemplateSpec:
    key: str
    file: str
    required: tuple[str, ...]
    optional: tuple[str, ...] = ()
    description: str = ""


TEMPLATES: dict[str, TemplateSpec] = {
    "P0_showrunner": TemplateSpec("P0_showrunner", "P0_showrunner.md.j2", (), ("film_brief_header",), "orchestrator system prompt"),
    "P1_parse": TemplateSpec("P1_parse", "P1_parse.md.j2", ("raw_text",), ("format_hint", "location_aliases"), "L0/L1 parser (model-assisted pass)"),
    "P2a_film": TemplateSpec("P2a_film", "P2a_film.md.j2", ("scenes", "release_target"), ("mechanism_notes", "cast_notes", "budget_tier"), "film-level dramaturgy"),
    "P2b_scene": TemplateSpec("P2b_scene", "P2b_scene.md.j2", ("scene", "prev_scene_summary", "next_scene_summary"), (), "scene report card"),
    "P3_breakdown": TemplateSpec("P3_breakdown", "P3_breakdown.md.j2", ("scenes", "budget_tier", "release_target"), ("budget_inr",), "production breakdown"),
    "P4_style_bible": TemplateSpec("P4_style_bible", "P4_style_bible.md.j2", ("film_brief", "feasibility_facts", "release_target"), ("director_intent", "references", "posture_hint"), "the constitution"),
    "P5s_sequence_lens": TemplateSpec("P5s_sequence_lens", "P5s_sequence_lens.md.j2", ("lens_card", "sequence", "pleasure_map_entry", "style_bible", "release_target"), (), "sequence-level lens"),
    "P5_lens": TemplateSpec("P5_lens", "P5_lens.md.j2", ("lens_card", "sequence_plan", "scene", "scene_constraints", "style_bible"), (), "scene-level lens"),
    "P6_critique": TemplateSpec("P6_critique", "P6_critique.md.j2", ("lens_card", "own_vision", "other_visions", "scene", "style_bible"), (), "round-2 cross-critique"),
    "P7_integrator": TemplateSpec("P7_integrator", "P7_integrator.md.j2", ("visions", "critiques", "scene", "sequence_plan", "style_bible", "scene_constraints", "caps_used_so_far", "rubric_weights"), ("consensus_devices", "lone_high_fidelity_lens", "lone_high_engagement"), "the single directing mind"),
    "P7s_sequence_integrator": TemplateSpec("P7s_sequence_integrator", "P7s_sequence_integrator.md.j2", ("sequence_visions", "sequence", "style_bible", "pleasure_map_entry"), (), "merge SequenceVisions into a SequencePlan"),
    "P8_department": TemplateSpec("P8_department", "P8_department.md.j2", ("dept", "dept_brief", "plan", "scene", "style_bible", "breakdown_row"), ("caps_status",), "shared department shell + per-dept brief"),
    "P9_1_continuity": TemplateSpec("P9_1_continuity", "P9_1_continuity.md.j2", ("plans", "directives", "ledgers"), (), "continuity/coherence"),
    "P9_2_feasibility": TemplateSpec("P9_2_feasibility", "P9_2_feasibility.md.j2", ("plans", "breakdown_rows", "film_breakdown", "budget_tier"), (), "feasibility/compliance"),
    "P9_3_earned_device": TemplateSpec("P9_3_earned_device", "P9_3_earned_device.md.j2", ("plans", "device_permissions", "caps", "caps_used_so_far", "recent_devices"), (), "earned-device audit"),
    "P9_4_engagement": TemplateSpec("P9_4_engagement", "P9_4_engagement.md.j2", ("plans", "scenes", "sequence_plans", "style_bible", "posture_policy", "release_target"), ("star_cast",), "engagement audit"),
    "P10_review": TemplateSpec("P10_review", "P10_review.md.j2", ("plan", "scene", "audit_flags", "caps_status"), (), "human review screen (digest voice)"),
    "P10_pushback": TemplateSpec("P10_pushback", "P10_pushback.md.j2", ("plan", "scene", "override", "style_bible"), (), "the one push-back on an override"),
    "P11_judge": TemplateSpec("P11_judge", "P11_judge.md.j2", ("plan", "scene", "ideal", "rubric_weights", "style_bible"), (), "CP-8 judge-model grading"),
}

# Lens roster (file stems under prompts/lenses/). bloc + posture_range live in the cards.
AUTEUR_LENSES: tuple[str, ...] = ("kubrick", "kurosawa", "bergman", "wong_kar_wai", "inarritu", "spielberg", "ray_adoor")
AUTEUR_EXTENSION_LENSES: tuple[str, ...] = ("padmarajan_bharathan", "lijo_jose_pellissery", "tarkovsky", "haneke", "ozu")
COMMERCIAL_LENSES: tuple[str, ...] = ("rajamouli", "mani_ratnam", "edgar_wright", "scorsese", "bong_joon_ho", "boyle", "malayalam_new_wave")
COMMERCIAL_EXTENSION_LENSES: tuple[str, ...] = ("cameron", "nolan", "villeneuve", "lokesh_kanagaraj", "tarantino", "luhrmann")
DP_LENSES: tuple[str, ...] = ("deakins", "lubezki", "nykvist", "doyle", "miyagawa", "kaminski", "sivan_mohanan_mitra", "kk_senthil_kumar", "pc_sreeram", "bill_pope", "hong_kyung_pyo", "dod_mantle", "shyju_khalid_anend_sameer")
CRAFT_LENSES: tuple[str, ...] = ("murch", "schoonmaker", "comedy_energy_edit", "sound", "music", "bgm_song", "design", "performance", "star_ensemble")
ALL_DIRECTING_LENSES: tuple[str, ...] = AUTEUR_LENSES + AUTEUR_EXTENSION_LENSES + COMMERCIAL_LENSES + COMMERCIAL_EXTENSION_LENSES


class StrictUndefined(jinja2.StrictUndefined):
    pass


def make_env(prompts_dir: Path | None = None) -> jinja2.Environment:
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(prompts_dir or PROMPTS_DIR)),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
        autoescape=False,
    )
    env.filters["tojson_pretty"] = lambda v: __import__("json").dumps(v, ensure_ascii=False, indent=2, default=str)
    return env


def render(key: str, env: jinja2.Environment | None = None, **variables) -> str:
    spec = TEMPLATES[key]
    missing = [v for v in spec.required if v not in variables]
    if missing:
        raise KeyError(f"template '{key}' missing required variables: {missing}")
    env = env or make_env()
    tpl = env.get_template(spec.file)
    return tpl.render(**variables)


def template_files() -> list[str]:
    return sorted(p.name for p in PROMPTS_DIR.glob("*.md.j2"))


def lens_card_files() -> list[str]:
    return sorted(p.stem for p in LENSES_DIR.glob("*.yaml"))
