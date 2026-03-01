"""Domain-specific validation rules for TITAN — Swing/Multi-day Trading Systems.

Deterministic checks for:
- Multi-timeframe analysis (daily, 4H, 1H alignment)
- Swing structure formulas (Higher Highs, Higher Lows, pivot points)
- Overnight/gap risk management
- Swing FSM (FLAT → SETUP → ENTRY → HOLDING → PARTIAL → EXIT)
- Multi-day position sizing and drawdown limits
"""

import re
from prompt_validator.result import Issue, Severity, Category


def _find_sections(prompt: str) -> dict[str, str]:
    pattern = re.compile(r"SECTION\s+(\d+)\s*[—–-]\s*(.*?)(?=SECTION\s+\d+|LOCK STATEMENT|FREEZE|$)", re.DOTALL)
    return {int(m.group(1)): m.group(2).strip() for m in pattern.finditer(prompt)}


REQUIRED_SECTIONS = {
    0: "AXIOMS",
    1: "DATA CONTRACT",
    2: "MULTI-TIMEFRAME ANALYSIS",
    3: "SWING STRUCTURE",
    4: "ENTRY RULES",
    5: "POSITION SIZING",
    6: "PARTIAL EXITS",
    7: "GAP RISK",
    8: "FSM",
    9: "RISK MANAGEMENT",
    10: "OUTPUT FORMAT",
    11: "GOVERNANCE",
}


def check_section_completeness(prompt: str) -> list[Issue]:
    sections = _find_sections(prompt)
    missing = [f"Section {n} ({l})" for n, l in REQUIRED_SECTIONS.items() if n not in sections]
    if missing:
        return [Issue(message="Missing critical swing trading sections", severity=Severity.ERROR,
                      category=Category.STRUCTURE, detail=f"Missing: {', '.join(missing)}", penalty=15 * len(missing))]
    return []


def check_freeze_declaration(prompt: str) -> list[Issue]:
    lower = prompt.lower()
    issues = []
    if "freeze declaration" not in lower and "lock statement" not in lower:
        issues.append(Issue(message="No freeze/lock declaration", severity=Severity.WARNING,
                            category=Category.STRUCTURE, penalty=8))
    if "governance" not in lower:
        issues.append(Issue(message="No governance section", severity=Severity.WARNING,
                            category=Category.STRUCTURE, penalty=8))
    return issues


EXPECTED_FORMULAS = [
    ("SWING_HIGH", r"SWING_HIGH\s*="),
    ("SWING_LOW", r"SWING_LOW\s*="),
    ("PIVOT", r"PIVOT\s*="),
    ("ATR_DAILY", r"ATR_DAILY\s*="),
    ("R_MULTIPLE", r"R_MULTIPLE\s*="),
    ("GAP_RISK", r"GAP_RISK\s*="),
    ("DRAWDOWN", r"DRAWDOWN\s*="),
    ("PARTIAL_SIZE", r"PARTIAL_SIZE\s*="),
]


def check_formula_definitions(prompt: str) -> list[Issue]:
    missing = [n for n, p in EXPECTED_FORMULAS if not re.search(p, prompt)]
    if missing:
        return [Issue(message="Missing swing formula definitions", severity=Severity.ERROR,
                      category=Category.ACCURACY, detail=f"Not defined: {', '.join(missing)}", penalty=10 * len(missing))]
    return []


def check_multi_timeframe(prompt: str) -> list[Issue]:
    lower = prompt.lower()
    timeframes = ["daily", "4h", "4-hour", "1h", "1-hour", "weekly", "higher timeframe"]
    found = [t for t in timeframes if t in lower]
    if len(found) < 2:
        return [Issue(message="Insufficient multi-timeframe analysis", severity=Severity.WARNING,
                      category=Category.ACCURACY, detail=f"Found {len(found)} timeframes. Swing trading requires 2+ aligned timeframes.", penalty=10)]
    return []


def check_swing_structure(prompt: str) -> list[Issue]:
    lower = prompt.lower()
    has_structure = any(k in lower for k in ["higher high", "higher low", "lower high", "lower low", "pivot", "swing point"])
    if not has_structure:
        return [Issue(message="No swing structure definitions", severity=Severity.WARNING,
                      category=Category.ACCURACY, detail="Define HH, HL, LH, LL or pivot point methodology.", penalty=10)]
    return []


def check_gap_risk(prompt: str) -> list[Issue]:
    lower = prompt.lower()
    has_gap = any(k in lower for k in ["gap risk", "overnight", "gap_risk", "gap exposure", "pre-market"])
    if not has_gap:
        return [Issue(message="No overnight/gap risk management", severity=Severity.ERROR,
                      category=Category.ACCURACY, detail="Multi-day systems must address overnight gap risk.", penalty=15)]
    return []


EXPECTED_STATES = {"FLAT", "SETUP", "ENTRY", "HOLDING", "PARTIAL", "EXIT"}

EXPECTED_TRANSITIONS = [
    ("FLAT", "SETUP"),
    ("SETUP", "ENTRY"),
    ("ENTRY", "HOLDING"),
    ("HOLDING", "PARTIAL"),
    ("PARTIAL", "EXIT"),
]


def check_fsm_states(prompt: str) -> list[Issue]:
    upper = prompt.upper()
    missing = [s for s in EXPECTED_STATES if s not in upper]
    if missing:
        return [Issue(message="Missing swing FSM states", severity=Severity.ERROR,
                      category=Category.ACCURACY, detail=f"Not found: {', '.join(missing)}", penalty=10 * len(missing))]
    return []


def check_fsm_transitions(prompt: str) -> list[Issue]:
    missing = []
    for s, d in EXPECTED_TRANSITIONS:
        if not any(re.search(f"{s}.*?(?:→|->|to).*?{d}", prompt, re.IGNORECASE) for _ in [1]):
            missing.append(f"{s} → {d}")
    if missing:
        return [Issue(message="Missing swing FSM transitions", severity=Severity.WARNING,
                      category=Category.ACCURACY, detail=f"Not documented: {', '.join(missing)}", penalty=5 * len(missing))]
    return []


def check_partial_exits(prompt: str) -> list[Issue]:
    lower = prompt.lower()
    has_partial = any(k in lower for k in ["partial exit", "partial_size", "scale out", "partial profit", "take partial"])
    if not has_partial:
        return [Issue(message="No partial exit strategy", severity=Severity.WARNING,
                      category=Category.ACCURACY, detail="Swing systems should define partial profit-taking rules.", penalty=10)]
    return []


JUDGMENT_WORDS = [
    "probably", "likely", "seems", "appears", "might", "could be",
    "use your judgment", "discretion", "feel free", "up to you",
]


def check_determinism(prompt: str) -> list[Issue]:
    found = [w for w in JUDGMENT_WORDS if w in prompt.lower()]
    if found:
        return [Issue(message="Non-deterministic language", severity=Severity.ERROR,
                      category=Category.ACCURACY, detail=f"Words: {', '.join(repr(w) for w in found)}.", penalty=10 * len(found))]
    return []


def check_halt_conditions(prompt: str) -> list[Issue]:
    lower = prompt.lower()
    issues = []
    if not any(w in lower for w in ["halt", "max_loss", "max drawdown", "weekly limit"]):
        issues.append(Issue(message="No halt/drawdown limit", severity=Severity.ERROR, category=Category.ACCURACY, penalty=20))
    if not any(w in lower for w in ["missing", "critical", "data contract"]):
        issues.append(Issue(message="No data health check", severity=Severity.WARNING, category=Category.ACCURACY, penalty=10))
    return issues


def check_output_format(prompt: str) -> list[Issue]:
    if "output format" not in prompt.lower():
        return [Issue(message="No output format", severity=Severity.WARNING, category=Category.STRUCTURE, penalty=8)]
    return []


def check_governance_entries(prompt: str) -> list[Issue]:
    gov = re.findall(r"GOV-[\w-]+", prompt)
    if not gov:
        return [Issue(message="No governance entries", severity=Severity.INFO, category=Category.STRUCTURE, penalty=3)]
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


ALL_TITAN_RULES = [
    check_section_completeness, check_freeze_declaration,
    check_formula_definitions, check_multi_timeframe, check_swing_structure,
    check_gap_risk, check_fsm_states, check_fsm_transitions,
    check_partial_exits, check_determinism, check_halt_conditions,
    check_output_format, check_governance_entries,
]
