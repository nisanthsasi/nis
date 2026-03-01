"""Domain-specific validation rules for PRISM — Options/Greeks Trading Systems.

Deterministic checks for:
- Greeks formulas (Delta, Gamma, Theta, Vega, Rho)
- Implied volatility surface consistency
- Strategy payoff definitions (spreads, straddles, iron condors)
- Options FSM (SCANNING → PRICED → LEGGED_IN → MANAGING → CLOSED)
- Expiry and assignment risk checks
"""

import re
from prompt_validator.result import Issue, Severity, Category


def _find_sections(prompt: str) -> dict[str, str]:
    pattern = re.compile(r"SECTION\s+(\d+)\s*[—–-]\s*(.*?)(?=SECTION\s+\d+|LOCK STATEMENT|FREEZE|$)", re.DOTALL)
    return {int(m.group(1)): m.group(2).strip() for m in pattern.finditer(prompt)}


REQUIRED_SECTIONS = {
    0: "AXIOMS",
    1: "DATA CONTRACT",
    2: "GREEKS ENGINE",
    3: "VOLATILITY SURFACE",
    4: "STRATEGY DEFINITIONS",
    5: "ENTRY RULES",
    6: "POSITION SIZING",
    7: "ADJUSTMENT RULES",
    8: "EXIT RULES",
    9: "FSM",
    10: "RISK MANAGEMENT",
    11: "OUTPUT FORMAT",
    12: "GOVERNANCE",
}


def check_section_completeness(prompt: str) -> list[Issue]:
    sections = _find_sections(prompt)
    missing = [f"Section {n} ({l})" for n, l in REQUIRED_SECTIONS.items() if n not in sections]
    if missing:
        return [Issue(message="Missing critical options sections", severity=Severity.ERROR,
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
    ("DELTA", r"DELTA\s*="),
    ("GAMMA", r"GAMMA\s*="),
    ("THETA", r"THETA\s*="),
    ("VEGA", r"VEGA\s*="),
    ("IV_RANK", r"IV_RANK\s*="),
    ("POP", r"POP\s*="),
    ("MAX_LOSS", r"MAX_LOSS\s*="),
    ("BREAKEVEN", r"BREAKEVEN\s*="),
]


def check_formula_definitions(prompt: str) -> list[Issue]:
    missing = [n for n, p in EXPECTED_FORMULAS if not re.search(p, prompt)]
    if missing:
        return [Issue(message="Missing options formula definitions", severity=Severity.ERROR,
                      category=Category.ACCURACY, detail=f"Not defined: {', '.join(missing)}", penalty=10 * len(missing))]
    return []


def check_greeks_coverage(prompt: str) -> list[Issue]:
    lower = prompt.lower()
    greeks = ["delta", "gamma", "theta", "vega", "rho"]
    found = [g for g in greeks if g in lower]
    if len(found) < 4:
        return [Issue(message="Insufficient Greeks coverage", severity=Severity.WARNING,
                      category=Category.ACCURACY, detail=f"Found {len(found)}/5: {', '.join(found)}.", penalty=5 * (5 - len(found)))]
    return []


def check_iv_surface(prompt: str) -> list[Issue]:
    lower = prompt.lower()
    has_iv = any(k in lower for k in ["implied volatility", "iv surface", "vol surface", "iv_rank", "iv skew", "vol smile"])
    if not has_iv:
        return [Issue(message="No implied volatility surface defined", severity=Severity.ERROR,
                      category=Category.ACCURACY, detail="Options systems must define IV surface or rank methodology.", penalty=15)]
    return []


def check_strategy_definitions(prompt: str) -> list[Issue]:
    lower = prompt.lower()
    strategies = ["spread", "straddle", "strangle", "iron condor", "butterfly", "vertical", "calendar"]
    found = [s for s in strategies if s in lower]
    if not found:
        return [Issue(message="No options strategy definitions", severity=Severity.WARNING,
                      category=Category.ACCURACY, detail="Define at least one multi-leg strategy.", penalty=10)]
    return []


EXPECTED_STATES = {"SCANNING", "PRICED", "LEGGED_IN", "MANAGING", "ADJUSTING", "CLOSED"}

EXPECTED_TRANSITIONS = [
    ("SCANNING", "PRICED"),
    ("PRICED", "LEGGED_IN"),
    ("LEGGED_IN", "MANAGING"),
    ("MANAGING", "ADJUSTING"),
    ("MANAGING", "CLOSED"),
]


def check_fsm_states(prompt: str) -> list[Issue]:
    upper = prompt.upper()
    missing = [s for s in EXPECTED_STATES if s not in upper]
    if missing:
        return [Issue(message="Missing options FSM states", severity=Severity.ERROR,
                      category=Category.ACCURACY, detail=f"Not found: {', '.join(missing)}", penalty=10 * len(missing))]
    return []


def check_fsm_transitions(prompt: str) -> list[Issue]:
    missing = []
    for s, d in EXPECTED_TRANSITIONS:
        if not any(re.search(f"{s}.*?(?:→|->|to).*?{d}", prompt, re.IGNORECASE) for _ in [1]):
            missing.append(f"{s} → {d}")
    if missing:
        return [Issue(message="Missing options FSM transitions", severity=Severity.WARNING,
                      category=Category.ACCURACY, detail=f"Not documented: {', '.join(missing)}", penalty=5 * len(missing))]
    return []


def check_expiry_risk(prompt: str) -> list[Issue]:
    lower = prompt.lower()
    has_expiry = any(k in lower for k in ["expir", "dte", "days to expiration", "assignment risk", "early exercise"])
    if not has_expiry:
        return [Issue(message="No expiration/assignment risk handling", severity=Severity.WARNING,
                      category=Category.ACCURACY, detail="Options systems must define DTE and assignment risk rules.", penalty=10)]
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
    if not any(w in lower for w in ["halt", "max_loss", "daily limit", "portfolio limit"]):
        issues.append(Issue(message="No halt/loss limit", severity=Severity.ERROR, category=Category.ACCURACY, penalty=20))
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


ALL_PRISM_RULES = [
    check_section_completeness, check_freeze_declaration,
    check_formula_definitions, check_greeks_coverage, check_iv_surface,
    check_strategy_definitions, check_fsm_states, check_fsm_transitions,
    check_expiry_risk, check_determinism, check_halt_conditions,
    check_output_format, check_governance_entries,
]
