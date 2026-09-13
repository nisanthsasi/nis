"""L4 stage runner and Gate 1: P4 proposes the constitution, the human approves it, the header freezes.

The human sets ``commercial_posture`` at approval — the dial the rubric weights, the panel
sizer, the device audit, the caps and the department prompts read from then on. Nothing
downstream reads posture from anywhere but the approved bible.
"""
from __future__ import annotations

from typing import Any, Iterable

from ..agents.base import AgentContext
from ..agents.style_bible import StyleBibleAgent, panel_mix_problems
from ..schemas.common import ReleaseTarget
from ..schemas.film_brief import FilmBrief
from ..schemas.style_bible import StyleBible
from .header import FilmBriefHeader, build_film_brief_header
from .posture import policy_for_posture

FILM_KEY = "film"
PENDING = "pending"


async def run_style_bible(
    ctx: AgentContext,
    film_brief: FilmBrief,
    feasibility_facts: Iterable[str],
    *,
    release_target: ReleaseTarget | str,
    director_intent: str = "",
    references: list[Any] | None = None,
    posture_hint: int | None = None,
) -> StyleBible:
    """P4 once, at film level. Returns v1.0 with ``approved_by='pending'`` — Gate 1 approves it."""
    variables: dict[str, Any] = {
        "film_brief": film_brief,
        "feasibility_facts": list(feasibility_facts),
        "release_target": ReleaseTarget(release_target).value,
        "director_intent": director_intent,
        "references": list(references or []),
        "posture_hint": posture_hint,
    }
    result = await StyleBibleAgent(ctx).run(key=FILM_KEY, **variables)
    bible = result.parsed
    bible.approved_by = PENDING
    return bible


def approve_style_bible(bible: StyleBible, approved_by: str, *, posture: int | None = None, edits: dict[str, Any] | None = None) -> StyleBible:
    """Gate 1: the human approves the constitution and sets its commercial posture.

    Caps and device permissions at a posture change. P4 proposed caps and permissions for the
    posture it argued; when the human approves a different posture, the caps and permissions
    that still equal the preset defaults of the *proposed* posture are re-derived from the
    presets of the *approved* posture (P4 never reasoned about them there), while values that
    differ from those defaults were chosen with a reason — by P4 or by the human — and are
    kept. Anything in ``edits`` wins outright; ``edits`` may carry any top-level StyleBible
    field (``caps``, ``device_permissions``, ``lens_affinity``, ``refusals`` …) except the
    posture, which is set with ``posture``. The approved bible must still seat the panel mix of
    its posture — otherwise ValueError names what to edit. Returns a new, validated StyleBible.
    """
    if not approved_by.strip() or approved_by.strip() == PENDING:
        raise ValueError("approved_by must name the human who approves the Style Bible")
    edits = dict(edits or {})
    if "commercial_posture" in edits:
        raise ValueError("set the posture with the 'posture' argument, not through edits")
    data = bible.model_dump()
    if posture is not None and posture != bible.commercial_posture:
        proposed, approved = policy_for_posture(bible.commercial_posture), policy_for_posture(posture)
        if bible.caps == proposed.caps:
            data["caps"] = approved.caps
        if bible.device_permissions == proposed.device_permissions:
            data["device_permissions"] = list(approved.device_permissions)
        data["commercial_posture"] = posture
        data["posture_defence"] = f"{bible.posture_defence} [posture set to {posture} by {approved_by} at approval; P4 proposed {bible.commercial_posture}]".strip()
    data.update(edits)
    data["approved_by"] = approved_by.strip()
    approved_bible = StyleBible.model_validate(data)
    problems = panel_mix_problems(approved_bible.lens_affinity, approved_bible.commercial_posture)
    if problems:
        raise ValueError("lens affinity does not seat the panel mix for posture " f"{approved_bible.commercial_posture}: " + "; ".join(problems) + " — edit lens_affinity at approval")
    return approved_bible


def freeze_header(film_brief: FilmBrief, bible: StyleBible, max_tokens: int) -> FilmBriefHeader:
    """Approval freezes the Film Brief Header: the bible's digest joins the brief and the header
    is built frozen, ready to be prompt-cached into every call after L4."""
    if not bible.is_approved:
        raise PermissionError("Gate 1: the Style Bible must be approved before the Film Brief Header is frozen")
    film_brief.style_bible_digest = bible.digest
    return build_film_brief_header(film_brief, bible, max_tokens=max_tokens, frozen=True)


def _cap(value: int | None) -> str:
    return "unlimited (each earned)" if value is None else str(value)


def bible_gate_summary(bible: StyleBible) -> str:
    """The Gate-1 screen: manifesto, posture and its defence, pleasure map, caps, device
    permissions, lens affinity, refusals — what the human accepts or edits before approval."""
    lines: list[str] = [
        f"STYLE BIBLE v{bible.version} — {'approved by ' + bible.approved_by if bible.is_approved else 'pending approval'}",
        "",
        "HOW WE SHOOT THIS FILM",
        bible.manifesto.strip() or "(no manifesto)",
        "",
        f"COMMERCIAL POSTURE: {bible.commercial_posture}/10 ({bible.band})",
        f"Defence: {bible.posture_defence.strip() or '(none)'}",
        f"Audience promise: {', '.join(p.value for p in bible.audience_promise) or '(none)'}",
        "",
        "PLEASURE MAP",
    ]
    for e in bible.pleasure_map:
        set_piece = f" — set-piece {e.set_piece_scene_id}" if e.set_piece_scene_id else ""
        reason = f" (reason: {e.reason_if_none})" if e.reason_if_none else ""
        lines.append(f"- {e.sequence_id}: {e.pleasure_type.value}{set_piece}{reason}")
    if not bible.pleasure_map:
        lines.append("- (empty)")
    caps = bible.caps
    lines += [
        "",
        "CAPS (film-wide)",
        f"- elevation cues: {_cap(caps.elevation_cues)} · slow motion: {_cap(caps.slow_motion)} · needle drops: {_cap(caps.needle_drops)}",
        "",
        "DEVICE PERMISSIONS",
    ]
    lines += [f"- {p.device} → must pay off: {p.must_pay_off}" for p in bible.device_permissions] or ["- (none)"]
    affinity = bible.lens_affinity
    lines += [
        "",
        "LENS AFFINITY",
        f"- primary: {', '.join(affinity.primary) or '(none)'}",
        f"- secondary: {', '.join(affinity.secondary) or '(none)'}",
        f"- excluded: {'; '.join(f'{e.lens} ({e.reason})' for e in affinity.excluded) or '(none)'}",
        "",
        "REFUSALS",
    ]
    lines += [f"- {r}" for r in bible.refusals] or ["- (none)"]
    if bible.human_questions:
        lines += ["", "HUMAN QUESTIONS"] + [f"- {q}" for q in bible.human_questions]
    return "\n".join(lines)
