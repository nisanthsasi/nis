"""L1 normalisation: raw lines → :class:`~the_panel.schemas.scene.ParsedScript` (structure only, no interpretation).

Rule-based, deterministic and Malayalam-safe: sluglines are recognised by their ASCII
``INT./EXT.`` prefix and the rest of every line is carried verbatim (uppercasing is a
no-op on Malayalam script; punctuation classes are explicit ASCII so vowel signs and the
virama are never mangled). Dialogue is never transliterated or translated.

What comes out per scene (a :class:`~the_panel.schemas.scene.SceneSkeleton`):
``S{n}`` ids in script order, hygiene-normalised slug, INT/EXT, DAY/NIGHT, raw and
canonical location (via :class:`LocationAliasTable`), speaking characters (canonicalised
via :class:`CharacterRoster`), dialogue blocks with V.O./O.S. stripped into ``vo_os`` and a
rule-based register, action lines, capitalised items (candidate props / sounds /
pay-offs — meaning is not decided here), montage / series-of-shots / intercut children,
song candidates, page-eighths from line counts and parse warnings (inconsistent slugs,
missing time of day, …). The model-assisted refinement seam is
:func:`the_panel.ingest.refine`.
"""
from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable

from ..schemas.common import DayNight, IntExt
from ..schemas.scene import (
    CharacterAlias,
    DialogueBlock,
    LocationAlias,
    MontageChild,
    ParsedScript,
    SceneSkeleton,
    SongCandidate,
)
from .document import EIGHTHS_PER_PAGE, LINES_PER_PAGE, RawDocument
from .register import detect_register

# --- line grammar ---------------------------------------------------------------------

SLUG_RE = re.compile(
    r"""^\s*
    (?P<num>\d{1,4}[A-Z]{0,2}[.:)]?\s+)?                       # leading scene number (PDF/FDX exports)
    (?P<prefix>INT\.?\s*/\s*EXT\.?|EXT\.?\s*/\s*INT\.?|I\s*/\s*E\.?|INT\.?|EXT\.?|EST\.?)
    (?=[\s.\-–—:])[\s.\-–—:]*                                  # the prefix must be followed by a separator
    (?P<rest>.*?)\s*$""",
    re.IGNORECASE | re.VERBOSE,
)
FORCED_SLUG_RE = re.compile(r"^\s*\.(?!\.)(?P<rest>\S.*?)\s*$")
FOUNTAIN_SCENE_NUMBER_RE = re.compile(r"\s*#([^#]+)#\s*$")
TRANSITION_RE = re.compile(
    r"""^\s*(?:
        [A-Z][A-Z .'’\-]*\s+TO:|
        FADE\s+(?:IN|OUT|TO\s+BLACK|TO\s+WHITE)[.:]?|
        CUT\s+TO\s+BLACK[.:]?|SMASH\s+CUT[.:]?|DISSOLVE[.:]?|BLACKOUT[.:]?|
        (?:THE\s+)?END(?:\s+OF\s+(?:SCENE|EPISODE|PILOT|ACT\s+\w+))?[.:]?
    )\s*$""",
    re.VERBOSE,
)
MONTAGE_START_RE = re.compile(
    r"^\s*(?:BEGIN\s+|START\s+)?(?P<kind>MONTAGE|SERIES\s+OF\s+SHOTS|QUICK\s+CUTS|INTERCUT)\b",
)
MONTAGE_END_RE = re.compile(
    r"^\s*(?:END\s+(?:OF\s+)?(?:MONTAGE|SERIES|QUICK\s+CUTS|INTERCUT)|BACK\s+TO\s+(?:SCENE|PRESENT|THE\s+SCENE))[.:]?\s*$",
)
SONG_MARKER_RE = re.compile(r"^\s*(?:SONG|LYRICS?|GAANAM|PAATTU)\b\s*(?:[:\-–—#\d\"“'(]|$)")
SONG_MENTION_RE = re.compile(r"\b(?:MONTAGE\s+TO\s+MUSIC|SONG\s+MONTAGE|MUSIC\s+MONTAGE|SONG\s+(?:BEGINS|STARTS|PLAYS))\b")
LYRIC_LINE_RE = re.compile(r"^\s*(?:~|♪|🎵)")
PARENTHETICAL_RE = re.compile(r"^\((?P<inner>.*)\)$", re.DOTALL)
CUE_RE = re.compile(r"^(?P<name>.*?)\s*(?P<ext>(?:\([^)]*\)\s*)+)?\^?\s*$")
CUE_EXT_RE = re.compile(r"\(([^)]*)\)")
LATIN_CUE_NAME_RE = re.compile(r"^[A-Z0-9][A-Z0-9 .'’\-&#/]*$")
MALAYALAM_CUE_NAME_RE = re.compile(r"^[ഀ-ൿ][ഀ-ൿ\s]*$")
SENTENCE_END = (".", "!", "?", "…", ":", ",", ";")
CAPS_RUN_RE = re.compile(r"(?<![A-Za-z0-9])([A-Z][A-Z0-9'’\-]*(?:\s+[A-Z][A-Z0-9'’\-]*)*)(?![A-Za-z0-9])")
CONTINUED_RE = re.compile(r"^\s*(?:\(CONTINUED\)|CONTINUED:?|\(MORE\))\s*$", re.IGNORECASE)
CENTERED_RE = re.compile(r"^\s*>\s*(?P<inner>.*?)\s*<\s*$")
ASCII_PUNCT_RE = re.compile(r"[.,;:!?'’\"“”()\[\]{}/\\\-–—_*#&+]")
TITLE_KEY_RE = re.compile(r"^[A-Za-z][A-Za-z ]{1,30}:\s*\S")

VO_OS_KINDS: dict[str, str] = {"VO": "V.O.", "OS": "O.S.", "OC": "O.C.", "OFF": "O.S.", "OFFSCREEN": "O.S.", "VOICEOVER": "V.O.", "VOICE": "V.O.", "FILTER": "V.O.", "FILTERED": "V.O.", "PHONE": "V.O.", "ONPHONE": "V.O.", "INTOPHONE": "V.O.", "ONRADIO": "V.O.", "ONTV": "V.O."}
CUE_EXT_DROP: frozenset[str] = frozenset({"CONTD", "CONT", "CONTINUED", "CONTINUING"})

# --- time of day -----------------------------------------------------------------------

_TIME_WORDS: dict[str, DayNight] = {
    "DAY": DayNight.DAY, "DAYTIME": DayNight.DAY, "MORNING": DayNight.DAY, "AFTERNOON": DayNight.DAY, "NOON": DayNight.DAY, "MIDDAY": DayNight.DAY,
    "NIGHT": DayNight.NIGHT, "MIDNIGHT": DayNight.NIGHT, "NIGHTTIME": DayNight.NIGHT, "PREDAWN": DayNight.NIGHT,
    "DAWN": DayNight.DAWN, "SUNRISE": DayNight.DAWN, "DAYBREAK": DayNight.DAWN,
    "DUSK": DayNight.DUSK, "SUNSET": DayNight.DUSK, "TWILIGHT": DayNight.DUSK, "EVENING": DayNight.DUSK, "MAGIC HOUR": DayNight.DUSK, "GOLDEN HOUR": DayNight.DUSK,
    "CONTINUOUS": DayNight.CONTINUOUS, "CONT": DayNight.CONTINUOUS, "CONT'D": DayNight.CONTINUOUS, "SAME": DayNight.CONTINUOUS, "SAME TIME": DayNight.CONTINUOUS, "MEANWHILE": DayNight.CONTINUOUS,
    "LATER": DayNight.LATER, "MOMENTS LATER": DayNight.LATER, "MINUTES LATER": DayNight.LATER, "HOURS LATER": DayNight.LATER, "DAYS LATER": DayNight.LATER, "WEEKS LATER": DayNight.LATER, "YEARS LATER": DayNight.LATER, "NEXT DAY": DayNight.DAY, "NEXT MORNING": DayNight.DAY, "THAT NIGHT": DayNight.NIGHT,
}
_CONCRETE_TIMES = frozenset({DayNight.DAY, DayNight.NIGHT, DayNight.DAWN, DayNight.DUSK})
_SEGMENT_SPLIT_RE = re.compile(r"\s+[-–—]+\s+|\s*--+\s*|\s+[-–—]\s*$")


def _time_of(segment: str) -> DayNight | None:
    """DayNight for a slug segment like ``NIGHT``, ``NIGHT (CONTINUOUS)``, ``THE NEXT MORNING`` — or None if it is not a time."""
    words = ASCII_PUNCT_RE.sub(" ", segment.upper().replace("CONT'D", "CONTD")).split()
    if not words:
        return None
    phrase = " ".join(words)
    if phrase in _TIME_WORDS:
        return _TIME_WORDS[phrase]
    if words[-1] in _TIME_WORDS and len(words) <= 3:
        return _TIME_WORDS[words[-1]]
    if "LATER" in words:
        return DayNight.LATER
    if "CONTINUOUS" in words or "CONTD" in words:
        return DayNight.CONTINUOUS
    return None


# --- canonicalisation keys --------------------------------------------------------------

_TRANSLIT_RULES: tuple[tuple[str, str], ...] = (
    ("ph", "f"), ("kh", "k"), ("gh", "g"), ("th", "t"), ("dh", "d"), ("bh", "b"), ("ch", "c"), ("sh", "s"), ("zh", "l"),
    ("ee", "i"), ("oo", "u"), ("ou", "u"), ("w", "v"), ("y", "i"),
)
_DOUBLE_RE = re.compile(r"([a-z])\1+")


def translit_key(token: str) -> str:
    """Spelling-variant key for a romanised Malayalam word: VYPIN/VYPEEN, SHIBU/SHIBOO, RAVI/RAVEE collapse together."""
    t = token.lower()
    if not t.isascii() or len(t) < 4:
        return t
    for src, dst in _TRANSLIT_RULES:
        t = t.replace(src, dst)
    return _DOUBLE_RE.sub(r"\1", t)


LOCATION_ABBREVIATIONS: dict[str, str] = {
    "APT": "APARTMENT", "APTS": "APARTMENT", "BLDG": "BUILDING", "RD": "ROAD", "ST": "STREET", "AVE": "AVENUE", "JN": "JUNCTION", "JCN": "JUNCTION", "JCT": "JUNCTION",
    "STN": "STATION", "HOSP": "HOSPITAL", "RM": "ROOM", "HQ": "HEADQUARTERS", "GOVT": "GOVERNMENT", "PS": "POLICE STATION", "DEPT": "DEPARTMENT", "MKT": "MARKET",
    "HSE": "HOUSE", "FLR": "FLOOR", "OFC": "OFFICE", "PKG": "PARKING", "NO": "NUMBER", "BLK": "BLOCK", "CORR": "CORRIDOR", "REST": "RESTAURANT", "STA": "STATION", "UNIV": "UNIVERSITY", "SCH": "SCHOOL", "HOSPL": "HOSPITAL",
}
LOCATION_SYNONYMS: dict[str, str] = {
    "FLAT": "APARTMENT", "FLATS": "APARTMENT", "APARTMENTS": "APARTMENT", "HOME": "HOUSE", "VEEDU": "HOUSE", "VEED": "HOUSE",
    "AUTO": "AUTORICKSHAW", "RICKSHAW": "AUTORICKSHAW", "KADA": "SHOP", "AMBALAM": "TEMPLE", "KSHETHRAM": "TEMPLE", "KSHETRAM": "TEMPLE", "PALLI": "CHURCH",
    "KADAPPURAM": "BEACH", "KADAVU": "JETTY", "KADAV": "JETTY", "SHAAP": "TODDY SHOP", "SHAPPU": "TODDY SHOP", "SHAP": "TODDY SHOP", "KALLUSHAAP": "TODDY SHOP",
    "THEATER": "THEATRE", "CENTER": "CENTRE", "CAFE": "CAFE", "CAFÉ": "CAFE", "CHAYAKKADA": "TEA SHOP", "CHAAYAKKADA": "TEA SHOP",
}
_LOCATION_STOPWORDS = frozenset({"THE", "A", "AN", "OF", "AT", "IN", "ON", "TO", "AND", "&"})


def clean_display(raw: str) -> str:
    """Display form of a raw location / character spelling: uppercase, whitespace collapsed, stray edge punctuation dropped."""
    s = " ".join(raw.replace("’", "'").split()).upper()
    return s.strip(" .,;:-–—")


def _singular(token: str) -> str:
    """ANJU'S / ANJUS / ANJU and FLATS / FLAT collapse: a possessive or plural S is forgiven on ASCII tokens."""
    if token.isascii() and len(token) >= 4 and token.endswith("S") and not token.endswith("SS"):
        return token[:-1]
    return token


def location_key(raw: str) -> str:
    """Heuristic identity of a location: case, punctuation, possessives, trailing DAY/NIGHT, abbreviations, synonyms and token order are all forgiven."""
    s = ASCII_PUNCT_RE.sub(" ", clean_display(raw).replace("'", ""))
    tokens = s.split()
    while tokens and _time_of(tokens[-1]) is not None:
        tokens.pop()
    expanded: list[str] = []
    for t in tokens:
        t = LOCATION_ABBREVIATIONS.get(t, t)
        expanded.extend(LOCATION_SYNONYMS.get(t, t).split())
    keyed = sorted(translit_key(_singular(t)) for t in expanded if t not in _LOCATION_STOPWORDS)
    return " ".join(keyed)


def character_key(raw: str) -> str:
    """Heuristic identity of a character cue name (case, punctuation, spelling variants)."""
    s = ASCII_PUNCT_RE.sub(" ", clean_display(raw).replace("'", ""))
    return " ".join(translit_key(t) for t in s.split())


class _AliasGroups:
    """Spellings grouped by a heuristic key; the canonical display form is the most frequent spelling (first seen on ties)."""

    def __init__(self, key_fn):
        self._key = key_fn
        self._explicit: dict[str, str] = {}
        self._explicit_pairs: list[tuple[str, str]] = []
        self._spellings: dict[str, list[str]] = {}
        self._counts: Counter[str] = Counter()

    def add(self, alias: str, canonical: str) -> None:
        canon = clean_display(canonical)
        self._explicit[self._key(alias)] = canon
        self._explicit.setdefault(self._key(canonical), canon)
        pair = (clean_display(alias), canon)
        if pair[0] != canon and pair not in self._explicit_pairs:
            self._explicit_pairs.append(pair)

    def observe(self, raw: str) -> None:
        display = clean_display(raw)
        if not display:
            return
        group = self._spellings.setdefault(self._key(raw), [])
        if display not in group:
            group.append(display)
        self._counts[display] += 1

    def has(self, raw: str) -> bool:
        key = self._key(raw)
        return key in self._spellings or key in self._explicit

    def canonical(self, raw: str) -> str:
        key = self._key(raw)
        if key in self._explicit:
            return self._explicit[key]
        if key not in self._spellings:
            self.observe(raw)
        group = self._spellings[key]
        return max(group, key=lambda d: (self._counts[d], -group.index(d)))

    def variants(self, canonical: str) -> list[str]:
        key = self._key(canonical)
        return list(self._spellings.get(key, []))

    def pairs(self) -> list[tuple[str, str]]:
        out: list[tuple[str, str]] = list(self._explicit_pairs)
        for key, group in self._spellings.items():
            canon = self._explicit.get(key) or self.canonical(group[0])
            out.extend((d, canon) for d in group if d != canon)
        seen: set[tuple[str, str]] = set()
        return [p for p in out if not (p in seen or seen.add(p))]


class LocationAliasTable:
    """The location alias table of P1: ``"KOCHI FLAT" = "APARTMENT, KOCHI"``.

    Explicit pairs (from the human, a previous run or the model pass) win outright; everything
    else is merged by :func:`location_key`, a heuristic that forgives case, punctuation,
    possessive ``'S``, trailing DAY/NIGHT, common abbreviations and synonyms (FLAT/APARTMENT)
    and word order. Sub-locations (``KOCHI FLAT - KITCHEN``) stay distinct.
    """

    def __init__(self, pairs: Iterable[tuple[str, str]] | None = None):
        self._groups = _AliasGroups(location_key)
        for alias, canonical in pairs or ():
            self.add(alias, canonical)

    @classmethod
    def from_aliases(cls, aliases: Iterable[LocationAlias]) -> "LocationAliasTable":
        return cls((a.alias, a.canonical) for a in aliases)

    def add(self, alias: str, canonical: str) -> None:
        """Declare that ``alias`` names the same place as ``canonical`` (explicit; beats the heuristic)."""
        self._groups.add(alias, canonical)

    def observe(self, raw: str) -> None:
        """Count a raw spelling so the most frequent one becomes the canonical display form."""
        self._groups.observe(raw)

    def canonical(self, raw: str) -> str:
        """Canonical location for a raw slug location (registers it if unseen)."""
        return self._groups.canonical(raw)

    def variants(self, canonical: str) -> list[str]:
        """Every raw spelling seen for the place ``canonical`` names."""
        return self._groups.variants(canonical)

    def aliases(self) -> list[LocationAlias]:
        return [LocationAlias(alias=a, canonical=c) for a, c in self._groups.pairs()]


class CharacterRoster:
    """Character canonicalisation: case, punctuation and romanised spelling variants collapse; the most frequent spelling is the name."""

    def __init__(self, pairs: Iterable[tuple[str, str]] | None = None):
        self._groups = _AliasGroups(character_key)
        for alias, canonical in pairs or ():
            self.add(alias, canonical)

    def add(self, alias: str, canonical: str) -> None:
        self._groups.add(alias, canonical)

    def observe(self, raw: str) -> None:
        self._groups.observe(raw)

    def canonical(self, raw: str) -> str:
        return self._groups.canonical(raw)

    def knows(self, raw: str) -> bool:
        """Whether a capitalised item names a character that speaks somewhere in the script."""
        return self._groups.has(raw)

    def aliases(self) -> list[CharacterAlias]:
        return [CharacterAlias(alias=a, canonical=c) for a, c in self._groups.pairs()]


# --- slug parsing ------------------------------------------------------------------------

_PREFIX_TO_INT_EXT: dict[str, IntExt] = {"INT": IntExt.INT, "EXT": IntExt.EXT, "EST": IntExt.EXT, "IE": IntExt.INT_EXT, "INTEXT": IntExt.INT_EXT, "EXTINT": IntExt.INT_EXT}
_INT_EXT_LABEL: dict[IntExt, str] = {IntExt.INT: "INT.", IntExt.EXT: "EXT.", IntExt.INT_EXT: "INT./EXT."}


class ParsedSlug:
    """One slugline taken apart: prefix, raw location, time segments — plus the hygiene warnings it earned."""

    def __init__(self, int_ext: IntExt | None, location_raw: str, times: list[str], warnings: list[str], scene_number: str | None):
        self.int_ext = int_ext
        self.location_raw = location_raw
        self.times = times
        self.warnings = warnings
        self.scene_number = scene_number

    @property
    def day_night(self) -> DayNight:
        found = [t for t in (_time_of(s) for s in self.times) if t is not None]
        concrete = [t for t in found if t in _CONCRETE_TIMES]
        if concrete:
            return concrete[0]
        return found[0] if found else DayNight.UNKNOWN

    def normalised(self) -> str:
        """Hygiene-normalised slug: canonical prefix, single ``-`` separators, uppercase, raw location kept."""
        head = _INT_EXT_LABEL[self.int_ext or IntExt.INT]
        parts = [clean_display(self.location_raw)] + [clean_display(t) for t in self.times]
        return f"{head} " + " - ".join(p for p in parts if p)


def is_slug(line: str) -> bool:
    return bool(SLUG_RE.match(line) or FORCED_SLUG_RE.match(line))


def parse_slug(line: str) -> ParsedSlug:
    """Take a slugline apart. Never mangles Malayalam: only the ASCII prefix and dash separators are interpreted."""
    warnings: list[str] = []
    scene_number: str | None = None
    m = SLUG_RE.match(line)
    if m:
        prefix_key = re.sub(r"[^A-Z]", "", m.group("prefix").upper())
        int_ext: IntExt | None = _PREFIX_TO_INT_EXT.get(prefix_key, IntExt.INT_EXT)
        rest = m.group("rest")
        if m.group("num"):
            scene_number = m.group("num").strip(" .:)")
    else:
        fm = FORCED_SLUG_RE.match(line)
        if fm is None:
            raise ValueError(f"not a slugline: {line!r}")
        int_ext = None
        rest = fm.group("rest")
        warnings.append("slug has no INT/EXT prefix (forced slugline); assumed INT")
    fn = FOUNTAIN_SCENE_NUMBER_RE.search(rest)
    if fn:
        scene_number = fn.group(1).strip()
        rest = rest[: fn.start()]
    if scene_number and re.search(rf"\s+{re.escape(scene_number)}\s*$", rest):
        rest = re.sub(rf"\s+{re.escape(scene_number)}\s*$", "", rest)
    segments = [s for s in (seg.strip() for seg in _SEGMENT_SPLIT_RE.split(rest)) if s]
    times: list[str] = []
    while len(segments) > 1 and _time_of(segments[-1]) is not None:
        times.insert(0, segments.pop())
    location = " - ".join(segments)
    if not times:
        words = location.split()
        if len(words) > 1 and _time_of(words[-1]) is not None:
            times = [words.pop()]
            location = " ".join(words)
            warnings.append("slug time of day was not separated by ' - '")
        else:
            warnings.append("slug missing time of day (DAY/NIGHT)")
    if not location.strip():
        warnings.append("slug has no location")
    if re.search(r"[.;:]\s*$", location):
        warnings.append(f"slug location has stray trailing punctuation: '{location}'")
    return ParsedSlug(int_ext, location.strip(), times, warnings, scene_number)


# --- line classification helpers ---------------------------------------------------------------

def _is_transition(s: str) -> bool:
    """Written transitions: ``CUT TO:`` family, fades, or a Fountain forced transition (``> TEXT`` without a closing ``<``)."""
    if CENTERED_RE.match(s):
        return False
    if s.startswith(">"):
        return True
    return bool(TRANSITION_RE.match(s))


def _is_parenthetical(s: str) -> bool:
    return bool(PARENTHETICAL_RE.match(s))


def _montage_kind(s: str) -> str | None:
    m = MONTAGE_START_RE.match(s)
    if m is None:
        if SONG_MENTION_RE.search(s.upper()) and "MONTAGE" in s.upper():
            return "montage"
        return None
    kind = re.sub(r"\s+", " ", m.group("kind").upper())
    return {"MONTAGE": "montage", "SERIES OF SHOTS": "series_of_shots", "QUICK CUTS": "montage", "INTERCUT": "intercut"}[kind]


def _is_song_marker(s: str) -> bool:
    return bool(SONG_MARKER_RE.match(s)) or bool(SONG_MENTION_RE.search(s.upper()))


def _is_lyric(s: str) -> bool:
    return bool(LYRIC_LINE_RE.match(s))


def _strip_lyric_markup(s: str) -> str:
    return s[1:].strip() if s.startswith("~") else s.strip()


def split_cue(cue: str) -> tuple[str, str | None, str | None]:
    """``"ANJU (V.O.) (CONT'D)"`` → ``("ANJU", "V.O.", None)``; other extensions become a parenthetical hint."""
    s = cue.strip()
    if s.startswith("@"):
        s = s[1:].strip()
    m = CUE_RE.match(s)
    name = (m.group("name") if m else s).strip()
    vo: list[str] = []
    hints: list[str] = []
    for inner in CUE_EXT_RE.findall(m.group("ext") or "") if m else []:
        key = re.sub(r"[^A-Z]", "", inner.upper())
        if key in CUE_EXT_DROP or not inner.strip():
            continue
        if key in VO_OS_KINDS:
            if VO_OS_KINDS[key] not in vo:
                vo.append(VO_OS_KINDS[key])
        else:
            hints.append(inner.strip())
    return name, ("/".join(vo) or None), ("; ".join(hints) or None)


def _cue_name_ok(name: str) -> bool:
    if not name or len(name) > 40 or name.endswith(SENTENCE_END):
        return False
    if LATIN_CUE_NAME_RE.match(name):
        return any(c.isalpha() for c in name) and len(name.split()) <= 5
    return bool(MALAYALAM_CUE_NAME_RE.match(name)) and len(name.split()) <= 3


def _is_cue(lines: list[str], i: int, start: int, end: int) -> bool:
    s = lines[i].strip()
    if s.startswith("@"):
        return i + 1 < end and bool(lines[i + 1].strip())
    prev_blank = i == start + 1 or not lines[i - 1].strip()
    next_text = i + 1 < end and bool(lines[i + 1].strip())
    if not (prev_blank and next_text) or s.startswith(("!", ">", "~", "♪", "(", "-", "=", "#")):
        return False
    if _is_transition(s) or _montage_kind(s) or MONTAGE_END_RE.match(s) or is_slug(s) or _is_song_marker(s):
        return False
    name, _, _ = split_cue(s)
    return _cue_name_ok(name)


def _action_text(s: str) -> str:
    c = CENTERED_RE.match(s)
    if c:
        return c.group("inner")
    if s.startswith("!"):
        return s[1:].strip()
    return s


def capitalised_items(text: str) -> list[str]:
    """Capitalised runs in an action line — candidate props / sounds / pay-offs. Meaning is not decided here."""
    out: list[str] = []
    for run in CAPS_RUN_RE.findall(text):
        words = run.split()
        while words and len(words[0]) == 1:
            words.pop(0)
        while words and len(words[-1]) == 1:
            words.pop()
        if not words or not any(len(w) >= 2 and any(ch.isalpha() for ch in w) for w in words):
            continue
        item = " ".join(words)
        if item not in out:
            out.append(item)
    return out


# --- typed paragraphs (FDX, styled DOCX) → Fountain-shaped lines -------------------------------------

ParagraphKind = str
"""``scene_heading | action | character | parenthetical | dialogue | transition | lyrics | general``."""

_BLANK_BEFORE = frozenset({"scene_heading", "action", "character", "transition", "general", "lyrics"})


def lines_from_paragraphs(paragraphs: list[tuple[ParagraphKind, str]]) -> list[str]:
    """Lay typed paragraphs out as Fountain-shaped lines (blank line before every block, none inside a dialogue block).

    Scene headings that do not start with INT/EXT are forced with a leading ``.``; transitions
    that do not end in ``TO:`` are forced with ``>``; lyrics are prefixed ``~`` — all Fountain
    syntax this normaliser understands, so every format goes through one parser.
    """
    out: list[str] = []
    prev_kind: ParagraphKind | None = None
    for kind, raw in paragraphs:
        text = raw.strip()
        if not text:
            if kind == "general" and out and out[-1] != "":
                out.append("")
            continue
        if kind in _BLANK_BEFORE and out and out[-1] != "" and not (kind == "lyrics" and prev_kind == "lyrics"):
            out.append("")
        if kind == "scene_heading" and not SLUG_RE.match(text):
            text = "." + text
        elif kind == "transition" and not _is_transition(text):
            text = "> " + text
        elif kind == "lyrics" and not text.startswith(("~", "♪")):
            text = "~" + text
        elif kind == "parenthetical" and not (text.startswith("(") and text.endswith(")")):
            text = f"({text})"
        out.extend(text.split("\n"))
        prev_kind = kind
    return out


# --- scene building -----------------------------------------------------------------------------

class _SceneDraft:
    def __init__(self, number: int, start: int):
        self.number = number
        self.start = start
        self.action: list[str] = []
        self.dialogue: list[DialogueBlock] = []
        self.raw_cues: list[str] = []
        self.caps: list[str] = []
        self.montage: list[MontageChild] = []
        self.songs: list[SongCandidate] = []
        self.transitions: list[str] = []
        self.warnings: list[str] = []
        self.last_content = start

    def add_caps(self, text: str) -> None:
        for item in capitalised_items(text):
            if item not in self.caps:
                self.caps.append(item)


def _consume_dialogue(lines: list[str], i: int, end: int, draft: _SceneDraft) -> int:
    cue = lines[i].strip()
    name, vo, hint = split_cue(cue)
    j = i + 1
    parenthetical: str | None = None
    text_lines: list[str] = []
    while j < end:
        t = lines[j].strip()
        if not t or is_slug(t):
            break
        if CONTINUED_RE.match(t):
            j += 1
            continue
        if _is_parenthetical(t) and not text_lines and parenthetical is None:
            parenthetical = PARENTHETICAL_RE.match(t).group("inner").strip()  # type: ignore[union-attr]
        else:
            text_lines.append(t)
        draft.last_content = j
        j += 1
    if hint:
        parenthetical = f"{hint}; {parenthetical}" if parenthetical else hint
    text = "\n".join(text_lines)
    if not text:
        draft.warnings.append(f"character cue '{name}' has no dialogue text")
        return j
    register, region = detect_register(text)
    draft.raw_cues.append(name)
    draft.dialogue.append(DialogueBlock(character=name, text=text, parenthetical=parenthetical, vo_os=vo, dialogue_register=register, region=region, line_ref=i + 1))
    return j


def _consume_montage(lines: list[str], i: int, start: int, end: int, kind: str) -> tuple[list[str], int]:
    """Collect a montage / series-of-shots / intercut block. Intercut keeps only its header; the others run to an end marker, a cue, a transition or a double blank."""
    block: list[str] = [lines[i].strip()]
    j = i + 1
    if kind == "intercut":
        while j < end and lines[j].strip():
            block.append(lines[j].strip())
            j += 1
        return block, j
    blank_run = 0
    while j < end:
        t = lines[j].strip()
        if not t:
            blank_run += 1
            if blank_run >= 2:
                break
            j += 1
            continue
        if MONTAGE_END_RE.match(t):
            j += 1
            break
        if is_slug(t) or _is_transition(t) or _is_cue(lines, j, start, end):
            break
        blank_run = 0
        block.append(t)
        j += 1
    return block, j


def _song_from_block(marker: str, block: list[str], line_ref: int) -> SongCandidate:
    lyric_marked = [_strip_lyric_markup(x) for x in block[1:] if _is_lyric(x)]
    if lyric_marked:
        return SongCandidate(marker=marker, lyrics=lyric_marked, line_ref=line_ref)
    return SongCandidate(marker=marker, lyrics=[x for x in block[1:] if not x.startswith(("--", "-", "•"))], line_ref=line_ref)


def _consume_song(lines: list[str], i: int, end: int) -> tuple[SongCandidate, int, int]:
    """A ``SONG:`` block or a run of ``~`` / ``♪`` lyric lines (stanza breaks allowed while the next stanza is lyric-marked)."""
    first = lines[i].strip()
    marker = first
    lyrics: list[str] = []
    if _is_lyric(first):
        lyrics.append(_strip_lyric_markup(first))
    j = i + 1
    last = i
    while j < end:
        t = lines[j].strip()
        if not t:
            k = j + 1
            while k < end and not lines[k].strip():
                k += 1
            if k < end and _is_lyric(lines[k].strip()):
                j = k
                continue
            break
        if is_slug(t) or _is_transition(t):
            break
        lyrics.append(_strip_lyric_markup(t))
        last = j
        j += 1
    return SongCandidate(marker=marker, lyrics=lyrics, line_ref=i + 1), j, last


def _build_scene(doc: RawDocument, number: int, start: int, end: int) -> tuple[_SceneDraft, ParsedSlug]:
    lines = doc.lines
    slug = parse_slug(lines[start])
    draft = _SceneDraft(number, start)
    draft.warnings.extend(slug.warnings)
    if slug.scene_number and slug.scene_number != str(number):
        draft.warnings.append(f"script numbers this scene '{slug.scene_number}'; pipeline id is S{number} (script order)")
    i = start + 1
    while i < end:
        s = lines[i].strip()
        if not s or s.startswith(("#", "=")) or CONTINUED_RE.match(s):
            i += 1
            continue
        if MONTAGE_END_RE.match(s):
            i += 1
            continue
        kind = _montage_kind(s)
        if kind is not None:
            block, nxt = _consume_montage(lines, i, start, end, kind)
            draft.montage.append(MontageChild(kind=kind, lines=block))
            if _is_song_marker(s) or any(_is_lyric(x) for x in block[1:]):
                draft.songs.append(_song_from_block(s, block, i + 1))
            for x in block[1:]:  # the marker line is markup, not a candidate item
                draft.add_caps(x)
            draft.last_content = nxt - 1
            i = nxt
            continue
        if _is_song_marker(s) or _is_lyric(s):
            song, nxt, last = _consume_song(lines, i, end)
            draft.songs.append(song)
            draft.last_content = max(last, i)
            i = nxt
            continue
        if _is_transition(s):
            draft.transitions.append(" ".join(s.lstrip("> ").split()).upper())
            draft.last_content = i
            i += 1
            continue
        if _is_cue(lines, i, start, end):
            i = _consume_dialogue(lines, i, end, draft)
            continue
        text = _action_text(s)
        draft.action.append(text)
        draft.add_caps(text)
        draft.last_content = i
        i += 1
    return draft, slug


def _scene_bounds(doc: RawDocument) -> list[tuple[int, int]]:
    slug_idx = [i for i, line in enumerate(doc.lines) if is_slug(line)]
    return [(s, slug_idx[k + 1] if k + 1 < len(slug_idx) else len(doc.lines)) for k, s in enumerate(slug_idx)]


def _preamble_warning(doc: RawDocument, first_slug: int) -> str | None:
    stray = [ln for ln in doc.lines[:first_slug] if ln.strip() and not TITLE_KEY_RE.match(ln) and not _is_transition(ln.strip()) and not ln.startswith((" ", "\t"))]
    if not stray:
        return None
    return f"{len(stray)} line(s) before the first slugline were not assigned to a scene"


def normalise_document(doc: RawDocument, *, aliases: LocationAliasTable | None = None) -> ParsedScript:
    """Rule-based L1: split a :class:`RawDocument` on sluglines and build scene skeletons.

    Two passes: the first parses every scene and observes every raw location and cue
    spelling; the second resolves canonical locations / characters (most frequent spelling
    wins) so canonicalisation never depends on script order.
    """
    table = aliases or LocationAliasTable()
    roster = CharacterRoster()
    script_warnings: list[str] = list(doc.warnings)
    bounds = _scene_bounds(doc)
    if not bounds:
        script_warnings.append("no sluglines found (INT./EXT.); nothing to parse")
        return ParsedScript(scenes=[], parse_warnings=script_warnings, source_format=doc.source_format, total_pages=doc.total_pages)
    pre = _preamble_warning(doc, bounds[0][0])
    if pre:
        script_warnings.append(pre)
    if not doc.has_page_map:
        script_warnings.append(f"no page markers in source; page_start estimated from line counts ({LINES_PER_PAGE} lines/page)")

    drafts: list[tuple[_SceneDraft, ParsedSlug]] = []
    for number, (start, end) in enumerate(bounds, 1):
        draft, slug = _build_scene(doc, number, start, end)
        table.observe(slug.location_raw)
        for cue in draft.raw_cues:
            roster.observe(cue)
        drafts.append((draft, slug))

    scenes: list[SceneSkeleton] = []
    inconsistent: dict[str, list[str]] = {}
    for draft, slug in drafts:
        canonical = table.canonical(slug.location_raw)
        variants = table.variants(canonical)
        warnings = list(draft.warnings)
        if len(variants) > 1:
            here = clean_display(slug.location_raw)
            others = ", ".join(repr(v) for v in variants if v != here)
            if here == canonical:
                warnings.append(f"inconsistent slug: '{canonical}' is also spelled {others} elsewhere (canonical kept)")
            else:
                warnings.append(f"inconsistent slug: location spelled '{slug.location_raw}' here; canonical '{canonical}' (also spelled: {others})")
            inconsistent[canonical] = variants
        if slug.day_night == DayNight.UNKNOWN and not any("time of day" in w for w in warnings):
            warnings.append("slug missing time of day (DAY/NIGHT)")
        characters: list[str] = []
        blocks: list[DialogueBlock] = []
        for block in draft.dialogue:
            name = roster.canonical(block.character)
            if name not in characters:
                characters.append(name)
            blocks.append(block.model_copy(update={"character": name}))
        for item in draft.caps:
            if roster.knows(item):
                name = roster.canonical(item)
                if name not in characters:
                    characters.append(name)
        if not draft.action and not blocks and not draft.montage and not draft.songs:
            warnings.append("empty scene: no action or dialogue after the slugline")
        line_count = max(draft.last_content - draft.start + 1, 1)
        scenes.append(
            SceneSkeleton(
                id=f"S{draft.number}",
                number=draft.number,
                slug=slug.normalised(),
                int_ext=slug.int_ext or IntExt.INT,
                day_night=slug.day_night,
                location_raw=slug.location_raw,
                location_canonical=canonical,
                page_start=doc.page_start(draft.start),
                page_eighths=max(1, round(line_count * EIGHTHS_PER_PAGE / LINES_PER_PAGE)),
                characters=characters,
                dialogue_blocks=blocks,
                action_lines=draft.action,
                capitalised_items=draft.caps,
                montage_children=draft.montage,
                song_candidates=draft.songs,
                transitions=draft.transitions,
                parse_warnings=warnings,
                line_start=draft.start + 1,
                line_end=draft.last_content + 1,
            )
        )
    for canonical, variants in inconsistent.items():
        script_warnings.append(f"inconsistent slug: {' / '.join(repr(v) for v in variants)} → '{canonical}'")
    for alias in roster.aliases():
        script_warnings.append(f"character '{alias.alias}' merged into '{alias.canonical}' (spelling variant)")
    missing_time = [s.id for s in scenes if s.day_night == DayNight.UNKNOWN]
    if missing_time:
        script_warnings.append(f"{len(missing_time)} scene(s) missing time of day: {', '.join(missing_time)}")
    return ParsedScript(
        scenes=scenes,
        location_aliases=table.aliases(),
        character_aliases=roster.aliases(),
        parse_warnings=script_warnings,
        source_format=doc.source_format,
        total_pages=doc.total_pages,
    )
