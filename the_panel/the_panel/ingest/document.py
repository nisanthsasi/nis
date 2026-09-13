"""L0 output: raw text plus a page map — what every format reader hands to the L1 normaliser.

A :class:`RawDocument` keeps the source *lines* exactly as read (so ``line_ref`` /
``line_start`` / ``line_end`` on the scene skeletons point back into the source) and a
list of line indices where new pages begin. Formats that really paginate (PDF, DOCX
with page breaks, Fountain with ``===``) give a *real* page map, so ``page_start`` on a
scene is real; text formats without one fall back to the 55-lines-per-page estimate.

Page markers travel with the text as ``--- PAGE n ---`` lines (:func:`page_marker`),
which is also how the model-assisted P1 pass receives "raw text with page markers".
"""
from __future__ import annotations

import re
from bisect import bisect_right
from dataclasses import dataclass, field

LINES_PER_PAGE = 55
EIGHTHS_PER_PAGE = 8

PAGE_MARKER_RE = re.compile(r"^\s*-{3,}\s*PAGE\s+(\d+)\s*-{3,}\s*$", re.IGNORECASE)
_FORM_FEED = "\f"


def page_marker(n: int) -> str:
    """The textual page marker inserted into raw text handed to the model pass."""
    return f"--- PAGE {n} ---"


@dataclass
class RawDocument:
    """Raw screenplay text with a page map (L0)."""

    lines: list[str]
    source_format: str
    page_breaks: list[int] = field(default_factory=list, metadata={"doc": "0-based indices of the first line of pages 2, 3, …"})
    page_count: int | None = field(default=None, metadata={"doc": "real page count when the format paginates; None → estimated"})
    warnings: list[str] = field(default_factory=list)

    # --- pages -------------------------------------------------------------------
    @property
    def has_page_map(self) -> bool:
        return self.page_count is not None

    def add_page_break(self, index: int) -> None:
        """Record that ``lines[index]`` begins a new page (idempotent, keeps the list sorted)."""
        if index <= 0 or index >= len(self.lines) or index in self.page_breaks:
            return
        self.page_breaks.append(index)
        self.page_breaks.sort()
        self.page_count = len(self.page_breaks) + 1

    def page_of(self, index: int) -> int:
        """1-based page number of ``lines[index]`` (1 when there is no page map)."""
        return 1 + bisect_right(self.page_breaks, index)

    def page_start(self, index: int) -> float:
        """Fractional page position of ``lines[index]``: real when a page map exists, else from cumulative lines."""
        if not self.has_page_map:
            return round(1 + index / LINES_PER_PAGE, 2)
        page = self.page_of(index)
        first = self.page_breaks[page - 2] if page > 1 else 0
        nxt = self.page_breaks[page - 1] if page - 1 < len(self.page_breaks) else len(self.lines)
        span = max(nxt - first, 1)
        return round(page + (index - first) / span, 2)

    @property
    def total_pages(self) -> float:
        if self.has_page_map:
            return float(self.page_count or 1)
        return round(max(len(self.lines), 1) / LINES_PER_PAGE, 2)

    # --- text --------------------------------------------------------------------
    @property
    def text(self) -> str:
        return "\n".join(self.lines)

    def text_with_markers(self) -> str:
        """The raw text the P1 model pass reads: every page announced by a ``--- PAGE n ---`` line."""
        if not self.has_page_map:
            return self.text
        breaks = set(self.page_breaks)
        out: list[str] = [page_marker(1)]
        page = 1
        for i, line in enumerate(self.lines):
            if i in breaks:
                page += 1
                out.append(page_marker(page))
            out.append(line)
        return "\n".join(out)

    @classmethod
    def from_text(cls, text: str, source_format: str) -> "RawDocument":
        """Split text into lines, reading form feeds and ``--- PAGE n ---`` lines as page breaks.

        Marker lines are blanked rather than removed so line numbers still match the source.
        """
        lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
        doc = cls(lines=lines, source_format=source_format)
        for i, line in enumerate(doc.lines):
            marker = PAGE_MARKER_RE.match(line)
            if marker is not None:
                doc.lines[i] = ""
                if int(marker.group(1)) > 1:
                    doc.add_page_break(i + 1)
                elif doc.page_count is None:
                    doc.page_count = 1
                continue
            if _FORM_FEED in line:
                doc.lines[i] = line.replace(_FORM_FEED, "")
                doc.add_page_break(i)
        return doc

