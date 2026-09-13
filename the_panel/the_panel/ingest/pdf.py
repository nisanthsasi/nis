"""L0 reader for PDF screenplays (pdfplumber): text lines per page, with a real page map.

Screenplay PDFs carry their structure in vertical whitespace, which plain text extraction
throws away. This reader takes the positioned lines of every page, rebuilds blank lines
from the vertical gaps (one blank per extra line-height), drops page furniture (page
numbers, ``(CONTINUED)``) and records where every page starts, so ``page_start`` on a
scene is the real page. A page with no text layer (scanned) yields a warning, not a crash.
"""
from __future__ import annotations

import re
from pathlib import Path
from statistics import median

from .document import RawDocument

PAGE_NUMBER_RE = re.compile(r"^\s*(?:page\s+)?\d{1,4}\.?\s*$", re.IGNORECASE)
FURNITURE_RE = re.compile(r"^\s*(?:\(CONTINUED\)|CONTINUED:?(?:\s*\(\d+\))?|\(MORE\))\s*$", re.IGNORECASE)
DEFAULT_LEADING = 14.0


def _leading(tops: list[float]) -> float:
    deltas = sorted(b - a for a, b in zip(tops, tops[1:]) if b - a > 2)
    if not deltas:
        return DEFAULT_LEADING
    small = deltas[: max(1, len(deltas) // 2)]
    return max(median(small), 6.0)


def page_lines(page) -> list[str]:
    """Text lines of one pdfplumber page with blank lines rebuilt from vertical gaps."""
    rows = page.extract_text_lines(strip=True, return_chars=False)
    if not rows:
        text = page.extract_text() or ""
        return [ln.rstrip() for ln in text.splitlines()]
    rows.sort(key=lambda r: (round(r["top"], 1), r["x0"]))
    tops = [r["top"] for r in rows]
    lead = _leading(tops)
    out: list[str] = []
    prev_top: float | None = None
    for r in rows:
        if prev_top is not None:
            blanks = int(round((r["top"] - prev_top) / lead)) - 1
            out.extend([""] * max(0, min(blanks, 3)))
        out.append(" ".join(r["text"].split()))
        prev_top = r["top"]
    return out


def _strip_furniture(lines: list[str]) -> list[str]:
    body = list(lines)
    while body and (not body[0].strip() or PAGE_NUMBER_RE.match(body[0]) or FURNITURE_RE.match(body[0])):
        body.pop(0)
    while body and (not body[-1].strip() or PAGE_NUMBER_RE.match(body[-1]) or FURNITURE_RE.match(body[-1])):
        body.pop()
    return [ln for ln in body if not FURNITURE_RE.match(ln)]


def read_pdf(path: str | Path) -> RawDocument:
    """PDF → RawDocument; ``page_breaks`` mark the first line of every page after the first."""
    import pdfplumber

    doc = RawDocument(lines=[], source_format="pdf", page_count=0)
    with pdfplumber.open(str(path)) as pdf:
        for n, page in enumerate(pdf.pages, 1):
            body = _strip_furniture(page_lines(page))
            if not body:
                doc.warnings.append(f"page {n} has no text layer (scanned?) — nothing extracted")
            start = len(doc.lines)
            if n > 1:
                if doc.lines and doc.lines[-1].strip():
                    doc.lines.append("")
                    start += 1
                doc.page_breaks.append(start)
            doc.lines.extend(body)
        doc.page_count = len(pdf.pages)
    doc.page_breaks = [b for b in doc.page_breaks if b < len(doc.lines)]
    return doc
