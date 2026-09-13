"""Excel exports: breakdown.xlsx (L3), shotlist.xlsx (L6/L7) and hooks.xlsx (the Commercial Hooks Ledger).

Every sheet has a styled, frozen header row and an auto-filter; list-valued cells (cast,
props, production flags) are comma-joined so the 1st AD can filter and sort in Excel.
"""
from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any, Iterable

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from ..schemas.breakdown import BreakdownRow, FilmBreakdown
from ..schemas.common import Department
from ..schemas.directive import CinematographyBody, DepartmentDirective
from ..schemas.hooks_ledger import CommercialHooksLedger
from ..schemas.plan import IntegratedScenePlan

HEADER_FILL = PatternFill("solid", fgColor="1F3864")
HEADER_FONT = Font(bold=True, color="FFFFFF")
SECTION_FONT = Font(bold=True, size=12)
MAX_COL_WIDTH = 60

BREAKDOWN_COLUMNS: tuple[str, ...] = (
    "scene_id",
    "location",
    "location_new",
    "company_move",
    "cast_speaking",
    "cast_non_speaking",
    "background_count",
    "props",
    "set_dressing",
    "wardrobe_notes",
    "makeup_sfx",
    "vehicles",
    "animals",
    "minors",
    "stunts",
    "vfx",
    "special_equipment",
    "light_window",
    "schedule_critical",
    "estimated_setups",
    "page_eighths",
    "production_flags",
    "cost_flag",
    "cbfc_notes",
)

SET_PIECE_COLUMNS: tuple[str, ...] = (
    "set_piece",
    "sp_extra_shoot_days",
    "sp_rehearsal_days",
    "sp_playback_lipsync",
    "sp_crowd_count",
    "sp_high_speed_days",
    "sp_vfx_plates",
    "sp_star_windows",
    "sp_cheapest_staging_keeping_must_remember",
)

SHOTLIST_COLUMNS: tuple[str, ...] = (
    "scene_id",
    "source",
    "option",
    "shot_no",
    "cannot_live_without",
    "size",
    "angle",
    "height",
    "camera_height_cm",
    "lens_mm",
    "movement",
    "movement_motivation",
    "duration_est_s",
    "subject",
    "action",
    "beat_ref",
    "light_note",
    "sound_note",
    "transition_in",
    "transition_out",
    "frame_rate",
    "aspect_ratio",
    "filtration",
    "previz_prompt",
)

HOOKS_COLUMNS: tuple[str, ...] = ("section", "scene_id", "kind", "description")


# ------------------------------------------------------------------ cell helpers


def cell_value(v: Any) -> Any:
    """Excel-safe scalar: enums → value, lists → comma list, None → blank, bools stay bools."""
    if v is None:
        return ""
    if isinstance(v, Enum):
        return v.value
    if isinstance(v, (list, tuple, set)):
        return ", ".join(str(cell_value(x)) for x in v)
    if isinstance(v, (bool, int, float, str)):
        return v
    return str(v)


def style_header(ws: Worksheet, row: int = 1) -> None:
    for cell in ws[row]:
        if cell.value in (None, ""):
            continue
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = Alignment(vertical="center", wrap_text=True)


def autosize(ws: Worksheet) -> None:
    widths: dict[int, int] = {}
    for row in ws.iter_rows():
        for cell in row:
            if cell.value is None:
                continue
            widths[cell.column] = max(widths.get(cell.column, 0), min(MAX_COL_WIDTH, len(str(cell.value)) + 2))
    for col, w in widths.items():
        ws.column_dimensions[get_column_letter(col)].width = max(8, w)


def write_table(ws: Worksheet, headers: Iterable[str], rows: Iterable[Iterable[Any]], *, freeze: bool = True) -> None:
    """A full-sheet table: styled header row, frozen, auto-filtered."""
    headers = list(headers)
    ws.append(headers)
    style_header(ws, 1)
    for r in rows:
        ws.append([cell_value(v) for v in r])
    if freeze:
        ws.freeze_panes = "A2"
    if ws.max_row >= 1 and headers:
        ws.auto_filter.ref = f"A1:{get_column_letter(len(headers))}{ws.max_row}"
    autosize(ws)


def write_section(ws: Worksheet, title: str, headers: Iterable[str], rows: Iterable[Iterable[Any]]) -> None:
    """A titled sub-table on a stacked sheet (the film-level breakdown page)."""
    ws.append([title])
    ws.cell(row=ws.max_row, column=1).font = SECTION_FONT
    ws.append(list(headers))
    style_header(ws, ws.max_row)
    n = 0
    for r in rows:
        ws.append([cell_value(v) for v in r])
        n += 1
    if n == 0:
        ws.append(["(none)"])
    ws.append([])


# ------------------------------------------------------------------ breakdown


def breakdown_row_values(row: BreakdownRow) -> list[Any]:
    base = [getattr(row, c) for c in BREAKDOWN_COLUMNS]
    sp = row.set_piece_costing
    if sp is None:
        return base + [False] + [""] * (len(SET_PIECE_COLUMNS) - 1)
    return base + [
        True,
        sp.extra_shoot_days,
        sp.rehearsal_days,
        sp.playback_lipsync,
        sp.crowd_count,
        sp.high_speed_days,
        sp.vfx_plates,
        sp.star_windows,
        sp.cheapest_staging_keeping_must_remember,
    ]


def export_breakdown_xlsx(rows: list[BreakdownRow], film: FilmBreakdown, path: str | Path) -> Path:
    """One row per scene (flags as comma lists, set-piece costing columns) + a film-level sheet."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Scenes"
    write_table(ws, BREAKDOWN_COLUMNS + SET_PIECE_COLUMNS, (breakdown_row_values(r) for r in rows))

    fs = wb.create_sheet("Film")
    write_section(
        fs,
        "Film facts",
        ("fact", "value"),
        [
            ("budget_tier", film.budget_tier),
            ("budget_inr", film.budget_inr),
            ("night_ext_count", film.night_ext_count),
            ("crowd_scene_ids", film.crowd_scene_ids),
            ("weather_dependent_ids", film.weather_dependent_ids),
            ("song_choreography_days", film.song_choreography_days),
            ("likely_certificate", film.likely_certificate),
            ("digest", film.digest),
        ],
    )
    write_section(fs, "Feasibility facts (hard constraints for L5–L7)", ("n", "fact"), [(i + 1, f) for i, f in enumerate(film.feasibility_facts)])
    write_section(fs, "Locations", ("name", "group", "reuse_count", "scene_ids"), [(l.name, l.group, l.reuse_count, l.scene_ids) for l in film.locations])
    write_section(fs, "Cast days", ("name", "days", "is_star"), [(c.name, c.days, c.is_star) for c in film.cast_days])
    write_section(fs, "Cost drivers", ("driver", "scene_ids", "cheaper_alternative"), [(d.driver, d.scene_ids, d.cheaper_alternative) for d in film.cost_drivers])
    write_section(fs, "CBFC / OTT flags", ("scene_id", "category", "likely_band", "safer_staging", "dramatic_cost"), [(f.scene_id, f.category, f.likely_band, f.safer_staging, f.dramatic_cost) for f in film.cbfc_flags])
    fs.freeze_panes = "A2"
    autosize(fs)

    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out)
    return out


# ------------------------------------------------------------------ shot list


def shotlist_rows(plan: IntegratedScenePlan, directives: list[DepartmentDirective]) -> list[list[Any]]:
    """The scene's final shots: the cinematography directive's shot_list when present (frame rate,
    filtration, previz prompt included), else the chosen option of the IntegratedScenePlan."""
    cine = next((d for d in directives if d.dept == Department.CINEMATOGRAPHY), None)
    label = plan.chosen or plan.recommended
    keeper = plan.the_shot_it_cannot_live_without.shot_no
    rows: list[list[Any]] = []
    if cine is not None:
        body = CinematographyBody.model_validate(cine.directive)
        fps_by_shot = {f.shot_no: f.fps for f in body.slow_motion_frame_rates}
        for sh in body.shot_list:
            rows.append(
                [
                    plan.scene_id,
                    "cinematography",
                    label,
                    sh.no,
                    sh.no == keeper,
                    sh.size,
                    sh.angle,
                    sh.height,
                    sh.camera_height_cm,
                    sh.lens_mm,
                    sh.movement,
                    sh.movement_motivation,
                    sh.duration_est_s,
                    sh.subject,
                    sh.action,
                    sh.beat_ref,
                    sh.light_note,
                    sh.sound_note,
                    sh.transition_in,
                    sh.transition_out,
                    sh.frame_rate or fps_by_shot.get(sh.no, body.base_frame_rate),
                    sh.aspect_ratio or body.aspect_ratio,
                    sh.filtration,
                    sh.previz_prompt,
                ]
            )
        return rows
    for sh in plan.chosen_option().shots:
        rows.append(
            [
                plan.scene_id,
                f"plan option {label}",
                label,
                sh.no,
                sh.no == keeper,
                sh.size,
                sh.angle,
                sh.height,
                None,
                sh.lens_mm,
                sh.movement,
                sh.movement_motivation,
                sh.duration_est_s,
                sh.subject,
                sh.action,
                sh.beat_ref,
                sh.light_note,
                sh.sound_note,
                sh.transition_in,
                sh.transition_out,
                sh.frame_rate,
                None,
                None,
                None,
            ]
        )
    return rows


def export_shotlist_xlsx(plans: list[IntegratedScenePlan], directives: dict[str, list[DepartmentDirective]], path: str | Path) -> Path:
    wb = Workbook()
    ws = wb.active
    ws.title = "Shot list"
    rows: list[list[Any]] = []
    for plan in plans:
        rows.extend(shotlist_rows(plan, directives.get(plan.scene_id, [])))
    write_table(ws, SHOTLIST_COLUMNS, rows)
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out)
    return out


# ------------------------------------------------------------------ hooks


def hooks_rows(ledger: CommercialHooksLedger) -> list[list[Any]]:
    rows: list[list[Any]] = []
    if ledger.interval_block is not None:
        ib = ledger.interval_block
        rows.append(["interval_block", ib.scene_id, ib.kind, ib.description])
    for section, entries in ledger.sections().items():
        for e in entries:
            rows.append([section, e.scene_id, e.kind, e.description])
    return rows


def export_hooks_xlsx(ledger: CommercialHooksLedger, path: str | Path) -> Path:
    wb = Workbook()
    ws = wb.active
    ws.title = "Hooks"
    write_table(ws, HOOKS_COLUMNS, hooks_rows(ledger))
    approved = wb.create_sheet("Approved scenes")
    write_table(approved, ("scene_id",), ([sid] for sid in ledger.approved_scene_ids))
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out)
    return out
