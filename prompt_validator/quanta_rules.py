"""Domain-specific validation rules for QUANTA — Scientific Computing/Research Systems.

Deterministic checks for:
- Methodology section completeness
- Formula/equation definitions and variable consistency
- Unit dimensional analysis
- Error bound and uncertainty specifications
- Reproducibility requirements (seed, versioning)
- Statistical rigor (p-values, confidence intervals)
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
    1: "DATA CONTRACT",
    2: "UNITS AND CONSTANTS",
    3: "CORE EQUATIONS",
    4: "ERROR BOUNDS",
    5: "STATISTICAL METHODS",
    6: "CONVERGENCE CRITERIA",
    7: "VALIDATION PROTOCOL",
    8: "REPRODUCIBILITY",
    9: "OUTPUT FORMAT",
    10: "GOVERNANCE",
}


def check_section_completeness(prompt: str) -> list[Issue]:
    sections = _find_sections(prompt)
    missing = [f"Section {n} ({l})" for n, l in REQUIRED_SECTIONS.items() if n not in sections]
    if missing:
        return [Issue(
            message="Missing critical research sections",
            severity=Severity.ERROR,
            category=Category.STRUCTURE,
            detail=f"Missing: {', '.join(missing)}",
            penalty=15 * len(missing),
        )]
    return []


def check_freeze_declaration(prompt: str) -> list[Issue]:
    lower = prompt.lower()
    has_freeze = "freeze declaration" in lower or "lock statement" in lower or "version lock" in lower
    has_governance = "governance" in lower
    issues = []
    if not has_freeze:
        issues.append(Issue(
            message="No methodology freeze/lock declaration found",
            severity=Severity.WARNING,
            category=Category.STRUCTURE,
            detail="Scientific computing systems should include an explicit methodology freeze.",
            penalty=8,
        ))
    if not has_governance:
        issues.append(Issue(
            message="No governance section found",
            severity=Severity.WARNING,
            category=Category.STRUCTURE,
            detail="Research systems require version-controlled governance for reproducibility.",
            penalty=8,
        ))
    return issues


# ---------------------------------------------------------------------------
# 2. EQUATION & FORMULA INTEGRITY
# ---------------------------------------------------------------------------

EXPECTED_FORMULAS = [
    ("RESIDUAL", r"RESIDUAL\s*="),
    ("CHI_SQUARED", r"CHI_SQUARED\s*="),
    ("RMSE", r"RMSE\s*="),
    ("CONFIDENCE_INTERVAL", r"CONFIDENCE_INTERVAL\s*="),
    ("P_VALUE", r"P_VALUE\s*="),
    ("CONVERGENCE_METRIC", r"CONVERGENCE_METRIC\s*="),
    ("NORM_ERROR", r"NORM_ERROR\s*="),
    ("LIKELIHOOD", r"LIKELIHOOD\s*="),
]


def check_formula_definitions(prompt: str) -> list[Issue]:
    missing = [name for name, pat in EXPECTED_FORMULAS if not re.search(pat, prompt)]
    if missing:
        return [Issue(
            message="Missing scientific formula definitions",
            severity=Severity.ERROR,
            category=Category.ACCURACY,
            detail=f"Formulas not defined: {', '.join(missing)}",
            penalty=10 * len(missing),
        )]
    return []


def check_unit_definitions(prompt: str) -> list[Issue]:
    """Verify that physical units/constants are explicitly defined."""
    lower = prompt.lower()
    has_units = any(k in lower for k in [
        "si unit", "unit:", "dimension:", "meter", "kilogram", "second",
        "joule", "kelvin", "mole", "ampere", "radian",
        "dimensionless", "unit system",
    ])
    if not has_units:
        return [Issue(
            message="No unit system defined",
            severity=Severity.WARNING,
            category=Category.ACCURACY,
            detail="Scientific computations must specify the unit system (SI, CGS, natural units).",
            penalty=10,
        )]
    return []


def check_constants(prompt: str) -> list[Issue]:
    """Verify that physical/mathematical constants are pinned to specific values."""
    lower = prompt.lower()
    constant_terms = ["pi =", "e =", "c =", "h =", "k_b =", "boltzmann", "avogadro", "planck"]
    found = [c for c in constant_terms if c in lower]
    has_constants_section = "constants" in lower or "physical constants" in lower
    if not has_constants_section and not found:
        return [Issue(
            message="No physical/mathematical constants pinned",
            severity=Severity.INFO,
            category=Category.ACCURACY,
            detail="Pin constants to specific values for reproducibility (e.g., pi = 3.14159265358979).",
            penalty=5,
        )]
    return []


# ---------------------------------------------------------------------------
# 3. ERROR BOUNDS & UNCERTAINTY
# ---------------------------------------------------------------------------

def check_error_bounds(prompt: str) -> list[Issue]:
    """Verify error bounds / uncertainty quantification exists."""
    lower = prompt.lower()
    has_error = any(k in lower for k in [
        "error bound", "uncertainty", "tolerance", "epsilon",
        "±", "sigma", "standard deviation", "confidence interval",
        "error propagation", "monte carlo",
    ])
    if not has_error:
        return [Issue(
            message="No error bounds or uncertainty quantification defined",
            severity=Severity.ERROR,
            category=Category.ACCURACY,
            detail="Scientific computations must specify error bounds or uncertainty measures.",
            penalty=15,
        )]
    return []


def check_convergence_criteria(prompt: str) -> list[Issue]:
    """Verify that iterative methods have convergence criteria."""
    lower = prompt.lower()
    has_iterative = any(k in lower for k in ["iterate", "iteration", "converge", "loop until", "while"])
    if has_iterative:
        has_criteria = any(k in lower for k in [
            "convergence", "tolerance", "max_iter", "residual <", "epsilon",
            "stopping criterion", "termination",
        ])
        if not has_criteria:
            return [Issue(
                message="Iterative method without convergence criteria",
                severity=Severity.ERROR,
                category=Category.ACCURACY,
                detail="All iterative computations must define convergence/termination criteria.",
                penalty=15,
            )]
    return []


# ---------------------------------------------------------------------------
# 4. REPRODUCIBILITY
# ---------------------------------------------------------------------------

EXPECTED_REPRO_STATES = {"DRAFT", "VALIDATED", "PEER_REVIEWED", "PUBLISHED", "RETRACTED", "ARCHIVED"}

EXPECTED_TRANSITIONS = [
    ("DRAFT", "VALIDATED"),
    ("VALIDATED", "PEER_REVIEWED"),
    ("PEER_REVIEWED", "PUBLISHED"),
    ("PUBLISHED", "RETRACTED"),
]


def check_repro_states(prompt: str) -> list[Issue]:
    upper = prompt.upper()
    missing = [s for s in EXPECTED_REPRO_STATES if s not in upper]
    if missing:
        return [Issue(
            message="Missing research lifecycle states",
            severity=Severity.WARNING,
            category=Category.ACCURACY,
            detail=f"States not found: {', '.join(missing)}",
            penalty=3 * len(missing),
        )]
    return []


def check_repro_transitions(prompt: str) -> list[Issue]:
    missing = []
    for src, dst in EXPECTED_TRANSITIONS:
        patterns = [f"{src}.*?→.*?{dst}", f"{src}.*?->.*?{dst}", f"{src}.*?to.*?{dst}"]
        if not any(re.search(p, prompt, re.IGNORECASE) for p in patterns):
            missing.append(f"{src} → {dst}")
    if missing:
        return [Issue(
            message="Missing research lifecycle transitions",
            severity=Severity.WARNING,
            category=Category.ACCURACY,
            detail=f"Transitions not documented: {', '.join(missing)}",
            penalty=5 * len(missing),
        )]
    return []


def check_random_seed(prompt: str) -> list[Issue]:
    """Verify random seed / deterministic execution is specified."""
    lower = prompt.lower()
    has_seed = any(k in lower for k in ["random seed", "seed =", "rng_seed", "deterministic", "fixed seed"])
    if not has_seed:
        return [Issue(
            message="No random seed specification",
            severity=Severity.WARNING,
            category=Category.ACCURACY,
            detail="Stochastic computations must specify random seeds for reproducibility.",
            penalty=8,
        )]
    return []


# ---------------------------------------------------------------------------
# 5. DETERMINISM
# ---------------------------------------------------------------------------

JUDGMENT_WORDS = [
    "probably", "likely", "seems", "appears", "might", "could be",
    "use your judgment", "discretion", "feel free", "up to you",
    "as appropriate", "if you think", "in your opinion",
    "approximately right", "close enough",
]


def check_determinism(prompt: str) -> list[Issue]:
    lower = prompt.lower()
    found = [w for w in JUDGMENT_WORDS if w in lower]
    if found:
        return [Issue(
            message="Non-deterministic language in scientific computing system",
            severity=Severity.ERROR,
            category=Category.ACCURACY,
            detail=f"Judgment words: {', '.join(repr(w) for w in found)}. "
                   f"Scientific computations must use precise, deterministic language.",
            penalty=10 * len(found),
        )]
    return []


def check_output_format_section(prompt: str) -> list[Issue]:
    lower = prompt.lower()
    if "output format" not in lower and "results format" not in lower:
        return [Issue(
            message="No output format section",
            severity=Severity.WARNING,
            category=Category.STRUCTURE,
            detail="Scientific systems must define exact output format for reproducibility.",
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
            detail="Research systems require governance entries for methodology audit trails.",
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

ALL_QUANTA_RULES = [
    check_section_completeness,
    check_freeze_declaration,
    check_formula_definitions,
    check_unit_definitions,
    check_constants,
    check_error_bounds,
    check_convergence_criteria,
    check_repro_states,
    check_repro_transitions,
    check_random_seed,
    check_determinism,
    check_output_format_section,
    check_governance_entries,
]
