"""Domain-specific validation rules for NEXUS — Mean Reversion Systems.

Deterministic checks for:
- Mean/fair-value calculations (VWAP, Bollinger, Z-score)
- Oversold/overbought threshold definitions
- Reversion entry FSM (NEUTRAL → DEVIATED → ENTRY → REVERTING → TARGET)
- Risk management (max adverse excursion, time-based stops)
- Correlation and regime filtering
"""

import re
from prompt_validator.result import Issue, Severity, Category


def _find_sections(prompt: str) -> dict[str, str]:
    pattern = re.compile(r"SECTION\s+(\d+)\s*[—–-]\s*(.*?)(?=SECTION\s+\d+|LOCK STATEMENT|FREEZE|$)", re.DOTALL)
    return {int(m.group(1)): m.group(2).strip() for m in pattern.finditer(prompt)}


REQUIRED_SECTIONS = {
    0: "AXIOMS",
    1: "DATA CONTRACT",
    2: "FAIR VALUE CALCULATION",
    3: "DEVIATION SCORING",
    4: "ENTRY RULES",
    5: "POSITION SIZING",
    6: "EXIT RULES",
    7: "TIME STOPS",
    8: "FSM",
    9: "RISK MANAGEMENT",
    10: "OUTPUT FORMAT",
    11: "GOVERNANCE",
}


def check_section_completeness(prompt: str) -> list[Issue]:
    sections = _find_sections(prompt)
    missing = [f"Section {n} ({l})" for n, l in REQUIRED_SECTIONS.items() if n not in sections]
    if missing:
        return [Issue(message="Missing critical mean-reversion sections", severity=Severity.ERROR,
                      category=Category.STRUCTURE, detail=f"Missing: {', '.join(missing)}", penalty=15 * len(missing))]
    return []


def check_freeze_declaration(prompt: str) -> list[Issue]:
    lower = prompt.lower()
    issues = []
    if "freeze declaration" not in lower and "lock statement" not in lower:
        issues.append(Issue(message="No freeze/lock declaration", severity=Severity.WARNING,
                            category=Category.STRUCTURE, detail="Mean reversion parameters must be locked.", penalty=8))
    if "governance" not in lower:
        issues.append(Issue(message="No governance section", severity=Severity.WARNING,
                            category=Category.STRUCTURE, penalty=8))
    return issues


EXPECTED_FORMULAS = [
    ("FAIR_VALUE", r"FAIR_VALUE\s*="),
    ("Z_SCORE", r"Z_SCORE\s*="),
    ("BOLLINGER_UPPER", r"BOLLINGER_UPPER\s*="),
    ("BOLLINGER_LOWER", r"BOLLINGER_LOWER\s*="),
    ("DEVIATION", r"DEVIATION\s*="),
    ("REVERSION_SCORE", r"REVERSION_SCORE\s*="),
    ("MAE", r"MAE\s*="),
    ("TIME_STOP", r"TIME_STOP\s*="),
]


def check_formula_definitions(prompt: str) -> list[Issue]:
    missing = [n for n, p in EXPECTED_FORMULAS if not re.search(p, prompt)]
    if missing:
        return [Issue(message="Missing mean-reversion formula definitions", severity=Severity.ERROR,
                      category=Category.ACCURACY, detail=f"Not defined: {', '.join(missing)}", penalty=10 * len(missing))]
    return []


def check_mean_definition(prompt: str) -> list[Issue]:
    lower = prompt.lower()
    has_mean = any(k in lower for k in ["vwap", "sma", "ema", "moving average", "fair value", "equilibrium"])
    if not has_mean:
        return [Issue(message="No mean/fair-value definition", severity=Severity.ERROR,
                      category=Category.ACCURACY, detail="Must define the central tendency measure.", penalty=15)]
    return []


def check_deviation_thresholds(prompt: str) -> list[Issue]:
    lower = prompt.lower()
    has_dev = any(k in lower for k in ["z-score", "z_score", "standard deviation", "sigma", "bollinger", "oversold", "overbought"])
    if not has_dev:
        return [Issue(message="No deviation/threshold bands defined", severity=Severity.WARNING,
                      category=Category.ACCURACY, detail="Need Bollinger bands or Z-score thresholds.", penalty=10)]
    return []


EXPECTED_STATES = {"NEUTRAL", "DEVIATED", "ENTRY", "REVERTING", "TARGET", "TIME_STOP"}

EXPECTED_TRANSITIONS = [
    ("NEUTRAL", "DEVIATED"),
    ("DEVIATED", "ENTRY"),
    ("ENTRY", "REVERTING"),
    ("REVERTING", "TARGET"),
    ("ENTRY", "TIME_STOP"),
]


def check_fsm_states(prompt: str) -> list[Issue]:
    upper = prompt.upper()
    missing = [s for s in EXPECTED_STATES if s not in upper]
    if missing:
        return [Issue(message="Missing reversion FSM states", severity=Severity.ERROR,
                      category=Category.ACCURACY, detail=f"Not found: {', '.join(missing)}", penalty=10 * len(missing))]
    return []


def check_fsm_transitions(prompt: str) -> list[Issue]:
    missing = []
    for s, d in EXPECTED_TRANSITIONS:
        if not any(re.search(f"{s}.*?(?:→|->|to).*?{d}", prompt, re.IGNORECASE) for _ in [1]):
            missing.append(f"{s} → {d}")
    if missing:
        return [Issue(message="Missing reversion FSM transitions", severity=Severity.WARNING,
                      category=Category.ACCURACY, detail=f"Not documented: {', '.join(missing)}", penalty=5 * len(missing))]
    return []


def check_time_stop(prompt: str) -> list[Issue]:
    lower = prompt.lower()
    if not any(k in lower for k in ["time stop", "time_stop", "time-based exit", "max bars", "max holding"]):
        return [Issue(message="No time-based stop defined", severity=Severity.WARNING,
                      category=Category.ACCURACY, detail="Mean reversion needs time stops for non-reverting trades.", penalty=10)]
    return []


JUDGMENT_WORDS = [
    "probably", "likely", "seems", "appears", "might", "could be",
    "use your judgment", "discretion", "feel free", "up to you",
    "as appropriate", "if you think", "in your opinion",
]


def check_determinism(prompt: str) -> list[Issue]:
    found = [w for w in JUDGMENT_WORDS if w in prompt.lower()]
    if found:
        return [Issue(message="Non-deterministic language in reversion system", severity=Severity.ERROR,
                      category=Category.ACCURACY, detail=f"Words: {', '.join(repr(w) for w in found)}.", penalty=10 * len(found))]
    return []


def check_halt_conditions(prompt: str) -> list[Issue]:
    lower = prompt.lower()
    issues = []
    if not any(w in lower for w in ["halt", "session_lock", "max_loss", "daily limit"]):
        issues.append(Issue(message="No halt/loss limit", severity=Severity.ERROR, category=Category.ACCURACY,
                            detail="Must define max loss halt.", penalty=20))
    if not any(w in lower for w in ["missing", "critical", "data health", "data contract"]):
        issues.append(Issue(message="No data health check", severity=Severity.WARNING, category=Category.ACCURACY,
                            detail="Verify data integrity.", penalty=10))
    return issues


def check_output_format(prompt: str) -> list[Issue]:
    if "output format" not in prompt.lower():
        return [Issue(message="No output format section", severity=Severity.WARNING,
                      category=Category.STRUCTURE, penalty=8)]
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


ALL_NEXUS_RULES = [
    check_section_completeness, check_freeze_declaration,
    check_formula_definitions, check_mean_definition, check_deviation_thresholds,
    check_fsm_states, check_fsm_transitions, check_time_stop,
    check_determinism, check_halt_conditions,
    check_output_format, check_governance_entries,
]
