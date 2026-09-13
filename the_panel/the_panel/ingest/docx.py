"""L0 reader for DOCX screenplays (python-docx): paragraphs → lines, page breaks → page map.

Two kinds of Word screenplay arrive here. A *styled* one (exported from Final Draft or a
screenplay template) names its elements in paragraph styles — Scene Heading, Character,
Dialogue, … — and is laid out as Fountain-shaped lines like FDX. A *plain* one (a writer's
Normal-style document) is read paragraph by paragraph; its blank paragraphs are the
structure. Song / lyric paragraphs are kept verbatim for the normaliser's song detection.
Bilingual text (Malayalam script inside English action) passes through untouched.
"""
from __future__ import annotations

from pathlib import Path

from .document import RawDocument
from .normalise import ParagraphKind, lines_from_paragraphs

STYLE_TO_KIND: dict[str, ParagraphKind] = {
    "scene heading": "scene_heading",
    "sceneheading": "scene_heading",
    "slugline": "scene_heading",
    "action": "action",
    "character": "character",
    "character name": "character",
    "parenthetical": "parenthetical",
    "dialogue": "dialogue",
    "dialog": "dialogue",
    "transition": "transition",
    "lyrics": "lyrics",
    "lyric": "lyrics",
    "song": "lyrics",
    "shot": "action",
}
_W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def _starts_new_page(paragraph) -> bool:
    el = paragraph._element
    return bool(el.findall(f".//{{{_W_NS}}}br[@{{{_W_NS}}}type='page']") or el.findall(f".//{{{_W_NS}}}lastRenderedPageBreak"))


def _style_kind(paragraph) -> ParagraphKind | None:
    name = (paragraph.style.name if paragraph.style is not None else "") or ""
    return STYLE_TO_KIND.get(name.strip().lower())


def read_docx(path: str | Path) -> RawDocument:
    """DOCX → RawDocument. Styled documents go through the typed-paragraph layout; plain ones are read line for line."""
    from docx import Document

    document = Document(str(path))
    paragraphs = list(document.paragraphs)
    styled = any(_style_kind(p) for p in paragraphs)
    doc = RawDocument(lines=[], source_format="docx")
    page_break_before: list[int] = []
    if styled:
        typed: list[tuple[ParagraphKind, str]] = []
        for p in paragraphs:
            if _starts_new_page(p):
                page_break_before.append(len(typed))
            typed.append((_style_kind(p) or "general", p.text))
        doc.lines = lines_from_paragraphs(typed)
        if page_break_before:
            doc.warnings.append("styled DOCX page breaks are approximate: page_start estimated from line counts")
        return doc
    pending_break: int | None = None
    for p in paragraphs:
        if _starts_new_page(p):
            if doc.lines and doc.lines[-1].strip():
                doc.lines.append("")
            pending_break = len(doc.lines)
        doc.lines.extend(p.text.replace("\r", "").split("\n"))
        if pending_break is not None and pending_break < len(doc.lines):
            doc.add_page_break(pending_break)
            pending_break = None
    return doc
