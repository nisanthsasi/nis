"""Director's-notes PDF: one page per scene — slug, must-feel, governing idea, director's note,
pleasure beat, the shot it cannot live without, the Option A shot list.

reportlab is not a declared dependency, so the default engine is a minimal, dependency-free
PDF 1.4 writer (Helvetica / Helvetica-Bold, WinAnsi, word-wrapped, multi-page). Text is
WinAnsi (cp1252 — Latin-1 plus the typographic punctuation a director's note uses: em
dashes, curly quotes, ellipses). Standard PDF fonts cannot carry Malayalam script: any run
of characters outside WinAnsi is replaced by a single ``?`` and the page carries the note
"see vault for original" — the Obsidian note keeps the original text. When reportlab *is* importable the same laid-out pages are
rendered through it (``engine="auto"``); the fallback is always available as ``engine="minimal"``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Literal

from ..schemas.plan import IntegratedScenePlan
from ..schemas.scene import Scene

try:  # optional, never required
    from reportlab.pdfgen import canvas as _rl_canvas  # type: ignore

    HAVE_REPORTLAB = True
except ImportError:  # pragma: no cover - depends on the environment
    _rl_canvas = None
    HAVE_REPORTLAB = False

Engine = Literal["auto", "minimal", "reportlab"]

PAGE_W, PAGE_H = 595.0, 842.0  # A4 points
MARGIN = 56.0
BODY_SIZE = 10.5
H1_SIZE = 16.0
H2_SIZE = 11.5
LEADING = 1.35
FALLBACK_NOTE = "Non-Latin text (e.g. Malayalam) shown as '?' - see vault for original."

# Helvetica advance widths (1/1000 em) for ASCII 32..126; other WinAnsi glyphs default to 556.
_HELVETICA_WIDTHS = [
    278, 278, 355, 556, 556, 889, 667, 191, 333, 333, 389, 584, 278, 333, 278, 278,
    556, 556, 556, 556, 556, 556, 556, 556, 556, 556, 278, 278, 584, 584, 584, 556,
    1015, 667, 667, 722, 722, 667, 611, 778, 722, 278, 500, 667, 556, 833, 722, 778,
    667, 778, 722, 667, 611, 722, 667, 944, 667, 667, 611, 278, 278, 278, 469, 556,
    333, 556, 556, 500, 556, 556, 278, 556, 556, 222, 222, 500, 222, 833, 556, 556,
    556, 556, 333, 500, 278, 556, 500, 722, 500, 500, 500, 334, 260, 334, 584,
]
PDF_ENCODING = "cp1252"  # WinAnsiEncoding, a Latin-1 superset


def text_width(text: str, size: float) -> float:
    return sum(_HELVETICA_WIDTHS[ord(ch) - 32] if 32 <= ord(ch) <= 126 else 556 for ch in text) * size / 1000.0


@lru_cache(maxsize=4096)
def _encodable(ch: str) -> bool:
    try:
        ch.encode(PDF_ENCODING)
    except UnicodeEncodeError:
        return False
    return True


def winansi_safe(text: str) -> tuple[str, bool]:
    """Collapse every run of characters outside WinAnsi (e.g. Malayalam script) to a single ``?``;
    report whether anything was replaced so the page can carry the "see vault" note."""
    out: list[str] = []
    replaced = False
    in_run = False
    for ch in text:
        if _encodable(ch):
            out.append(ch)
            in_run = False
        else:
            replaced = True
            if not in_run:
                out.append("?")
                in_run = True
    return "".join(out), replaced


@dataclass
class Line:
    text: str
    size: float = BODY_SIZE
    bold: bool = False
    indent: float = 0.0


@dataclass
class Page:
    lines: list[Line] = field(default_factory=list)
    fallback_used: bool = False


class Layout:
    """Word-wraps styled paragraphs into A4 pages; a new page is started per scene and on overflow."""

    def __init__(self) -> None:
        self.pages: list[Page] = []
        self._y = 0.0

    @property
    def usable_width(self) -> float:
        return PAGE_W - 2 * MARGIN

    def new_page(self) -> None:
        self.pages.append(Page())
        self._y = PAGE_H - MARGIN

    def _ensure_room(self, height: float) -> None:
        if not self.pages or self._y - height < MARGIN + BODY_SIZE * LEADING:
            self.new_page()

    def wrap(self, text: str, size: float, width: float) -> list[str]:
        out: list[str] = []
        for para in text.split("\n"):
            words = para.split()
            if not words:
                out.append("")
                continue
            cur = ""
            for w in words:
                while text_width(w, size) > width and len(w) > 1:  # a word wider than the line: split it
                    cut = max(1, int(len(w) * width / text_width(w, size)))
                    head, w = w[:cut], w[cut:]
                    if cur:
                        out.append(cur)
                        cur = ""
                    out.append(head)
                trial = f"{cur} {w}" if cur else w
                if text_width(trial, size) <= width:
                    cur = trial
                else:
                    out.append(cur)
                    cur = w
            out.append(cur)
        return out

    def add(self, text: str, *, size: float = BODY_SIZE, bold: bool = False, indent: float = 0.0, gap_after: float = 0.0) -> None:
        safe, fallback = winansi_safe(text)
        lines = self.wrap(safe, size, self.usable_width - indent)
        for ln in lines:
            self._ensure_room(size * LEADING)
            page = self.pages[-1]
            page.lines.append(Line(ln, size, bold, indent))
            page.fallback_used = page.fallback_used or fallback
            self._y -= size * LEADING
        self._y -= gap_after

    def space(self, pts: float) -> None:
        self._y -= pts


def _shot_line(sh) -> str:
    fps = f" @{sh.frame_rate}fps" if sh.frame_rate else ""
    return f"{sh.no}. {sh.size.value} / {sh.angle} / {sh.height} / {sh.lens_mm}mm / {sh.movement}{fps} / {sh.duration_est_s:g}s - {sh.subject}: {sh.action} [beat {sh.beat_ref}] - light: {sh.light_note}"


def layout_directors_notes(film_title: str, scenes: list[Scene], plans: dict[str, IntegratedScenePlan]) -> Layout:
    lay = Layout()
    for scene in sorted(scenes, key=lambda s: (s.number, s.id)):
        lay.new_page()
        plan = plans.get(scene.id)
        lay.add(f"{film_title} - Director's notes", size=8.5)
        lay.space(4)
        lay.add(f"{scene.id} - {scene.slug}", size=H1_SIZE, bold=True, gap_after=6)
        meta = f"{scene.rasa.primary.value}" + (f"/{scene.rasa.secondary.value}" if scene.rasa.secondary else "") + f" - pleasure: {scene.pleasure_type.value} - energy {scene.energy_target}/10 - {scene.cost_flag.value}"
        if scene.set_piece:
            meta += " - SET-PIECE"
        if scene.load_bearing:
            meta += " - load-bearing"
        lay.add(meta, size=9, gap_after=8)
        sections: list[tuple[str, str]] = [("Must-feel", scene.must_feel or "not analysed")]
        if plan is None:
            sections += [("Governing idea", "not yet integrated"), ("Director's note", "not yet integrated"), ("Pleasure beat", f"planned: {scene.pleasure_type.value}")]
        else:
            pleasure = plan.pleasure_beat + (f" (none because: {plan.pleasure_none_reason})" if plan.pleasure_none_reason else "")
            if plan.must_remember_delivery:
                pleasure += f" Must-remember: {plan.must_remember_delivery}"
            k = plan.the_shot_it_cannot_live_without
            sections += [
                ("Governing idea", plan.governing_idea),
                ("Director's note", plan.directors_note),
                ("Pleasure beat", pleasure),
                ("The shot it cannot live without", f"Shot {k.shot_no} - {k.why}"),
            ]
        for title, body in sections:
            lay.add(title, size=H2_SIZE, bold=True)
            lay.add(body, gap_after=6)
        lay.add("Option A shot list", size=H2_SIZE, bold=True)
        if plan is None:
            lay.add("not yet integrated")
        else:
            lay.add(plan.option_A.rationale, gap_after=3)
            for sh in plan.option_A.shots:
                lay.add(_shot_line(sh), size=9.5, indent=10)
    return lay


# ------------------------------------------------------------------ minimal writer


def _pdf_string(text: str) -> bytes:
    raw = text.encode(PDF_ENCODING, errors="replace")
    return b"(" + raw.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)") + b")"


def _content_stream(page: Page) -> bytes:
    ops: list[bytes] = []
    y = PAGE_H - MARGIN
    for ln in page.lines:
        y -= ln.size * LEADING
        if ln.text:
            font = b"/F2" if ln.bold else b"/F1"
            ops.append(b"BT " + font + b" %.1f Tf %.1f %.1f Td " % (ln.size, MARGIN + ln.indent, y) + _pdf_string(ln.text) + b" Tj ET")
    if page.fallback_used:
        ops.append(b"BT /F1 7.5 Tf %.1f %.1f Td " % (MARGIN, MARGIN / 2) + _pdf_string(FALLBACK_NOTE) + b" Tj ET")
    return b"\n".join(ops) + b"\n"


def render_minimal_pdf(layout: Layout, path: Path, *, title: str) -> Path:
    objects: list[bytes] = []

    def add(body: bytes) -> int:
        objects.append(body)
        return len(objects)

    catalog = add(b"")  # placeholder, filled once the pages object id is known
    pages_id = add(b"")
    f1 = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")
    f2 = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>")
    page_ids: list[int] = []
    for page in layout.pages or [Page()]:
        stream = _content_stream(page)
        content = add(b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"endstream")
        page_ids.append(
            add(
                b"<< /Type /Page /Parent %d 0 R /MediaBox [0 0 %.0f %.0f] /Resources << /Font << /F1 %d 0 R /F2 %d 0 R >> >> /Contents %d 0 R >>"
                % (pages_id, PAGE_W, PAGE_H, f1, f2, content)
            )
        )
    objects[catalog - 1] = b"<< /Type /Catalog /Pages %d 0 R >>" % pages_id
    objects[pages_id - 1] = b"<< /Type /Pages /Kids [" + b" ".join(b"%d 0 R" % i for i in page_ids) + b"] /Count %d >>" % len(page_ids)
    stamp = datetime.now(timezone.utc).strftime("D:%Y%m%d%H%M%SZ")
    info = add(b"<< /Title " + _pdf_string(title) + b" /Producer (THE PANEL) /CreationDate (" + stamp.encode("ascii") + b") >>")

    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets: list[int] = []
    for i, body in enumerate(objects, 1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % i + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n" % (len(objects) + 1)
    out += b"0000000000 65535 f \n"
    for off in offsets:
        out += b"%010d 00000 n \n" % off
    out += b"trailer\n<< /Size %d /Root %d 0 R /Info %d 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objects) + 1, catalog, info, xref)
    path.write_bytes(bytes(out))
    return path


def render_reportlab_pdf(layout: Layout, path: Path, *, title: str) -> Path:  # pragma: no cover - needs reportlab
    if _rl_canvas is None:
        raise RuntimeError("reportlab is not installed; use engine='minimal'")
    c = _rl_canvas.Canvas(str(path), pagesize=(PAGE_W, PAGE_H))
    c.setTitle(title)
    for page in layout.pages or [Page()]:
        y = PAGE_H - MARGIN
        for ln in page.lines:
            y -= ln.size * LEADING
            if ln.text:
                c.setFont("Helvetica-Bold" if ln.bold else "Helvetica", ln.size)
                c.drawString(MARGIN + ln.indent, y, ln.text)
        if page.fallback_used:
            c.setFont("Helvetica", 7.5)
            c.drawString(MARGIN, MARGIN / 2, FALLBACK_NOTE)
        c.showPage()
    c.save()
    return path


def export_directors_notes_pdf(film_title: str, scenes: list[Scene], plans: dict[str, IntegratedScenePlan], path: str | Path, *, engine: Engine = "auto") -> Path:
    """One page per scene (more if a scene overflows). ``engine``: auto → reportlab if importable, else minimal."""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    layout = layout_directors_notes(film_title, scenes, plans)
    title = f"{film_title} - Director's notes"
    use_reportlab = engine == "reportlab" or (engine == "auto" and HAVE_REPORTLAB)
    if use_reportlab:
        return render_reportlab_pdf(layout, out, title=title)
    return render_minimal_pdf(layout, out, title=title)
