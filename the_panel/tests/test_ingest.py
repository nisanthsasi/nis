"""CP-2 ingest & parse tests: golden round-trips, canonicalisation, verbatim dialogue, children, registers, ParserAgent."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from the_panel.agents.base import AgentContext, ValidationRejected
from the_panel.agents.parser import ParserAgent
from the_panel.ingest import (
    LocationAliasTable,
    detect_format,
    detect_register,
    detect_script,
    ingest_file,
    ingest_text,
    page_marker,
    read_document,
    refine,
)
from the_panel.ingest.document import RawDocument
from the_panel.ingest.fdx import read_fdx
from the_panel.ingest.normalise import CharacterRoster, capitalised_items, location_key, parse_slug, split_cue
from the_panel.schemas import DayNight, IntExt, LocationAlias, ParsedScript, Register, SceneSkeleton
from the_panel.testing import FakeLLM

from .conftest import GOLDEN_DIR

ANNOTATIONS = json.loads((GOLDEN_DIR / "annotations.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def kaitha() -> ParsedScript:
    return ingest_file(GOLDEN_DIR / ANNOTATIONS["kaitha_pilot"]["file"])


@pytest.fixture(scope="module")
def veri() -> ParsedScript:
    return ingest_file(GOLDEN_DIR / ANNOTATIONS["veri_scenes"]["file"])


@pytest.fixture(scope="module")
def ardha() -> ParsedScript:
    return ingest_file(GOLDEN_DIR / ANNOTATIONS["ardha_song"]["file"])


def _scene(parsed: ParsedScript, scene_id: str) -> SceneSkeleton:
    return next(s for s in parsed.scenes if s.id == scene_id)


def _check_registers(parsed: ParsedScript, expected: list[dict]) -> None:
    for e in expected:
        block = _scene(parsed, e["scene"]).dialogue_blocks[e["block"]]
        assert block.character == e["character"], e
        assert detect_script(block.text) == e["script"], e
        assert block.dialogue_register == Register(e["register"]), e
        assert block.region == e["region"], e


# ------------------------------------------------------------------ golden round-trips


@pytest.mark.parametrize("key", ["kaitha_pilot", "veri_scenes", "ardha_song"])
def test_golden_round_trip_is_schema_valid_and_sequential(key: str):
    ann = ANNOTATIONS[key]
    parsed = ingest_file(GOLDEN_DIR / ann["file"])
    assert parsed.source_format == ann["source_format"]
    assert len(parsed.scenes) == ann["scene_count"]
    assert [s.id for s in parsed.scenes] == [f"S{i}" for i in range(1, ann["scene_count"] + 1)]
    assert [s.number for s in parsed.scenes] == list(range(1, ann["scene_count"] + 1))
    ParsedScript.model_validate(parsed.model_dump(mode="json"))
    for s in parsed.scenes:
        assert s.line_start is not None and s.line_end is not None and s.line_start <= s.line_end
        assert s.page_eighths >= 1 and s.page_start >= 1
    for a, b in zip(parsed.scenes, parsed.scenes[1:]):
        assert a.line_end < b.line_start and a.page_start <= b.page_start
    for sid, loc in ann["canonical_locations"].items():
        assert _scene(parsed, sid).location_canonical == loc
    ParserAgent(AgentContext.offline()).check(parsed, {"raw_text": read_document(GOLDEN_DIR / ann["file"]).text})


def test_kaitha_structure_matches_annotations(kaitha: ParsedScript):
    ann = ANNOTATIONS["kaitha_pilot"]
    for sid, ie in ann["int_ext"].items():
        assert _scene(kaitha, sid).int_ext == IntExt(ie)
    for sid, dn in ann["day_night"].items():
        assert _scene(kaitha, sid).day_night == DayNight(dn)
    for sid, chars in ann["characters_by_scene"].items():
        assert _scene(kaitha, sid).characters == chars
    speaking = {b.character for s in kaitha.scenes for b in s.dialogue_blocks}
    assert speaking == set(ann["characters"])
    for sid in ann["night_exteriors"]:
        s = _scene(kaitha, sid)
        assert s.int_ext in (IntExt.EXT, IntExt.INT_EXT) and s.day_night == DayNight.NIGHT
    assert _scene(kaitha, ann["crowd_scene"]).capitalised_items[0] == "CROWD"
    assert _scene(kaitha, "S9").transitions == ["FADE OUT."]
    assert kaitha.total_pages > 3


def test_kaitha_set_piece_prop_is_planted_and_paid_off_as_capitalised_item(kaitha: ParsedScript):
    ann = ANNOTATIONS["kaitha_pilot"]
    prop = ann["set_piece_prop"]
    assert prop in _scene(kaitha, ann["prop_planted_in"]).capitalised_items
    assert prop in _scene(kaitha, ann["prop_pays_off_in"]).capitalised_items
    assert prop in _scene(kaitha, ann["crowd_scene"]).capitalised_items  # inside the series-of-shots child
    for s in kaitha.scenes:  # markers are markup, never candidate items
        assert not any(item in ("SERIES OF SHOTS", "INTERCUT", "SONG", "MONTAGE TO MUSIC") for item in s.capitalised_items)


# ------------------------------------------------------------------ slugs & locations


def test_slug_canonicalisation_merges_deliberate_variants(kaitha: ParsedScript):
    ann = ANNOTATIONS["kaitha_pilot"]
    for canonical, variants in ann["location_variants"].items():
        scenes = [s for s in kaitha.scenes if s.location_canonical == canonical]
        assert {s.location_raw for s in scenes} == set(variants)
        assert len(scenes) == len(variants)
    aliases = {a.alias: a.canonical for a in kaitha.location_aliases}
    assert aliases == {"VYPEEN JETTY": "VYPIN JETTY", "APARTMENT, KOCHI": "KOCHI FLAT"}
    assert _scene(kaitha, "S9").slug == "INT. KOCHI FLAT - DAWN"  # hygiene: stray period gone, raw kept
    assert _scene(kaitha, "S9").location_raw == "KOCHI FLAT."
    assert _scene(kaitha, "S6").location_canonical == "AMBULANCE / KOCHI FLAT"  # a sub-location stays distinct


def test_parse_warnings_flag_inconsistent_slugs(kaitha: ParsedScript):
    script_flags = [w for w in kaitha.parse_warnings if w.startswith("inconsistent slug")]
    assert any("'APARTMENT, KOCHI'" in w and "'KOCHI FLAT'" in w for w in script_flags)
    assert any("'VYPEEN JETTY'" in w and "'VYPIN JETTY'" in w for w in script_flags)
    assert any(w.startswith("inconsistent slug") and "APARTMENT, KOCHI" in w for w in _scene(kaitha, "S4").parse_warnings)
    assert any("stray trailing punctuation" in w for w in _scene(kaitha, "S9").parse_warnings)
    assert not any(w.startswith("inconsistent slug") for w in _scene(kaitha, "S7").parse_warnings)
    assert any("55 lines/page" in w for w in kaitha.parse_warnings)


def test_location_alias_table_heuristics_and_explicit_aliases():
    t = LocationAliasTable()
    assert t.canonical("Kochi Flat") == "KOCHI FLAT"
    assert t.canonical("KOCHI FLAT.") == "KOCHI FLAT"
    assert t.canonical("Apartment, Kochi - NIGHT") == "KOCHI FLAT"
    assert t.canonical("KOCHI APT.") == "KOCHI FLAT"
    assert t.canonical("ANJU'S FLAT") != "KOCHI FLAT"
    assert t.canonical("ANJUS FLAT") == t.canonical("ANJU'S FLAT")
    assert t.canonical("THE KOCHI FLAT - KITCHEN") != "KOCHI FLAT"
    assert location_key("Vypin Jetty") == location_key("VYPEEN JETTY")
    assert location_key("POLICE STATION") == location_key("PS")
    explicit = LocationAliasTable([("KOCHI FLAT", "APARTMENT, KOCHI")])
    assert explicit.canonical("kochi flat") == "APARTMENT, KOCHI"
    assert explicit.canonical("APARTMENT, KOCHI") == "APARTMENT, KOCHI"
    assert {(a.alias, a.canonical) for a in explicit.aliases()} == {("KOCHI FLAT", "APARTMENT, KOCHI")}
    frequent = LocationAliasTable()
    for raw in ("VYPEEN JETTY", "VYPIN JETTY", "VYPEEN JETTY"):
        frequent.observe(raw)
    assert frequent.canonical("VYPIN JETTY") == "VYPEEN JETTY"  # most frequent spelling wins


@pytest.mark.parametrize(
    "line,int_ext,location,day_night",
    [
        ("INT. KOCHI FLAT - NIGHT", IntExt.INT, "KOCHI FLAT", DayNight.NIGHT),
        ("ext. vypin jetty - dawn", IntExt.EXT, "vypin jetty", DayNight.DAWN),
        ("INT./EXT. AMBULANCE / KOCHI FLAT - NIGHT - CONTINUOUS", IntExt.INT_EXT, "AMBULANCE / KOCHI FLAT", DayNight.NIGHT),
        ("I/E. JEEP - MOVING - DAY", IntExt.INT_EXT, "JEEP - MOVING", DayNight.DAY),
        ("12 EXT. BEACH - SUNSET 12", IntExt.EXT, "BEACH", DayNight.DUSK),
        ("INT. STATION - LATER #4A#", IntExt.INT, "STATION", DayNight.LATER),
        ("INT KOCHI FLAT NIGHT", IntExt.INT, "KOCHI FLAT", DayNight.NIGHT),
        ("EXT. കൊച്ചി കായൽ - NIGHT", IntExt.EXT, "കൊച്ചി കായൽ", DayNight.NIGHT),
    ],
)
def test_parse_slug_variants(line, int_ext, location, day_night):
    slug = parse_slug(line)
    assert slug.int_ext == int_ext and slug.location_raw == location and slug.day_night == day_night


def test_script_scene_numbers_are_reported_not_trusted():
    parsed = ingest_text("INT. A - DAY #4A#\n\nx.\n\n12 EXT. B - NIGHT 12\n\ny.\n", "fountain")
    assert [s.id for s in parsed.scenes] == ["S1", "S2"] and [s.slug for s in parsed.scenes] == ["INT. A - DAY", "EXT. B - NIGHT"]
    assert any("'4A'" in w and "S1" in w for w in parsed.scenes[0].parse_warnings)
    assert any("'12'" in w and "S2" in w for w in parsed.scenes[1].parse_warnings)


def test_p1_template_renders_rule_based_parse(real_env, kaitha: ParsedScript):
    from the_panel.prompts.registry import render

    text = render("P1_parse", real_env, raw_text="--- PAGE 1 ---\nINT. A - DAY", format_hint="fountain", location_aliases=[a.model_dump() for a in kaitha.location_aliases], rule_based_parse=kaitha.model_dump(mode="json"))
    assert "RULE-BASED PARSE" in text and "byte-for-byte" in text and '"VYPEEN JETTY"' in text and "ചേട്ടാ, ഞാൻ ജെട്ടിയിൽ ഉണ്ട്." in text
    assert "RULE-BASED PARSE" not in render("P1_parse", real_env, raw_text="INT. A - DAY")


def test_slug_without_time_and_forced_slug_warn():
    slug = parse_slug("INT. KOCHI FLAT")
    assert slug.day_night == DayNight.UNKNOWN and any("missing time of day" in w for w in slug.warnings)
    forced = parse_slug(".THE RIVER - NIGHT")
    assert forced.int_ext is None and forced.location_raw == "THE RIVER" and any("forced" in w for w in forced.warnings)
    parsed = ingest_text("INT. KOCHI FLAT\n\nAnju waits.\n", "fountain")
    assert parsed.scenes[0].day_night == DayNight.UNKNOWN
    assert any("missing time of day: S1" in w for w in parsed.parse_warnings)


def test_malayalam_slug_and_names_survive_untouched():
    text = "EXT. കൊച്ചി കായൽ - NIGHT\n\nBoats. A LANTERN.\n\nഅമ്മച്ചി\nവാതിൽ കുറ്റിയിട്.\n"
    parsed = ingest_text(text, "fountain")
    s = parsed.scenes[0]
    assert s.location_raw == "കൊച്ചി കായൽ" and s.location_canonical == "കൊച്ചി കായൽ" and s.slug == "EXT. കൊച്ചി കായൽ - NIGHT"
    assert s.characters == ["അമ്മച്ചി"] and s.dialogue_blocks[0].text == "വാതിൽ കുറ്റിയിട്."


# ------------------------------------------------------------------ characters & dialogue


def test_character_canonicalisation_strips_vo_and_merges_spellings(kaitha: ParsedScript):
    ann = ANNOTATIONS["kaitha_pilot"]
    for e in ann["vo_os"]:
        blocks = [b for b in _scene(kaitha, e["scene"]).dialogue_blocks if b.character == e["character"] and b.vo_os]
        assert blocks and blocks[0].vo_os == e["vo_os"]
    assert not any("(" in b.character or "V.O." in b.character or "CONT" in b.character for s in kaitha.scenes for b in s.dialogue_blocks)
    assert {(a.alias, a.canonical) for a in kaitha.character_aliases} == set(ann["character_aliases"].items())
    s4 = _scene(kaitha, "S4")
    assert s4.dialogue_blocks[-1].character == "SHIBU" and s4.dialogue_blocks[-1].parenthetical == "at the door, to Anju"
    assert any("SHIBOO" in w and "SHIBU" in w for w in kaitha.parse_warnings)
    assert split_cue("ANJU (V.O.) (CONT'D)") == ("ANJU", "V.O.", None)
    assert split_cue("RAVI (O.S.)") == ("RAVI", "O.S.", None)
    assert split_cue("KUNJUMON (O.C.) (ON PHONE)") == ("KUNJUMON", "O.C./V.O.", None)
    assert split_cue("@Anju (into phone)") == ("Anju", "V.O.", None)
    assert split_cue("ANJU (sobbing)^") == ("ANJU", None, "sobbing")
    roster = CharacterRoster()
    for raw in ("Ravi", "RAVI", "RAVEE"):
        roster.observe(raw)
    assert roster.canonical("ravee") == "RAVI"
    assert {(a.alias, a.canonical) for a in roster.aliases()} == {("RAVEE", "RAVI")}


def test_dialogue_is_verbatim_malayalam_bytes_preserved(kaitha: ParsedScript, veri: ParsedScript, ardha: ParsedScript):
    source = (GOLDEN_DIR / "kaitha_pilot.fountain").read_bytes()
    for key, parsed in (("kaitha_pilot", kaitha), ("veri_scenes", veri), ("ardha_song", ardha)):
        for sid, lines in ANNOTATIONS[key]["verbatim_dialogue"].items():
            texts = [b.text for b in _scene(parsed, sid).dialogue_blocks]
            for line in lines:
                assert line in texts
    for s in kaitha.scenes:
        for b in s.dialogue_blocks:
            assert b.text.encode("utf-8") in source
    ml = ANNOTATIONS["veri_scenes"]["multiline_dialogue"]
    assert _scene(veri, ml["scene"]).dialogue_blocks[ml["block"]].text == "\n".join(ml["lines"])
    par = ANNOTATIONS["veri_scenes"]["parenthetical"]
    assert _scene(veri, par["scene"]).dialogue_blocks[par["block"]].parenthetical == par["value"]
    assert _scene(kaitha, "S1").dialogue_blocks[0].parenthetical == "low"
    assert _scene(kaitha, "S1").dialogue_blocks[0].line_ref == 19


# ------------------------------------------------------------------ children & pages


def test_song_candidates_and_montage_children(kaitha: ParsedScript, ardha: ParsedScript):
    for key, parsed in (("kaitha_pilot", kaitha), ("ardha_song", ardha)):
        ann = ANNOTATIONS[key]
        for sid, n in ann["song_candidates"].items():
            assert len(_scene(parsed, sid).song_candidates) == n
            assert len(_scene(parsed, sid).song_candidates[0].lyrics) == ann["song_lyric_count"][sid]
        for sid, kind in ann["montage_children"].items():
            kinds = [m.kind for m in _scene(parsed, sid).montage_children]
            assert kinds == [kind]
    assert sum(len(s.montage_children) for s in kaitha.scenes) == ANNOTATIONS["kaitha_pilot"]["montage_children_total"]
    assert sum(len(s.song_candidates) for s in kaitha.scenes) == ANNOTATIONS["kaitha_pilot"]["song_candidates_total"]
    series = _scene(kaitha, "S5").montage_children[0]
    assert series.lines[0].startswith("SERIES OF SHOTS") and len(series.lines) == 5 and "BACK TO SCENE" not in series.lines
    assert _scene(kaitha, "S6").montage_children[0].lines == ["INTERCUT - ANJU DRIVING / AMMACHI AT THE FLAT"]
    assert _scene(kaitha, "S6").dialogue_blocks  # dialogue after an INTERCUT header still parses
    song = _scene(ardha, "S1").song_candidates[0]
    assert ANNOTATIONS["ardha_song"]["song_marker_contains"] in song.marker
    for lyric in ANNOTATIONS["ardha_song"]["lyrics_verbatim"]:
        assert lyric in song.lyrics
    tilde = ingest_text("INT. ROOM - DAY\n\nShe sings.\n\n~Raavu theernnu\n~Poovu veenu\n\n~Nee varum\n\nShe stops.\n", "fountain")
    (candidate,) = tilde.scenes[0].song_candidates
    assert candidate.lyrics == ["Raavu theernnu", "Poovu veenu", "Nee varum"] and tilde.scenes[0].action_lines == ["She sings.", "She stops."]


def test_page_eighths_and_page_start(kaitha: ParsedScript, veri: ParsedScript, ardha: ParsedScript):
    for s in kaitha.scenes:
        assert 1 <= s.page_eighths <= 8
    assert _scene(kaitha, "S3").page_eighths >= 5  # the long load-bearing scene
    assert _scene(kaitha, "S2").page_eighths <= 3
    assert sum(s.page_eighths for s in kaitha.scenes) / 8 == pytest.approx(kaitha.total_pages, abs=1.0)
    ann = ANNOTATIONS["veri_scenes"]
    assert veri.total_pages == ann["total_pages"]
    for sid, page in ann["page_of_scene"].items():
        assert int(_scene(veri, sid).page_start) == page
    assert _scene(veri, "S3").page_start == 2.0
    assert ardha.total_pages == ANNOTATIONS["ardha_song"]["total_pages"]
    assert int(_scene(ardha, "S2").page_start) == 2
    assert not any("55 lines/page" in w for w in veri.parse_warnings)
    marked = ingest_text("--- PAGE 1 ---\nINT. A - DAY\n\nx.\n--- PAGE 2 ---\n\nINT. B - DAY\n\ny.\n\x0cINT. C - NIGHT\n\nz.\n", "fountain")
    assert [int(s.page_start) for s in marked.scenes] == [1, 2, 3] and marked.total_pages == 3.0
    assert marked.scenes[2].page_start == 3.0  # the form-feed line is the first line of page 3
    assert not any("55 lines/page" in w for w in marked.parse_warnings)
    fountain_break = ingest_text("INT. A - DAY\n\nx.\n\n===\n\nINT. B - DAY\n\ny.\n", "fountain")
    assert [int(s.page_start) for s in fountain_break.scenes] == [1, 2]


def test_pdf_reader_keeps_real_pages_and_drops_furniture(veri: ParsedScript):
    ann = ANNOTATIONS["veri_scenes"]
    doc = read_document(GOLDEN_DIR / ann["file"])
    assert doc.page_count == 2 and len(doc.page_breaks) == 1
    marked = doc.text_with_markers()
    assert page_marker(1) in marked and page_marker(2) in marked
    for junk in ann["furniture_never_parsed"]:
        assert junk not in doc.lines
    for s in veri.scenes:
        assert not any(a in ann["furniture_never_parsed"] for a in s.action_lines)
    assert veri.scenes[0].characters == ["VELU"]
    assert ann["set_piece_prop"] in veri.scenes[0].capitalised_items
    assert "CROWD" in veri.scenes[0].capitalised_items
    assert veri.scenes[2].transitions == ["FADE OUT."]
    for sid, dn in ann["day_night"].items():
        assert _scene(veri, sid).day_night == DayNight(dn)
    assert {b.character for s in veri.scenes for b in s.dialogue_blocks} == set(ann["characters"])
    assert any("before the first slugline" in w for w in veri.parse_warnings)
    _check_registers(veri, ann["registers"])


def test_docx_reader_bilingual_with_song_block(ardha: ParsedScript):
    ann = ANNOTATIONS["ardha_song"]
    assert {b.character for s in ardha.scenes for b in s.dialogue_blocks} == set(ann["characters"])
    for e in ann["vo_os"]:
        assert any(b.character == e["character"] and b.vo_os == e["vo_os"] for b in _scene(ardha, e["scene"]).dialogue_blocks)
    _check_registers(ardha, ann["registers"])
    s2 = _scene(ardha, "S2")
    assert s2.dialogue_blocks[1].parenthetical == "smiling" and s2.dialogue_blocks[1].text == "Amma, innu vayaru niranju."


def test_styled_docx_uses_paragraph_styles(tmp_path: Path):
    from docx import Document
    from docx.enum.style import WD_STYLE_TYPE

    document = Document()
    for name in ("Scene Heading", "Action", "Character", "Parenthetical", "Dialogue", "Transition"):
        document.styles.add_style(name, WD_STYLE_TYPE.PARAGRAPH)
    for style, text in (
        ("Scene Heading", "KOCHI FLAT - NIGHT"),
        ("Action", "Anju waits by the PHONE."),
        ("Character", "ANJU (V.O.)"),
        ("Parenthetical", "low"),
        ("Dialogue", "ഞാൻ ഇവിടെ ഉണ്ട്."),
        ("Character", "RAVI"),
        ("Dialogue", "Ippo varaam."),
        ("Transition", "CUT TO:"),
        ("Scene Heading", "EXT. JETTY - DAWN"),
        ("Action", "The ferry."),
    ):
        document.add_paragraph(text, style=style)
    path = tmp_path / "styled.docx"
    document.save(str(path))
    parsed = ingest_file(path)
    assert len(parsed.scenes) == 2
    s1 = parsed.scenes[0]
    assert s1.int_ext == IntExt.INT and s1.location_raw == "KOCHI FLAT" and any("forced" in w for w in s1.parse_warnings)
    assert [(b.character, b.vo_os, b.parenthetical, b.text) for b in s1.dialogue_blocks] == [("ANJU", "V.O.", "low", "ഞാൻ ഇവിടെ ഉണ്ട്."), ("RAVI", None, None, "Ippo varaam.")]
    assert s1.transitions == ["CUT TO:"] and s1.capitalised_items == ["PHONE"]
    assert parsed.scenes[1].day_night == DayNight.DAWN


def test_fdx_xml_and_fdx_exported_text():
    xml = """<?xml version="1.0" encoding="UTF-8" standalone="no" ?>
<FinalDraft DocumentType="Script" Template="No" Version="5">
  <Content>
    <Paragraph Type="Scene Heading" Number="1"><Text>INT. KOCHI FLAT - NIGHT</Text></Paragraph>
    <Paragraph Type="Action"><Text>Anju waits. The </Text><Text Style="Bold">BRASS LOCKET</Text><Text> glints.</Text></Paragraph>
    <Paragraph Type="Character"><Text>ANJU (V.O.)</Text></Paragraph>
    <Paragraph Type="Parenthetical"><Text>(low)</Text></Paragraph>
    <Paragraph Type="Dialogue"><Text>ചേട്ടാ, ഞാൻ ജെട്ടിയിൽ ഉണ്ട്.</Text></Paragraph>
    <Paragraph Type="Character"><Text>RAVI</Text></Paragraph>
    <Paragraph Type="Dialogue"><Text>Ippo varaam.</Text></Paragraph>
    <Paragraph Type="Transition"><Text>CUT TO:</Text></Paragraph>
    <Paragraph Type="Scene Heading" Number="2"><Text>EXT. VYPIN JETTY - DAWN</Text></Paragraph>
    <Paragraph Type="Lyrics"><Text>Raavu theernnu</Text></Paragraph>
    <Paragraph Type="Lyrics"><Text>Poovu veenu</Text></Paragraph>
    <Paragraph Type="Action"><Text>The ferry leaves.</Text></Paragraph>
  </Content>
</FinalDraft>"""
    parsed = ingest_text(xml, "fdx")
    assert parsed.source_format == "fdx" and [s.id for s in parsed.scenes] == ["S1", "S2"]
    s1, s2 = parsed.scenes
    assert s1.slug == "INT. KOCHI FLAT - NIGHT" and s1.capitalised_items == ["BRASS LOCKET"]
    assert [(b.character, b.vo_os, b.parenthetical, b.text) for b in s1.dialogue_blocks] == [("ANJU", "V.O.", "low", "ചേട്ടാ, ഞാൻ ജെട്ടിയിൽ ഉണ്ട്."), ("RAVI", None, None, "Ippo varaam.")]
    assert s1.transitions == ["CUT TO:"]
    assert s2.song_candidates[0].lyrics == ["Raavu theernnu", "Poovu veenu"] and s2.action_lines == ["The ferry leaves."]
    exported = "INT. KOCHI FLAT - NIGHT\n\nAnju waits.\n\n          ANJU\n     Ippo varaam.\n\nCUT TO:\n"
    text_parse = ingest_text(exported, "fdx")
    assert text_parse.source_format == "fdx" and text_parse.scenes[0].dialogue_blocks[0].text == "Ippo varaam."
    assert read_fdx(exported).source_format == "fdx"


def test_format_detection_and_text_entry_points(tmp_path: Path):
    assert detect_format("x.fountain") == "fountain" and detect_format("X.FDX") == "fdx" and detect_format("a/b.pdf") == "pdf" and detect_format("c.docx") == "docx"
    with pytest.raises(ValueError):
        detect_format("script.rtf")
    with pytest.raises(ValueError):
        ingest_text("INT. A - DAY", "rtf")
    empty = ingest_text("Just a note.\n", "fountain")
    assert empty.scenes == [] and any("no sluglines" in w for w in empty.parse_warnings)
    p = tmp_path / "mini.txt"
    p.write_text("INT. A - DAY\n\nx.\n", encoding="utf-8")
    assert ingest_file(p).scenes[0].slug == "INT. A - DAY"
    assert ingest_file(p, format="fountain").source_format == "fountain"
    doc = RawDocument.from_text("a\n\x0cb\n--- PAGE 3 ---\nc", "txt")
    assert doc.page_breaks == [1, 3] and doc.page_count == 3 and doc.lines == ["a", "b", "", "c"]
    again = RawDocument.from_text(doc.text_with_markers(), "txt")  # markers add lines, but the same lines start the same pages
    assert again.page_count == 3 and [again.lines[i] for i in again.page_breaks] == ["b", "c"]


def test_capitalised_items_do_not_decide_meaning():
    assert capitalised_items("A BRASS LOCKET swings. The TV plays. ANJU (29) enters; 2 A.M.") == ["BRASS LOCKET", "TV", "ANJU"]
    assert capitalised_items("Two TVs and a phone.") == []
    assert capitalised_items("The BRASS LOCKET's chain glints.") == ["BRASS LOCKET"]
    assert capitalised_items("അമ്മച്ചി holds the ROSARY.") == ["ROSARY"]


# ------------------------------------------------------------------ register detection


def test_register_detection_malayalam_manglish_english(kaitha: ParsedScript):
    _check_registers(kaitha, ANNOTATIONS["kaitha_pilot"]["registers"])
    assert detect_register("എടാ, നീ എവിടെയാ? ഇപ്പോ വാ.") == (Register.COLLOQUIAL, None)
    assert detect_register("Njan ippo varaam, nee avide nikk.") == (Register.COLLOQUIAL, None)
    assert detect_register("I don't care what he said.") == (Register.COLLOQUIAL, None)
    assert detect_register("The witness is dead.") == (Register.UNKNOWN, None)
    assert detect_register("ഞമ്മടെ കാക്ക വരും.") == (Register.REGIONAL, "Malabar")
    assert detect_register("Entharappi, aliya?") == (Register.REGIONAL, "Trivandrum")
    assert detect_register("എടാ, phone charge cheyth vech, okay?")[0] == Register.CODE_SWITCHED
    assert detect_script("ഞാൻ ഇവിടെ ഉണ്ട്.") == "malayalam" and detect_script("Njan ivide undu.") == "manglish" and detect_script("I am here.") == "english"
    assert detect_register("") == (Register.UNKNOWN, None)


# ------------------------------------------------------------------ ParserAgent (offline)


async def test_refine_without_context_returns_rule_based_parse(kaitha: ParsedScript):
    assert await refine(None, kaitha, "irrelevant") is kaitha


async def test_parser_agent_offline_example_passes_check(offline_ctx: AgentContext, kaitha: ParsedScript):
    raw = read_document(GOLDEN_DIR / "kaitha_pilot.fountain").text_with_markers()
    refined = await refine(offline_ctx, kaitha, raw)
    assert [s.id for s in refined.scenes] == [s.id for s in kaitha.scenes]
    assert [b.text for s in refined.scenes for b in s.dialogue_blocks] == [b.text for s in kaitha.scenes for b in s.dialogue_blocks]
    assert refined.source_format == "fountain" and refined.total_pages == kaitha.total_pages
    call = offline_ctx.client.last
    assert "rule_based_parse" in call.prompt and "raw_text" in call.prompt and call.system[0]["cache_control"]["type"] == "ephemeral"
    assert len(call.system) == 1  # L1 runs before any Film Brief Header exists
    assert offline_ctx.store.latest("parser", "script") is not None


async def test_parser_agent_accepts_refined_registers_and_aliases(offline_ctx: AgentContext, kaitha: ParsedScript):
    def responder(call):
        out = kaitha.model_copy(deep=True)
        out.scenes[0].dialogue_blocks[0].dialogue_register = Register.REGIONAL
        out.scenes[0].dialogue_blocks[0].region = "Kochi"
        out.location_aliases = list(out.location_aliases) + [LocationAlias(alias="VYPIN FERRY", canonical="VYPIN JETTY")]
        out.parse_warnings = list(out.parse_warnings) + ["S9: no cue — the singer is not named"]
        return out

    offline_ctx.client = FakeLLM(responder)
    refined = await refine(offline_ctx, kaitha, read_document(GOLDEN_DIR / "kaitha_pilot.fountain").text_with_markers())
    assert refined.scenes[0].dialogue_blocks[0].region == "Kochi"
    assert any(a.alias == "VYPIN FERRY" for a in refined.location_aliases)
    assert offline_ctx.client.calls[-1].is_repair is False


async def test_parser_agent_rejects_duplicate_ids_after_repair(offline_ctx: AgentContext, kaitha: ParsedScript):
    def responder(call):
        out = kaitha.model_copy(deep=True)
        out.scenes[1].id = "S1"
        return out

    offline_ctx.client = FakeLLM(responder)
    with pytest.raises(ValidationRejected) as exc:
        await refine(offline_ctx, kaitha, read_document(GOLDEN_DIR / "kaitha_pilot.fountain").text_with_markers())
    assert "unique" in str(exc.value)
    assert len(offline_ctx.client.calls) == 2 and offline_ctx.client.calls[1].is_repair


async def test_parser_agent_rejects_translated_or_dropped_dialogue(offline_ctx: AgentContext, kaitha: ParsedScript):
    raw = read_document(GOLDEN_DIR / "kaitha_pilot.fountain").text_with_markers()

    def translates(call):
        out = kaitha.model_copy(deep=True)
        out.scenes[0].dialogue_blocks[0].text = "Chetta, I am at the jetty. Where are you?"
        return out

    offline_ctx.client = FakeLLM(translates)
    with pytest.raises(ValidationRejected) as exc:
        await refine(offline_ctx, kaitha, raw)
    assert "verbatim" in str(exc.value)

    def drops(call):
        out = kaitha.model_copy(deep=True)
        out.scenes[2].dialogue_blocks = out.scenes[2].dialogue_blocks[:-1]
        return out

    offline_ctx.client = FakeLLM(drops)
    with pytest.raises(ValidationRejected) as exc2:
        await refine(offline_ctx, kaitha, raw)
    assert "dropped or altered" in str(exc2.value)

    def moves_lines(call):
        out = kaitha.model_copy(deep=True)
        out.scenes[0].line_end = 999
        return out

    offline_ctx.client = FakeLLM(moves_lines)
    with pytest.raises(ValidationRejected):
        await refine(offline_ctx, kaitha, raw)


async def test_parser_agent_repairs_once_then_succeeds(offline_ctx: AgentContext, kaitha: ParsedScript):
    def responder(call):
        out = kaitha.model_copy(deep=True)
        if not call.is_repair:
            out.scenes[0].number = 7
        return out

    offline_ctx.client = FakeLLM(responder)
    raw = read_document(GOLDEN_DIR / "kaitha_pilot.fountain").text_with_markers()
    result = await ParserAgent(offline_ctx).run(key="script", raw_text=raw, rule_based_parse=kaitha)
    assert result.attempts == 2 and result.parsed.scenes[0].number == 1 and "S1" in (result.repair_error or "")


def test_parser_check_without_rule_based_parse_still_enforces_ids_and_verbatim():
    agent = ParserAgent(AgentContext.offline())
    ok = ParsedScript(scenes=[SceneSkeleton(id="S1", number=1, slug="INT. A - DAY", int_ext=IntExt.INT, day_night=DayNight.DAY, location_raw="A", location_canonical="A", page_start=1, page_eighths=1, dialogue_blocks=[{"character": "ANJU", "text": "ഞാൻ ഇവിടെ ഉണ്ട്."}])])  # type: ignore[list-item]
    agent.check(ok, {"raw_text": "INT. A - DAY\n\nANJU\nഞാൻ ഇവിടെ ഉണ്ട്.\n"})
    with pytest.raises(ValueError, match="verbatim"):
        agent.check(ok, {"raw_text": "INT. A - DAY\n\nANJU\nI am here.\n"})
    bad_ids = ok.model_copy(deep=True)
    bad_ids.scenes[0].id = "SCENE-1"
    with pytest.raises(ValueError, match="S1"):
        agent.check(bad_ids, {})
