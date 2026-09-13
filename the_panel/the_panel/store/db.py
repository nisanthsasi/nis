"""SQLite state for THE PANEL — the queryable mirror of the JSON snapshots.

``store/snapshots.py`` stays the raw record (every agent call writes raw + parsed JSON
there). This module mirrors the *parsed* side into SQLite via sqlmodel so the human
review loop, the cost dashboard and the exporters can ask questions the filesystem
cannot answer cheaply: which stage is running, what the latest plan for S3 is, how many
output tokens the lenses spent on S3, which amendments are still pending, what the cap
ledger and the Commercial Hooks Ledger currently hold.

Key convention (mirrors ``AgentResult.key``): ``"S3"`` for a scene-level artifact,
``"S3/kubrick"`` for a lens vision, ``"S3/dept_music"`` for a directive, ``"SEQ1"`` for a
sequence-level artifact, ``"film"`` for film-level ones. :func:`scene_of_key` extracts
the scene id so per-scene cost can be rolled up.

Artifact ``stage`` is the *kind* of parsed model the row stores (one model type per
stage so :meth:`PanelDB.load_all` can validate uniformly); the ``ARTIFACT_*`` constants
name the kinds the pipeline persists.
"""
from __future__ import annotations

import json as jsonlib
import re
from dataclasses import dataclass, field as dc_field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypeVar

from pydantic import BaseModel
from sqlalchemy import delete
from sqlalchemy.pool import StaticPool
from sqlmodel import Field, Session, SQLModel, create_engine, select

from ..orchestrator.caps import CapLedger
from ..schemas.audits import AuditBundle
from ..schemas.breakdown import BreakdownRow
from ..schemas.common import Usage
from ..schemas.decisions import DecisionLogEntry
from ..schemas.directive import DepartmentDirective
from ..schemas.hooks_ledger import CommercialHooksLedger, HookEntry
from ..schemas.plan import IntegratedScenePlan
from ..schemas.scene import Scene
from ..schemas.style_bible import Amendment, Caps
from ..schemas.vision import SceneVision

if TYPE_CHECKING:  # agents.base imports store.snapshots; keep the runtime graph acyclic
    from ..agents.base import AgentResult

M = TypeVar("M", bound=BaseModel)

STAGE_STATUSES: tuple[str, ...] = ("pending", "running", "done", "failed")

# Artifact kinds — one parsed model type per kind.
ARTIFACT_FILM_BRIEF = "film_brief"  # key "film"           → FilmBrief
ARTIFACT_SCENE = "scene"  # key "S3"                       → Scene (L2 report card)
ARTIFACT_BREAKDOWN_ROW = "breakdown_row"  # key "S3"       → BreakdownRow
ARTIFACT_FILM_BREAKDOWN = "film_breakdown"  # key "film"   → FilmBreakdown
ARTIFACT_STYLE_BIBLE = "style_bible"  # key "film"         → StyleBible (a new version per amendment)
ARTIFACT_SEQUENCE_PLAN = "sequence_plan"  # key "SEQ1"     → SequencePlan
ARTIFACT_VISION = "vision"  # key "S3/kubrick"             → SceneVision
ARTIFACT_CRITIQUE = "critique"  # key "S3/kubrick"         → Critique
ARTIFACT_PLAN = "plan"  # key "S3"                         → IntegratedScenePlan
ARTIFACT_DIRECTIVE = "directive"  # key "S3/cinematography" → DepartmentDirective
ARTIFACT_AUDIT = "audit"  # key "SEQ1" or "film"           → AuditBundle

HOOK_SECTIONS: tuple[str, ...] = (
    "trailer_shots",
    "poster_frames",
    "bgm_hooks",
    "song_slots",
    "teaser_scene_candidates",
    "interval_block",
    "shareable_moments",
)

_SCENE_KEY = re.compile(r"^(S\d+[A-Za-z]?)(?:/|$)")
_NATURAL = re.compile(r"(\d+)")


def scene_of_key(key: str) -> str | None:
    """``"S3/kubrick"`` → ``"S3"``; ``"S3"`` → ``"S3"``; ``"SEQ1"`` / ``"film"`` → ``None``."""
    m = _SCENE_KEY.match(key)
    return m.group(1) if m else None


def cost_bucket(key: str) -> str:
    """The cost-dashboard bucket for a call key: the scene id, else the head segment (``SEQ1``, ``film``)."""
    return scene_of_key(key) or key.split("/", 1)[0]


def natural_key(text: str) -> tuple[Any, ...]:
    """Sort helper so S2 comes before S10."""
    return tuple(int(p) if p.isdigit() else p for p in _NATURAL.split(text))


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _naive_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


def _dump_ids(ids: list[str]) -> str:
    return jsonlib.dumps(list(ids), ensure_ascii=False)


def _load_ids(blob: str) -> list[str]:
    return [str(x) for x in jsonlib.loads(blob or "[]")]


# ------------------------------------------------------------------ tables


class Call(SQLModel, table=True):
    """One model call (one :class:`AgentResult`) — the row the cost dashboard sums."""

    __tablename__ = "call"

    id: int | None = Field(default=None, primary_key=True)
    stage: str = Field(index=True)
    agent: str
    key: str = Field(index=True)
    model: str
    attempts: int = 1
    over_budget: bool = False
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_input_tokens: int = 0
    cache_creation_input_tokens: int = 0
    snapshot_path: str | None = None
    created_at: datetime = Field(default_factory=_now)

    @property
    def usage(self) -> Usage:
        return Usage(
            input_tokens=self.input_tokens,
            output_tokens=self.output_tokens,
            cache_creation_input_tokens=self.cache_creation_input_tokens,
            cache_read_input_tokens=self.cache_read_input_tokens,
        )


class StageRun(SQLModel, table=True):
    """The state machine's memory: one row per pipeline stage, upserted by :meth:`PanelDB.set_stage`."""

    __tablename__ = "stage_run"

    stage: str = Field(primary_key=True)
    status: str = "pending"
    started_at: datetime | None = None
    finished_at: datetime | None = None
    note: str = ""


class Artifact(SQLModel, table=True):
    """A parsed output, versioned per (stage, key); the latest version is the pipeline's truth."""

    __tablename__ = "artifact"

    id: int | None = Field(default=None, primary_key=True)
    stage: str = Field(index=True)
    key: str = Field(index=True)
    version: int = 1
    blob: str = Field(description="the parsed model as JSON")
    created_at: datetime = Field(default_factory=_now)


class Decision(SQLModel, table=True):
    """A :class:`DecisionLogEntry` — the human's sovereign word on a scene, sequence or the Style Bible."""

    __tablename__ = "decision"

    id: int | None = Field(default=None, primary_key=True)
    scene_id: str = Field(index=True)
    chosen: str
    gate: str = "scene"
    human_note: str = ""
    pushback_given: bool = False
    has_amendment: bool = False
    timestamp: datetime = Field(default_factory=_now)
    blob: str = Field(description="the DecisionLogEntry as JSON")

    def entry(self) -> DecisionLogEntry:
        return DecisionLogEntry.model_validate_json(self.blob)


class AmendmentRow(SQLModel, table=True):
    """A Style Bible amendment (pending until a human approves it) and the scenes it forces to re-run."""

    __tablename__ = "amendment"

    id: int | None = Field(default=None, primary_key=True)
    scene_id: str | None = Field(default=None, index=True)
    change: str
    reason: str
    approved: bool = False
    affected_scene_ids: str = "[]"
    rerun_scene_ids: str = "[]"
    decision_id: int | None = None
    created_at: datetime = Field(default_factory=_now)
    approved_at: datetime | None = None

    @property
    def rerun_ids(self) -> list[str]:
        return _load_ids(self.rerun_scene_ids)

    @property
    def affected_ids(self) -> list[str]:
        return _load_ids(self.affected_scene_ids)

    def to_amendment(self) -> Amendment:
        return Amendment(scene_id=self.scene_id, change=self.change, reason=self.reason, approved=self.approved, affected_scene_ids=self.affected_ids)


class CapSpendRow(SQLModel, table=True):
    """One spend of a film-wide cap (elevation cue, slow motion, needle drop) — never silent."""

    __tablename__ = "cap_spend"

    id: int | None = Field(default=None, primary_key=True)
    cap_key: str = Field(index=True)
    device: str
    scene_id: str = Field(index=True)
    setup_ref: str


class HookRow(SQLModel, table=True):
    """One Commercial Hooks Ledger entry (trailer shot, poster frame, BGM hook, …) from an approved scene."""

    __tablename__ = "hook"

    id: int | None = Field(default=None, primary_key=True)
    section: str = Field(index=True)
    scene_id: str = Field(index=True)
    description: str
    kind: str = ""
    created_at: datetime = Field(default_factory=_now)

    def entry(self) -> HookEntry:
        return HookEntry(scene_id=self.scene_id, description=self.description, kind=self.kind)


class SequenceApproval(SQLModel, table=True):
    """Gate 2: the human's approval of a SequencePlan (energy curve, pleasure placement, set-piece designation)."""

    __tablename__ = "sequence_approval"

    sequence_id: str = Field(primary_key=True)
    approved: bool = False
    note: str = ""
    updated_at: datetime = Field(default_factory=_now)


# ------------------------------------------------------------------ scene snapshot


def audit_flags_for(bundles: list[AuditBundle], scene_id: str) -> list[str]:
    """Flatten every auditor finding that names ``scene_id`` into one-line flags for the review screen."""
    flags: list[str] = []
    for b in bundles:
        for i in b.continuity.issues:
            if i.scene_id == scene_id:
                flags.append(f"continuity {i.severity.value}: {i.issue} → {i.fix}")
        for s in b.feasibility.statuses:
            if s.scene_id == scene_id and s.rag.value != "GREEN":
                detail = "; ".join(s.issues) or "see fixes"
                flags.append(f"feasibility {s.rag.value}: {detail}")
        for f in b.earned_device.flags:
            if f.scene_id == scene_id and f.verdict.value != "EARNED":
                alt = f" → {f.alternative}" if f.alternative else ""
                flags.append(f"device {f.verdict.value}: {f.device}{alt}")
        for g in b.engagement.gaps:
            if scene_id in g.scene_ids:
                flags.append(f"engagement {g.kind}: {g.detail} → {g.fix}")
    return flags


def audit_flags_by_scene(bundles: list[AuditBundle]) -> dict[str, list[str]]:
    """Every scene id any auditor mentions → its flags (what ``write_vault`` takes as ``audits``)."""
    ids: list[str] = []
    for b in bundles:
        ids += [i.scene_id for i in b.continuity.issues]
        ids += [s.scene_id for s in b.feasibility.statuses]
        ids += [f.scene_id for f in b.earned_device.flags]
        for g in b.engagement.gaps:
            ids += g.scene_ids
    out: dict[str, list[str]] = {}
    for sid in sorted(set(ids), key=natural_key):
        flags = audit_flags_for(bundles, sid)
        if flags:
            out[sid] = flags
    return out


@dataclass
class SceneOutputSnapshot:
    """Everything the pipeline currently holds for one scene, loaded from the latest Artifact rows."""

    scene_id: str
    scene: Scene | None = None
    breakdown_row: BreakdownRow | None = None
    visions: dict[str, SceneVision] = dc_field(default_factory=dict)
    plan: IntegratedScenePlan | None = None
    directives: list[DepartmentDirective] = dc_field(default_factory=list)
    audits: list[AuditBundle] = dc_field(default_factory=list)
    decision: DecisionLogEntry | None = None
    hooks: list[HookRow] = dc_field(default_factory=list)

    @property
    def audit_flags(self) -> list[str]:
        return audit_flags_for(self.audits, self.scene_id)

    @property
    def option_chosen(self) -> str | None:
        if self.decision is not None:
            return self.decision.chosen
        return self.plan.chosen if self.plan is not None else None

    @property
    def is_reviewed(self) -> bool:
        return self.decision is not None


# ------------------------------------------------------------------ the store


class PanelDB:
    """SQLite mirror of the pipeline state. ``PanelDB(":memory:")`` for tests."""

    def __init__(self, path: str | Path = ":memory:"):
        self.path = str(path)
        if self.path == ":memory:":
            self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        else:
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
            self.engine = create_engine(f"sqlite:///{self.path}")
        self.create_all()

    @classmethod
    def from_config(cls, config: Any) -> "PanelDB":
        return cls(config.path("store"))

    def create_all(self) -> None:
        SQLModel.metadata.create_all(self.engine)

    def close(self) -> None:
        self.engine.dispose()

    def __enter__(self) -> "PanelDB":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    def _session(self) -> Session:
        return Session(self.engine, expire_on_commit=False)

    # --- calls ----------------------------------------------------------------
    def record_call(self, result: "AgentResult") -> Call:
        u = result.usage
        row = Call(
            stage=result.stage,
            agent=result.agent,
            key=result.key,
            model=result.model,
            attempts=result.attempts,
            over_budget=result.over_budget,
            input_tokens=u.input_tokens,
            output_tokens=u.output_tokens,
            cache_read_input_tokens=u.cache_read_input_tokens,
            cache_creation_input_tokens=u.cache_creation_input_tokens,
            snapshot_path=str(result.snapshot_path) if result.snapshot_path else None,
            created_at=_naive_utc(result.created_at),
        )
        with self._session() as s:
            s.add(row)
            s.commit()
            s.refresh(row)
        return row

    def calls(self, stage: str | None = None, key: str | None = None) -> list[Call]:
        stmt = select(Call)
        if stage is not None:
            stmt = stmt.where(Call.stage == stage)
        if key is not None:
            stmt = stmt.where(Call.key == key)
        with self._session() as s:
            return list(s.exec(stmt.order_by(Call.id)).all())

    def usage_by_stage(self) -> dict[str, Usage]:
        out: dict[str, Usage] = {}
        for c in self.calls():
            out[c.stage] = out.get(c.stage, Usage()) + c.usage
        return out

    def usage_by_scene(self) -> dict[str, Usage]:
        """Tokens per :func:`cost_bucket` — scene ids, plus ``SEQ*``/``film`` for non-scene keys."""
        out: dict[str, Usage] = {}
        for c in self.calls():
            b = cost_bucket(c.key)
            out[b] = out.get(b, Usage()) + c.usage
        return dict(sorted(out.items(), key=lambda kv: natural_key(kv[0])))

    def usage_matrix(self) -> dict[str, dict[str, Usage]]:
        """Tokens per scene per stage — the CP-8 cost dashboard's grid."""
        out: dict[str, dict[str, Usage]] = {}
        for c in self.calls():
            row = out.setdefault(cost_bucket(c.key), {})
            row[c.stage] = row.get(c.stage, Usage()) + c.usage
        return dict(sorted(out.items(), key=lambda kv: natural_key(kv[0])))

    # --- stages ---------------------------------------------------------------
    def set_stage(self, stage: Any, status: str, note: str = "") -> StageRun:
        if status not in STAGE_STATUSES:
            raise ValueError(f"stage status must be one of {STAGE_STATUSES}, got {status!r}")
        name = _stage_name(stage)
        with self._session() as s:
            row = s.get(StageRun, name) or StageRun(stage=name)
            row.status = status
            row.note = note
            if status == "running":
                row.started_at = _now()
                row.finished_at = None
            elif status in ("done", "failed"):
                row.started_at = row.started_at or _now()
                row.finished_at = _now()
            else:
                row.started_at = None
                row.finished_at = None
            s.add(row)
            s.commit()
            s.refresh(row)
        return row

    def stage_status(self, stage: Any) -> str | None:
        with self._session() as s:
            row = s.get(StageRun, _stage_name(stage))
            return row.status if row else None

    def stage_runs(self) -> list[StageRun]:
        with self._session() as s:
            return list(s.exec(select(StageRun)).all())

    # --- artifacts ------------------------------------------------------------
    def save_artifact(self, stage: Any, key: str, instance: BaseModel) -> Artifact:
        name = _stage_name(stage)
        with self._session() as s:
            latest = s.exec(select(Artifact.version).where(Artifact.stage == name, Artifact.key == key).order_by(Artifact.version.desc())).first()
            row = Artifact(stage=name, key=key, version=(latest or 0) + 1, blob=instance.model_dump_json())
            s.add(row)
            s.commit()
            s.refresh(row)
        return row

    def artifact_versions(self, stage: Any, key: str) -> list[int]:
        with self._session() as s:
            return list(s.exec(select(Artifact.version).where(Artifact.stage == _stage_name(stage), Artifact.key == key).order_by(Artifact.version)).all())

    def load_artifact(self, stage: Any, key: str, model: type[M], version: int | None = None) -> M | None:
        stmt = select(Artifact).where(Artifact.stage == _stage_name(stage), Artifact.key == key)
        stmt = stmt.where(Artifact.version == version) if version is not None else stmt.order_by(Artifact.version.desc())
        with self._session() as s:
            row = s.exec(stmt).first()
        return model.model_validate_json(row.blob) if row else None

    def load_all(self, stage: Any, model: type[M], key_prefix: str | None = None) -> dict[str, M]:
        """Latest version per key (natural order); ``key_prefix`` narrows to e.g. ``"S3/"``."""
        stmt = select(Artifact).where(Artifact.stage == _stage_name(stage))
        if key_prefix:
            stmt = stmt.where(Artifact.key.startswith(key_prefix))
        with self._session() as s:
            rows = list(s.exec(stmt.order_by(Artifact.key, Artifact.version)).all())
        latest: dict[str, Artifact] = {}
        for r in rows:
            latest[r.key] = r
        return {k: model.model_validate_json(latest[k].blob) for k in sorted(latest, key=natural_key)}

    def artifact_keys(self, stage: Any) -> list[str]:
        with self._session() as s:
            keys = s.exec(select(Artifact.key).where(Artifact.stage == _stage_name(stage)).distinct()).all()
        return sorted(set(keys), key=natural_key)

    def scene_snapshot(self, scene_id: str) -> SceneOutputSnapshot:
        """Everything persisted for one scene: scene card, breakdown row, visions, plan, directives, audits, decision, hooks."""
        directives = [d for d in self.load_all(ARTIFACT_DIRECTIVE, DepartmentDirective, key_prefix=f"{scene_id}/").values() if d.scene_id == scene_id]
        audits = [b for b in self.load_all(ARTIFACT_AUDIT, AuditBundle).values() if audit_flags_for([b], scene_id)]
        with self._session() as s:
            hooks = list(s.exec(select(HookRow).where(HookRow.scene_id == scene_id).order_by(HookRow.id)).all())
        return SceneOutputSnapshot(
            scene_id=scene_id,
            scene=self.load_artifact(ARTIFACT_SCENE, scene_id, Scene),
            breakdown_row=self.load_artifact(ARTIFACT_BREAKDOWN_ROW, scene_id, BreakdownRow),
            visions={k.split("/", 1)[1]: v for k, v in self.load_all(ARTIFACT_VISION, SceneVision, key_prefix=f"{scene_id}/").items()},
            plan=self.load_artifact(ARTIFACT_PLAN, scene_id, IntegratedScenePlan),
            directives=directives,
            audits=audits,
            decision=self.latest_decision(scene_id),
            hooks=hooks,
        )

    # --- decisions & amendments -------------------------------------------------
    def log_decision(self, entry: DecisionLogEntry) -> int:
        """Persist the human's decision. A carried ``style_bible_amendment`` is filed as a pending
        :class:`AmendmentRow` (re-run ids from ``entry.rerun_scene_ids``) — do not add it again."""
        row = Decision(
            scene_id=entry.scene_id,
            chosen=entry.chosen,
            gate=entry.gate,
            human_note=entry.human_note,
            pushback_given=entry.pushback_given,
            has_amendment=entry.style_bible_amendment is not None,
            timestamp=_naive_utc(entry.timestamp),
            blob=entry.model_dump_json(),
        )
        with self._session() as s:
            s.add(row)
            s.commit()
            s.refresh(row)
            decision_id = int(row.id or 0)
        if entry.style_bible_amendment is not None:
            self.add_amendment(entry.style_bible_amendment, entry.rerun_scene_ids, decision_id=decision_id)
        return decision_id

    def decisions(self, scene_id: str | None = None) -> list[DecisionLogEntry]:
        stmt = select(Decision)
        if scene_id is not None:
            stmt = stmt.where(Decision.scene_id == scene_id)
        with self._session() as s:
            return [r.entry() for r in s.exec(stmt.order_by(Decision.id)).all()]

    def latest_decision(self, scene_id: str) -> DecisionLogEntry | None:
        with self._session() as s:
            row = s.exec(select(Decision).where(Decision.scene_id == scene_id).order_by(Decision.id.desc())).first()
        return row.entry() if row else None

    def approved_scene_ids(self) -> list[str]:
        """Scenes with a logged scene-gate decision, in the order they were approved."""
        seen: dict[str, None] = {}
        with self._session() as s:
            for sid in s.exec(select(Decision.scene_id).where(Decision.gate == "scene").order_by(Decision.id)).all():
                seen[sid] = None
        return list(seen)

    def add_amendment(self, amendment: Amendment, rerun_ids: list[str], *, decision_id: int | None = None) -> int:
        row = AmendmentRow(
            scene_id=amendment.scene_id,
            change=amendment.change,
            reason=amendment.reason,
            approved=amendment.approved,
            affected_scene_ids=_dump_ids(amendment.affected_scene_ids),
            rerun_scene_ids=_dump_ids(rerun_ids),
            decision_id=decision_id,
            approved_at=_now() if amendment.approved else None,
        )
        with self._session() as s:
            s.add(row)
            s.commit()
            s.refresh(row)
            return int(row.id or 0)

    def amendments(self, approved: bool | None = None) -> list[AmendmentRow]:
        stmt = select(AmendmentRow)
        if approved is not None:
            stmt = stmt.where(AmendmentRow.approved == approved)
        with self._session() as s:
            return list(s.exec(stmt.order_by(AmendmentRow.id)).all())

    def approve_amendment(self, amendment_id: int) -> AmendmentRow:
        with self._session() as s:
            row = s.get(AmendmentRow, amendment_id)
            if row is None:
                raise KeyError(f"no amendment with id {amendment_id}")
            row.approved = True
            row.approved_at = _now()
            s.add(row)
            s.commit()
            s.refresh(row)
        return row

    # --- cap ledger -------------------------------------------------------------
    def cap_ledger_save(self, ledger: CapLedger) -> None:
        with self._session() as s:
            s.exec(delete(CapSpendRow))
            for cap_key, spends in ledger.to_dict().items():
                for sp in spends:
                    s.add(CapSpendRow(cap_key=cap_key, device=sp["device"], scene_id=sp["scene_id"], setup_ref=sp["setup_ref"]))
            s.commit()

    def cap_ledger_load(self, caps: Caps) -> CapLedger:
        data: dict[str, list[dict[str, str]]] = {}
        with self._session() as s:
            for r in s.exec(select(CapSpendRow).order_by(CapSpendRow.id)).all():
                data.setdefault(r.cap_key, []).append({"scene_id": r.scene_id, "device": r.device, "setup_ref": r.setup_ref})
        return CapLedger.from_dict(caps, data)

    # --- commercial hooks ledger ------------------------------------------------
    def hooks_add(self, section: str, entry: HookEntry) -> int:
        """Add a hook from an approved scene. ``interval_block`` holds one entry: a new one replaces it."""
        if section not in HOOK_SECTIONS:
            raise ValueError(f"unknown hooks section {section!r}; expected one of {HOOK_SECTIONS}")
        with self._session() as s:
            if section == "interval_block":
                s.exec(delete(HookRow).where(HookRow.section == "interval_block"))
            row = HookRow(section=section, scene_id=entry.scene_id, description=entry.description, kind=entry.kind)
            s.add(row)
            s.commit()
            s.refresh(row)
            return int(row.id or 0)

    def hooks_release_scene(self, scene_id: str) -> int:
        """Withdraw a scene's hooks (when it is re-run); returns how many were removed."""
        with self._session() as s:
            rows = list(s.exec(select(HookRow).where(HookRow.scene_id == scene_id)).all())
            for r in rows:
                s.delete(r)
            s.commit()
        return len(rows)

    def hooks_ledger(self) -> CommercialHooksLedger:
        with self._session() as s:
            rows = list(s.exec(select(HookRow).order_by(HookRow.id)).all())
        ledger = CommercialHooksLedger()
        for r in rows:
            if r.section == "interval_block":
                ledger.interval_block = r.entry()
            else:
                getattr(ledger, r.section).append(r.entry())
        approved: dict[str, None] = {sid: None for sid in self.approved_scene_ids()}
        for r in rows:
            approved.setdefault(r.scene_id, None)
        ledger.approved_scene_ids = list(approved)
        return ledger

    # --- sequence approvals -----------------------------------------------------
    def approve_sequence(self, sequence_id: str, approved: bool = True, note: str = "") -> SequenceApproval:
        with self._session() as s:
            row = s.get(SequenceApproval, sequence_id) or SequenceApproval(sequence_id=sequence_id)
            row.approved = approved
            row.note = note
            row.updated_at = _now()
            s.add(row)
            s.commit()
            s.refresh(row)
        return row

    def sequence_approved(self, sequence_id: str) -> bool:
        with self._session() as s:
            row = s.get(SequenceApproval, sequence_id)
            return bool(row and row.approved)

    def sequence_approvals(self) -> list[SequenceApproval]:
        with self._session() as s:
            return list(s.exec(select(SequenceApproval)).all())


def _stage_name(stage: Any) -> str:
    return str(getattr(stage, "value", stage))
