"""The Film Brief Header — ~2–3k tokens, frozen at L4 approval, prompt-cached into every call after."""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field

from ..schemas.film_brief import FilmBrief
from ..schemas.style_bible import StyleBible

CHARS_PER_TOKEN = 3.6  # conservative for English + occasional Malayalam script


def estimate_tokens(text: str) -> int:
    return int(math.ceil(len(text) / CHARS_PER_TOKEN))


@dataclass
class FilmBriefHeader:
    text: str
    token_estimate: int
    frozen: bool = False
    sha: str = ""
    dropped_sections: list[str] = field(default_factory=list)

    def system_block(self, ttl: str = "1h") -> dict:
        return {"type": "text", "text": self.text, "cache_control": {"type": "ephemeral", "ttl": ttl}}


def _kv(label: str, value) -> str:
    if value in (None, "", [], {}):
        return ""
    if isinstance(value, (list, tuple)):
        value = "; ".join(str(v) for v in value)
    return f"{label}: {value}"


def _sections(brief: FilmBrief, bible: StyleBible | None) -> list[tuple[str, int, str]]:
    """(name, priority, text). Lower priority number = dropped first when over budget."""
    s: list[tuple[str, int, str]] = []
    s.append(("identity", 100, "\n".join(x for x in [
        f"FILM: {brief.title}",
        _kv("Logline", brief.logline),
        _kv("Dramatic question", brief.dramatic_question),
        _kv("Controlling idea", brief.controlling_idea),
        _kv("Release target", brief.release_target.value),
        _kv("Budget tier", brief.budget_tier.value),
        _kv("Language mix", brief.language_mix),
        _kv("CBFC posture", brief.cbfc_posture),
    ] if x)))
    if brief.mechanism:
        m = brief.mechanism
        s.append(("mechanism", 90, "\n".join(x for x in [
            "MECHANISM (NFE):",
            _kv("Family", m.family),
            _kv("Transposition premise", m.transposition_premise),
            _kv("One sentence", m.one_sentence),
            _kv("Executes in scenes", m.execution_scene_ids),
        ] if x)))
    beats = "; ".join(f"{b.name}→{b.scene_id}{'' if b.turns_central_value else ' (does not turn)'}" for b in brief.load_bearing_beats)
    s.append(("structure", 95, "\n".join(x for x in [
        f"STRUCTURE: {brief.structure_model.value}",
        _kv("Load-bearing beats", beats),
        _kv("Value arc", [f"{v.act}:{v.value}" for v in brief.value_arc]),
    ] if x)))
    seqs = "; ".join(f"{q.sequence_id}[{','.join(q.scene_ids)}] {q.function} ({q.rhythm})" for q in brief.sequences)
    s.append(("sequences", 60, _kv("SEQUENCES", seqs)))
    chars = []
    for c in brief.characters:
        arc = " → ".join(f"{a.act}:{a.state}" for a in c.arc_map)
        line = f"- {c.name}: want={c.want} | need={c.need} | wound={c.wound} | lie={c.lie} | answer={c.thematic_answer} | register={c.dialogue_register.value}"
        if c.is_antagonist:
            line += f" | ANTAGONIST: {c.antagonist_argument or ''}"
        if arc:
            line += f" | arc: {arc}"
        chars.append(line)
    s.append(("characters", 92, "CHARACTERS:\n" + "\n".join(chars) if chars else ""))
    s.append(("star_cast", 70, _kv("STAR CAST", [f"{x.actor} as {x.character} (entry {x.entry_scene_id})" for x in brief.star_cast])))
    s.append(("motifs", 50, "\n".join(x for x in [_kv("IMAGE SYSTEMS", brief.image_systems), _kv("MOTIFS", brief.motifs)] if x)))
    s.append(("plants", 40, _kv("PLANTS→PAYOFFS", [f"{p.item}: {p.plant_scene_id}→{p.payoff_scene_id}" for p in brief.plants_payoffs])))
    s.append(("set_pieces", 80, _kv("SET-PIECE CANDIDATES", [f"{x.scene_id} {x.kind.value} ({x.pleasure_type.value}){' INTERVAL' if x.interval_candidate else ''}" for x in brief.set_piece_candidates])))
    s.append(("theme", 45, "\n".join(x for x in [
        _kv("THEME dramatised", brief.theme_audit.dramatised),
        _kv("THEME silent", brief.theme_audit.silent),
        _kv("THEME preaches", brief.theme_audit.preaches),
    ] if x)))
    digest = (bible.digest if bible and bible.digest else brief.style_bible_digest) or ""
    if bible:
        caps = bible.caps
        digest_head = "\n".join(x for x in [
            f"STYLE BIBLE v{bible.version} ({bible.approved_by}) — posture {bible.commercial_posture}/10 ({bible.band})",
            _kv("Tone", bible.form.tone),
            _kv("Audience promise", [p.value for p in bible.audience_promise]),
            _kv("Caps", f"elevation {caps.elevation_cues if caps.elevation_cues is not None else '∞'}, slow-mo {caps.slow_motion if caps.slow_motion is not None else '∞'}, needle drops {caps.needle_drops if caps.needle_drops is not None else '∞'}"),
            _kv("Device permissions", [f"{d.device} (pays off: {d.must_pay_off})" for d in bible.device_permissions]),
            _kv("Signature devices", bible.signature_devices),
            _kv("Refusals", bible.refusals),
            _kv("Pleasure map", [f"{p.sequence_id}:{p.pleasure_type.value}{'@' + p.set_piece_scene_id if p.set_piece_scene_id else ''}" for p in bible.pleasure_map]),
            _kv("Lens affinity", f"primary {bible.lens_affinity.primary}; secondary {bible.lens_affinity.secondary}"),
        ] if x)
        digest = digest_head + ("\n" + digest if digest else "")
    s.append(("style_bible_digest", 99, digest))
    return [x for x in s if x[2]]


def build_film_brief_header(brief: FilmBrief, bible: StyleBible | None = None, *, max_tokens: int = 3000, frozen: bool = False) -> FilmBriefHeader:
    sections = _sections(brief, bible)
    dropped: list[str] = []
    text = "\n\n".join(t for _, _, t in sections)
    while estimate_tokens(text) > max_tokens and len(sections) > 1:
        # drop the lowest-priority section first
        idx = min(range(len(sections)), key=lambda i: sections[i][1])
        dropped.append(sections[idx][0])
        sections.pop(idx)
        text = "\n\n".join(t for _, _, t in sections)
    if estimate_tokens(text) > max_tokens:
        text = text[: int(max_tokens * CHARS_PER_TOKEN)]
        dropped.append("truncated")
    sha = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
    return FilmBriefHeader(text=text, token_estimate=estimate_tokens(text), frozen=frozen, sha=sha, dropped_sections=dropped)


def header_from_json(data: dict) -> FilmBriefHeader:
    return FilmBriefHeader(**data)


def header_to_json(h: FilmBriefHeader) -> str:
    return json.dumps(h.__dict__, ensure_ascii=False)
