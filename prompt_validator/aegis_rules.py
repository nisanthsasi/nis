"""Domain-specific validation rules for AEGIS — Autonomous/Safety-Critical Systems.

Deterministic checks for:
- Sensor fusion pipeline completeness
- Fail-safe FSM state/transition coverage
- Redundancy requirements (dual/triple modular)
- Safety constraint definitions (SIL/ASIL levels)
- Watchdog and timeout specifications
- Actuator command validation
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
    1: "SENSOR DATA CONTRACT",
    2: "SENSOR FUSION",
    3: "PERCEPTION PIPELINE",
    4: "DECISION ENGINE",
    5: "SAFETY CONSTRAINTS",
    6: "FAIL-SAFE FSM",
    7: "ACTUATOR COMMANDS",
    8: "WATCHDOG TIMERS",
    9: "REDUNDANCY SPEC",
    10: "OUTPUT FORMAT",
    11: "GOVERNANCE",
}


def check_section_completeness(prompt: str) -> list[Issue]:
    """Verify all critical autonomous system sections are present."""
    sections = _find_sections(prompt)
    missing = [f"Section {n} ({l})" for n, l in REQUIRED_SECTIONS.items() if n not in sections]
    if missing:
        return [Issue(
            message="Missing critical system sections",
            severity=Severity.ERROR,
            category=Category.STRUCTURE,
            detail=f"Missing: {', '.join(missing)}",
            penalty=15 * len(missing),
        )]
    return []


def check_freeze_declaration(prompt: str) -> list[Issue]:
    lower = prompt.lower()
    has_freeze = "freeze declaration" in lower or "lock statement" in lower or "system lock" in lower
    has_governance = "governance" in lower
    issues = []
    if not has_freeze:
        issues.append(Issue(
            message="No system freeze/lock declaration found",
            severity=Severity.WARNING,
            category=Category.STRUCTURE,
            detail="Safety-critical systems must include an explicit configuration freeze.",
            penalty=8,
        ))
    if not has_governance:
        issues.append(Issue(
            message="No governance section found",
            severity=Severity.WARNING,
            category=Category.STRUCTURE,
            detail="Autonomous systems require version-controlled governance for certification.",
            penalty=8,
        ))
    return issues


# ---------------------------------------------------------------------------
# 2. SENSOR FUSION & FORMULA INTEGRITY
# ---------------------------------------------------------------------------

EXPECTED_FORMULAS = [
    ("CONFIDENCE", r"CONFIDENCE\s*="),
    ("FUSION_WEIGHT", r"FUSION_WEIGHT\s*="),
    ("KALMAN_GAIN", r"KALMAN_GAIN\s*="),
    ("POSITION_EST", r"POSITION_EST\s*="),
    ("VELOCITY_EST", r"VELOCITY_EST\s*="),
    ("THREAT_SCORE", r"THREAT_SCORE\s*="),
    ("STOPPING_DIST", r"STOPPING_DIST\s*="),
    ("REACTION_TIME", r"REACTION_TIME\s*="),
]


def check_formula_definitions(prompt: str) -> list[Issue]:
    missing = [name for name, pat in EXPECTED_FORMULAS if not re.search(pat, prompt)]
    if missing:
        return [Issue(
            message="Missing sensor/control formula definitions",
            severity=Severity.ERROR,
            category=Category.ACCURACY,
            detail=f"Formulas not defined: {', '.join(missing)}",
            penalty=10 * len(missing),
        )]
    return []


def check_sensor_redundancy(prompt: str) -> list[Issue]:
    """Check that sensor redundancy requirements are specified."""
    lower = prompt.lower()
    redundancy_terms = ["dual modular", "triple modular", "tmr", "dmr", "redundan", "n+1", "failover"]
    found = [t for t in redundancy_terms if t in lower]
    if not found:
        return [Issue(
            message="No sensor redundancy specification",
            severity=Severity.ERROR,
            category=Category.ACCURACY,
            detail="Safety-critical systems must specify sensor redundancy (DMR, TMR, N+1).",
            penalty=15,
        )]
    return []


# ---------------------------------------------------------------------------
# 3. SAFETY CONSTRAINTS
# ---------------------------------------------------------------------------

def check_safety_levels(prompt: str) -> list[Issue]:
    """Verify safety integrity levels are defined (SIL or ASIL)."""
    lower = prompt.lower()
    has_sil = bool(re.search(r"\b(sil|asil)\s*[0-4abcd]", lower))
    has_safety_class = any(k in lower for k in ["safety integrity level", "safety class", "criticality level"])
    if not has_sil and not has_safety_class:
        return [Issue(
            message="No safety integrity level defined",
            severity=Severity.ERROR,
            category=Category.ACCURACY,
            detail="Must define SIL (IEC 61508) or ASIL (ISO 26262) levels for each subsystem.",
            penalty=20,
        )]
    return []


def check_boundary_constraints(prompt: str) -> list[Issue]:
    """Check that physical boundary constraints are defined."""
    lower = prompt.lower()
    boundaries = ["max_speed", "min_distance", "max_acceleration", "geofence", "operational domain"]
    found = [b for b in boundaries if b in lower.replace(" ", "_") or b.replace("_", " ") in lower]
    missing = [b for b in boundaries if b not in lower.replace(" ", "_") and b.replace("_", " ") not in lower]
    if len(found) < 3:
        return [Issue(
            message="Insufficient boundary constraints",
            severity=Severity.WARNING,
            category=Category.ACCURACY,
            detail=f"Found {len(found)}/5 boundary constraints. Missing: {', '.join(missing)}.",
            penalty=5 * len(missing),
        )]
    return []


# ---------------------------------------------------------------------------
# 4. FAIL-SAFE FSM
# ---------------------------------------------------------------------------

EXPECTED_STATES = {"NOMINAL", "DEGRADED", "EMERGENCY_STOP", "SAFE_STATE", "MANUAL_OVERRIDE", "SHUTDOWN"}

EXPECTED_TRANSITIONS = [
    ("NOMINAL", "DEGRADED"),
    ("DEGRADED", "EMERGENCY_STOP"),
    ("EMERGENCY_STOP", "SAFE_STATE"),
    ("DEGRADED", "NOMINAL"),
    ("MANUAL_OVERRIDE", "SAFE_STATE"),
]


def check_fsm_states(prompt: str) -> list[Issue]:
    upper = prompt.upper()
    missing = [s for s in EXPECTED_STATES if s not in upper]
    if missing:
        return [Issue(
            message="Missing fail-safe FSM states",
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
            message="Missing fail-safe FSM transitions",
            severity=Severity.WARNING,
            category=Category.ACCURACY,
            detail=f"Transitions not documented: {', '.join(missing)}",
            penalty=5 * len(missing),
        )]
    return []


def check_fsm_dead_states(prompt: str) -> list[Issue]:
    issues = []
    if "EMERGENCY_STOP" in prompt.upper():
        has_exit = bool(re.search(
            r"EMERGENCY_STOP.*?(safe_state|reset|recovery|manual|restart)",
            prompt, re.IGNORECASE | re.DOTALL,
        ))
        if not has_exit:
            issues.append(Issue(
                message="EMERGENCY_STOP may be a dead state",
                severity=Severity.ERROR,
                category=Category.ACCURACY,
                detail="EMERGENCY_STOP is entered but no recovery path is documented.",
                penalty=15,
            ))
    return issues


# ---------------------------------------------------------------------------
# 5. WATCHDOG & TIMEOUT
# ---------------------------------------------------------------------------

def check_watchdog_timers(prompt: str) -> list[Issue]:
    """Verify watchdog timer specifications exist."""
    lower = prompt.lower()
    has_watchdog = any(k in lower for k in ["watchdog", "heartbeat", "timeout", "deadman"])
    if not has_watchdog:
        return [Issue(
            message="No watchdog/timeout mechanism defined",
            severity=Severity.ERROR,
            category=Category.ACCURACY,
            detail="Autonomous systems must define watchdog timers for fault detection.",
            penalty=15,
        )]
    return []


# ---------------------------------------------------------------------------
# 6. DETERMINISM
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
            message="Non-deterministic language in safety-critical system",
            severity=Severity.ERROR,
            category=Category.ACCURACY,
            detail=f"Judgment words: {', '.join(repr(w) for w in found)}. "
                   f"Safety-critical systems must be fully deterministic.",
            penalty=10 * len(found),
        )]
    return []


def check_output_format_section(prompt: str) -> list[Issue]:
    lower = prompt.lower()
    if "output format" not in lower and "telemetry format" not in lower:
        return [Issue(
            message="No output/telemetry format section",
            severity=Severity.WARNING,
            category=Category.STRUCTURE,
            detail="Safety systems must define exact output format for logging and audit.",
            penalty=8,
        )]
    return []


# ---------------------------------------------------------------------------
# 7. GOVERNANCE
# ---------------------------------------------------------------------------

def check_governance_entries(prompt: str) -> list[Issue]:
    gov_entries = re.findall(r"GOV-[\w-]+", prompt)
    if not gov_entries:
        return [Issue(
            message="No governance entries found",
            severity=Severity.INFO,
            category=Category.STRUCTURE,
            detail="Safety-critical systems require governance entries for certification audits.",
            penalty=3,
        )]
    issues = []
    for entry_id in set(gov_entries):
        pattern = re.compile(re.escape(entry_id) + r".*?(?=GOV-|LOCK STATEMENT|FREEZE|$)", re.DOTALL)
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
# Aggregate
# ---------------------------------------------------------------------------

ALL_AEGIS_RULES = [
    check_section_completeness,
    check_freeze_declaration,
    check_formula_definitions,
    check_sensor_redundancy,
    check_safety_levels,
    check_boundary_constraints,
    check_fsm_states,
    check_fsm_transitions,
    check_fsm_dead_states,
    check_watchdog_timers,
    check_determinism,
    check_output_format_section,
    check_governance_entries,
]
