"""L0 ingest + L1 parse: Fountain / FDX / PDF / DOCX → :class:`~the_panel.schemas.scene.ParsedScript`.

Rule-based first (:func:`ingest_file`, :func:`ingest_text` — deterministic, offline,
Malayalam-safe), model-assisted second (:func:`refine` runs
:class:`~the_panel.agents.parser.ParserAgent` to correct registers, aliases and warnings
while every scene id, line ref and dialogue text stays exactly as parsed).
"""
from __future__ import annotations

from pathlib import Path

from ..agents.base import AgentContext
from ..agents.parser import ParserAgent
from ..schemas.scene import ParsedScript
from .document import RawDocument, page_marker
from .docx import read_docx
from .fdx import read_fdx
from .fountain import read_fountain
from .normalise import CharacterRoster, LocationAliasTable, normalise_document
from .pdf import read_pdf
from .register import add_regional_markers, detect_register, detect_script

FORMATS_BY_EXTENSION: dict[str, str] = {
    ".fountain": "fountain",
    ".spmd": "fountain",
    ".txt": "fountain",
    ".fdx": "fdx",
    ".pdf": "pdf",
    ".docx": "docx",
}
TEXT_FORMATS: frozenset[str] = frozenset({"fountain", "txt", "text", "fdx", "pdf", "docx"})


def detect_format(path: str | Path) -> str:
    ext = Path(path).suffix.lower()
    try:
        return FORMATS_BY_EXTENSION[ext]
    except KeyError:
        raise ValueError(f"cannot detect screenplay format from extension '{ext}' (expected one of {sorted(FORMATS_BY_EXTENSION)})") from None


def read_document(path: str | Path, *, format: str | None = None) -> RawDocument:
    """L0: read a screenplay file into raw lines plus a page map."""
    fmt = (format or detect_format(path)).lower()
    p = Path(path)
    if fmt == "pdf":
        return read_pdf(p)
    if fmt == "docx":
        return read_docx(p)
    text = p.read_text(encoding="utf-8-sig")
    if fmt == "fdx":
        return read_fdx(text)
    if fmt in ("fountain", "txt", "text"):
        return read_fountain(text)
    raise ValueError(f"unknown screenplay format '{fmt}'")


def parse_document(doc: RawDocument, *, aliases: LocationAliasTable | None = None) -> ParsedScript:
    """L1 (rule-based): scene skeletons from a RawDocument."""
    return normalise_document(doc, aliases=aliases)


def ingest_file(path: str | Path, *, format: str | None = None, aliases: LocationAliasTable | None = None) -> ParsedScript:
    """L0 + L1 for a file; the format is detected from the extension unless given (fountain | fdx | pdf | docx)."""
    return parse_document(read_document(path, format=format), aliases=aliases)


def ingest_text(text: str, source_format: str, *, aliases: LocationAliasTable | None = None) -> ParsedScript:
    """L0 + L1 for text already in memory.

    ``fdx`` accepts FDX XML or FDX-exported text; ``pdf`` / ``docx`` mean text already
    extracted from such a file (``--- PAGE n ---`` lines and form feeds are read as page
    markers). Binary PDF/DOCX files go through :func:`ingest_file`.
    """
    fmt = source_format.lower()
    if fmt not in TEXT_FORMATS:
        raise ValueError(f"unknown text format '{source_format}' (expected one of {sorted(TEXT_FORMATS)})")
    if fmt == "fdx":
        doc = read_fdx(text)
    else:
        doc = read_fountain(text, source_format="fountain" if fmt in ("txt", "text") else fmt)
    return parse_document(doc, aliases=aliases)


async def refine(ctx: AgentContext | None, parsed: ParsedScript, raw_text: str, *, key: str = "script") -> ParsedScript:
    """The model-assisted P1 pass: registers, regions, aliases and warnings refined by :class:`ParserAgent`.

    With ``ctx=None`` the rule-based parse is returned unchanged (the offline / no-model
    path). Otherwise the agent sees the raw text (with page markers) *and* the rule-based
    parse, and its output is validated to keep the structure: same scene ids and line refs,
    every dialogue text verbatim. Page facts (source format, total pages) are the rules'
    and are carried over.
    """
    if ctx is None:
        return parsed
    result = await ParserAgent(ctx).run(
        key=key,
        raw_text=raw_text,
        format_hint=parsed.source_format,
        location_aliases=parsed.location_aliases,
        rule_based_parse=parsed,
    )
    refined = result.parsed
    return refined.model_copy(update={"source_format": parsed.source_format or refined.source_format, "total_pages": parsed.total_pages or refined.total_pages})


__all__ = [
    "CharacterRoster",
    "LocationAliasTable",
    "ParserAgent",
    "RawDocument",
    "add_regional_markers",
    "detect_format",
    "detect_register",
    "detect_script",
    "ingest_file",
    "ingest_text",
    "page_marker",
    "parse_document",
    "read_document",
    "refine",
]
