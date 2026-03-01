"""Domain-specific validation rules for FLUX — Scalping/High-Frequency Trading Systems.

Deterministic checks for:
- Tick-level data requirements and latency budgets
- Microstructure formulas (spread, order flow imbalance, VWAP slippage)
- Scalping FSM (IDLE → STALKING → STRIKE → FILL → SCALP_EXIT)
- Fill quality and slippage tolerance
- Rapid-fire risk limits (max trades/minute, daily loss)
"""

import re
from prompt_validator.result import Issue, Severity, Category


def _find_sections(prompt: str) -> dict[str, str]:
    pattern = re.compile(r"SECTION\s+(\d+)\s*[—–-]\s*(.*?)(?=SECTION\s+\d+|LOCK STATEMENT|FREEZE|$)", re.DOTALL)
    return {int(m.group(1)): m.group(2).strip() for m in pattern.finditer(prompt)}


REQUIRED_SECTIONS = {
    0: "AXIOMS",
    1: "DATA CONTRACT",
    2: "MICROSTRUCTURE",
    3: "ORDER FLOW",
    4: "ENTRY RULES",
    5: "FILL QUALITY",
    6: "EXIT RULES",
    7: "FSM",
    8: "RATE LIMITS",
    9: "RISK MANAGEMENT",
    10: "OUTPUT FORMAT",
    11: "GOVERNANCE",
}


def check_section_completeness(prompt: str) -> list[Issue]:
    sections = _find_sections(prompt)
    missing = [f"Section {n} ({l})" for n, l in REQUIRED_SECTIONS.items() if n not in sections]
    if missing:
        return [Issue(message="Missing critical scalping sections", severity=Severity.ERROR,
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
    ("SPREAD", r"SPREAD\s*="),
    ("OFI", r"OFI\s*="),
    ("VWAP_SLIP", r"VWAP_SLIP\s*="),
    ("FILL_RATIO", r"FILL_RATIO\s*="),
    ("TICK_PNL", r"TICK_PNL\s*="),
    ("LATENCY_BUDGET", r"LATENCY_BUDGET\s*="),
    ("EDGE_PER_TRADE", r"EDGE_PER_TRADE\s*="),
    ("TRADE_RATE", r"TRADE_RATE\s*="),
]


def check_formula_definitions(prompt: str) -> list[Issue]:
    missing = [n for n, p in EXPECTED_FORMULAS if not re.search(p, prompt)]
    if missing:
        return [Issue(message="Missing scalping formula definitions", severity=Severity.ERROR,
                      category=Category.ACCURACY, detail=f"Not defined: {', '.join(missing)}", penalty=10 * len(missing))]
    return []


def check_latency_spec(prompt: str) -> list[Issue]:
    lower = prompt.lower()
    has_latency = any(k in lower for k in ["latency", "microsecond", "millisecond", "tick-to-trade", "co-location"])
    if not has_latency:
        return [Issue(message="No latency budget specification", severity=Severity.ERROR,
                      category=Category.ACCURACY, detail="Scalping systems must define latency budgets.", penalty=15)]
    return []


def check_spread_analysis(prompt: str) -> list[Issue]:
    lower = prompt.lower()
    has_spread = any(k in lower for k in ["bid-ask", "spread", "best bid", "best ask", "order book"])
    if not has_spread:
        return [Issue(message="No spread/order book analysis", severity=Severity.WARNING,
                      category=Category.ACCURACY, detail="HFT systems need bid-ask spread analysis.", penalty=10)]
    return []


EXPECTED_STATES = {"IDLE", "STALKING", "STRIKE", "FILL", "SCALP_EXIT", "RATE_LIMITED"}

EXPECTED_TRANSITIONS = [
    ("IDLE", "STALKING"),
    ("STALKING", "STRIKE"),
    ("STRIKE", "FILL"),
    ("FILL", "SCALP_EXIT"),
    ("SCALP_EXIT", "IDLE"),
]


def check_fsm_states(prompt: str) -> list[Issue]:
    upper = prompt.upper()
    missing = [s for s in EXPECTED_STATES if s not in upper]
    if missing:
        return [Issue(message="Missing scalping FSM states", severity=Severity.ERROR,
                      category=Category.ACCURACY, detail=f"Not found: {', '.join(missing)}", penalty=10 * len(missing))]
    return []


def check_fsm_transitions(prompt: str) -> list[Issue]:
    missing = []
    for s, d in EXPECTED_TRANSITIONS:
        if not any(re.search(f"{s}.*?(?:→|->|to).*?{d}", prompt, re.IGNORECASE) for _ in [1]):
            missing.append(f"{s} → {d}")
    if missing:
        return [Issue(message="Missing scalping FSM transitions", severity=Severity.WARNING,
                      category=Category.ACCURACY, detail=f"Not documented: {', '.join(missing)}", penalty=5 * len(missing))]
    return []


def check_rate_limits(prompt: str) -> list[Issue]:
    lower = prompt.lower()
    has_rate = any(k in lower for k in ["rate limit", "trades per minute", "max orders", "throttle", "circuit breaker"])
    if not has_rate:
        return [Issue(message="No trade rate limits defined", severity=Severity.ERROR,
                      category=Category.ACCURACY, detail="Scalping must define max trades/minute and circuit breakers.", penalty=15)]
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
    if not any(w in lower for w in ["halt", "kill switch", "max_loss", "daily limit", "circuit breaker"]):
        issues.append(Issue(message="No halt/kill switch", severity=Severity.ERROR, category=Category.ACCURACY, penalty=20))
    if not any(w in lower for w in ["missing", "critical", "data contract", "feed health"]):
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


ALL_FLUX_RULES = [
    check_section_completeness, check_freeze_declaration,
    check_formula_definitions, check_latency_spec, check_spread_analysis,
    check_fsm_states, check_fsm_transitions, check_rate_limits,
    check_determinism, check_halt_conditions,
    check_output_format, check_governance_entries,
]
