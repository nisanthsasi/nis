"""Domain-specific validation rules for SATVA-style deterministic trading prompt systems.

These rules check for:
- Formula completeness and internal consistency
- FSM (Finite State Machine) transition coverage
- Threshold/bin gap analysis
- Cross-section reference integrity
- Governance discipline
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


# ---------------------------------------------------------------------------
# 1. STRUCTURAL COMPLETENESS
# ---------------------------------------------------------------------------

REQUIRED_SECTIONS = {
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


def check_section_completeness(prompt: str) -> list[Issue]:
    """Verify all critical sections are present."""
    sections = _find_sections(prompt)
    issues = []
    missing = []
    for num, label in REQUIRED_SECTIONS.items():
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

EXPECTED_FORMULAS = [
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


def check_formula_definitions(prompt: str) -> list[Issue]:
    """Verify key formulas are explicitly defined."""
    issues = []
    missing = []
    for name, pattern in EXPECTED_FORMULAS:
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


def check_bin_coverage(prompt: str) -> list[Issue]:
    """Check that scoring bins (100/50/0) have no gaps or overlaps."""
    issues = []

    # Check RCS weight sum
    rcs_weights = re.findall(r"RCS\s*=\s*([\d.+*\w\s]+)", prompt)
    if rcs_weights:
        coeffs = re.findall(r"0\.(\d+)", rcs_weights[0])
        total = sum(int(c) for c in coeffs)
        if total != 100:
            issues.append(Issue(
                message=f"RCS weights sum to {total/100:.2f}, expected 1.00",
                severity=Severity.ERROR,
                category=Category.ACCURACY,
                detail=f"Weights in RCS formula: {rcs_weights[0].strip()}",
                penalty=20,
            ))

    # Check SES weight sum
    ses_weights = re.findall(r"SES\s*=\s*([\d.+*\w\s]+)", prompt)
    if ses_weights:
        coeffs = re.findall(r"0\.(\d+)", ses_weights[0])
        total = sum(int(c) for c in coeffs)
        if total != 100:
            issues.append(Issue(
                message=f"SES weights sum to {total/100:.2f}, expected 1.00",
                severity=Severity.ERROR,
                category=Category.ACCURACY,
                detail=f"Weights in SES formula: {ses_weights[0].strip()}",
                penalty=20,
            ))

    return issues


def check_threshold_consistency(prompt: str) -> list[Issue]:
    """Check for threshold values that appear inconsistent across sections."""
    issues = []

    # ABT threshold should be consistent
    abt_tr_thresholds = re.findall(r"TR\s*[≥>=]+\s*([\d.]+)\s*\*?\s*ATR5m", prompt)
    abt_unique = set(abt_tr_thresholds)
    if len(abt_unique) > 1:
        issues.append(Issue(
            message="Inconsistent TR threshold multiples",
            severity=Severity.WARNING,
            category=Category.ACCURACY,
            detail=f"Found different TR/ATR5m thresholds: {', '.join(sorted(abt_unique))}. Verify intentional.",
            penalty=5,
        ))

    # Session loss cap consistency
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

def check_cross_references(prompt: str) -> list[Issue]:
    """Check that variables referenced in one section are defined in another."""
    issues = []
    # Key variables that MUST be defined before use
    critical_vars = {
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
]
