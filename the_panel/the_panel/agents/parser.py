"""L1 model-assisted parse pass (P1): refine registers, regions, aliases and warnings on a rule-based parse.

The rule-based ingest (:mod:`the_panel.ingest`) owns the structure. This agent may only
refine it — so :meth:`ParserAgent.check` rejects (with a repair instruction) any output
whose scene ids are not ``S1..Sn`` in order, whose line refs moved, or whose dialogue is
not verbatim from the raw text. There is no interpretation field to smuggle a reading
into: :class:`~the_panel.schemas.scene.ParsedScript` is closed (``extra="forbid"``).
"""
from __future__ import annotations

from typing import Any

from ..schemas.scene import ParsedScript
from .base import BaseAgent


def _squash(text: str) -> str:
    return " ".join(text.split())


def _as_parsed(value: Any) -> ParsedScript | None:
    if isinstance(value, ParsedScript):
        return value
    if isinstance(value, dict):
        return ParsedScript.model_validate(value)
    return None


class ParserAgent(BaseAgent[ParsedScript]):
    stage = "parser"
    name = "parser"
    template = "P1_parse"
    output_model = ParsedScript
    uses_header = False

    def check(self, parsed: ParsedScript, variables: dict[str, Any]) -> None:
        problems: list[str] = []
        ids = [s.id for s in parsed.scenes]
        if len(set(ids)) != len(ids):
            dupes = sorted({i for i in ids if ids.count(i) > 1})
            problems.append(f"scene ids must be unique (duplicated: {', '.join(dupes)})")
        for n, scene in enumerate(parsed.scenes, 1):
            if scene.id != f"S{n}" or scene.number != n:
                problems.append(f"scene {n} must be id S{n} / number {n} in script order (got {scene.id} / {scene.number})")
        raw = variables.get("raw_text")
        if isinstance(raw, str) and raw.strip():
            haystack = _squash(raw)
            for scene in parsed.scenes:
                for block in scene.dialogue_blocks:
                    if not block.text.strip():
                        problems.append(f"{scene.id}: dialogue block for {block.character} has empty text")
                        continue
                    for line in block.text.splitlines():
                        squashed = _squash(line)
                        if squashed and squashed not in haystack:
                            problems.append(f"{scene.id}: dialogue for {block.character} is not verbatim from the input (never translate or transliterate): '{line[:60]}'")
                            break
        rule_based = _as_parsed(variables.get("rule_based_parse"))
        if rule_based is not None:
            if [s.id for s in rule_based.scenes] != ids:
                problems.append("keep the rule-based scene list exactly (same ids, same order); structure is not yours to change")
            else:
                for base, scene in zip(rule_based.scenes, parsed.scenes):
                    if (base.line_start, base.line_end) != (scene.line_start, scene.line_end):
                        problems.append(f"{scene.id}: keep line_start/line_end from the rule-based parse ({base.line_start}–{base.line_end})")
                    kept = [_squash(b.text) for b in scene.dialogue_blocks]
                    for block in base.dialogue_blocks:
                        if _squash(block.text) not in kept:
                            problems.append(f"{scene.id}: dialogue block for {block.character} was dropped or altered; keep it verbatim")
                            break
        if problems:
            raise ValueError("; ".join(problems[:12]))

    def _fake_hints(self, variables: dict[str, Any]) -> dict[str, Any]:
        """Offline: let the example builder echo the rule-based parse so the fake output passes ``check``."""
        hints = super()._fake_hints(variables)
        rule_based = _as_parsed(variables.get("rule_based_parse"))
        if rule_based is not None:
            hints.update(
                {
                    "ParsedScript.scenes": [s.model_dump(mode="json") for s in rule_based.scenes],
                    "ParsedScript.location_aliases": [a.model_dump(mode="json") for a in rule_based.location_aliases],
                    "ParsedScript.character_aliases": [a.model_dump(mode="json") for a in rule_based.character_aliases],
                    "ParsedScript.parse_warnings": list(rule_based.parse_warnings),
                    "ParsedScript.source_format": rule_based.source_format,
                    "ParsedScript.total_pages": rule_based.total_pages,
                }
            )
        else:
            hints.update({"SceneSkeleton.id": "S1", "SceneSkeleton.number": 1, "SceneSkeleton.dialogue_blocks": [], "SceneSkeleton.characters": []})
        return hints
