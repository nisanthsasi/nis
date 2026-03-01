"""Domain-specific validation rules for TITAN — Swing/Multi-day Trading Master System.

Deterministic checks for:
- 26-section structural completeness (Sections 0–25)
- Multi-timeframe alignment (daily EMA50/200, 4H EMA21, 1H EMA9/21)
- Swing structure formulas (HH/HL/LH/LL, pivots, ATR, RSI, ADX)
- Composite scores (SCS, TES, TAS, PQS — bin-weighted {100,50,0})
- Overnight/gap risk management (gap classification, weekend hold criteria)
- Partial exit engine (3-tier deterministic scale-out)
- Weekly Meta Governor (WMG with bootstrap tiers)
- 12-gate entry sequence
- FSM (FLAT → SETUP → ENTRY → HOLDING → PARTIAL → EXIT + locks)
- Position sizing and drawdown limits
- Governance patch discipline
"""

import re
from prompt_validator.result import Issue, Severity, Category


def _find_sections(prompt: str) -> dict[str, str]:
    pattern = re.compile(r"SECTION\s+(\d+)\s*[—–-]\s*(.*?)(?=SECTION\s+\d+|LOCK STATEMENT|FREEZE|$)", re.DOTALL)
    return {int(m.group(1)): m.group(2).strip() for m in pattern.finditer(prompt)}


# ---------------------------------------------------------------------------
# 1. STRUCTURAL COMPLETENESS
# ---------------------------------------------------------------------------

REQUIRED_SECTIONS = {
    0: "AXIOMS",
    1: "DATA CONTRACT",
    2: "CORE MEASUREMENTS",
    3: "SESSION GOVERNOR",
    4: "SWING PIVOTS",
    5: "MARKET STRUCTURE",
    6: "MULTI-TIMEFRAME ALIGNMENT",
    7: "TREND REGIME",
    8: "PULLBACK QUALITY",
    9: "VOLATILITY REGIME",
    10: "MOMENTUM CONFIRMATION",
    11: "VOLUME PROFILE",
    12: "SWING CONFIDENCE SCORE",
    13: "TRADE ELIGIBILITY SCORE",
    14: "SETUPS",
    15: "ENTRY RULES",
    16: "POSITION SIZING",
    17: "TARGETS",
    18: "PARTIAL EXIT",
    19: "GAP RISK",
    20: "RISK DEFINITIONS",
    21: "COOLDOWN",
    22: "WEEKLY META GOVERNOR",
    23: "FSM",
    24: "OUTPUT FORMAT",
    25: "GOVERNANCE",
}


def check_section_completeness(prompt: str) -> list[Issue]:
    sections = _find_sections(prompt)
    missing = [f"Section {n} ({l})" for n, l in REQUIRED_SECTIONS.items() if n not in sections]
    if missing:
        return [Issue(message="Missing critical swing trading sections", severity=Severity.ERROR,
                      category=Category.STRUCTURE, detail=f"Missing: {', '.join(missing)}", penalty=5 * len(missing))]
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


# ---------------------------------------------------------------------------
# 2. FORMULA & THRESHOLD INTEGRITY
# ---------------------------------------------------------------------------

EXPECTED_FORMULAS = [
    ("SWING_HIGH", r"SWING_HIGH\s*=|Swing High at bar"),
    ("SWING_LOW", r"SWING_LOW\s*=|Swing Low at bar"),
    ("PIVOT", r"PIVOT\s*="),
    ("ATR_DAILY", r"ATR_DAILY\s*="),
    ("ATR_4H", r"ATR_4H\s*="),
    ("ATR_1H", r"ATR_1H\s*="),
    ("EMA_50_DAILY", r"EMA_50_DAILY\s*="),
    ("EMA_200_DAILY", r"EMA_200_DAILY\s*="),
    ("R_TRADE", r"R_TRADE\s*="),
    ("R_MULTIPLE", r"R_MULTIPLE\s*=|R_AT_T"),
    ("GAP_RISK", r"GAP_RISK\s*="),
    ("DRAWDOWN", r"DRAWDOWN\s*="),
    ("PARTIAL_SIZE", r"PARTIAL_SIZE"),
    ("POSITION_SIZE", r"POSITION_SIZE\s*="),
    ("TAS", r"TAS[\s_]"),
    ("SCS", r"SCS\s*="),
    ("TES", r"TES\s*="),
    ("PQS", r"PQS\s*="),
    ("Exp_W", r"Exp_W\s*="),
]


def check_formula_definitions(prompt: str) -> list[Issue]:
    missing = [n for n, p in EXPECTED_FORMULAS if not re.search(p, prompt)]
    if missing:
        return [Issue(message="Missing swing formula definitions", severity=Severity.ERROR,
                      category=Category.ACCURACY, detail=f"Not defined: {', '.join(missing)}", penalty=4 * len(missing))]
    return []


# ---------------------------------------------------------------------------
# 3. MULTI-TIMEFRAME ALIGNMENT
# ---------------------------------------------------------------------------

def check_multi_timeframe(prompt: str) -> list[Issue]:
    lower = prompt.lower()
    timeframes = ["daily", "4h", "4-hour", "1h", "1-hour"]
    found = [t for t in timeframes if t in lower]
    if len(found) < 3:
        return [Issue(message="Insufficient multi-timeframe analysis", severity=Severity.WARNING,
                      category=Category.ACCURACY, detail=f"Found {len(found)} timeframes. TITAN requires daily + 4H + 1H.", penalty=10)]
    return []


def check_ema_alignment(prompt: str) -> list[Issue]:
    """Verify EMA crossover alignment rules are documented."""
    lower = prompt.lower()
    has_ema50_200 = "ema_50" in lower and "ema_200" in lower
    has_4h_ema = "ema_21_4h" in lower or "ema_21" in lower
    has_1h_ema = "ema_9_1h" in lower or "ema_21_1h" in lower
    issues = []
    if not has_ema50_200:
        issues.append(Issue(message="Missing daily EMA 50/200 alignment", severity=Severity.WARNING,
                            category=Category.ACCURACY, penalty=8))
    if not has_4h_ema:
        issues.append(Issue(message="Missing 4H EMA reference", severity=Severity.WARNING,
                            category=Category.ACCURACY, penalty=5))
    if not has_1h_ema:
        issues.append(Issue(message="Missing 1H EMA reference", severity=Severity.WARNING,
                            category=Category.ACCURACY, penalty=5))
    return issues


# ---------------------------------------------------------------------------
# 4. SWING STRUCTURE
# ---------------------------------------------------------------------------

def check_swing_structure(prompt: str) -> list[Issue]:
    lower = prompt.lower()
    has_hh_hl = "higher high" in lower and "higher low" in lower
    has_lh_ll = "lower high" in lower and "lower low" in lower
    has_bos = "break_of_structure" in lower or "break of structure" in lower
    issues = []
    if not has_hh_hl or not has_lh_ll:
        issues.append(Issue(message="Incomplete swing structure definitions", severity=Severity.WARNING,
                            category=Category.ACCURACY, detail="Define HH, HL, LH, LL for trend classification.", penalty=8))
    if not has_bos:
        issues.append(Issue(message="No break-of-structure detection", severity=Severity.INFO,
                            category=Category.ACCURACY, detail="BOS helps confirm trend continuation/reversal.", penalty=3))
    return issues


# ---------------------------------------------------------------------------
# 5. GAP RISK
# ---------------------------------------------------------------------------

def check_gap_risk(prompt: str) -> list[Issue]:
    lower = prompt.lower()
    has_gap = any(k in lower for k in ["gap risk", "overnight", "gap_risk", "gap exposure", "pre-market", "weekend hold"])
    has_gap_classification = any(k in lower for k in ["gap_small", "gap_medium", "gap_large", "gap_extreme"])
    issues = []
    if not has_gap:
        issues.append(Issue(message="No overnight/gap risk management", severity=Severity.ERROR,
                            category=Category.ACCURACY, detail="Multi-day systems must address overnight gap risk.", penalty=15))
    if not has_gap_classification:
        issues.append(Issue(message="No gap size classification", severity=Severity.INFO,
                            category=Category.ACCURACY, detail="Define gap size tiers for graduated response.", penalty=3))
    return issues


# ---------------------------------------------------------------------------
# 6. PARTIAL EXITS
# ---------------------------------------------------------------------------

def check_partial_exits(prompt: str) -> list[Issue]:
    lower = prompt.lower()
    has_partial = any(k in lower for k in ["partial_size", "scale out", "scale-out", "partial exit", "tier 1", "tier 2", "tier 3"])
    has_trail = any(k in lower for k in ["trail_stop", "trailing stop", "trail remainder", "ratchet"])
    issues = []
    if not has_partial:
        issues.append(Issue(message="No partial exit strategy", severity=Severity.WARNING,
                            category=Category.ACCURACY, detail="Swing systems should define deterministic scale-out rules.", penalty=10))
    if not has_trail:
        issues.append(Issue(message="No trailing stop mechanism", severity=Severity.INFO,
                            category=Category.ACCURACY, detail="Define ATR-based trailing stop for remainder position.", penalty=3))
    return issues


# ---------------------------------------------------------------------------
# 7. COMPOSITE SCORES
# ---------------------------------------------------------------------------

def check_composite_scores(prompt: str) -> list[Issue]:
    """Verify SCS, TES, TAS, PQS are defined with component weights."""
    upper = prompt.upper()
    issues = []
    for score_name in ["SCS", "TES", "TAS", "PQS"]:
        if score_name not in upper:
            issues.append(Issue(message=f"Missing composite score: {score_name}", severity=Severity.WARNING,
                                category=Category.ACCURACY, detail=f"{score_name} not found in prompt.", penalty=5))
    # Check for bin-weighted scoring pattern
    if not re.search(r"\{100,50,0\}|scored.*100.*50.*0|bins.*100.*50.*0", prompt, re.IGNORECASE):
        issues.append(Issue(message="No bin-weighted scoring pattern", severity=Severity.INFO,
                            category=Category.ACCURACY, detail="Composite scores should use {100,50,0} bin weights.", penalty=3))
    return issues


# ---------------------------------------------------------------------------
# 8. FSM VALIDATION
# ---------------------------------------------------------------------------

EXPECTED_STATES = {"FLAT", "SETUP", "ENTRY", "HOLDING", "PARTIAL", "EXIT"}

LOCK_STATES = {"DAY_LOCK", "WEEKLY_LOCK", "WMG_LOCK", "SYSTEM_HALT"}

EXPECTED_TRANSITIONS = [
    ("FLAT", "SETUP"),
    ("SETUP", "ENTRY"),
    ("SETUP", "FLAT"),
    ("ENTRY", "HOLDING"),
    ("HOLDING", "PARTIAL"),
    ("PARTIAL", "EXIT"),
    ("EXIT", "FLAT"),
]


def check_fsm_states(prompt: str) -> list[Issue]:
    upper = prompt.upper()
    missing_core = [s for s in EXPECTED_STATES if s not in upper]
    missing_locks = [s for s in LOCK_STATES if s not in upper]
    issues = []
    if missing_core:
        issues.append(Issue(message="Missing core FSM states", severity=Severity.ERROR,
                            category=Category.ACCURACY, detail=f"Not found: {', '.join(missing_core)}", penalty=8 * len(missing_core)))
    if missing_locks:
        issues.append(Issue(message="Missing lock/halt FSM states", severity=Severity.WARNING,
                            category=Category.ACCURACY, detail=f"Not found: {', '.join(missing_locks)}", penalty=3 * len(missing_locks)))
    return issues


def check_fsm_transitions(prompt: str) -> list[Issue]:
    missing = []
    for s, d in EXPECTED_TRANSITIONS:
        if not any(re.search(f"{s}.*?(?:→|->|to).*?{d}", prompt, re.IGNORECASE) for _ in [1]):
            missing.append(f"{s} → {d}")
    if missing:
        return [Issue(message="Missing swing FSM transitions", severity=Severity.WARNING,
                      category=Category.ACCURACY, detail=f"Not documented: {', '.join(missing)}", penalty=3 * len(missing))]
    return []


# ---------------------------------------------------------------------------
# 9. ENTRY GATE SEQUENCE
# ---------------------------------------------------------------------------

def check_entry_gates(prompt: str) -> list[Issue]:
    """Verify a multi-gate entry sequence is defined."""
    lower = prompt.lower()
    gate_keywords = ["gate 1", "gate 2", "gate 3", "gate sequence", "all gates must pass"]
    has_gates = any(k in lower for k in gate_keywords)
    if not has_gates:
        return [Issue(message="No entry gate sequence", severity=Severity.WARNING,
                      category=Category.STRUCTURE, detail="Define a sequential gate check for entry validation.", penalty=5)]
    return []


# ---------------------------------------------------------------------------
# 10. WEEKLY META GOVERNOR
# ---------------------------------------------------------------------------

def check_weekly_meta_governor(prompt: str) -> list[Issue]:
    """Verify WMG/MEG-equivalent is defined for swing systems."""
    lower = prompt.lower()
    has_wmg = any(k in lower for k in ["weekly meta governor", "wmg", "exp_w", "meta governor", "meta expectancy"])
    has_bootstrap = "bootstrap" in lower
    issues = []
    if not has_wmg:
        issues.append(Issue(message="No weekly meta governor", severity=Severity.WARNING,
                            category=Category.ACCURACY, detail="Swing systems need a rolling expectancy governor.", penalty=8))
    if has_wmg and not has_bootstrap:
        issues.append(Issue(message="No bootstrap tiers for meta governor", severity=Severity.INFO,
                            category=Category.ACCURACY, detail="Define bootstrap behavior when trade count is low.", penalty=3))
    return issues


# ---------------------------------------------------------------------------
# 11. DETERMINISM & SAFETY
# ---------------------------------------------------------------------------

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
    if not any(w in lower for w in ["halt", "system_halt", "weekly_lock", "max drawdown"]):
        issues.append(Issue(message="No halt/drawdown limit", severity=Severity.ERROR, category=Category.ACCURACY, penalty=15))
    if not any(w in lower for w in ["missing", "critical", "data contract", "data health"]):
        issues.append(Issue(message="No data health check", severity=Severity.WARNING, category=Category.ACCURACY, penalty=8))
    return issues


# ---------------------------------------------------------------------------
# 12. OUTPUT FORMAT & GOVERNANCE
# ---------------------------------------------------------------------------

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
        m = re.search(re.escape(eid) + r".*?(?=GOV-|LOCK STATEMENT|FREEZE DECLARATION|$)", prompt, re.DOTALL)
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


# ---------------------------------------------------------------------------
# Aggregate all TITAN rules
# ---------------------------------------------------------------------------

ALL_TITAN_RULES = [
    check_section_completeness,
    check_freeze_declaration,
    check_formula_definitions,
    check_multi_timeframe,
    check_ema_alignment,
    check_swing_structure,
    check_gap_risk,
    check_partial_exits,
    check_composite_scores,
    check_fsm_states,
    check_fsm_transitions,
    check_entry_gates,
    check_weekly_meta_governor,
    check_determinism,
    check_halt_conditions,
    check_output_format,
    check_governance_entries,
]
