"""L0 reader for Fountain (and plain screenplay ``.txt``): text → :class:`~the_panel.ingest.document.RawDocument`.

Fountain markup that is *not* scene content is neutralised here so the normaliser sees
screenplay lines only: boneyards (``/* … */``) and notes (``[[ … ]]``) are blanked
(newline count preserved, so line numbers still match the file), ``===`` page breaks and
form feeds become the page map. Sections (``#``), synopses (``=``), forced elements
(``.``, ``@``, ``!``, ``>``, ``~``) and title-page keys are left in place — the normaliser
reads those.
"""
from __future__ import annotations

import re

from .document import RawDocument

BONEYARD_RE = re.compile(r"/\*.*?\*/", re.DOTALL)
NOTE_RE = re.compile(r"\[\[.*?\]\]", re.DOTALL)
PAGE_BREAK_RE = re.compile(r"^\s*={3,}\s*$")


def _blank_keeping_newlines(match: re.Match[str]) -> str:
    return "\n" * match.group(0).count("\n")


def strip_markup(text: str) -> str:
    """Remove boneyards and notes without shifting any line number."""
    text = BONEYARD_RE.sub(_blank_keeping_newlines, text)
    return NOTE_RE.sub(_blank_keeping_newlines, text)


def read_fountain(text: str, source_format: str = "fountain") -> RawDocument:
    """Fountain / plain text → RawDocument with ``===`` and form-feed page breaks in the page map."""
    doc = RawDocument.from_text(strip_markup(text), source_format)
    for i, line in enumerate(doc.lines):
        if PAGE_BREAK_RE.match(line):
            doc.lines[i] = ""
            doc.add_page_break(i + 1)
    return doc
