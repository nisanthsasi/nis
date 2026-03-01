"""Domain-specific validation rules for VORTEX — Momentum/Trend Following Systems.

Deterministic checks for:
- Trend identification formulas (EMA crossovers, ADX, slope)
- Momentum scoring (RSI, MACD, Rate of Change)
- Position sizing with trend strength weighting
- Trailing stop FSM (SCANNING → TREND_CONFIRMED → RIDING → TRAILING → EXIT)
- Pullback entry logic and continuation patterns
"""

import re
from prompt_validator.result import Issue, Severity, Category


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _find_sections(prompt: str) -> dict[str, str]:
    pattern = re.compile(r"SECTION\s+(\d+)\s*[—–-]\s*(.*?)(?=SECTION\s+\d+|LOCK STATEMENT|FREEZE|$)", re.DOTALL)
    sections = {}
    for match in pattern.finditer(prompt):
        sections[int(match.group(1))] = match.group(2).strip()
    return sections


# ---------------------------------------------------------------------------
# 1. STRUCTURAL COMPLETENESS
# ---------------------------------------------------------------------------

REQUIRED_SECTIONS = {
    0: "AXIOMS",
    1: "DATA CONTRACT",
    2: "TREND IDENTIFICATION",
    3: "MOMENTUM SCORING",
    4: "ENTRY RULES",
    5: "POSITION SIZING",
    6: "TRAILING STOP",
    7: "EXIT RULES",
    8: "FSM",
    9: "RISK MANAGEMENT",
    10: "OUTPUT FORMAT",
    11: "GOVERNANCE",
}


def check_section_completeness(prompt: str) -> list[Issue]:
    sections = _find_sections(prompt)
    missing = [f"Section {n} ({l})" for n, l in REQUIRED_SECTIONS.items() if n not in sections]
    if missing:
        return [Issue(
            message="Missing critical trend-following sections",
            severity=Severity.ERROR,
            category=Category.STRUCTURE,
            detail=f"Missing: {', '.join(missing)}",
            penalty=15 * len(missing),
        )]
    return []


def check_freeze_declaration(prompt: str) -> list[Issue]:
    lower = prompt.lower()
    issues = []
    if "freeze declaration" not in lower and "lock statement" not in lower:
        issues.append(Issue(message="No freeze/lock declaration", severity=Severity.WARNING,
                            category=Category.STRUCTURE, detail="Trend systems must lock parameters to prevent curve-fitting.", penalty=8))
    if "governance" not in lower:
        issues.append(Issue(message="No governance section", severity=Severity.WARNING,
                            category=Category.STRUCTURE, detail="Version-controlled governance required.", penalty=8))
    return issues


# ---------------------------------------------------------------------------
# 2. TREND & MOMENTUM FORMULAS
# ---------------------------------------------------------------------------

EXPECTED_FORMULAS = [
    ("EMA_FAST", r"EMA_FAST\s*="),
    ("EMA_SLOW", r"EMA_SLOW\s*="),
    ("ADX", r"ADX\s*="),
    ("MACD", r"MACD\s*="),
    ("RSI", r"RSI\s*="),
    ("TREND_SCORE", r"TREND_SCORE\s*="),
    ("MOMENTUM_SCORE", r"MOMENTUM_SCORE\s*="),
    ("TRAIL_STOP", r"TRAIL_STOP\s*="),
]


def check_formula_definitions(prompt: str) -> list[Issue]:
    missing = [name for name, pat in EXPECTED_FORMULAS if not re.search(pat, prompt)]
    if missing:
        return [Issue(
            message="Missing trend/momentum formula definitions",
            severity=Severity.ERROR,
            category=Category.ACCURACY,
            detail=f"Formulas not defined: {', '.join(missing)}",
            penalty=10 * len(missing),
        )]
    return []


def check_ema_crossover(prompt: str) -> list[Issue]:
    """Verify EMA crossover logic is defined."""
    lower = prompt.lower()
    has_crossover = any(k in lower for k in ["crossover", "cross above", "cross below", "golden cross", "death cross"])
    if not has_crossover:
        return [Issue(
            message="No EMA crossover logic defined",
            severity=Severity.WARNING,
            category=Category.ACCURACY,
            detail="Trend systems should define EMA crossover conditions for entry/exit signals.",
            penalty=10,
        )]
    return []


def check_trend_strength(prompt: str) -> list[Issue]:
    """Verify trend strength classification exists."""
    lower = prompt.lower()
    has_adx = "adx" in lower
    has_classification = any(k in lower for k in ["strong trend", "weak trend", "no trend", "trending", "ranging"])
    if not has_adx and not has_classification:
        return [Issue(
            message="No trend strength classification",
            severity=Severity.WARNING,
            category=Category.ACCURACY,
            detail="Momentum systems need ADX or equivalent trend strength measure with thresholds.",
            penalty=10,
        )]
    return []


# ---------------------------------------------------------------------------
# 3. FSM VALIDATION
# ---------------------------------------------------------------------------

EXPECTED_STATES = {"SCANNING", "TREND_CONFIRMED", "RIDING", "TRAILING", "EXIT", "COOLDOWN"}

EXPECTED_TRANSITIONS = [
    ("SCANNING", "TREND_CONFIRMED"),
    ("TREND_CONFIRMED", "RIDING"),
    ("RIDING", "TRAILING"),
    ("TRAILING", "EXIT"),
    ("EXIT", "COOLDOWN"),
]


def check_fsm_states(prompt: str) -> list[Issue]:
    upper = prompt.upper()
    missing = [s for s in EXPECTED_STATES if s not in upper]
    if missing:
        return [Issue(
            message="Missing trend FSM states",
            severity=Severity.ERROR,
            category=Category.ACCURACY,
            detail=f"States not found: {', '.join(missing)}",
            penalty=10 * len(missing),
        )]
    return []


def check_fsm_transitions(prompt: str) -> list[Issue]:
    missing = []
    for src, dst in EXPECTED_TRANSITIONS:
        patterns = [f"{src}.*?→.*?{dst}", f"{src}.*?->.*?{dst}", f"{src}.*?to.*?{dst}"]
        if not any(re.search(p, prompt, re.IGNORECASE) for p in patterns):
            missing.append(f"{src} → {dst}")
    if missing:
        return [Issue(
            message="Missing trend FSM transitions",
            severity=Severity.WARNING,
            category=Category.ACCURACY,
            detail=f"Transitions not documented: {', '.join(missing)}",
            penalty=5 * len(missing),
        )]
    return []


# ---------------------------------------------------------------------------
# 4. RISK MANAGEMENT
# ---------------------------------------------------------------------------

def check_trailing_stop(prompt: str) -> list[Issue]:
    lower = prompt.lower()
    has_trail = any(k in lower for k in ["trailing stop", "trail_stop", "trailing exit", "chandelier"])
    if not has_trail:
        return [Issue(
            message="No trailing stop mechanism defined",
            severity=Severity.ERROR,
            category=Category.ACCURACY,
            detail="Trend-following systems must define trailing stop logic to protect profits.",
            penalty=15,
        )]
    return []


def check_position_sizing(prompt: str) -> list[Issue]:
    lower = prompt.lower()
    has_sizing = any(k in lower for k in ["position size", "position_size", "risk per trade", "kelly", "fixed fractional"])
    if not has_sizing:
        return [Issue(
            message="No position sizing rules",
            severity=Severity.WARNING,
            category=Category.ACCURACY,
            detail="Trend systems must define position sizing relative to trend strength.",
            penalty=10,
        )]
    return []


# ---------------------------------------------------------------------------
# 5. DETERMINISM & GOVERNANCE
# ---------------------------------------------------------------------------

JUDGMENT_WORDS = [
    "probably", "likely", "seems", "appears", "might", "could be",
    "use your judgment", "discretion", "feel free", "up to you",
    "as appropriate", "if you think", "in your opinion",
]


def check_determinism(prompt: str) -> list[Issue]:
    lower = prompt.lower()
    found = [w for w in JUDGMENT_WORDS if w in lower]
    if found:
        return [Issue(
            message="Non-deterministic language in trend system",
            severity=Severity.ERROR, category=Category.ACCURACY,
            detail=f"Judgment words: {', '.join(repr(w) for w in found)}.",
            penalty=10 * len(found),
        )]
    return []


def check_halt_conditions(prompt: str) -> list[Issue]:
    lower = prompt.lower()
    has_halt = any(w in lower for w in ["halt", "session_lock", "max_loss", "daily limit"])
    has_data_check = any(w in lower for w in ["missing", "critical", "data health", "data contract"])
    issues = []
    if not has_halt:
        issues.append(Issue(message="No halt/loss limit defined", severity=Severity.ERROR,
                            category=Category.ACCURACY, detail="Must define maximum loss halt.", penalty=20))
    if not has_data_check:
        issues.append(Issue(message="No data health check", severity=Severity.WARNING,
                            category=Category.ACCURACY, detail="Verify data integrity before computing.", penalty=10))
    return issues


def check_output_format_section(prompt: str) -> list[Issue]:
    if "output format" not in prompt.lower():
        return [Issue(message="No output format section", severity=Severity.WARNING,
                      category=Category.STRUCTURE, detail="Define exact output format.", penalty=8)]
    return []


def check_governance_entries(prompt: str) -> list[Issue]:
    gov = re.findall(r"GOV-[\w-]+", prompt)
    if not gov:
        return [Issue(message="No governance entries", severity=Severity.INFO,
                      category=Category.STRUCTURE, detail="Governance entries expected.", penalty=3)]
    issues = []
    for eid in set(gov):
        m = re.search(re.escape(eid) + r".*?(?=GOV-|LOCK|FREEZE|$)", prompt, re.DOTALL)
        if m:
            b = m.group(0).lower()
            mf = []
            if "before:" not in b and "change:" not in b: mf.append("Before")
            if "after:" not in b and "change:" not in b: mf.append("After")
            if "rationale:" not in b and "reason:" not in b: mf.append("Rationale")
            if mf:
                issues.append(Issue(message=f"Governance {eid} missing fields", severity=Severity.INFO,
                                    category=Category.STRUCTURE, detail=f"Missing: {', '.join(mf)}", penalty=2))
    return issues


ALL_VORTEX_RULES = [
    check_section_completeness, check_freeze_declaration,
    check_formula_definitions, check_ema_crossover, check_trend_strength,
    check_fsm_states, check_fsm_transitions,
    check_trailing_stop, check_position_sizing,
    check_determinism, check_halt_conditions,
    check_output_format_section, check_governance_entries,
]
