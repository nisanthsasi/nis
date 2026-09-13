"""Rule-based dialogue register detection — the first (cheap, deterministic) pass of L1.

The pipeline needs to *name the Malayalam register* whenever dialogue is analysed
(P0/P1). This module answers three questions about one dialogue text without a model:

* which **script** it is written in — Malayalam script, Manglish (Malayalam in Latin
  letters), plain English, a Malayalam–English/Tamil mix, or Tamil;
* which :class:`~the_panel.schemas.common.Register` it reads as — literary,
  colloquial, regional or code-switched (``UNKNOWN`` when no marker fires);
* which **region** the idiom points at (Kollam / Thrissur / Malabar / Trivandrum) via a
  small, extensible marker lexicon.

Everything here is a heuristic seam: :func:`the_panel.ingest.refine` lets the model-assisted
:class:`~the_panel.agents.parser.ParserAgent` overwrite ``dialogue_register`` / ``region`` on
each :class:`~the_panel.schemas.scene.DialogueBlock`; the rule-based result is what the
pipeline falls back to offline. Dialogue text is only *read* here — never transliterated,
translated or altered.
"""
from __future__ import annotations

import re
from typing import Literal

from ..schemas.common import Register

ScriptKind = Literal["malayalam", "manglish", "english", "mixed", "tamil", "unknown"]

# Unicode blocks. Malayalam includes combining vowel signs and the virama, which are
# *not* ``str.isalpha()`` — every check below uses the code-point range, never ``\\w``.
_MALAYALAM = re.compile(r"[ഀ-ൿ]")
_TAMIL = re.compile(r"[஀-௿]")
_LATIN_WORD = re.compile(r"[A-Za-z][A-Za-z'’]*")

# --- Manglish lexicon --------------------------------------------------------------
# Frequent Malayalam function words / particles as they are usually romanised. Whole-token
# matches; the STEMS below also match as prefixes so inflected forms (ningale, paranjilla,
# enthoottu …) still register.
MANGLISH_WORDS: frozenset[str] = frozenset(
    {
        "njan", "nee", "ente", "ninte", "avan", "aval", "avar", "ivan", "ival", "ivar", "nammal", "njangal", "ningal",
        "enthu", "entha", "enthaa", "enth", "enthina", "enthinaa", "ethra", "evide", "avide", "ivide", "evideya", "aara", "aaru", "aarum", "aar",
        "alle", "alla", "aanu", "aano", "aan", "aayirunnu", "ayirunnu", "aayo", "aavum", "aakum",
        "illa", "ille", "illya", "illallo", "undu", "undo", "ondu", "ondo", "indu", "indo",
        "venda", "vendaa", "veno", "venam", "vende", "mathi", "pattilla", "pattum", "pattoola",
        "poyi", "poda", "podi", "pokaam", "pokku", "poyo", "povilla", "pokilla", "vaa", "va", "varuu", "vannu", "vanno", "varilla", "varaam",
        "pinne", "ippo", "appo", "ippol", "appol", "innu", "innale", "naale", "raavile", "raathri", "rathri",
        "angane", "ingane", "onnum", "ellam", "kure", "koode", "koodi", "kooda", "onnu", "randu", "oru", "ee", "aa", "athu", "ithu", "athe", "athey", "ithe", "athinu", "ithinu",
        "sheri", "seri", "sherikkum", "ayyo", "eda", "edi", "edaa", "ediye", "mone", "mole", "chetta", "chechi", "chettan", "achan", "amma", "ammachi", "achayan", "aliya",
        "ariyam", "ariyaam", "ariyilla", "ariyo", "ariyaamo", "paranju", "parayu", "parayaam", "paranjilla", "paranjille", "kettu", "kettille", "ketto", "kelkku", "kelkkaam",
        "kandu", "kanaam", "kaanaam", "kaanam", "nokku", "nokkaam", "nokkiye", "cheyy", "cheyyu", "cheythu", "cheyyilla", "kodukku", "kodukkaam", "tharu", "tharaam", "thannu",
        "enik", "enikku", "ninak", "ninakku", "avanu", "avalu", "nammude", "ningalude", "njangalude", "nammude", "enikkum", "ninakkum",
        "vandi", "vare", "thanne", "thanneya", "kondu", "kaashu", "kaash", "paisa", "sathyam", "karyam", "kaaryam", "onnumilla", "aarkkum", "kayyil", "kaiyyil",
        "aayittu", "poyittu", "vannittu", "kazhinju", "kazhinjilla", "thudangi", "theernnu", "theernu", "vegam", "pathukke", "mindaathe", "mindathe",
        "alleda", "alledi", "aanoda", "aanodi", "kollamallo", "mathiyeda", "enthadaa", "enthada", "enthadi", "evideda", "evidedi", "gadi", "gadiye",
    }
)
MANGLISH_STEMS: tuple[str, ...] = tuple(sorted({w for w in MANGLISH_WORDS if len(w) >= 5} | {"njangal", "ningal", "paranj", "parayu", "ariyaa", "ariyill", "cheyyu", "kodukk", "enthoott", "njammal", "njammad", "bedakk", "randin", "avare", "avanod", "avalod"}))

# Common English function words (never Malayalam romanisations). Loanwords Malayalam
# speakers use inside Malayalam sentences (phone, office, bus …) are deliberately absent:
# they count as neither language.
ENGLISH_WORDS: frozenset[str] = frozenset(
    {
        "the", "a", "an", "and", "is", "are", "was", "were", "be", "been", "am", "you", "i", "we", "they", "he", "she", "it", "this", "that", "these", "those",
        "what", "why", "how", "when", "where", "who", "which", "do", "does", "did", "done", "not", "no", "yes", "of", "to", "in", "on", "for", "with", "at", "by", "from",
        "have", "has", "had", "will", "would", "can", "could", "should", "shall", "may", "might", "must", "please", "okay", "ok", "fine", "just", "only", "come", "go", "get", "let",
        "tell", "know", "think", "want", "need", "look", "see", "right", "now", "here", "there", "then", "than", "never", "always", "time", "money", "man", "boy", "girl", "one", "two",
        "my", "your", "our", "their", "his", "her", "me", "him", "them", "us", "up", "down", "out", "off", "about", "again", "back", "because", "but", "or", "so", "if", "very", "really",
        "stop", "wait", "listen", "sorry", "thank", "thanks", "hello", "hi", "hey", "bye", "brother", "sister", "mother", "father", "home", "night", "day", "morning", "today", "tomorrow",
        "yesterday", "good", "bad", "big", "small", "new", "old", "last", "first", "any", "all", "some", "every", "nothing", "something", "anything", "everything", "whose", "care",
        "find", "give", "take", "make", "say", "said", "way", "move", "leave", "keep", "open", "close", "call", "answer", "true", "false", "dead", "alive", "life", "death",
        "don't", "can't", "won't", "isn't", "aren't", "wasn't", "weren't", "didn't", "doesn't", "it's", "i'm", "you're", "we're", "they're", "what's", "that's", "let's", "i'll", "i've", "i'd",
    }
)
_ENGLISH_COLLOQUIAL_MARKERS: tuple[str, ...] = ("come on", "hey", "yeah", "yep", "nope", "okay", "ok", "gonna", "wanna", "gotta", "dude", "man", "damn", "bloody", "shut up", "get out", "get in", "get lost", "whatever", "kinda", "sorta", "buddy", "guys", "cool")
_ENGLISH_LITERARY_MARKERS: tuple[str, ...] = ("shall", "whom", "hence", "thus", "henceforth", "therefore", "nevertheless", "whereupon", "thereby", "hitherto", "forsooth", "verily")
_CONTRACTION = re.compile(r"[A-Za-z]['’](?:t|s|m|re|ll|ve|d)\b", re.IGNORECASE)

# --- Malayalam-script markers -------------------------------------------------------
# Literary / formal Malayalam: Sanskritised copulas, honorifics, formal connectives.
LITERARY_MARKERS: tuple[str, ...] = (
    "ആകുന്നു", "ആയിരിക്കുന്നു", "അല്ലയോ", "ഭവാൻ", "ഭവതി", "അങ്ങയുടെ", "അങ്ങേയ്ക്ക്", "അടിയൻ", "ഏവം", "എന്തെന്നാൽ", "ആയതിനാൽ", "അതിനാൽ",
    "താങ്കൾ", "താങ്കള", "പ്രിയേ", "പ്രിയപ്പെട്ട", "സഖേ", "അഹോ", "ആകയാൽ", "എന്നിരുന്നാലും", "പക്ഷം", "ഏതൊരു", "യാതൊരു", "പ്രകാരം", "ആകാം", "ആയിരിക്കും",
)
# Colloquial Malayalam: contracted verb endings, vocatives, particles.
COLLOQUIAL_MARKERS: tuple[str, ...] = (
    "ണ്", "ല്ല", "ഡാ", "ഡീ", "എടാ", "എടീ", "മോനെ", "മോനേ", "മോളെ", "മോളേ", "ചേട്ടാ", "ചേട്ടൻ", "ചേച്ചീ", "ചേച്ചി", "അല്ലേ", "ആണോ", "ഇല്ലേ", "ഇല്ല", "വേണ്ട",
    "എന്താ", "എന്തുവാ", "അയ്യോ", "പോടാ", "പോടീ", "വാ", "മതി", "ഇപ്പോ", "അപ്പോ", "ന്ന്", "ണ്ട്", "ണ്ടോ", "ല്ലേ", "ഏയ്", "ശരി", "പിന്നെ", "അല്ല", "ഉവ്വ്", "ആന്ന്", "ആണ്",
    "സോറി", "ഓക്കേ", "കേട്ടോ", "നോക്ക്", "ചെയ്യ്", "പറ", "ഇനി", "അതാ", "ഇതാ",
)

# --- Regional lexicon (extensible) --------------------------------------------------
# Markers in Malayalam script are matched as substrings (agglutination); Latin markers
# match at a token start. Extend at runtime with :func:`add_regional_markers`.
REGIONAL_LEXICON: dict[str, set[str]] = {
    "Kollam": {"ഗഡി", "ഗഡീ", "ഗഡിയേ", "gadi", "gadiye", "gadee"},
    "Thrissur": {"എന്തൂട്ട്", "എന്തൂട്ടാ", "ഇണ്ട്", "ഇണ്ടോ", "ഇല്ല്യ", "ല്ല്യ", "ഒന്നൂല്ല്യ", "enthoottu", "enthootu", "enthoott", "indu", "indo", "illya", "onnoollya", "ontoo"},
    "Malabar": {"ഞമ്മള്", "ഞമ്മടെ", "ഞമ്മക്ക്", "ഇജ്ജ്", "ഓള്", "ഓള്‍", "ഓൻ", "ബെടക്ക്", "അയിന്", "ഇക്ക", "കാക്ക", "njammal", "njammade", "njammakku", "ijj", "ijju", "bedakku", "ayinu", "ikka", "kaakka", "kaka", "olu", "oalu"},
    "Trivandrum": {"എന്തര്", "എന്തരപ്പി", "അളിയാ", "ചെല", "പോടേ", "അല്ലിയോ", "enthar", "entharappi", "aliya", "aliyaa", "chela", "alliyo", "pode"},
}


def add_regional_markers(region: str, *markers: str) -> None:
    """Extend the regional lexicon at runtime (a new region, or more idiom for an existing one)."""
    REGIONAL_LEXICON.setdefault(region, set()).update(m.strip() for m in markers if m.strip())


def _latin_tokens(text: str) -> list[str]:
    return [t.lower().replace("’", "'") for t in _LATIN_WORD.findall(text)]


def _is_manglish_token(tok: str) -> bool:
    if tok in ENGLISH_WORDS:
        return False
    if tok in MANGLISH_WORDS:
        return True
    return any(tok.startswith(stem) for stem in MANGLISH_STEMS)


def detect_script(text: str) -> ScriptKind:
    """Which writing system / language mix a dialogue text uses.

    ``mixed`` covers Malayalam script with real English words in it, Manglish with a
    dominant English share, or Malayalam alongside Tamil — every case the pipeline reads
    as code-switched.
    """
    has_ml = bool(_MALAYALAM.search(text))
    has_ta = bool(_TAMIL.search(text))
    tokens = _latin_tokens(text)
    latin_content = [t for t in tokens if len(t) >= 3 and not _is_manglish_token(t)]
    if has_ml and has_ta:
        return "mixed"
    if has_ml:
        return "mixed" if latin_content else "malayalam"
    if has_ta:
        return "mixed" if latin_content else "tamil"
    if not tokens:
        return "unknown"
    manglish = sum(1 for t in tokens if _is_manglish_token(t))
    english = sum(1 for t in tokens if t in ENGLISH_WORDS)
    if manglish == 0:
        return "english"
    if english >= 2 and english > manglish:
        return "mixed"
    return "manglish"


def detect_region(text: str) -> str | None:
    """Name the region whose idiom markers appear in *text*, or ``None``. First region with the most hits wins."""
    tokens = _latin_tokens(text)
    best: tuple[int, str] | None = None
    for region, markers in REGIONAL_LEXICON.items():
        hits = 0
        for m in markers:
            if _MALAYALAM.search(m) or _TAMIL.search(m):
                hits += text.count(m)
            else:
                ml = m.lower()
                hits += sum(1 for t in tokens if t == ml or (len(ml) >= 4 and t.startswith(ml)))
        if hits and (best is None or hits > best[0]):
            best = (hits, region)
    return best[1] if best else None


def detect_register(text: str) -> tuple[Register, str | None]:
    """Rule-based register hook: ``(Register, region | None)`` for one dialogue text.

    * Malayalam + English/Tamil in one line → ``CODE_SWITCHED``.
    * Regional idiom marker → ``REGIONAL`` with the region named.
    * Malayalam script: literary markers outweigh colloquial ones → ``LITERARY``; colloquial
      markers → ``COLLOQUIAL``; nothing fires → ``UNKNOWN`` (left for the model pass).
    * Manglish is by nature spoken language → ``COLLOQUIAL``.
    * English: contractions/slang → ``COLLOQUIAL``, formal markers → ``LITERARY``, else ``UNKNOWN``.
    """
    if not text or not text.strip():
        return Register.UNKNOWN, None
    kind = detect_script(text)
    region = detect_region(text)
    if kind == "mixed":
        return Register.CODE_SWITCHED, region
    if region is not None:
        return Register.REGIONAL, region
    if kind in ("malayalam", "tamil"):
        literary = sum(text.count(m) for m in LITERARY_MARKERS)
        colloquial = sum(text.count(m) for m in COLLOQUIAL_MARKERS)
        if literary and literary * 2 > colloquial:
            return Register.LITERARY, None
        if colloquial:
            return Register.COLLOQUIAL, None
        return Register.UNKNOWN, None
    if kind == "manglish":
        return Register.COLLOQUIAL, None
    if kind == "english":
        low = f" {text.lower()} "
        if _CONTRACTION.search(text) or any(f" {m} " in low or f" {m}!" in low or f" {m}," in low or f" {m}." in low for m in _ENGLISH_COLLOQUIAL_MARKERS):
            return Register.COLLOQUIAL, None
        if any(f" {m} " in low for m in _ENGLISH_LITERARY_MARKERS):
            return Register.LITERARY, None
    return Register.UNKNOWN, None
