"""Obsidian vault export: one note per scene with frontmatter, one per sequence, the Film Brief,
the Style Bible, and an index — so the second brain and the directing brain share one graph.

Frontmatter carries the review-screen facts (must_feel, pleasure_type, set_piece,
option_chosen, …) so Dataview/graph queries can ask "which set-pieces still have no
decision?" without opening a note. Wikilinks (``[[S2]]``, ``[[SEQ1]]``) resolve by filename,
so scene notes are named exactly by scene id and sequence notes by sequence id.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from ..schemas.decisions import DecisionLogEntry
from ..schemas.directive import DepartmentDirective
from ..schemas.film_brief import FilmBrief
from ..schemas.plan import IntegratedScenePlan, PlanOption
from ..schemas.scene import Scene
from ..schemas.style_bible import StyleBible
from ..schemas.vision import Shot

FILM_BRIEF_NOTE = "00-Film-Brief.md"
STYLE_BIBLE_NOTE = "01-Style-Bible.md"
INDEX_NOTE = "02-Index.md"
SCENES_DIR = "scenes"
SEQUENCES_DIR = "sequences"
UNSEQUENCED = "UNSEQUENCED"

_UNSAFE = re.compile(r'[\\/:*?"<>|#^\[\]]+')


def safe_filename(name: str) -> str:
    """Strip the characters Obsidian (and Windows) refuse in note names; never empty."""
    cleaned = _UNSAFE.sub("-", name).strip(" .-")
    return cleaned or "note"


def frontmatter(data: dict[str, Any]) -> str:
    body = yaml.safe_dump(data, sort_keys=False, allow_unicode=True, default_flow_style=False).rstrip("\n")
    return f"---\n{body}\n---\n"


def wikilink(target: str, label: str | None = None) -> str:
    return f"[[{target}|{label}]]" if label else f"[[{target}]]"


def _cell(v: Any) -> str:
    s = "" if v is None else str(getattr(v, "value", v))
    return s.replace("|", "\\|").replace("\n", " ")


def shot_table(shots: list[Shot]) -> str:
    head = "| # | Size | Angle | Height | Lens | Move | Dur (s) | Subject | Action | Beat | Light |\n|---|---|---|---|---|---|---|---|---|---|---|"
    rows = [f"| {s.no} | {_cell(s.size)} | {_cell(s.angle)} | {_cell(s.height)} | {s.lens_mm}mm | {_cell(s.movement)} | {s.duration_est_s:g} | {_cell(s.subject)} | {_cell(s.action)} | {s.beat_ref} | {_cell(s.light_note)} |" for s in shots]
    return "\n".join([head, *rows])


def _is_scalar(v: Any) -> bool:
    return not isinstance(v, (dict, list))


def _empty(v: Any) -> bool:
    return v is None or v == "" or v == [] or v == {}


def bullets(value: Any, indent: int = 0) -> list[str]:
    """Render a dumped directive body as nested bullet lists (empty values dropped, False/0 kept)."""
    pad = "  " * indent
    out: list[str] = []
    if isinstance(value, dict):
        for k, v in value.items():
            if _empty(v):
                continue
            if _is_scalar(v):
                out.append(f"{pad}- **{k}:** {_cell(v)}")
            else:
                out.append(f"{pad}- **{k}:**")
                out.extend(bullets(v, indent + 1))
    elif isinstance(value, list):
        for i, item in enumerate(value, 1):
            if _is_scalar(item):
                out.append(f"{pad}- {_cell(item)}")
            else:
                label = item.get("no", item.get("cue_id", item.get("beat", i))) if isinstance(item, dict) else i
                out.append(f"{pad}- **{label}.**")
                out.extend(bullets(item, indent + 1))
    else:
        out.append(f"{pad}- {_cell(value)}")
    return out


def _option_section(label: str, opt: PlanOption, score_line: str) -> list[str]:
    lines = [f"## Option {label}"]
    if opt.governing_idea:
        lines.append(f"_{opt.governing_idea}_")
    lines.append(f"**Rationale:** {opt.rationale}")
    lines.append(f"**Blocking:** {opt.blocking}")
    if opt.source_lenses:
        lines.append(f"**From lenses:** {', '.join(opt.source_lenses)}")
    lines.append(score_line)
    lines.append("")
    lines.append(shot_table(opt.shots))
    if opt.devices_used:
        lines.append("")
        lines.append("**Devices:** " + "; ".join(f"{d.device} (set up by {d.setup_ref})" for d in opt.devices_used))
    if opt.reduced_coverage_variant:
        lines.append(f"**Reduced-coverage variant:** {opt.reduced_coverage_variant}")
    lines.append("")
    return lines


def _score_line(plan: IntegratedScenePlan, label: str) -> str:
    s = plan.resonance_scores[label]
    parts = [f"{k.replace('_', ' ')} {v:g}" for k, v in s.as_dict().items()]
    total = f" · **weighted {s.weighted_total:g}**" if s.weighted_total is not None else ""
    return "**Resonance:** " + ", ".join(parts) + total


def scene_markdown(
    scene: Scene,
    plan: IntegratedScenePlan | None,
    directives: list[DepartmentDirective],
    audit_flags: list[str],
    decision: DecisionLogEntry | None,
    *,
    prev_id: str | None = None,
    next_id: str | None = None,
    sequence_id: str | None = None,
) -> str:
    """The scene note: frontmatter + the Gate-3 review screen in Obsidian markdown."""
    seq = sequence_id or scene.sequence_id or UNSEQUENCED
    option_chosen = decision.chosen if decision else (plan.chosen if plan else None)
    fm = {
        "scene_id": scene.id,
        "number": scene.number,
        "sequence": seq,
        "slug": scene.slug,
        "rasa_primary": scene.rasa.primary.value,
        "rasa_secondary": scene.rasa.secondary.value if scene.rasa.secondary else None,
        "must_feel": scene.must_feel,
        "pleasure_type": scene.pleasure_type.value,
        "set_piece": scene.set_piece,
        "must_remember": scene.must_remember,
        "energy_target": scene.energy_target,
        "load_bearing": scene.load_bearing,
        "option_chosen": option_chosen,
        "cost_flag": scene.cost_flag.value,
        "tags": ["panel", f"seq/{seq}"],
    }
    L: list[str] = [frontmatter(fm), f"# {scene.id} · {scene.slug}", ""]
    if scene.synopsis:
        L += [f"_{scene.synopsis}_", ""]
    L += ["## Must-feel", scene.must_feel or "_not analysed_", ""]
    if plan is None:
        L += ["## Governing idea", "_not yet integrated_", "", "## Pleasure beat", f"_planned pleasure: {scene.pleasure_type.value}_", "", "## Director's note", "_not yet integrated_", ""]
    else:
        L += ["## Governing idea", plan.governing_idea, ""]
        pb = [plan.pleasure_beat]
        if plan.pleasure_none_reason:
            pb.append(f"_none because: {plan.pleasure_none_reason}_")
        if plan.trailer_shot:
            pb.append(f"**Trailer shot:** {plan.trailer_shot}")
        if plan.must_remember_delivery:
            pb.append(f"**Must-remember delivery:** {plan.must_remember_delivery}")
        ec = plan.energy_check
        pb.append(f"**Energy:** plan {ec.plan_energy} vs sequence target {ec.sequence_energy_target} ({'matches' if ec.matches else 'MISMATCH'}); ASL {ec.asl_target_s:g}s, {ec.camera_velocity}, {ec.cut_rate}")
        L += ["## Pleasure beat", *pb, ""]
        L += ["## Director's note", plan.directors_note, ""]
        L += _option_section("A", plan.option_A, _score_line(plan, "A"))
        L += _option_section("B", plan.option_B, _score_line(plan, "B"))
        k = plan.the_shot_it_cannot_live_without
        L += ["## The shot it cannot live without", f"**Shot {k.shot_no}** — {k.why}", ""]
        h = plan.department_handoff
        L += ["## Department stances"]
        L += [f"- **Colour:** {h.colour_stance}", f"- **Music:** {h.music_stance}", f"- **Sound:** {h.sound_stance}", f"- **Design:** {h.design_stance}", f"- **Performance:** {h.performance_stance}", ""]
        if plan.unresolved_tensions:
            L += ["**Unresolved tensions:**", *[f"- {t}" for t in plan.unresolved_tensions], ""]
        if plan.human_questions:
            L += ["**Human questions:**", *[f"- {q.id}: {q.question} — (a) {q.options[0]} (b) {q.options[1]}" for q in plan.human_questions], ""]
    L += ["## Directives"]
    if not directives:
        L.append("_no department directives yet_")
    for d in sorted(directives, key=lambda d: d.dept.value):
        L.append(f"<details><summary><b>{d.dept.value}</b> — {d.digest or 'no digest'}</summary>")
        L.append("")
        L.extend(bullets(d.directive))
        if d.deliverables:
            L.append("- **deliverables:**")
            L.extend(bullets(d.deliverables, 1))
        if d.must_not:
            L.append("- **must_not:**")
            L.extend(bullets(d.must_not, 1))
        if d.dept_flags:
            L.append("- **DEPT_FLAG:**")
            L.extend(f"  - {f.issue} → cheapest fix: {f.cheapest_fix}" for f in d.dept_flags)
        L.append("")
        L.append("</details>")
    L.append("")
    L += ["## Audit flags", *([f"- {f}" for f in audit_flags] or ["_none_"]), ""]
    L += ["## Decision"]
    if decision is None:
        L.append("_pending human review_")
    else:
        L.append(f"**Chosen:** {decision.chosen}" + (f" — {decision.custom_text}" if decision.custom_text else ""))
        if decision.human_note:
            L.append(f"**Note:** {decision.human_note}")
        if decision.overrides:
            L.append("**Overrides:** " + "; ".join(decision.overrides))
        if decision.pushback_given:
            L.append(f"**Push-back given:** {decision.pushback_reason or ''}")
        if decision.style_bible_amendment:
            a = decision.style_bible_amendment
            L.append(f"**Style Bible amendment ({'approved' if a.approved else 'pending'}):** {a.change} — {a.reason}")
        if decision.rerun_scene_ids:
            L.append("**Re-run:** " + ", ".join(wikilink(s) for s in decision.rerun_scene_ids))
        L.append(f"_{decision.timestamp.isoformat()}_")
    L.append("")
    nav = []
    if prev_id:
        nav.append(f"← {wikilink(prev_id)}")
    nav.append(f"sequence {wikilink(seq)}")
    if next_id:
        nav.append(f"{wikilink(next_id)} →")
    L += ["## Links", " · ".join(nav), ""]
    return "\n".join(L)


# ------------------------------------------------------------------ film-level notes


def film_brief_markdown(brief: FilmBrief) -> str:
    fm = {"title": brief.title, "structure_model": brief.structure_model.value, "release_target": brief.release_target.value, "budget_tier": brief.budget_tier.value, "tags": ["panel", "film-brief"]}
    L = [frontmatter(fm), f"# {brief.title} — Film Brief", ""]
    L += [f"**Logline:** {brief.logline}", f"**Dramatic question:** {brief.dramatic_question}", f"**Controlling idea:** {brief.controlling_idea}", ""]
    L += [f"**Release target:** {brief.release_target.value} · **Budget tier:** {brief.budget_tier.value}" + (f" · **CBFC posture:** {brief.cbfc_posture}" if brief.cbfc_posture else "") + (f" · **Language:** {brief.language_mix}" if brief.language_mix else ""), ""]
    if brief.mechanism:
        m = brief.mechanism
        L += ["## Mechanism (NFE)", f"**Family:** {m.family}", f"**Premise:** {m.transposition_premise}", m.one_sentence, "**Executes in:** " + ", ".join(wikilink(s) for s in m.execution_scene_ids), ""]
    L += ["## Structure", f"**Model:** {brief.structure_model.value}"]
    L += [f"- **{b.name}** → {wikilink(b.scene_id)}{'' if b.turns_central_value else ' (does not turn the central value)'}{' — ' + b.note if b.note else ''}" for b in brief.load_bearing_beats]
    if brief.value_arc:
        L.append("**Value arc:** " + " · ".join(f"{v.act}:{v.value}" for v in brief.value_arc))
    L.append("")
    if brief.sequences:
        L += ["## Sequences", *[f"- {wikilink(s.sequence_id)} — {s.function} ({s.rhythm}) · " + ", ".join(wikilink(x) for x in s.scene_ids) for s in brief.sequences], ""]
    if brief.characters:
        L += ["## Characters", "| Name | Want | Need | Wound | Lie | Thematic answer | Register |", "|---|---|---|---|---|---|---|"]
        L += [f"| {_cell(c.name)}{' (antagonist)' if c.is_antagonist else ''} | {_cell(c.want)} | {_cell(c.need)} | {_cell(c.wound)} | {_cell(c.lie)} | {_cell(c.thematic_answer)} | {c.dialogue_register.value} |" for c in brief.characters]
        L.append("")
    if brief.star_cast:
        L += ["## Star cast", *[f"- **{s.actor}** as {s.character}" + (f" — entry {wikilink(s.entry_scene_id)}" if s.entry_scene_id else "") + (f": {s.entry_note}" if s.entry_note else "") for s in brief.star_cast], ""]
    if brief.set_piece_candidates:
        L += ["## Set-piece candidates", *[f"- {wikilink(c.scene_id)} — {c.kind.value} ({c.pleasure_type.value}){' · INTERVAL' if c.interval_candidate else ''}{' — earned by ' + c.earning_beat if c.earning_beat else ''}" for c in brief.set_piece_candidates], ""]
    if brief.image_systems or brief.motifs:
        L += ["## Image systems & motifs", *[f"- image system: {x}" for x in brief.image_systems], *[f"- motif: {x}" for x in brief.motifs], ""]
    if brief.plants_payoffs:
        L += ["## Plants → payoffs", *[f"- {p.item}: {wikilink(p.plant_scene_id)} → {wikilink(p.payoff_scene_id) if p.payoff_scene_id else '_unpaid_'}" for p in brief.plants_payoffs], ""]
    ta = brief.theme_audit
    if ta.dramatised or ta.silent or ta.preaches:
        L += ["## Theme audit", *[f"- dramatised: {x}" for x in ta.dramatised], *[f"- silent: {x}" for x in ta.silent], *[f"- preaches: {x}" for x in ta.preaches], ""]
    if brief.human_digest:
        L += ["## Digest", brief.human_digest, ""]
    return "\n".join(L)


def _cap(v: int | None) -> str:
    return "unlimited (each earned)" if v is None else str(v)


def style_bible_markdown(bible: StyleBible) -> str:
    fm = {"version": bible.version, "approved_by": bible.approved_by, "commercial_posture": bible.commercial_posture, "band": bible.band, "tags": ["panel", "style-bible"]}
    L = [frontmatter(fm), f"# Style Bible v{bible.version} — {bible.approved_by}", ""]
    if bible.manifesto:
        L += ["## How we shoot this film", bible.manifesto, ""]
    L += ["## Commercial posture", f"**{bible.commercial_posture}/10 ({bible.band})** — {bible.posture_defence or 'no defence recorded'}", "**Audience promise:** " + ", ".join(p.value for p in bible.audience_promise), ""]
    L += ["## Caps", f"- elevation cues: {_cap(bible.caps.elevation_cues)}", f"- slow motion: {_cap(bible.caps.slow_motion)}", f"- needle drops: {_cap(bible.caps.needle_drops)}", ""]
    L += ["## Device permissions", *([f"- **{d.device}** must pay off: {d.must_pay_off}" for d in bible.device_permissions] or ["_none_"]), ""]
    if bible.signature_devices:
        L += ["## Signature devices", *[f"- {d}" for d in bible.signature_devices], ""]
    L += ["## Pleasure map", *([f"- {wikilink(e.sequence_id)} → {e.pleasure_type.value}" + (f" @ {wikilink(e.set_piece_scene_id)}" if e.set_piece_scene_id else "") + (f" — none because: {e.reason_if_none}" if e.reason_if_none else "") for e in bible.pleasure_map] or ["_none_"]), ""]
    L += ["## Refusals", *([f"- {r}" for r in bible.refusals] or ["_none_"]), ""]
    la = bible.lens_affinity
    L += ["## Lens affinity", f"- primary: {', '.join(la.primary) or '—'}", f"- secondary: {', '.join(la.secondary) or '—'}", *[f"- excluded: {x.lens} — {x.reason}" for x in la.excluded], ""]
    f = bible.form
    L += ["## Form", f"- genre contract: {f.genre_contract}", f"- tone: {f.tone}", f"- narrative stance: {f.narrative_stance}", f"- POV: {f.pov_strategy}", f"- audience relationship: {f.audience_relationship}", ""]
    s = bible.structure
    L += ["## Structure", f"- time: {s.time_organisation}", f"- architecture: {s.sequence_architecture}", *[f"- act {r.act}: {r.rhythm}" + (f" (ASL {r.asl_target_s:g}s)" if r.asl_target_s else "") for r in s.rhythm_plan_by_act]]
    if s.ellipsis_policy:
        L.append(f"- ellipsis: {s.ellipsis_policy}")
    if s.where_it_breathes:
        L.append(f"- breathes: {s.where_it_breathes}")
    h = bible.structural_hooks
    L += [f"- first hook by minute {h.first_hook_minute:g}" + (f"; cold open: {h.cold_open}" if h.cold_open else "") + (f"; interval block {wikilink(h.interval_block_scene)} detonates {h.interval_detonates}" if h.interval_block_scene else "") + (f"; finale promise: {h.finale_promise}" if h.finale_promise else ""), ""]
    st = bible.style
    L += ["## Style"]
    for label, val in (("camera grammar", st.camera_grammar), ("lens policy", st.lens_policy), ("movement", st.movement_policy), ("light", st.light_policy), ("colour energy", st.colour_energy), ("editing", st.editing_grammar), ("sound", st.sound_philosophy), ("music", st.music_philosophy), ("BGM policy", st.bgm_policy), ("mise-en-scène", st.mise_en_scene_rules), ("performance", st.performance_style)):
        if val:
            L.append(f"- **{label}:** {val}")
    L += [f"- **colour arc:** {p.act} → {p.palette}" for p in st.color_arc]
    L += [f"- **motif colour:** {m.motif} = {m.colour}" + (f" ({m.carriers})" if m.carriers else "") for m in st.motif_colours]
    if st.colour_set_pieces:
        L.append("- **colour set-pieces:** " + ", ".join(st.colour_set_pieces))
    if st.song_plan:
        L += [f"- **song slot {x.slot}:** {x.type} — {x.narrative_job}" + (f" @ {wikilink(x.scene_id)}" if x.scene_id else "") for x in st.song_plan]
    elif st.song_plan_reason_if_none:
        L.append(f"- **no songs:** {st.song_plan_reason_if_none}")
    L.append("")
    if bible.governing_references:
        L += ["## Governing references", *[f"- **{g.film}** — borrowed: {g.borrowed}; refused: {g.refused}" for g in bible.governing_references], ""]
    if bible.malayalam_grounding:
        L += ["## Malayalam grounding", bible.malayalam_grounding, ""]
    L += ["## Amendments", *([f"- [{'x' if a.approved else ' '}] {wikilink(a.scene_id) + ': ' if a.scene_id else ''}{a.change} — {a.reason}" + (" · re-run " + ", ".join(wikilink(x) for x in a.affected_scene_ids) if a.affected_scene_ids else "") for a in bible.amendments] or ["_none_"]), ""]
    if bible.human_questions:
        L += ["## Human questions", *[f"- {q}" for q in bible.human_questions], ""]
    return "\n".join(L)


def sequence_markdown(sequence_id: str, function: str, scenes: list[Scene], plans: dict[str, IntegratedScenePlan], decisions: dict[str, DecisionLogEntry], bible: StyleBible | None) -> str:
    entry = next((e for e in (bible.pleasure_map if bible else []) if e.sequence_id == sequence_id), None)
    fm = {
        "sequence_id": sequence_id,
        "function": function,
        "scene_ids": [s.id for s in scenes],
        "pleasure_type": entry.pleasure_type.value if entry else None,
        "set_piece_scene_id": entry.set_piece_scene_id if entry else None,
        "tags": ["panel", "sequence"],
    }
    L = [frontmatter(fm), f"# {sequence_id}", ""]
    if function:
        L += [f"**Function:** {function}", ""]
    if entry:
        L += [f"**Pleasure:** {entry.pleasure_type.value}" + (f" — set-piece {wikilink(entry.set_piece_scene_id)}" if entry.set_piece_scene_id else "") + (f" — none because: {entry.reason_if_none}" if entry.reason_if_none else ""), ""]
    L += ["## Scenes", "| Scene | Slug | Must-feel | Pleasure | Energy | Set-piece | Option |", "|---|---|---|---|---|---|---|"]
    for s in scenes:
        d = decisions.get(s.id)
        p = plans.get(s.id)
        opt = d.chosen if d else (p.chosen if p else None) or ("_pending_" if p else "_no plan_")
        L.append(f"| {wikilink(s.id)} | {_cell(s.slug)} | {_cell(s.must_feel)} | {s.pleasure_type.value} | {s.energy_target} | {'yes' if s.set_piece else ''} | {opt} |")
    L.append("")
    return "\n".join(L)


def index_markdown(brief: FilmBrief, groups: list[tuple[str, str, list[Scene]]], plans: dict[str, IntegratedScenePlan], decisions: dict[str, DecisionLogEntry]) -> str:
    L = [frontmatter({"title": brief.title, "tags": ["panel", "index"]}), f"# {brief.title} — Panel index", "", f"- {wikilink(FILM_BRIEF_NOTE[:-3], 'Film Brief')}", f"- {wikilink(STYLE_BIBLE_NOTE[:-3], 'Style Bible')}", ""]
    n_plans = sum(1 for g in groups for s in g[2] if s.id in plans)
    n_dec = sum(1 for g in groups for s in g[2] if s.id in decisions)
    total = sum(len(g[2]) for g in groups)
    L += [f"_{total} scenes · {n_plans} integrated · {n_dec} decided_", ""]
    for seq_id, function, scenes in groups:
        L.append(f"## {wikilink(seq_id)}" + (f" — {function}" if function else ""))
        for s in scenes:
            marks = []
            if s.set_piece:
                marks.append("set-piece")
            if s.load_bearing:
                marks.append("load-bearing")
            d = decisions.get(s.id)
            status = f"chosen {d.chosen}" if d else ("integrated" if s.id in plans else "not integrated")
            L.append(f"- {wikilink(s.id)} {s.slug} — {s.must_feel or '…'} ({s.pleasure_type.value}{', ' + ', '.join(marks) if marks else ''}) · {status}")
        L.append("")
    return "\n".join(L)


# ------------------------------------------------------------------ the vault


def group_by_sequence(brief: FilmBrief, scenes: list[Scene]) -> list[tuple[str, str, list[Scene]]]:
    """(sequence_id, function, scenes) in Film Brief order; scenes outside any sequence go last."""
    ordered = sorted(scenes, key=lambda s: (s.number, s.id))
    by_id = {s.id: s for s in ordered}
    groups: list[tuple[str, str, list[Scene]]] = []
    placed: set[str] = set()
    for seq in brief.sequences:
        members = [by_id[sid] for sid in seq.scene_ids if sid in by_id]
        placed.update(s.id for s in members)
        groups.append((seq.sequence_id, seq.function, members))
    leftovers: dict[str, list[Scene]] = {}
    for s in ordered:
        if s.id not in placed:
            leftovers.setdefault(s.sequence_id or UNSEQUENCED, []).append(s)
    for seq_id, members in leftovers.items():
        existing = next((g for g in groups if g[0] == seq_id), None)
        if existing:
            existing[2].extend(members)
            existing[2].sort(key=lambda s: (s.number, s.id))
        else:
            groups.append((seq_id, "", members))
    return groups


def write_vault(
    vault_root: str | Path,
    film_brief: FilmBrief,
    style_bible: StyleBible | None,
    scenes: list[Scene],
    plans: dict[str, IntegratedScenePlan],
    directives: dict[str, list[DepartmentDirective]],
    audits: dict[str, list[str]],
    decisions: dict[str, DecisionLogEntry],
) -> list[Path]:
    """Write the whole vault; returns every path written. ``audits`` maps scene id → flags
    (see :func:`the_panel.store.audit_flags_by_scene`); ``decisions`` holds the latest entry per scene."""
    root = Path(vault_root)
    (root / SCENES_DIR).mkdir(parents=True, exist_ok=True)
    (root / SEQUENCES_DIR).mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    def put(rel: str, text: str) -> None:
        p = root / rel
        p.write_text(text, encoding="utf-8")
        written.append(p)

    put(FILM_BRIEF_NOTE, film_brief_markdown(film_brief))
    if style_bible is not None:
        put(STYLE_BIBLE_NOTE, style_bible_markdown(style_bible))
    groups = group_by_sequence(film_brief, scenes)
    ordered = [s for _, _, members in groups for s in members]
    for i, s in enumerate(ordered):
        seq_id = next(g[0] for g in groups if s in g[2])
        text = scene_markdown(
            s,
            plans.get(s.id),
            directives.get(s.id, []),
            audits.get(s.id, []),
            decisions.get(s.id),
            prev_id=ordered[i - 1].id if i > 0 else None,
            next_id=ordered[i + 1].id if i + 1 < len(ordered) else None,
            sequence_id=seq_id,
        )
        put(f"{SCENES_DIR}/{safe_filename(s.id)}.md", text)
    for seq_id, function, members in groups:
        put(f"{SEQUENCES_DIR}/{safe_filename(seq_id)}.md", sequence_markdown(seq_id, function, members, plans, decisions, style_bible))
    put(INDEX_NOTE, index_markdown(film_brief, groups, plans, decisions))
    return written
