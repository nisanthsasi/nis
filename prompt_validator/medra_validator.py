"""MEDRA-specific prompt system validator.

Validates Medical/Clinical Decision System prompts with both generic
prompt quality checks AND domain-specific clinical integrity checks.

Usage:
    python -m prompt_validator.medra_validator prompts/medra_clinical.txt
"""

import argparse
import json
import sys

from prompt_validator.result import ValidationResult, Category, Severity
from prompt_validator.rules import ALL_RULES as GENERIC_RULES, generate_suggestions
from prompt_validator.medra_rules import ALL_MEDRA_RULES


class MedraValidator:
    """Validates MEDRA-style deterministic clinical decision systems."""

    def __init__(self):
        self.generic_rules = GENERIC_RULES
        self.domain_rules = ALL_MEDRA_RULES

    def validate(self, prompt: str) -> dict:
        generic_result = ValidationResult(prompt=prompt)
        for rule in self.generic_rules:
            for issue in rule(prompt):
                generic_result.issues.append(issue)
                generic_result.score = max(0, generic_result.score - issue.penalty)
        generic_result.suggestions = generate_suggestions(prompt, generic_result.issues)

        domain_result = ValidationResult(prompt=prompt)
        for rule in self.domain_rules:
            for issue in rule(prompt):
                domain_result.issues.append(issue)
                domain_result.score = max(0, domain_result.score - issue.penalty)

        domain_suggestions = []
        cats = set(i.category for i in domain_result.issues)
        if Category.ACCURACY in cats:
            domain_suggestions.append("Fix clinical formula definitions and cross-references before deployment.")
            domain_suggestions.append("Verify all dosage thresholds and drug interactions are consistent.")
        if Category.STRUCTURE in cats:
            domain_suggestions.append("Ensure all required clinical sections are present and numbered.")
        has_fsm_issue = any("triage" in i.message.lower() for i in domain_result.issues)
        if has_fsm_issue:
            domain_suggestions.append("Review triage FSM transitions — every severity level needs escalation and de-escalation paths.")
        domain_result.suggestions = domain_suggestions

        combined_score = int(0.35 * generic_result.score + 0.65 * domain_result.score)

        return {
            "combined_score": combined_score,
            "combined_grade": _grade(combined_score),
            "generic": generic_result,
            "domain": domain_result,
        }


def _grade(score: int) -> str:
    if score >= 90: return "A"
    elif score >= 80: return "B"
    elif score >= 70: return "C"
    elif score >= 60: return "D"
    else: return "F"


def print_report(results: dict):
    generic = results["generic"]
    domain = results["domain"]

    print("=" * 70)
    print("  MEDRA CLINICAL DECISION SYSTEM — FULL VALIDATION REPORT")
    print("=" * 70)

    word_count = len(generic.prompt.split())
    char_count = len(generic.prompt)
    print(f"\n  Document: {word_count} words / {char_count} chars")
    print(f"  Combined Score: {results['combined_score']}/100 (Grade: {results['combined_grade']})")
    print()

    print("-" * 70)
    print("  PART 1: GENERIC PROMPT QUALITY")
    print(f"  Score: {generic.score}/100 (Grade: {generic.grade})")
    print("-" * 70)
    if generic.issues:
        for issue in generic.issues:
            icon = {"error": "[ERR]", "warning": "[WARN]", "info": "[INFO]"}[issue.severity.value]
            print(f"  {icon} [{issue.category.value}] {issue.message}")
            if issue.detail:
                print(f"        -> {issue.detail}")
    else:
        print("  No issues found.")
    if generic.suggestions:
        print("\n  Suggestions:")
        for s in generic.suggestions:
            print(f"    * {s}")

    print()
    print("-" * 70)
    print("  PART 2: DOMAIN-SPECIFIC (CLINICAL DECISION INTEGRITY)")
    print(f"  Score: {domain.score}/100 (Grade: {domain.grade})")
    print("-" * 70)
    if domain.issues:
        for issue in domain.issues:
            icon = {"error": "[ERR]", "warning": "[WARN]", "info": "[INFO]"}[issue.severity.value]
            print(f"  {icon} [{issue.category.value}] {issue.message}")
            if issue.detail:
                print(f"        -> {issue.detail}")
    else:
        print("  No issues found.")
    if domain.suggestions:
        print("\n  Suggestions:")
        for s in domain.suggestions:
            print(f"    * {s}")

    print()
    print("=" * 70)
    print("  VERDICT")
    print("=" * 70)
    score = results["combined_score"]
    if score >= 85:
        verdict = "PASS — System is well-structured and ready for clinical deployment."
    elif score >= 70:
        verdict = "CONDITIONAL PASS — Minor issues found; review before deployment."
    elif score >= 50:
        verdict = "NEEDS WORK — Significant issues that should be addressed."
    else:
        verdict = "FAIL — Critical problems detected; not ready for clinical use."
    print(f"  {verdict}")
    print(f"  Combined: {score}/100 | Generic: {generic.score}/100 | Domain: {domain.score}/100")
    print("=" * 70)


def main():
    parser = argparse.ArgumentParser(description="Validate a MEDRA clinical decision prompt system.")
    parser.add_argument("file", help="Path to the MEDRA prompt file.")
    parser.add_argument("--json", action="store_true", dest="json_output", help="Output as JSON.")
    args = parser.parse_args()

    try:
        with open(args.file) as f:
            prompt = f.read()
    except FileNotFoundError:
        print(f"Error: file not found: {args.file}", file=sys.stderr)
        sys.exit(1)

    validator = MedraValidator()
    results = validator.validate(prompt)

    if args.json_output:
        out = {
            "combined_score": results["combined_score"],
            "combined_grade": results["combined_grade"],
            "generic": results["generic"].to_dict(),
            "domain": results["domain"].to_dict(),
        }
        print(json.dumps(out, indent=2))
    else:
        print_report(results)

    sys.exit(0 if results["combined_score"] >= 70 else 1)


if __name__ == "__main__":
    main()
