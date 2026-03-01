"""Domain-specific validation rules for SENTINEL — Cybersecurity/Threat Detection Systems.

Deterministic checks for:
- MITRE ATT&CK mapping completeness
- Severity scoring formula definitions
- Alert escalation FSM validation
- False positive handling rules
- IoC (Indicator of Compromise) classification
- Response playbook coverage
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
    1: "DATA INGESTION CONTRACT",
    2: "IOC CLASSIFICATION",
    3: "SEVERITY SCORING",
    4: "DETECTION RULES",
    5: "CORRELATION ENGINE",
    6: "ALERT FSM",
    7: "ESCALATION PROTOCOL",
    8: "RESPONSE PLAYBOOKS",
    9: "FALSE POSITIVE HANDLING",
    10: "OUTPUT FORMAT",
    11: "GOVERNANCE",
}


def check_section_completeness(prompt: str) -> list[Issue]:
    sections = _find_sections(prompt)
    missing = [f"Section {n} ({l})" for n, l in REQUIRED_SECTIONS.items() if n not in sections]
    if missing:
        return [Issue(
            message="Missing critical security sections",
            severity=Severity.ERROR,
            category=Category.STRUCTURE,
            detail=f"Missing: {', '.join(missing)}",
            penalty=15 * len(missing),
        )]
    return []


def check_freeze_declaration(prompt: str) -> list[Issue]:
    lower = prompt.lower()
    has_freeze = "freeze declaration" in lower or "lock statement" in lower or "ruleset lock" in lower
    has_governance = "governance" in lower
    issues = []
    if not has_freeze:
        issues.append(Issue(
            message="No ruleset freeze/lock declaration found",
            severity=Severity.WARNING,
            category=Category.STRUCTURE,
            detail="Security detection systems must include an explicit ruleset freeze.",
            penalty=8,
        ))
    if not has_governance:
        issues.append(Issue(
            message="No governance section found",
            severity=Severity.WARNING,
            category=Category.STRUCTURE,
            detail="Security systems require version-controlled governance for incident audit.",
            penalty=8,
        ))
    return issues


# ---------------------------------------------------------------------------
# 2. SEVERITY SCORING & FORMULAS
# ---------------------------------------------------------------------------

EXPECTED_FORMULAS = [
    ("SEVERITY_SCORE", r"SEVERITY_SCORE\s*="),
    ("CVSS_BASE", r"CVSS_BASE\s*="),
    ("CONFIDENCE_LEVEL", r"CONFIDENCE_LEVEL\s*="),
    ("RISK_PRIORITY", r"RISK_PRIORITY\s*="),
    ("IOC_WEIGHT", r"IOC_WEIGHT\s*="),
    ("CORRELATION_SCORE", r"CORRELATION_SCORE\s*="),
    ("FALSE_POS_RATE", r"FALSE_POS_RATE\s*="),
    ("DWELL_TIME", r"DWELL_TIME\s*="),
]


def check_formula_definitions(prompt: str) -> list[Issue]:
    missing = [name for name, pat in EXPECTED_FORMULAS if not re.search(pat, prompt)]
    if missing:
        return [Issue(
            message="Missing security scoring formula definitions",
            severity=Severity.ERROR,
            category=Category.ACCURACY,
            detail=f"Formulas not defined: {', '.join(missing)}",
            penalty=10 * len(missing),
        )]
    return []


def check_mitre_mapping(prompt: str) -> list[Issue]:
    """Verify MITRE ATT&CK framework mapping exists."""
    lower = prompt.lower()
    has_mitre = any(k in lower for k in [
        "mitre", "att&ck", "attack framework", "tactic", "technique",
        "t1", "ta00", "kill chain",
    ])
    if not has_mitre:
        return [Issue(
            message="No MITRE ATT&CK framework mapping",
            severity=Severity.ERROR,
            category=Category.ACCURACY,
            detail="Threat detection systems must map rules to MITRE ATT&CK tactics/techniques.",
            penalty=15,
        )]
    return []


def check_ioc_classification(prompt: str) -> list[Issue]:
    """Verify IoC types are classified."""
    lower = prompt.lower()
    ioc_types = ["ip address", "domain", "hash", "file hash", "url", "email", "registry"]
    found = [t for t in ioc_types if t in lower]
    if len(found) < 3:
        return [Issue(
            message="Incomplete IoC type classification",
            severity=Severity.WARNING,
            category=Category.ACCURACY,
            detail=f"Found {len(found)}/7 IoC types: {', '.join(found) or 'none'}.",
            penalty=5 * (7 - len(found)),
        )]
    return []


# ---------------------------------------------------------------------------
# 3. ALERT FSM
# ---------------------------------------------------------------------------

EXPECTED_STATES = {"NEW", "TRIAGED", "INVESTIGATING", "ESCALATED", "CONTAINED", "RESOLVED", "FALSE_POSITIVE"}

EXPECTED_TRANSITIONS = [
    ("NEW", "TRIAGED"),
    ("TRIAGED", "INVESTIGATING"),
    ("INVESTIGATING", "ESCALATED"),
    ("INVESTIGATING", "CONTAINED"),
    ("TRIAGED", "FALSE_POSITIVE"),
    ("CONTAINED", "RESOLVED"),
]


def check_alert_states(prompt: str) -> list[Issue]:
    upper = prompt.upper()
    missing = [s for s in EXPECTED_STATES if s not in upper]
    if missing:
        return [Issue(
            message="Missing alert lifecycle states",
            severity=Severity.ERROR,
            category=Category.ACCURACY,
            detail=f"States not found: {', '.join(missing)}",
            penalty=10 * len(missing),
        )]
    return []


def check_alert_transitions(prompt: str) -> list[Issue]:
    missing = []
    for src, dst in EXPECTED_TRANSITIONS:
        patterns = [f"{src}.*?→.*?{dst}", f"{src}.*?->.*?{dst}", f"{src}.*?to.*?{dst}"]
        if not any(re.search(p, prompt, re.IGNORECASE) for p in patterns):
            missing.append(f"{src} → {dst}")
    if missing:
        return [Issue(
            message="Missing alert lifecycle transitions",
            severity=Severity.WARNING,
            category=Category.ACCURACY,
            detail=f"Transitions not documented: {', '.join(missing)}",
            penalty=5 * len(missing),
        )]
    return []


def check_alert_dead_states(prompt: str) -> list[Issue]:
    """Check that escalated alerts have resolution paths."""
    if "ESCALATED" in prompt.upper():
        has_exit = bool(re.search(
            r"ESCALATED.*?(contained|resolved|mitigated|closed|soc)",
            prompt, re.IGNORECASE | re.DOTALL,
        ))
        if not has_exit:
            return [Issue(
                message="ESCALATED alert has no resolution path",
                severity=Severity.ERROR,
                category=Category.ACCURACY,
                detail="Escalated alerts must define a path to containment or resolution.",
                penalty=15,
            )]
    return []


# ---------------------------------------------------------------------------
# 4. FALSE POSITIVE HANDLING
# ---------------------------------------------------------------------------

def check_false_positive_handling(prompt: str) -> list[Issue]:
    """Verify false positive handling is defined."""
    lower = prompt.lower()
    has_fp = any(k in lower for k in [
        "false positive", "false_positive", "fp rate", "whitelist",
        "allowlist", "exclusion", "suppression rule",
    ])
    if not has_fp:
        return [Issue(
            message="No false positive handling mechanism",
            severity=Severity.ERROR,
            category=Category.ACCURACY,
            detail="Security systems must define false positive identification and suppression rules.",
            penalty=15,
        )]
    return []


def check_response_playbooks(prompt: str) -> list[Issue]:
    """Verify response playbooks are defined."""
    lower = prompt.lower()
    has_playbook = any(k in lower for k in [
        "playbook", "runbook", "response procedure", "containment step",
        "isolation", "quarantine", "remediation",
    ])
    if not has_playbook:
        return [Issue(
            message="No response playbooks defined",
            severity=Severity.WARNING,
            category=Category.ACCURACY,
            detail="Threat detection systems should define automated response playbooks.",
            penalty=10,
        )]
    return []


# ---------------------------------------------------------------------------
# 5. DETERMINISM
# ---------------------------------------------------------------------------

JUDGMENT_WORDS = [
    "probably", "likely", "seems", "appears", "might", "could be",
    "use your judgment", "discretion", "feel free", "up to you",
    "as appropriate", "if you think", "in your opinion",
    "suspicious-looking", "looks malicious",
]


def check_determinism(prompt: str) -> list[Issue]:
    lower = prompt.lower()
    found = [w for w in JUDGMENT_WORDS if w in lower]
    if found:
        return [Issue(
            message="Non-deterministic language in security detection system",
            severity=Severity.ERROR,
            category=Category.ACCURACY,
            detail=f"Judgment words: {', '.join(repr(w) for w in found)}. "
                   f"Detection rules must be fully deterministic.",
            penalty=10 * len(found),
        )]
    return []


def check_output_format_section(prompt: str) -> list[Issue]:
    lower = prompt.lower()
    if "output format" not in lower and "alert format" not in lower:
        return [Issue(
            message="No output/alert format section",
            severity=Severity.WARNING,
            category=Category.STRUCTURE,
            detail="Security systems must define exact alert output format for SIEM integration.",
            penalty=8,
        )]
    return []


# ---------------------------------------------------------------------------
# 6. GOVERNANCE
# ---------------------------------------------------------------------------

def check_governance_entries(prompt: str) -> list[Issue]:
    gov_entries = re.findall(r"GOV-[\w-]+", prompt)
    if not gov_entries:
        return [Issue(
            message="No governance entries found",
            severity=Severity.INFO,
            category=Category.STRUCTURE,
            detail="Security systems require governance entries for incident response audit.",
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

ALL_SENTINEL_RULES = [
    check_section_completeness,
    check_freeze_declaration,
    check_formula_definitions,
    check_mitre_mapping,
    check_ioc_classification,
    check_alert_states,
    check_alert_transitions,
    check_alert_dead_states,
    check_false_positive_handling,
    check_response_playbooks,
    check_determinism,
    check_output_format_section,
    check_governance_entries,
]
