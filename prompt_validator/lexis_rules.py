"""Domain-specific validation rules for LEXIS — Legal/Compliance Decision Systems.

Deterministic checks for:
- Jurisdiction and statute section completeness
- Legal rule definitions and precedent references
- Decision tree coverage and consistency
- Compliance threshold validation
- Appeal/override path verification
- Determinism in legal reasoning
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
    1: "JURISDICTION CONTRACT",
    2: "STATUTE DEFINITIONS",
    3: "COMPLIANCE RULES",
    4: "DECISION TREE",
    5: "PENALTY MATRIX",
    6: "ESCALATION PROTOCOL",
    7: "APPEAL PATH",
    8: "CONFLICT RESOLUTION",
    9: "OUTPUT FORMAT",
    10: "GOVERNANCE",
}


def check_section_completeness(prompt: str) -> list[Issue]:
    sections = _find_sections(prompt)
    missing = [f"Section {n} ({l})" for n, l in REQUIRED_SECTIONS.items() if n not in sections]
    if missing:
        return [Issue(
            message="Missing critical legal sections",
            severity=Severity.ERROR,
            category=Category.STRUCTURE,
            detail=f"Missing: {', '.join(missing)}",
            penalty=15 * len(missing),
        )]
    return []


def check_freeze_declaration(prompt: str) -> list[Issue]:
    lower = prompt.lower()
    has_freeze = "freeze declaration" in lower or "lock statement" in lower or "regulation lock" in lower
    has_governance = "governance" in lower
    issues = []
    if not has_freeze:
        issues.append(Issue(
            message="No regulation freeze/lock declaration found",
            severity=Severity.WARNING,
            category=Category.STRUCTURE,
            detail="Legal compliance systems must include an explicit regulatory freeze declaration.",
            penalty=8,
        ))
    if not has_governance:
        issues.append(Issue(
            message="No governance section found",
            severity=Severity.WARNING,
            category=Category.STRUCTURE,
            detail="Legal systems require version-controlled governance for audit compliance.",
            penalty=8,
        ))
    return issues


# ---------------------------------------------------------------------------
# 2. LEGAL RULE & STATUTE INTEGRITY
# ---------------------------------------------------------------------------

EXPECTED_FORMULAS = [
    ("PENALTY_CALC", r"PENALTY_CALC\s*="),
    ("SEVERITY_SCORE", r"SEVERITY_SCORE\s*="),
    ("COMPLIANCE_RATE", r"COMPLIANCE_RATE\s*="),
    ("RISK_RATING", r"RISK_RATING\s*="),
    ("STATUTE_MATCH", r"STATUTE_MATCH\s*="),
    ("PRECEDENT_WEIGHT", r"PRECEDENT_WEIGHT\s*="),
    ("LIABILITY_INDEX", r"LIABILITY_INDEX\s*="),
    ("DEADLINE_CALC", r"DEADLINE_CALC\s*="),
]


def check_formula_definitions(prompt: str) -> list[Issue]:
    missing = [name for name, pat in EXPECTED_FORMULAS if not re.search(pat, prompt)]
    if missing:
        return [Issue(
            message="Missing legal formula definitions",
            severity=Severity.ERROR,
            category=Category.ACCURACY,
            detail=f"Formulas not defined: {', '.join(missing)}",
            penalty=10 * len(missing),
        )]
    return []


def check_jurisdiction_coverage(prompt: str) -> list[Issue]:
    """Verify jurisdiction scope is explicitly defined."""
    lower = prompt.lower()
    jurisdiction_terms = ["jurisdiction", "applicable law", "governing law", "venue", "forum"]
    found = [t for t in jurisdiction_terms if t in lower]
    if not found:
        return [Issue(
            message="No jurisdiction scope defined",
            severity=Severity.ERROR,
            category=Category.ACCURACY,
            detail="Legal systems must explicitly define the applicable jurisdiction(s).",
            penalty=20,
        )]
    return []


def check_statute_references(prompt: str) -> list[Issue]:
    """Verify that statute/regulation references are present."""
    lower = prompt.lower()
    has_refs = any(k in lower for k in [
        "§", "section ", "article ", "regulation ", "statute ",
        "usc", "cfr", "gdpr", "ccpa", "hipaa", "sox", "act ",
    ])
    if not has_refs:
        return [Issue(
            message="No statute or regulation references found",
            severity=Severity.WARNING,
            category=Category.ACCURACY,
            detail="Legal compliance rules should reference specific statutes or regulations.",
            penalty=10,
        )]
    return []


# ---------------------------------------------------------------------------
# 3. DECISION TREE VALIDATION
# ---------------------------------------------------------------------------

EXPECTED_STATES = {"COMPLIANT", "NON_COMPLIANT", "UNDER_REVIEW", "ESCALATED", "APPEAL", "RESOLVED"}

EXPECTED_TRANSITIONS = [
    ("COMPLIANT", "NON_COMPLIANT"),
    ("NON_COMPLIANT", "ESCALATED"),
    ("NON_COMPLIANT", "UNDER_REVIEW"),
    ("UNDER_REVIEW", "RESOLVED"),
    ("ESCALATED", "APPEAL"),
]


def check_decision_states(prompt: str) -> list[Issue]:
    upper = prompt.upper()
    missing = [s for s in EXPECTED_STATES if s not in upper]
    if missing:
        return [Issue(
            message="Missing compliance decision states",
            severity=Severity.ERROR,
            category=Category.ACCURACY,
            detail=f"States not found: {', '.join(missing)}",
            penalty=10 * len(missing),
        )]
    return []


def check_decision_transitions(prompt: str) -> list[Issue]:
    missing = []
    for src, dst in EXPECTED_TRANSITIONS:
        patterns = [f"{src}.*?→.*?{dst}", f"{src}.*?->.*?{dst}", f"{src}.*?to.*?{dst}"]
        if not any(re.search(p, prompt, re.IGNORECASE) for p in patterns):
            missing.append(f"{src} → {dst}")
    if missing:
        return [Issue(
            message="Missing compliance transition paths",
            severity=Severity.WARNING,
            category=Category.ACCURACY,
            detail=f"Transitions not documented: {', '.join(missing)}",
            penalty=5 * len(missing),
        )]
    return []


def check_appeal_path(prompt: str) -> list[Issue]:
    """Verify that an appeal/review mechanism exists for adverse decisions."""
    lower = prompt.lower()
    has_appeal = any(k in lower for k in ["appeal", "review", "reconsideration", "grievance", "challenge"])
    if not has_appeal:
        return [Issue(
            message="No appeal/review mechanism defined",
            severity=Severity.ERROR,
            category=Category.ACCURACY,
            detail="Legal decision systems must provide an appeal or review path.",
            penalty=15,
        )]
    return []


# ---------------------------------------------------------------------------
# 4. PENALTY CONSISTENCY
# ---------------------------------------------------------------------------

def check_penalty_consistency(prompt: str) -> list[Issue]:
    """Check that penalty thresholds don't conflict."""
    issues = []
    # Check severity score thresholds are monotonic
    severity_vals = re.findall(r"SEVERITY_SCORE\s*[≥>=]+\s*([\d.]+)", prompt)
    if len(set(severity_vals)) > 1:
        vals = sorted(set(severity_vals))
        # Just verify they exist and are ordered
        try:
            floats = [float(v) for v in vals]
            if floats != sorted(floats):
                issues.append(Issue(
                    message="SEVERITY_SCORE thresholds not monotonically ordered",
                    severity=Severity.WARNING,
                    category=Category.ACCURACY,
                    detail=f"Values found: {', '.join(vals)}",
                    penalty=10,
                ))
        except ValueError:
            pass
    return issues


# ---------------------------------------------------------------------------
# 5. DETERMINISM & SAFETY
# ---------------------------------------------------------------------------

JUDGMENT_WORDS = [
    "probably", "likely", "seems", "appears", "might", "could be",
    "use your judgment", "discretion", "feel free", "up to you",
    "as appropriate", "if you think", "in your opinion",
    "reasonable person", "spirit of the law",
]


def check_determinism(prompt: str) -> list[Issue]:
    lower = prompt.lower()
    found = [w for w in JUDGMENT_WORDS if w in lower]
    if found:
        return [Issue(
            message="Non-deterministic language in legal decision system",
            severity=Severity.ERROR,
            category=Category.ACCURACY,
            detail=f"Judgment words: {', '.join(repr(w) for w in found)}. "
                   f"Compliance algorithms must be fully deterministic.",
            penalty=10 * len(found),
        )]
    return []


def check_output_format_section(prompt: str) -> list[Issue]:
    lower = prompt.lower()
    if "output format" not in lower and "report format" not in lower:
        return [Issue(
            message="No output format section",
            severity=Severity.WARNING,
            category=Category.STRUCTURE,
            detail="Legal systems must define exact output format for court/regulatory submissions.",
            penalty=8,
        )]
    return []


def check_conflict_resolution(prompt: str) -> list[Issue]:
    """Verify that conflicting rule resolution is defined."""
    lower = prompt.lower()
    has_conflict = any(k in lower for k in [
        "conflict resolution", "rule priority", "precedence", "lex specialis",
        "hierarchy", "supersede", "override rule",
    ])
    if not has_conflict:
        return [Issue(
            message="No conflict resolution mechanism defined",
            severity=Severity.WARNING,
            category=Category.ACCURACY,
            detail="When legal rules conflict, a resolution hierarchy must be specified.",
            penalty=10,
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
            detail="Legal systems require governance entries for regulatory audit trails.",
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

ALL_LEXIS_RULES = [
    check_section_completeness,
    check_freeze_declaration,
    check_formula_definitions,
    check_jurisdiction_coverage,
    check_statute_references,
    check_decision_states,
    check_decision_transitions,
    check_appeal_path,
    check_penalty_consistency,
    check_determinism,
    check_output_format_section,
    check_conflict_resolution,
    check_governance_entries,
]
