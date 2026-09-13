"""L0 reader for Final Draft: FDX XML paragraphs, or FDX-exported plain text.

FDX carries the element type on every ``<Paragraph Type="…">`` (Scene Heading / Action /
Character / Parenthetical / Dialogue / Transition / Lyrics / Shot / General), so the
reader lays those out as Fountain-shaped lines via
:func:`~the_panel.ingest.normalise.lines_from_paragraphs` and one normaliser serves every
format. Text exported from Final Draft ("FDX-exported text") has no types — it is read as
plain screenplay text.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET

from .document import RawDocument
from .fountain import read_fountain
from .normalise import ParagraphKind, lines_from_paragraphs

FDX_TYPE_TO_KIND: dict[str, ParagraphKind] = {
    "Scene Heading": "scene_heading",
    "Action": "action",
    "Character": "character",
    "Parenthetical": "parenthetical",
    "Dialogue": "dialogue",
    "Transition": "transition",
    "Lyrics": "lyrics",
    "Song": "lyrics",
    "Shot": "action",
    "General": "general",
    "Cast List": "general",
    "New Act": "general",
    "End of Act": "general",
}


def looks_like_fdx_xml(text: str) -> bool:
    head = text.lstrip()[:200]
    return head.startswith("<?xml") or head.startswith("<FinalDraft")


def _paragraph_text(p: ET.Element) -> str:
    return "".join((t.text or "") for t in p.iter("Text")).replace("\r", "")


def fdx_paragraphs(xml_text: str) -> list[tuple[ParagraphKind, str]]:
    """``(kind, text)`` for every ``<Paragraph>`` under ``<Content>``; a scene number attribute is appended Fountain-style (``#12#``)."""
    root = ET.fromstring(xml_text)
    content = root.find("Content")
    if content is None:
        raise ValueError("FDX has no <Content> element")
    out: list[tuple[ParagraphKind, str]] = []
    for p in content.iter("Paragraph"):
        kind = FDX_TYPE_TO_KIND.get(p.get("Type", "General"), "general")
        text = _paragraph_text(p)
        number = p.get("Number")
        if kind == "scene_heading" and number:
            text = f"{text.rstrip()} #{number}#"
        out.append((kind, text))
    return out


def read_fdx(text: str) -> RawDocument:
    """FDX XML → RawDocument (typed paragraphs laid out as Fountain lines); plain text → read as exported screenplay text."""
    if not looks_like_fdx_xml(text):
        return read_fountain(text, source_format="fdx")
    lines = lines_from_paragraphs(fdx_paragraphs(text))
    return RawDocument(lines=lines, source_format="fdx")
