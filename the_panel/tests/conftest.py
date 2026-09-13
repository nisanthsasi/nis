"""Shared fixtures — the test contract every module's tests build on.

* ``stub_env`` renders a minimal template for every registry key (so agent tests never
  depend on the real prompt text); ``real_env`` uses the shipped templates.
* ``offline_ctx`` is an AgentContext backed by FakeLLM + a temp SnapshotStore.
* ``make_*`` factories return valid schema instances with sensible overrides.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from the_panel.agents.base import AgentContext
from the_panel.config import PanelConfig, load_config
from the_panel.orchestrator.header import build_film_brief_header
from the_panel.prompts.registry import TEMPLATES, make_env
from the_panel.schemas import (
    Beat,
    Character,
    DayNight,
    DevicePermission,
    FilmBrief,
    Form,
    IntExt,
    IntegratedScenePlan,
    LensAffinity,
    LoadBearingBeat,
    PleasureMapEntry,
    PleasureType,
    Rasa,
    RasaPair,
    ReleaseTarget,
    Scene,
    SceneVision,
    SequenceEntry,
    SequencePlan,
    SequenceSceneEntry,
    SetPieceCandidate,
    SetPieceKind,
    Structure,
    Style,
    StyleBible,
    Turn,
)
from the_panel.store.snapshots import SnapshotStore
from the_panel.testing import FakeLLM, build_example

ROOT = Path(__file__).resolve().parent.parent
GOLDEN_DIR = ROOT / "tests" / "golden"


@pytest.fixture(scope="session")
def config() -> PanelConfig:
    return load_config(ROOT / "config.yaml")


@pytest.fixture(scope="session")
def stub_prompts_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    d = tmp_path_factory.mktemp("stub_prompts")
    for key, spec in TEMPLATES.items():
        lines = [f"STUB TEMPLATE {key}"]
        for var in spec.required + spec.optional:
            lines.append("{% if " + var + " is defined %}" + var + ": {{ " + var + " | tojson_pretty }}{% endif %}")
        (d / spec.file).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return d


@pytest.fixture
def stub_env(stub_prompts_dir: Path):
    return make_env(stub_prompts_dir)


@pytest.fixture
def real_env():
    return make_env()


@pytest.fixture
def fake_llm() -> FakeLLM:
    return FakeLLM()


@pytest.fixture
def offline_ctx(config: PanelConfig, stub_env, fake_llm: FakeLLM, tmp_path: Path) -> AgentContext:
    return AgentContext(config=config, client=fake_llm, env=stub_env, store=SnapshotStore(tmp_path / "snapshots"))


@pytest.fixture
def offline_ctx_real_templates(config: PanelConfig, real_env, fake_llm: FakeLLM, tmp_path: Path) -> AgentContext:
    return AgentContext(config=config, client=fake_llm, env=real_env, store=SnapshotStore(tmp_path / "snapshots"))


# ------------------------------------------------------------------ factories


def make_scene(scene_id: str = "S1", number: int = 1, *, beats: int = 4, **overrides: Any) -> Scene:
    base: dict[str, Any] = dict(
        id=scene_id,
        number=number,
        slug="INT. KOCHI FLAT - NIGHT",
        int_ext=IntExt.INT,
        day_night=DayNight.NIGHT,
        location="KOCHI FLAT",
        page_start=float(number),
        page_eighths=8,
        characters=["ANJU", "RAVI"],
        synopsis=f"Scene {scene_id}: Anju confronts Ravi about the money.",
        whose_scene="ANJU",
        objective="get Ravi to admit he took the money",
        obstacle="Ravi deflects with charm",
        tactics=["ask gently", "present evidence", "threaten to leave"],
        turn=Turn(entry_value="+", exit_value="-", value_named="trust"),
        story_function="Anju's trust breaks; without it the third act has no wound",
        beats=[Beat(n=i + 1, action=f"action {i + 1}", reaction=f"reaction {i + 1}", tactic_shift=(i == 1)) for i in range(beats)],
        rasa=RasaPair(primary=Rasa.KARUNA, secondary=Rasa.RAUDRA),
        emotional_temperature=6,
        tension_curve=[min(10, 3 + i * 2) for i in range(beats)],
        must_feel="the floor has gone from under Anju",
        pleasure_type=PleasureType.TEARS,
        energy_target=4,
        load_bearing=False,
        sequence_id="SEQ1",
        estimated_setups=5,
    )
    base.update(overrides)
    return Scene(**base)


def make_film_brief(**overrides: Any) -> FilmBrief:
    base: dict[str, Any] = dict(
        title="KAITHA",
        logline="A night-shift nurse must smuggle a dying witness across Kochi before dawn, or lose her brother to the men hunting him.",
        dramatic_question="Will Anju choose the truth over her family?",
        controlling_idea="Loyalty wins over safety when the cost is borne, not passed on.",
        load_bearing_beats=[LoadBearingBeat(name="inciting", scene_id="S1"), LoadBearingBeat(name="midpoint", scene_id="S3"), LoadBearingBeat(name="climax", scene_id="S5")],
        sequences=[SequenceEntry(sequence_id="SEQ1", scene_ids=["S1", "S2", "S3"], function="the smuggling begins", rhythm="accelerating", act="1"), SequenceEntry(sequence_id="SEQ2", scene_ids=["S4", "S5"], function="the price is paid", rhythm="releasing", act="3")],
        characters=[Character(name="ANJU", want="get through the night", need="stop carrying her brother", wound="their father's debt", lie="if I hold everything, nothing falls", thematic_answer="loyalty as burden"), Character(name="RAVI", want="the money", need="to be forgiven", wound="the same debt", lie="charm is enough", thematic_answer="loyalty as leverage", is_antagonist=True, antagonist_argument="love is a debt to be collected")],
        set_piece_candidates=[SetPieceCandidate(scene_id="S3", kind=SetPieceKind.ACTION, pleasure_type=PleasureType.THRILL, earning_beat="Anju's choice at the barrier", interval_candidate=True)],
        release_target=ReleaseTarget.BOTH,
        language_mix="Malayalam dialogue (colloquial, Kochi), English action lines",
    )
    base.update(overrides)
    return FilmBrief(**base)


def make_style_bible(posture: int = 5, *, approved: bool = True, **overrides: Any) -> StyleBible:
    base: dict[str, Any] = dict(
        version="1.0",
        approved_by="nisanth" if approved else "pending",
        form=Form(genre_contract="single-night noir that keeps its promise of thrill and colour", tone="austere-tender", narrative_stance="immersive", pov_strategy="Anju's eyes; we never know more than she does", audience_relationship="participant"),
        audience_promise=[PleasureType.THRILL, PleasureType.TEARS, PleasureType.DREAD],
        commercial_posture=posture,
        posture_defence="a single-take noir that still owes the audience thrill and colour",
        structure=Structure(time_organisation="linear", sequence_architecture="eight sequences, one night", ellipsis_policy="no ellipsis inside the night", where_it_breathes="SEQ2 opening"),
        pleasure_map=[PleasureMapEntry(sequence_id="SEQ1", pleasure_type=PleasureType.THRILL, set_piece_scene_id="S3"), PleasureMapEntry(sequence_id="SEQ2", pleasure_type=PleasureType.TEARS, set_piece_scene_id="S5")],
        style=Style(camera_grammar="oners with hybrid coverage on set-pieces", lens_policy="wide primes 18–35mm, close to the body", movement_policy="the camera moves with breath; never a decorative move", light_policy="practicals and sodium street light; contrast 8:1 to 16:1", editing_grammar="cut only when the body changes state", sound_philosophy="perspective follows Anju; silence is designed", music_philosophy="one motif, sparse; diegetic radio", bgm_policy="elevation permitted once, at the barrier", mise_en_scene_rules="depth staging; Kochi night texture", performance_style="realism, low tempo, Kochi colloquial register"),
        signature_devices=["the participant oner", "sound-led POV", "the doorway frame"],
        device_permissions=[DevicePermission(device="slow motion", must_pay_off="Anju's decision at the barrier"), DevicePermission(device="bgm elevation", must_pay_off="the barrier reversal")],
        refusals=["score under dialogue in Act 1", "coverage-by-default", "an interval block without a reversal"],
        lens_affinity=LensAffinity(primary=["inarritu", "ray_adoor", "malayalam_new_wave"], secondary=["bergman", "bong_joon_ho"]),
        digest="posture 5 hybrid; caps: elevation 3, slow-mo 3, needle drops 2; pleasure map SEQ1 thrill@S3, SEQ2 tears@S5",
    )
    base.update(overrides)
    return StyleBible(**base)


def make_sequence_plan(sequence_id: str = "SEQ1", scene_ids: tuple[str, ...] = ("S1", "S2", "S3"), **overrides: Any) -> SequencePlan:
    base: dict[str, Any] = dict(
        sequence_id=sequence_id,
        function="the smuggling begins",
        key_image="Anju's face lit by a passing sodium lamp, the witness slumped behind her",
        escalation_strategy="each scene removes one exit",
        scenes=[SequenceSceneEntry(scene_id=s, energy_target=3 + i * 2, pleasure_type=PleasureType.THRILL if i == len(scene_ids) - 1 else PleasureType.DREAD, set_piece=(i == len(scene_ids) - 1), asl_target_s=8.0 - i * 2) for i, s in enumerate(scene_ids)],
        oner_placement=scene_ids[-1],
        silence_placement=scene_ids[0],
        temperature_curve=[4, 6, 9][: len(scene_ids)],
    )
    base.update(overrides)
    return SequencePlan(**base)


def make_vision(lens: str = "kubrick", scene_id: str = "S1", **overrides: Any) -> SceneVision:
    v = build_example(SceneVision, {"lens": lens, "scene_id": scene_id, **overrides})
    return v


def make_plan(scene_id: str = "S1", **overrides: Any) -> IntegratedScenePlan:
    return build_example(IntegratedScenePlan, {"scene_id": scene_id, **overrides})


@pytest.fixture
def scene() -> Scene:
    return make_scene()


@pytest.fixture
def film_brief() -> FilmBrief:
    return make_film_brief()


@pytest.fixture
def style_bible() -> StyleBible:
    return make_style_bible()


@pytest.fixture
def sequence_plan() -> SequencePlan:
    return make_sequence_plan()


@pytest.fixture
def header(film_brief: FilmBrief, style_bible: StyleBible):
    return build_film_brief_header(film_brief, style_bible, frozen=True)


@pytest.fixture
def offline_ctx_with_header(offline_ctx: AgentContext, header) -> AgentContext:
    offline_ctx.header = header
    return offline_ctx
