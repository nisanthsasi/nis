"""Domain-specific validation rules for MEDRA — Medical/Clinical Decision Systems.

Deterministic checks for:
- Protocol section completeness (triage, dosage, contraindications, escalation)
- Dosage formula definitions and unit consistency
- Drug interaction matrix coverage
- Triage FSM state/transition validation
- Contraindication cross-reference integrity
- Evidence grading and determinism
"""

import re
from prompt_validator.result import Issue, Severity, Category


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _find_sections(prompt: str) -> dict[str, str]:
    """Split prompt into sections by 'SECTION N' headers."""
    pattern = re.compile(r"SECTION\s+(\d+)\s*[—–-]\s*(.*?)(?=SECTION\s+\d+|LOCK STATEMENT|FREEZE|$)", re.DOTALL)
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
    1: "PATIENT DATA CONTRACT",
    2: "VITAL SIGNS",
    3: "TRIAGE ENGINE",
    4: "DOSAGE CALCULATIONS",
    5: "DRUG INTERACTIONS",
    6: "CONTRAINDICATIONS",
    7: "CLINICAL DECISION TREE",
    8: "ESCALATION PROTOCOL",
    9: "OUTPUT FORMAT",
    10: "GOVERNANCE",
}


def check_section_completeness(prompt: str) -> list[Issue]:
    """Verify all critical clinical sections are present."""
    sections = _find_sections(prompt)
    missing = []
    for num, label in REQUIRED_SECTIONS.items():
        if num not in sections:
            missing.append(f"Section {num} ({label})")
    if missing:
        return [Issue(
            message="Missing critical clinical sections",
            severity=Severity.ERROR,
            category=Category.STRUCTURE,
            detail=f"Missing: {', '.join(missing)}",
            penalty=15 * len(missing),
        )]
    return []


def check_freeze_declaration(prompt: str) -> list[Issue]:
    """Verify a freeze/lock declaration exists for clinical governance."""
    lower = prompt.lower()
    has_freeze = "freeze declaration" in lower or "lock statement" in lower or "protocol lock" in lower
    has_governance = "governance" in lower
    issues = []
    if not has_freeze:
        issues.append(Issue(
            message="No protocol freeze/lock declaration found",
            severity=Severity.WARNING,
            category=Category.STRUCTURE,
            detail="A clinical decision system must include an explicit protocol freeze declaration.",
            penalty=8,
        ))
    if not has_governance:
        issues.append(Issue(
            message="No governance section found",
            severity=Severity.WARNING,
            category=Category.STRUCTURE,
            detail="Clinical systems require version-controlled governance for audit trails.",
            penalty=8,
        ))
    return issues


# ---------------------------------------------------------------------------
# 2. DOSAGE FORMULA & UNIT INTEGRITY
# ---------------------------------------------------------------------------

EXPECTED_FORMULAS = [
    ("DOSE_WEIGHT", r"DOSE_WEIGHT\s*="),
    ("BSA", r"BSA\s*="),
    ("CrCl", r"CrCl\s*="),
    ("GFR", r"GFR\s*="),
    ("AdjustedDose", r"AdjustedDose\s*="),
    ("InfusionRate", r"InfusionRate\s*="),
    ("MAX_DAILY", r"MAX_DAILY\s*="),
    ("PeakTrough", r"PeakTrough\s*="),
]


def check_formula_definitions(prompt: str) -> list[Issue]:
    """Verify key clinical formulas are explicitly defined."""
    missing = [name for name, pattern in EXPECTED_FORMULAS if not re.search(pattern, prompt)]
    if missing:
        return [Issue(
            message="Missing clinical formula definitions",
            severity=Severity.ERROR,
            category=Category.ACCURACY,
            detail=f"Formulas not defined: {', '.join(missing)}",
            penalty=10 * len(missing),
        )]
    return []


def check_unit_consistency(prompt: str) -> list[Issue]:
    """Check that dosage units are consistently defined (mg/kg, mL/hr, etc.)."""
    issues = []
    # Check for mixed unit systems
    has_metric = bool(re.search(r"\b(mg|mL|kg|mcg|mmol)\b", prompt))
    has_imperial = bool(re.search(r"\b(lbs|oz|grains|drams)\b", prompt, re.IGNORECASE))
    if has_metric and has_imperial:
        issues.append(Issue(
            message="Mixed unit systems detected",
            severity=Severity.ERROR,
            category=Category.ACCURACY,
            detail="Clinical formulas mix metric (mg, mL, kg) and imperial (lbs, oz) units. Use one system.",
            penalty=20,
        ))

    # Check that weight-based dosing specifies units
    weight_dose = re.findall(r"dose\s*=\s*[\d.]+\s*\*\s*weight", prompt, re.IGNORECASE)
    if weight_dose:
        has_units = bool(re.search(r"dose\s*=\s*[\d.]+\s*\*\s*weight.*?(mg/kg|mcg/kg)", prompt, re.IGNORECASE))
        if not has_units:
            issues.append(Issue(
                message="Weight-based dosing missing unit specification",
                severity=Severity.WARNING,
                category=Category.ACCURACY,
                detail="Weight-based dose calculations should specify units (e.g., mg/kg).",
                penalty=10,
            ))
    return issues


# ---------------------------------------------------------------------------
# 3. DRUG INTERACTION MATRIX
# ---------------------------------------------------------------------------

def check_interaction_matrix(prompt: str) -> list[Issue]:
    """Verify drug interaction severity levels are defined."""
    issues = []
    lower = prompt.lower()

    severity_levels = ["contraindicated", "major", "moderate", "minor"]
    found = [s for s in severity_levels if s in lower]
    if len(found) < 3:
        issues.append(Issue(
            message="Incomplete drug interaction severity classification",
            severity=Severity.WARNING,
            category=Category.ACCURACY,
            detail=f"Found {len(found)}/4 severity levels: {', '.join(found) or 'none'}. "
                   f"Expected: {', '.join(severity_levels)}.",
            penalty=8 * (4 - len(found)),
        ))

    # Check for interaction lookup mechanism
    has_lookup = any(k in lower for k in ["interaction matrix", "interaction table", "drug_a", "drug_b", "pair"])
    if not has_lookup:
        issues.append(Issue(
            message="No drug interaction lookup mechanism defined",
            severity=Severity.WARNING,
            category=Category.STRUCTURE,
            detail="A systematic interaction lookup (matrix/table) is needed for deterministic checking.",
            penalty=10,
        ))
    return issues


# ---------------------------------------------------------------------------
# 4. TRIAGE FSM VALIDATION
# ---------------------------------------------------------------------------

EXPECTED_STATES = {"GREEN", "YELLOW", "ORANGE", "RED", "BLACK", "OVERRIDE"}

EXPECTED_TRANSITIONS = [
    ("GREEN", "YELLOW"),
    ("YELLOW", "ORANGE"),
    ("ORANGE", "RED"),
    ("RED", "BLACK"),
]


def check_triage_states(prompt: str) -> list[Issue]:
    """Verify all triage severity states are defined."""
    upper = prompt.upper()
    missing = [s for s in EXPECTED_STATES if s not in upper]
    if missing:
        return [Issue(
            message="Missing triage states",
            severity=Severity.ERROR,
            category=Category.ACCURACY,
            detail=f"States not found: {', '.join(missing)}",
            penalty=10 * len(missing),
        )]
    return []


def check_triage_transitions(prompt: str) -> list[Issue]:
    """Verify triage escalation transitions are documented."""
    missing = []
    for src, dst in EXPECTED_TRANSITIONS:
        patterns = [f"{src}.*?→.*?{dst}", f"{src}.*?->.*?{dst}", f"{src}.*?to.*?{dst}"]
        if not any(re.search(p, prompt, re.IGNORECASE) for p in patterns):
            missing.append(f"{src} → {dst}")
    if missing:
        return [Issue(
            message="Missing triage escalation transitions",
            severity=Severity.WARNING,
            category=Category.ACCURACY,
            detail=f"Transitions not documented: {', '.join(missing)}",
            penalty=5 * len(missing),
        )]
    return []


def check_triage_dead_states(prompt: str) -> list[Issue]:
    """Check that terminal states have exit/review conditions."""
    issues = []
    if "BLACK" in prompt.upper():
        has_exit = bool(re.search(
            r"BLACK.*?(review|palliative|comfort|override|reassess|attending)",
            prompt, re.IGNORECASE | re.DOTALL,
        ))
        if not has_exit:
            issues.append(Issue(
                message="BLACK (expectant) triage has no review/override path",
                severity=Severity.ERROR,
                category=Category.ACCURACY,
                detail="Terminal triage categories must have physician override or reassessment rules.",
                penalty=15,
            ))
    return []


# ---------------------------------------------------------------------------
# 5. CONTRAINDICATION CROSS-REFERENCES
# ---------------------------------------------------------------------------

def check_contraindication_coverage(prompt: str) -> list[Issue]:
    """Verify contraindication checks reference defined patient data fields."""
    issues = []
    lower = prompt.lower()

    # Must check at least these patient factors
    required_checks = ["allergy", "renal", "hepatic", "pregnancy", "age"]
    found = [c for c in required_checks if c in lower]
    missing = [c for c in required_checks if c not in lower]
    if missing:
        issues.append(Issue(
            message="Incomplete contraindication screening",
            severity=Severity.WARNING,
            category=Category.ACCURACY,
            detail=f"Missing screening for: {', '.join(missing)}. Found: {', '.join(found)}.",
            penalty=5 * len(missing),
        ))
    return issues


# ---------------------------------------------------------------------------
# 6. DETERMINISM & SAFETY CHECKS
# ---------------------------------------------------------------------------

JUDGMENT_WORDS = [
    "probably", "likely", "seems", "appears", "might", "could be",
    "use your judgment", "discretion", "feel free", "up to you",
    "as appropriate", "if you think", "in your opinion",
    "clinical intuition", "gut feeling",
]


def check_determinism(prompt: str) -> list[Issue]:
    """Flag non-deterministic language in a clinical decision system."""
    lower = prompt.lower()
    found = [w for w in JUDGMENT_WORDS if w in lower]
    if found:
        return [Issue(
            message="Non-deterministic language in clinical decision system",
            severity=Severity.ERROR,
            category=Category.ACCURACY,
            detail=f"Judgment words found: {', '.join(repr(w) for w in found)}. "
                   f"Clinical algorithms must be fully deterministic.",
            penalty=10 * len(found),
        )]
    return []


def check_safety_halts(prompt: str) -> list[Issue]:
    """Verify that safety halt conditions are defined for critical failures."""
    lower = prompt.lower()
    has_halt = any(w in lower for w in ["halt", "emergency stop", "critical alert", "code blue"])
    has_override = any(w in lower for w in ["override", "physician override", "attending review"])
    issues = []
    if not has_halt:
        issues.append(Issue(
            message="No emergency halt condition defined",
            severity=Severity.ERROR,
            category=Category.ACCURACY,
            detail="Clinical systems must define halt conditions for critical patient deterioration.",
            penalty=20,
        ))
    if not has_override:
        issues.append(Issue(
            message="No physician override mechanism",
            severity=Severity.WARNING,
            category=Category.ACCURACY,
            detail="Automated clinical decisions must allow physician override.",
            penalty=10,
        ))
    return issues


def check_output_format_section(prompt: str) -> list[Issue]:
    """Verify that the clinical output format is rigidly defined."""
    lower = prompt.lower()
    has_output = "output format" in lower or "report format" in lower or "print every" in lower
    if not has_output:
        return [Issue(
            message="No output format section",
            severity=Severity.WARNING,
            category=Category.STRUCTURE,
            detail="Clinical systems must define exact output format for reproducibility and audit.",
            penalty=8,
        )]
    return []


# ---------------------------------------------------------------------------
# 7. EVIDENCE GRADING
# ---------------------------------------------------------------------------

def check_evidence_grading(prompt: str) -> list[Issue]:
    """Check that clinical rules reference evidence levels."""
    lower = prompt.lower()
    has_evidence = any(k in lower for k in [
        "evidence level", "grade a", "grade b", "level i", "level ii",
        "cochrane", "meta-analysis", "rct", "randomized",
        "evidence-based", "guideline", "protocol reference",
    ])
    if not has_evidence:
        return [Issue(
            message="No evidence grading referenced",
            severity=Severity.INFO,
            category=Category.ACCURACY,
            detail="Clinical decision rules should reference evidence levels or guideline sources.",
            penalty=5,
        )]
    return []


# ---------------------------------------------------------------------------
# 8. GOVERNANCE
# ---------------------------------------------------------------------------

def check_governance_entries(prompt: str) -> list[Issue]:
    """Verify governance entries have required audit fields."""
    gov_entries = re.findall(r"GOV-[\w-]+", prompt)
    if not gov_entries:
        return [Issue(
            message="No governance entries found",
            severity=Severity.INFO,
            category=Category.STRUCTURE,
            detail="Clinical systems require governance entries for regulatory audit trails.",
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
# Aggregate all MEDRA rules
# ---------------------------------------------------------------------------

ALL_MEDRA_RULES = [
    check_section_completeness,
    check_freeze_declaration,
    check_formula_definitions,
    check_unit_consistency,
    check_interaction_matrix,
    check_triage_states,
    check_triage_transitions,
    check_triage_dead_states,
    check_contraindication_coverage,
    check_determinism,
    check_safety_halts,
    check_output_format_section,
    check_evidence_grading,
    check_governance_entries,
]
