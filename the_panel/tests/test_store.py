"""PanelDB: the SQLite mirror — calls & cost, stages, versioned artifacts, decisions, amendments,
cap ledger, hooks ledger, sequence approvals and the per-scene snapshot."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from the_panel.agents.base import AgentContext, AgentResult, BaseAgent
from the_panel.orchestrator.caps import CapLedger
from the_panel.orchestrator.stages import Stage
from the_panel.schemas import (
    Amendment,
    AuditBundle,
    Caps,
    CinematographyOutput,
    ContinuityIssue,
    ContinuityReport,
    DecisionLogEntry,
    Department,
    DepartmentDirective,
    DeviceFlag,
    DeviceVerdict,
    EarnedDeviceReport,
    EngagementGap,
    EngagementReport,
    FeasibilityReport,
    FeasibilityStatus,
    HookEntry,
    IntegratedScenePlan,
    RAG,
    Scene,
    SceneVision,
    Severity,
    Usage,
)
from the_panel.store import (
    ARTIFACT_AUDIT,
    ARTIFACT_DIRECTIVE,
    ARTIFACT_PLAN,
    ARTIFACT_SCENE,
    ARTIFACT_VISION,
    PanelDB,
    audit_flags_by_scene,
    cost_bucket,
    scene_of_key,
)
from the_panel.testing import build_example

from .conftest import make_plan, make_scene, make_vision


def _result(stage: str, key: str, out: int, inp: int = 100, *, agent: str | None = None, attempts: int = 1, over: bool = False) -> AgentResult:
    return AgentResult(
        stage=stage,
        agent=agent or stage,
        model="claude-opus-5",
        parsed=make_scene(),
        raw_text="{}",
        usage=Usage(input_tokens=inp, output_tokens=out, cache_read_input_tokens=50, cache_creation_input_tokens=5),
        attempts=attempts,
        budget=750,
        over_budget=over,
        key=key,
        snapshot_path=Path("/snap") / f"{key.replace('/', '_')}.v1.json",
    )


@pytest.fixture
def db() -> PanelDB:
    with PanelDB(":memory:") as d:
        yield d


# ------------------------------------------------------------------ keys & cost


@pytest.mark.parametrize("key,scene,bucket", [("S3", "S3", "S3"), ("S3/kubrick", "S3", "S3"), ("S3/dept_music", "S3", "S3"), ("S12A/critique/x", "S12A", "S12A"), ("SEQ1", None, "SEQ1"), ("SEQ1/rajamouli", None, "SEQ1"), ("film", None, "film")])
def test_scene_of_key_and_cost_bucket(key, scene, bucket):
    assert scene_of_key(key) == scene
    assert cost_bucket(key) == bucket


def test_record_call_and_usage_rollups(db: PanelDB):
    db.record_call(_result("lens", "S3/kubrick", 700))
    db.record_call(_result("lens", "S3/bergman", 650, attempts=2, over=True))
    db.record_call(_result("integrator", "S3", 1500))
    db.record_call(_result("department", "S3/dept_music", 800))
    db.record_call(_result("sequence_lens", "SEQ1/rajamouli", 400))
    db.record_call(_result("analyst_film", "film", 5000))
    row = db.record_call(_result("lens", "S10/kubrick", 100))
    assert row.id is not None and row.snapshot_path.endswith("S10_kubrick.v1.json") and row.model == "claude-opus-5"

    by_stage = db.usage_by_stage()
    assert by_stage["lens"].output_tokens == 1450 and by_stage["lens"].input_tokens == 300 and by_stage["lens"].cache_read_input_tokens == 150
    assert by_stage["integrator"].output_tokens == 1500

    by_scene = db.usage_by_scene()
    assert list(by_scene) == ["S3", "S10", "SEQ1", "film"]  # natural order, scenes before sequence/film buckets
    assert by_scene["S3"].output_tokens == 700 + 650 + 1500 + 800
    assert by_scene["SEQ1"].output_tokens == 400 and by_scene["film"].output_tokens == 5000

    matrix = db.usage_matrix()
    assert matrix["S3"]["lens"].output_tokens == 1350 and matrix["S3"]["department"].output_tokens == 800
    assert [c.key for c in db.calls(stage="lens")] == ["S3/kubrick", "S3/bergman", "S10/kubrick"]
    assert db.calls(key="S3")[0].stage == "integrator"
    over = [c for c in db.calls() if c.over_budget]
    assert len(over) == 1 and over[0].attempts == 2


class _Lens(BaseAgent[SceneVision]):
    stage = "lens"
    name = "kubrick"
    template = "P5_lens"
    output_model = SceneVision


async def test_record_call_from_a_real_agent_result(db: PanelDB, offline_ctx: AgentContext, scene, style_bible, sequence_plan):
    res = await _Lens(offline_ctx).run(key="S1/kubrick", lens_card={"name": "kubrick"}, scene=scene, sequence_plan=sequence_plan, scene_constraints={"scene_id": "S1"}, style_bible=style_bible)
    row = db.record_call(res)
    assert row.stage == "lens" and row.agent == "kubrick" and row.key == "S1/kubrick"
    assert row.output_tokens == res.usage.output_tokens and Path(row.snapshot_path) == res.snapshot_path
    assert row.created_at == res.created_at.astimezone(timezone.utc).replace(tzinfo=None)
    assert db.usage_by_scene()["S1"].output_tokens == res.usage.output_tokens


# ------------------------------------------------------------------ stages


def test_stage_runs_upsert_and_timestamps(db: PanelDB):
    assert db.stage_status("L2_understand") is None
    run = db.set_stage(Stage.L2_UNDERSTAND, "running")
    assert run.started_at is not None and run.finished_at is None and db.stage_status("L2_understand") == "running"
    done = db.set_stage("L2_understand", "done", note="42 scenes")
    assert done.finished_at is not None and done.note == "42 scenes" and done.started_at == run.started_at
    failed = db.set_stage("L5_scene_panel", "failed", note="over cap on S3")
    assert failed.started_at is not None and failed.finished_at is not None
    assert db.set_stage("L5_scene_panel", "pending").started_at is None
    assert {r.stage: r.status for r in db.stage_runs()} == {"L2_understand": "done", "L5_scene_panel": "pending"}
    with pytest.raises(ValueError):
        db.set_stage("L6_integrate", "half-done")


# ------------------------------------------------------------------ artifacts


def test_artifacts_are_versioned_and_latest_wins(db: PanelDB):
    s1 = make_scene("S1", must_feel="first pass")
    db.save_artifact(ARTIFACT_SCENE, "S1", s1)
    a2 = db.save_artifact(ARTIFACT_SCENE, "S1", make_scene("S1", must_feel="corrected by the human"))
    assert a2.version == 2 and db.artifact_versions(ARTIFACT_SCENE, "S1") == [1, 2]
    assert db.load_artifact(ARTIFACT_SCENE, "S1", Scene).must_feel == "corrected by the human"
    assert db.load_artifact(ARTIFACT_SCENE, "S1", Scene, version=1).must_feel == "first pass"
    assert db.load_artifact(ARTIFACT_SCENE, "S99", Scene) is None
    assert db.load_artifact(ARTIFACT_PLAN, "S1", IntegratedScenePlan) is None  # a different kind, same key


def test_load_all_returns_latest_per_key_in_natural_order(db: PanelDB):
    for sid in ("S10", "S2", "S1"):
        db.save_artifact(ARTIFACT_SCENE, sid, make_scene(sid, number=int(sid[1:])))
    db.save_artifact(ARTIFACT_SCENE, "S2", make_scene("S2", number=2, must_feel="v2"))
    all_scenes = db.load_all(ARTIFACT_SCENE, Scene)
    assert list(all_scenes) == ["S1", "S2", "S10"] and all_scenes["S2"].must_feel == "v2"
    assert db.artifact_keys(ARTIFACT_SCENE) == ["S1", "S2", "S10"]
    db.save_artifact(ARTIFACT_VISION, "S1/kubrick", make_vision("kubrick", "S1"))
    db.save_artifact(ARTIFACT_VISION, "S1/bergman", make_vision("bergman", "S1"))
    db.save_artifact(ARTIFACT_VISION, "S10/kubrick", make_vision("kubrick", "S10"))
    only_s1 = db.load_all(ARTIFACT_VISION, SceneVision, key_prefix="S1/")
    assert set(only_s1) == {"S1/kubrick", "S1/bergman"} and only_s1["S1/kubrick"].lens == "kubrick"
    assert db.save_artifact(Stage.L4_STYLE_BIBLE, "film", make_scene()).stage == "L4_style_bible"


# ------------------------------------------------------------------ decisions & amendments


def test_decisions_round_trip_and_amendments_file_pending(db: PanelDB):
    plain = DecisionLogEntry(scene_id="S1", chosen="A", human_note="keep the doorway", overrides=["no crane"], pushback_given=True, pushback_reason="the crane is the Style Bible's one move")
    amended = DecisionLogEntry(
        scene_id="S3",
        chosen="custom",
        custom_text="hold the wide for the whole beat",
        style_bible_amendment=Amendment(scene_id="S3", change="allow one needle drop in Act 1", reason="the radio is a character", affected_scene_ids=["S2", "S4"]),
        rerun_scene_ids=["S2", "S4"],
        timestamp=datetime(2026, 9, 13, 10, 0, tzinfo=timezone.utc),
    )
    db.log_decision(plain)
    db.log_decision(amended)
    db.log_decision(DecisionLogEntry(scene_id="S1", chosen="B", human_note="changed my mind"))
    db.log_decision(DecisionLogEntry(scene_id="film", chosen="A", gate="style_bible"))

    assert [d.chosen for d in db.decisions("S1")] == ["A", "B"]
    assert db.latest_decision("S1").human_note == "changed my mind"
    assert db.decisions("S3") == [amended]  # timestamp, amendment and overrides survive the blob
    assert len(db.decisions()) == 4 and db.approved_scene_ids() == ["S1", "S3"]  # scene gate only, in approval order

    pending = db.amendments(approved=False)
    assert len(pending) == 1 and pending[0].rerun_ids == ["S2", "S4"] and pending[0].affected_ids == ["S2", "S4"]
    assert pending[0].to_amendment() == amended.style_bible_amendment and pending[0].decision_id == 2
    assert db.amendments(approved=True) == []
    row = db.approve_amendment(pending[0].id)
    assert row.approved and row.approved_at is not None
    assert [a.id for a in db.amendments(approved=True)] == [row.id] and db.amendments(approved=False) == []
    assert len(db.amendments()) == 1
    with pytest.raises(KeyError):
        db.approve_amendment(999)

    aid = db.add_amendment(Amendment(scene_id=None, change="posture 5 → 6", reason="the interval demands it", approved=True), rerun_ids=["S3"])
    assert db.amendments(approved=True)[-1].id == aid and db.amendments(approved=True)[-1].rerun_ids == ["S3"]


# ------------------------------------------------------------------ cap ledger


def test_cap_ledger_persists_and_reload_keeps_cap_discipline(db: PanelDB):
    caps = Caps(elevation_cues=1, slow_motion=2, needle_drops=0)
    ledger = CapLedger(caps)
    ledger.spend("bgm elevation", "S3", "beat 4")
    ledger.spend("slow motion", "S3", "beat 2")
    db.cap_ledger_save(ledger)
    db.cap_ledger_save(ledger)  # idempotent: a re-save replaces, never duplicates
    loaded = db.cap_ledger_load(caps)
    assert loaded.to_dict() == ledger.to_dict()
    assert loaded.position("bgm elevation") == "1 of 1" and loaded.would_exceed("bgm elevation")
    assert loaded.remaining("slow motion") == 1 and loaded.would_exceed("needle drop")
    loaded.release_scene("S3")
    db.cap_ledger_save(loaded)
    assert db.cap_ledger_load(caps).used("bgm elevation") == 0


# ------------------------------------------------------------------ hooks ledger


def test_hooks_ledger_accumulates_by_section(db: PanelDB):
    db.log_decision(DecisionLogEntry(scene_id="S3", chosen="A"))
    db.hooks_add("trailer_shots", HookEntry(scene_id="S3", description="the barrier oner", kind="oner"))
    db.hooks_add("poster_frames", HookEntry(scene_id="S3", description="Anju under the sodium lamp"))
    db.hooks_add("interval_block", HookEntry(scene_id="S2", description="first candidate"))
    db.hooks_add("interval_block", HookEntry(scene_id="S3", description="the barrier reversal", kind="reversal"))
    db.hooks_add("bgm_hooks", HookEntry(scene_id="S5", description="the theme's first full statement"))
    with pytest.raises(ValueError):
        db.hooks_add("memes", HookEntry(scene_id="S3", description="x"))

    ledger = db.hooks_ledger()
    assert [h.description for h in ledger.trailer_shots] == ["the barrier oner"] and ledger.trailer_shots[0].kind == "oner"
    assert ledger.interval_block.scene_id == "S3" and ledger.interval_block.kind == "reversal"  # one interval block, latest wins
    assert ledger.poster_frames[0].scene_id == "S3" and ledger.song_slots == []
    assert ledger.approved_scene_ids == ["S3", "S5"]  # decisions first, then hook-only scenes

    assert db.hooks_release_scene("S3") == 3
    after = db.hooks_ledger()
    assert after.trailer_shots == [] and after.interval_block is None and after.bgm_hooks[0].scene_id == "S5"
    assert db.scene_snapshot("S5").hooks[0].section == "bgm_hooks"


# ------------------------------------------------------------------ sequence approvals


def test_sequence_approval_gate(db: PanelDB):
    assert not db.sequence_approved("SEQ1")
    db.approve_sequence("SEQ1", note="energy curve accepted")
    assert db.sequence_approved("SEQ1")
    db.approve_sequence("SEQ1", approved=False, note="set-piece moved to S4")
    assert not db.sequence_approved("SEQ1") and db.sequence_approvals()[0].note == "set-piece moved to S4"


# ------------------------------------------------------------------ scene snapshot


def _bundle() -> AuditBundle:
    return AuditBundle(
        continuity=ContinuityReport(issues=[ContinuityIssue(scene_id="S1", severity=Severity.BLOCK, issue="eyeline crosses the line", fix="flip the OTS"), ContinuityIssue(scene_id="S2", severity=Severity.NOTE, issue="motif repeats", fix="drop one")]),
        feasibility=FeasibilityReport(statuses=[FeasibilityStatus(scene_id="S1", rag=RAG.AMBER, issues=["7 setups in a 5-setup day"]), FeasibilityStatus(scene_id="S2", rag=RAG.GREEN)]),
        earned_device=EarnedDeviceReport(flags=[DeviceFlag(scene_id="S1", device="slow motion", verdict=DeviceVerdict.UNEARNED, alternative="hold the wide"), DeviceFlag(scene_id="S1", device="bgm elevation", verdict=DeviceVerdict.EARNED)]),
        engagement=EngagementReport(gaps=[EngagementGap(kind="pleasure_gap", scene_ids=["S1", "S2"], detail="12 minutes without a delivered pleasure", fix="move the laugh to S2")]),
    )


def test_audit_flags_by_scene_flattens_only_findings():
    flags = audit_flags_by_scene([_bundle()])
    assert set(flags) == {"S1", "S2"}
    assert flags["S1"] == [
        "continuity BLOCK: eyeline crosses the line → flip the OTS",
        "feasibility AMBER: 7 setups in a 5-setup day",
        "device UNEARNED: slow motion → hold the wide",
        "engagement pleasure_gap: 12 minutes without a delivered pleasure → move the laugh to S2",
    ]
    assert flags["S2"] == ["continuity NOTE: motif repeats → drop one", "engagement pleasure_gap: 12 minutes without a delivered pleasure → move the laugh to S2"]


def test_scene_snapshot_gathers_everything_for_one_scene(db: PanelDB):
    plan = make_plan("S1")
    db.save_artifact(ARTIFACT_SCENE, "S1", make_scene("S1"))
    db.save_artifact(ARTIFACT_PLAN, "S1", plan)
    db.save_artifact(ARTIFACT_PLAN, "S1", make_plan("S1", governing_idea="the second integration"))
    db.save_artifact(ARTIFACT_VISION, "S1/kubrick", make_vision("kubrick", "S1"))
    db.save_artifact(ARTIFACT_VISION, "S10/kubrick", make_vision("kubrick", "S10"))
    cine = DepartmentDirective.from_output(Department.CINEMATOGRAPHY, "S1", plan.governing_idea, plan.pleasure_beat, build_example(CinematographyOutput))
    db.save_artifact(ARTIFACT_DIRECTIVE, "S1/cinematography", cine)
    db.save_artifact(ARTIFACT_DIRECTIVE, "S10/cinematography", cine.model_copy(update={"scene_id": "S10"}))
    db.save_artifact(ARTIFACT_AUDIT, "SEQ1", _bundle())
    db.save_artifact(ARTIFACT_AUDIT, "SEQ2", AuditBundle())
    db.log_decision(DecisionLogEntry(scene_id="S1", chosen="B"))
    db.hooks_add("trailer_shots", HookEntry(scene_id="S1", description="the doorway"))

    snap = db.scene_snapshot("S1")
    assert snap.scene.id == "S1" and snap.plan.governing_idea == "the second integration"
    assert list(snap.visions) == ["kubrick"] and snap.visions["kubrick"].scene_id == "S1"
    assert [d.dept for d in snap.directives] == [Department.CINEMATOGRAPHY] and snap.directives[0].scene_id == "S1"
    assert len(snap.audits) == 1 and snap.audit_flags[0].startswith("continuity BLOCK")
    assert snap.option_chosen == "B" and snap.is_reviewed and snap.hooks[0].description == "the doorway"
    assert snap.breakdown_row is None

    empty = db.scene_snapshot("S2")
    assert empty.scene is None and empty.plan is None and empty.directives == [] and not empty.is_reviewed
    assert empty.audit_flags == ["continuity NOTE: motif repeats → drop one", "engagement pleasure_gap: 12 minutes without a delivered pleasure → move the laugh to S2"]


# ------------------------------------------------------------------ file-backed


def test_file_backed_db_survives_reopen(tmp_path: Path):
    path = tmp_path / ".panel" / "state.sqlite"
    with PanelDB(path) as db:
        db.set_stage("L1_parse", "done")
        db.save_artifact(ARTIFACT_SCENE, "S1", make_scene("S1"))
        db.record_call(_result("parser", "film", 3000))
    assert path.exists()
    with PanelDB(path) as db:
        assert db.stage_status("L1_parse") == "done"
        assert db.load_artifact(ARTIFACT_SCENE, "S1", Scene).id == "S1"
        assert db.usage_by_stage()["parser"].output_tokens == 3000
