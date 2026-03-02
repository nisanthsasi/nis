"""Domain-specific validation rules for SATVA-style deterministic trading prompt systems.

These rules check for:
- Formula completeness and internal consistency
- FSM (Finite State Machine) transition coverage
- Threshold/bin gap analysis
- Cross-section reference integrity
- Governance discipline

Supports both v14.x and v15.x section layouts.
"""

import re
from prompt_validator.result import Issue, Severity, Category


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _find_sections(prompt: str) -> dict[str, str]:
    """Split prompt into sections by 'SECTION N' headers."""
    pattern = re.compile(r"SECTION\s+(\d+)\s*[—–-]\s*(.*?)(?=SECTION\s+\d+|LOCK STATEMENT|$)", re.DOTALL)
    sections = {}
    for match in pattern.finditer(prompt):
        num = int(match.group(1))
        sections[num] = match.group(2).strip()
    return sections


def _extract_variables(prompt: str) -> set[str]:
    """Extract variable-like tokens (UPPER_CASE identifiers)."""
    return set(re.findall(r"\b([A-Z][A-Z_]{2,})\b", prompt))


def _detect_version(prompt: str) -> str:
    """Detect SATVA version from prompt text. Returns 'v15' or 'v14'."""
    if re.search(r"v15\.\d+\.\d+", prompt):
        return "v15"
    return "v14"


# ---------------------------------------------------------------------------
# 1. STRUCTURAL COMPLETENESS
# ---------------------------------------------------------------------------

# v14 section layout
REQUIRED_SECTIONS_V14 = {
    0: "AXIOMS",
    1: "DATA CONTRACT",
    2: "CORE MEASUREMENTS",
    3: "SESSION GOVERNOR",
    5: "LEVEL SET",
    6: "ABT",
    12: "RCS",
    13: "REGIME",
    15: "SES",
    16: "SETUPS",
    17: "TARGETS",
    19: "RISK",
    22: "FSM",
    23: "OUTPUT FORMAT",
    24: "GOVERNANCE",
}

# v15 section layout (sections renumbered to accommodate new modules)
REQUIRED_SECTIONS_V15 = {
    0: "AXIOMS",
    1: "DATA CONTRACT",
    2: "CORE MEASUREMENTS",
    3: "SESSION GOVERNOR",
    5: "LEVEL SET",
    6: "ABT",
    12: "TAS",
    13: "MOMENTUM",
    14: "VOLUME PROFILE",
    15: "PQS",
    16: "RCS",
    17: "REGIME",
    19: "SES",
    20: "SETUPS",
    21: "TARGETS",
    22: "PARTIAL EXIT",
    25: "RISK",
    29: "FSM",
    30: "OUTPUT FORMAT",
    31: "GOVERNANCE",
}

# Union mapping used by default — selects based on version detection
REQUIRED_SECTIONS = REQUIRED_SECTIONS_V14


def check_section_completeness(prompt: str) -> list[Issue]:
    """Verify all critical sections are present."""
    sections = _find_sections(prompt)
    version = _detect_version(prompt)
    required = REQUIRED_SECTIONS_V15 if version == "v15" else REQUIRED_SECTIONS_V14
    issues = []
    missing = []
    for num, label in required.items():
        if num not in sections:
            missing.append(f"Section {num} ({label})")
    if missing:
        issues.append(Issue(
            message="Missing critical sections",
            severity=Severity.ERROR,
            category=Category.STRUCTURE,
            detail=f"Missing: {', '.join(missing)}",
            penalty=15 * len(missing),
        ))
    return issues


def check_freeze_declaration(prompt: str) -> list[Issue]:
    """Verify a freeze/lock declaration exists for governance control."""
    lower = prompt.lower()
    has_freeze = "freeze declaration" in lower or "lock statement" in lower
    has_governance = "governance" in lower
    issues = []
    if not has_freeze:
        issues.append(Issue(
            message="No freeze/lock declaration found",
            severity=Severity.WARNING,
            category=Category.STRUCTURE,
            detail="A frozen prompt system should include an explicit freeze declaration.",
            penalty=8,
        ))
    if not has_governance:
        issues.append(Issue(
            message="No governance section found",
            severity=Severity.WARNING,
            category=Category.STRUCTURE,
            detail="Version-controlled prompt systems need a governance/changelog section.",
            penalty=8,
        ))
    return issues


# ---------------------------------------------------------------------------
# 2. FORMULA & THRESHOLD INTEGRITY
# ---------------------------------------------------------------------------

EXPECTED_FORMULAS_BASE = [
    ("TR", r"TR\[?\w*\]?\s*=\s*max"),
    ("ATR5m", r"ATR5m\s*=\s*SMA"),
    ("RCS", r"RCS\s*=\s*0\.\d+"),
    ("SES", r"SES\s*=\s*0\.\d+"),
    ("Exp_M", r"Exp_M\s*="),
    ("SessionLossR", r"SessionLossR"),
    ("Eff", r"Eff\s*=\s*StopDist"),
    ("EntropyScore", r"EntropyScore\s*="),
    ("OverlapPct", r"OverlapPct\s*="),
    ("Contraction", r"Contraction\s*="),
]

# Additional formulas expected in v15
EXPECTED_FORMULAS_V15 = [
    ("TAS", r"TAS\s*=\s*0\.\d+"),
    ("PQS", r"PQS\s*=\s*0\.\d+"),
    ("ATR1H", r"ATR1H\s*=\s*SMA"),
    ("RSI_5m", r"RSI_5m\s*=\s*RSI"),
    ("MOM", r"MOM\s*=\s*max"),
]


def check_formula_definitions(prompt: str) -> list[Issue]:
    """Verify key formulas are explicitly defined."""
    version = _detect_version(prompt)
    formulas = list(EXPECTED_FORMULAS_BASE)
    if version == "v15":
        formulas.extend(EXPECTED_FORMULAS_V15)
    issues = []
    missing = []
    for name, pattern in formulas:
        if not re.search(pattern, prompt):
            missing.append(name)
    if missing:
        issues.append(Issue(
            message="Missing formula definitions",
            severity=Severity.ERROR,
            category=Category.ACCURACY,
            detail=f"The following formulas are referenced but not defined: {', '.join(missing)}",
            penalty=10 * len(missing),
        ))
    return issues


def _check_weight_sum(prompt: str, label: str, pattern: str) -> list[Issue]:
    """Check that a weighted formula sums to 1.00."""
    issues = []
    matches = re.findall(pattern, prompt)
    if matches:
        coeffs = re.findall(r"0\.(\d+)", matches[0])
        total = sum(int(c) for c in coeffs)
        if total != 100:
            issues.append(Issue(
                message=f"{label} weights sum to {total/100:.2f}, expected 1.00",
                severity=Severity.ERROR,
                category=Category.ACCURACY,
                detail=f"Weights in {label} formula: {matches[0].strip()}",
                penalty=20,
            ))
    return issues


def check_bin_coverage(prompt: str) -> list[Issue]:
    """Check that scoring bins (100/50/0) have no gaps or overlaps."""
    version = _detect_version(prompt)
    issues = []

    # Check RCS weight sum
    issues.extend(_check_weight_sum(prompt, "RCS", r"RCS\s*=\s*([\d.+*\w\s]+)"))

    # Check SES weight sum
    issues.extend(_check_weight_sum(prompt, "SES", r"SES\s*=\s*([\d.+*\w\s]+)"))

    # v15-specific composite score checks
    if version == "v15":
        issues.extend(_check_weight_sum(prompt, "TAS", r"TAS\s*=\s*(0\.\d+[\d.+*\w\s]+)"))
        issues.extend(_check_weight_sum(prompt, "PQS", r"PQS\s*=\s*(0\.\d+[\d.+*\w\s]+)"))

    return issues


def check_threshold_consistency(prompt: str) -> list[Issue]:
    """Check for threshold values that appear inconsistent across sections.

    TR/ATR5m thresholds are checked *per section* because different sections
    legitimately use different multiples (e.g., ABT uses 2.2, Expansion uses
    1.2/1.4).  Only flag when the same section contains conflicting values
    for the same concept.
    """
    issues = []
    sections = _find_sections(prompt)

    # Check TR thresholds per-section (same section should be self-consistent
    # for ABT-type checks; Expansion intentionally has Valid vs Strong tiers)
    for sec_num, sec_text in sections.items():
        tr_thresholds = re.findall(r"TR\s*[≥>=]+\s*([\d.]+)\s*\*?\s*ATR5m", sec_text)
        unique = set(tr_thresholds)
        # ABT (Section 6) should use a single spike threshold
        if sec_num == 6 and len(unique) > 1:
            issues.append(Issue(
                message=f"Inconsistent TR thresholds within Section {sec_num} (ABT)",
                severity=Severity.WARNING,
                category=Category.ACCURACY,
                detail=f"ABT section uses multiple TR/ATR5m multiples: {', '.join(sorted(unique))}. "
                       f"Spike detection should use a single threshold.",
                penalty=10,
            ))

    # Session loss cap consistency (must be same everywhere)
    loss_caps = re.findall(r"SessionLossR\s*[≥>=]+\s*([\d.]+)", prompt)
    unique_caps = set(loss_caps)
    if len(unique_caps) > 1:
        issues.append(Issue(
            message="Inconsistent SessionLossR thresholds",
            severity=Severity.ERROR,
            category=Category.ACCURACY,
            detail=f"Found different loss caps: {', '.join(sorted(unique_caps))}",
            penalty=20,
        ))

    return issues


# ---------------------------------------------------------------------------
# 3. FSM VALIDATION
# ---------------------------------------------------------------------------

EXPECTED_STATES = {"FLAT", "ARMED", "IN_POSITION", "COOLDOWN", "SESSION_LOCK", "MEG_LOCK"}

EXPECTED_TRANSITIONS = [
    ("FLAT", "ARMED"),
    ("ARMED", "IN_POSITION"),
    ("ARMED", "FLAT"),
    ("IN_POSITION", "FLAT"),
    ("IN_POSITION", "SESSION_LOCK"),
]


def check_fsm_states(prompt: str) -> list[Issue]:
    """Verify all FSM states are defined."""
    issues = []
    upper = prompt.upper()
    missing_states = [s for s in EXPECTED_STATES if s not in upper]
    if missing_states:
        issues.append(Issue(
            message="Missing FSM states",
            severity=Severity.ERROR,
            category=Category.ACCURACY,
            detail=f"States not found in prompt: {', '.join(missing_states)}",
            penalty=15,
        ))
    return issues


def check_fsm_transitions(prompt: str) -> list[Issue]:
    """Verify key FSM transitions are documented."""
    issues = []
    missing = []
    for src, dst in EXPECTED_TRANSITIONS:
        # Look for "src → dst" or "src->dst" or "src to dst"
        patterns = [
            f"{src}.*?→.*?{dst}",
            f"{src}.*?->.*?{dst}",
            f"{src}.*?to.*?{dst}",
        ]
        found = any(re.search(p, prompt, re.IGNORECASE) for p in patterns)
        if not found:
            missing.append(f"{src} → {dst}")
    if missing:
        issues.append(Issue(
            message="Missing FSM transitions",
            severity=Severity.WARNING,
            category=Category.ACCURACY,
            detail=f"Transitions not documented: {', '.join(missing)}",
            penalty=5 * len(missing),
        ))
    return issues


def check_fsm_dead_states(prompt: str) -> list[Issue]:
    """Check for states that can be entered but have no exit transition."""
    issues = []
    # SESSION_LOCK and MEG_LOCK should have exit conditions
    if "SESSION_LOCK" in prompt:
        has_exit = bool(re.search(
            r"SESSION_LOCK.*?(reset|end|exit|flat|release|next session|09:00)",
            prompt, re.IGNORECASE | re.DOTALL,
        ))
        if not has_exit:
            issues.append(Issue(
                message="SESSION_LOCK may be a dead state (no exit documented)",
                severity=Severity.ERROR,
                category=Category.ACCURACY,
                detail="SESSION_LOCK is entered but no exit/reset rule is visible.",
                penalty=15,
            ))
    if "MEG_LOCK" in prompt:
        has_exit = bool(re.search(
            r"MEG_LOCK.*?(reset|end|exit|flat|release|Exp_M\s*>)",
            prompt, re.IGNORECASE | re.DOTALL,
        ))
        if not has_exit:
            issues.append(Issue(
                message="MEG_LOCK may be a dead state (no exit documented)",
                severity=Severity.ERROR,
                category=Category.ACCURACY,
                detail="MEG_LOCK is entered but no exit/reset rule is visible.",
                penalty=15,
            ))
    return issues


# ---------------------------------------------------------------------------
# 4. CROSS-REFERENCE INTEGRITY
# ---------------------------------------------------------------------------

CRITICAL_VARS_BASE = {
    "ATR5m": r"ATR5m\s*=",
    "ATR_prev": r"ATR_prev\s*=",
    "SLIPPAGE_PAD": r"SLIPPAGE_PAD\s*=",
    "VWAP_session": r"VWAP.?session",
    "RCS": r"RCS\s*=\s*0\.",
    "SES": r"SES\s*=\s*0\.",
    "CompressionValid": r"CompressionValid\s*(if|=|:)",
    "ExpansionValid": r"ExpansionValid\s*(if|=|:)",
    "EntropyScore": r"EntropyScore\s*=",
}

CRITICAL_VARS_V15 = {
    "TAS": r"TAS\s*=\s*0\.",
    "PQS": r"PQS\s*=\s*0\.",
    "ATR1H": r"ATR1H\s*=",
    "MOM": r"MOM\s*=\s*max",
    "PORTFOLIO_HEAT": r"PORTFOLIO_HEAT\s*=",
}


def check_cross_references(prompt: str) -> list[Issue]:
    """Check that variables referenced in one section are defined in another."""
    version = _detect_version(prompt)
    issues = []
    critical_vars = dict(CRITICAL_VARS_BASE)
    if version == "v15":
        critical_vars.update(CRITICAL_VARS_V15)
    undefined = []
    for var, definition_pattern in critical_vars.items():
        # Variable is used
        if var in prompt:
            # But not defined
            if not re.search(definition_pattern, prompt):
                undefined.append(var)
    if undefined:
        issues.append(Issue(
            message="Variables used but not defined",
            severity=Severity.ERROR,
            category=Category.ACCURACY,
            detail=f"Used but no definition found: {', '.join(undefined)}",
            penalty=10 * len(undefined),
        ))
    return issues


# ---------------------------------------------------------------------------
# 5. DETERMINISM & SAFETY CHECKS
# ---------------------------------------------------------------------------

JUDGMENT_WORDS = [
    "probably", "likely", "seems", "appears", "might", "could be",
    "use your judgment", "discretion", "feel free", "up to you",
    "as appropriate", "if you think", "in your opinion",
]


def check_determinism(prompt: str) -> list[Issue]:
    """Flag non-deterministic / judgment language in a system claiming determinism."""
    issues = []
    lower = prompt.lower()
    found = [w for w in JUDGMENT_WORDS if w in lower]
    if found:
        issues.append(Issue(
            message="Non-deterministic language in a deterministic system",
            severity=Severity.ERROR,
            category=Category.ACCURACY,
            detail=f"Judgment words found: {', '.join(repr(w) for w in found)}. "
                   f"This violates Axiom A0 (Determinism).",
            penalty=10 * len(found),
        ))
    return issues


def check_halt_conditions(prompt: str) -> list[Issue]:
    """Verify that halt/safety conditions are defined for data failures."""
    issues = []
    lower = prompt.lower()
    has_halt = any(w in lower for w in ["session_lock", "halt", "system halt"])
    has_data_check = any(w in lower for w in ["missing", "critical", "data health", "datahealth"])
    if not has_halt:
        issues.append(Issue(
            message="No halt/safety condition defined",
            severity=Severity.ERROR,
            category=Category.ACCURACY,
            detail="A deterministic trading system must define halt conditions for data failures.",
            penalty=20,
        ))
    if not has_data_check:
        issues.append(Issue(
            message="No data health check defined",
            severity=Severity.WARNING,
            category=Category.ACCURACY,
            detail="System should verify data integrity before computing.",
            penalty=10,
        ))
    return issues


def check_output_format_section(prompt: str) -> list[Issue]:
    """Verify that the output format is rigidly defined."""
    issues = []
    lower = prompt.lower()
    has_output = "output format" in lower or "print every" in lower
    if not has_output:
        issues.append(Issue(
            message="No output format section",
            severity=Severity.WARNING,
            category=Category.STRUCTURE,
            detail="A deterministic system should define exact output format for reproducibility.",
            penalty=8,
        ))
    return issues


# ---------------------------------------------------------------------------
# 6. GOVERNANCE CHECKS
# ---------------------------------------------------------------------------

def check_governance_entries(prompt: str) -> list[Issue]:
    """Verify governance entries have required fields."""
    issues = []
    gov_entries = re.findall(r"GOV-[\w-]+", prompt)
    if not gov_entries:
        issues.append(Issue(
            message="No governance entries found",
            severity=Severity.INFO,
            category=Category.STRUCTURE,
            detail="If this is a versioned system, governance entries (patch log) are expected.",
            penalty=3,
        ))
        return issues

    # Check each entry has Before/After/Rationale
    for entry_id in set(gov_entries):
        # Find the block for this entry
        pattern = re.compile(
            re.escape(entry_id) + r".*?(?=GOV-|LOCK STATEMENT|$)",
            re.DOTALL,
        )
        match = pattern.search(prompt)
        if match:
            block = match.group(0).lower()
            missing_fields = []
            if "before:" not in block and "change:" not in block:
                missing_fields.append("Before/Change")
            if "after:" not in block and "change:" not in block:
                missing_fields.append("After")
            if "rationale:" not in block and "reason:" not in block:
                missing_fields.append("Rationale/Reason")
            if missing_fields:
                issues.append(Issue(
                    message=f"Governance entry {entry_id} missing fields",
                    severity=Severity.INFO,
                    category=Category.STRUCTURE,
                    detail=f"Missing: {', '.join(missing_fields)}",
                    penalty=2,
                ))
    return issues


# ---------------------------------------------------------------------------
# 7. v15-SPECIFIC MODULE CHECKS
# ---------------------------------------------------------------------------

V15_REQUIRED_MODULES = [
    ("TAS", ["HTF", "EXEC"]),
    ("MOM", ["RSI", "divergence"]),
    ("VOLP", ["VOL_EXPANDING", "VOL_CONTRACTING", "VOL_DRYUP"]),
    ("PQS", ["PB_DEPTH", "PB_CANDLE"]),
]


def check_v15_modules(prompt: str) -> list[Issue]:
    """Verify v15-specific analytical modules are present and complete."""
    version = _detect_version(prompt)
    if version != "v15":
        return []

    issues = []
    lower = prompt.lower()
    for module_name, keywords in V15_REQUIRED_MODULES:
        missing_kw = [kw for kw in keywords if kw.lower() not in lower]
        if missing_kw:
            issues.append(Issue(
                message=f"v15 module {module_name} missing components",
                severity=Severity.WARNING,
                category=Category.ACCURACY,
                detail=f"Expected keywords not found: {', '.join(missing_kw)}",
                penalty=5 * len(missing_kw),
            ))

    # Check Setup D exists in v15
    if "setup d" not in lower:
        issues.append(Issue(
            message="v15 Setup D (Momentum Pullback) not found",
            severity=Severity.WARNING,
            category=Category.STRUCTURE,
            detail="SATVA v15 should define Setup D for momentum pullback entries.",
            penalty=8,
        ))

    # Check 3-tier partial exit engine
    if "tier 1" not in lower and "tier 2" not in lower:
        issues.append(Issue(
            message="v15 3-tier partial exit engine not found",
            severity=Severity.WARNING,
            category=Category.STRUCTURE,
            detail="SATVA v15 should define a 3-tier partial exit engine (T1/T2/T3).",
            penalty=8,
        ))

    # Check data health watchdogs
    if "watchdog" not in lower and "data_stale" not in lower:
        issues.append(Issue(
            message="v15 data health watchdogs not found",
            severity=Severity.WARNING,
            category=Category.STRUCTURE,
            detail="SATVA v15 should define data freshness and volume anomaly watchdogs.",
            penalty=5,
        ))

    return issues


def check_partial_exit_tiers(prompt: str) -> list[Issue]:
    """Verify partial exit percentages in the Partial Exit Engine section sum correctly."""
    version = _detect_version(prompt)
    if version != "v15":
        return []

    issues = []
    # Find the Partial Exit Engine section specifically
    sections = _find_sections(prompt)
    exit_section = sections.get(22, "")
    if not exit_section:
        return issues

    # Look for tier percentage allocations within the exit section only
    tier_pcts = re.findall(r"(?:close|exit)\s+(\d+)%", exit_section.lower())
    if len(tier_pcts) >= 3:
        total = sum(int(p) for p in tier_pcts[:3])
        if total != 100:
            issues.append(Issue(
                message=f"Partial exit tiers sum to {total}%, expected 100%",
                severity=Severity.WARNING,
                category=Category.ACCURACY,
                detail=f"Tier percentages found: {', '.join(tier_pcts[:3])}",
                penalty=10,
            ))
    return issues


# ---------------------------------------------------------------------------
# Aggregate all SATVA rules
# ---------------------------------------------------------------------------

ALL_SATVA_RULES = [
    check_section_completeness,
    check_freeze_declaration,
    check_formula_definitions,
    check_bin_coverage,
    check_threshold_consistency,
    check_fsm_states,
    check_fsm_transitions,
    check_fsm_dead_states,
    check_cross_references,
    check_determinism,
    check_halt_conditions,
    check_output_format_section,
    check_governance_entries,
    check_v15_modules,
    check_partial_exit_tiers,
]
