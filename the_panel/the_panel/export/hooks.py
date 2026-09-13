"""The Commercial Hooks Ledger as a document — hooks.md + hooks.xlsx for presenter and
distributor conversations. The ledger accumulates from approved scenes only; every hook
names its scene so the conversation can jump to the plan behind it."""
from __future__ import annotations

from pathlib import Path

from ..schemas.hooks_ledger import CommercialHooksLedger, HookEntry
from .xlsx import export_hooks_xlsx

SECTION_TITLES: dict[str, str] = {
    "interval_block": "Interval block",
    "trailer_shots": "Trailer shots",
    "poster_frames": "Poster frames",
    "bgm_hooks": "BGM hooks",
    "song_slots": "Song slots",
    "teaser_scene_candidates": "Teaser scene candidates",
    "shareable_moments": "Shareable moments",
}


def _entry_line(e: HookEntry) -> str:
    kind = f" _({e.kind})_" if e.kind else ""
    return f"- **{e.scene_id}** — {e.description}{kind}"


def hooks_markdown(ledger: CommercialHooksLedger) -> str:
    """hooks.md: grouped by section, each hook with its scene id; empty sections say so."""
    n = len(ledger.approved_scene_ids)
    L = ["# Commercial Hooks Ledger", "", "_For presenter and distributor conversations. Accumulated from " + (f"{n} approved scene{'s' if n != 1 else ''}: " + ", ".join(ledger.approved_scene_ids) if n else "no approved scenes yet") + "._", ""]
    L.append(f"## {SECTION_TITLES['interval_block']}")
    L.append(_entry_line(ledger.interval_block) if ledger.interval_block else "- _not yet designated_")
    L.append("")
    for section, entries in ledger.sections().items():
        L.append(f"## {SECTION_TITLES[section]}")
        L.extend([_entry_line(e) for e in entries] or ["- _none yet_"])
        L.append("")
    return "\n".join(L)


def export_hooks(ledger: CommercialHooksLedger, out_dir: str | Path) -> dict[str, Path]:
    """Write ``hooks.md`` and ``hooks.xlsx`` into ``out_dir``; returns both paths by name."""
    d = Path(out_dir)
    d.mkdir(parents=True, exist_ok=True)
    md = d / "hooks.md"
    md.write_text(hooks_markdown(ledger), encoding="utf-8")
    xlsx = export_hooks_xlsx(ledger, d / "hooks.xlsx")
    return {"hooks.md": md, "hooks.xlsx": xlsx}
