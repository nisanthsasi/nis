"""Unified trading strategy validator factory.

Supports all 5 trading strategy models:
- VORTEX (Momentum/Trend Following)
- NEXUS (Mean Reversion)
- PRISM (Options/Greeks)
- FLUX (Scalping/HFT)
- TITAN (Swing/Multi-day)

Usage:
    python -m prompt_validator.trading_validator --model vortex prompts/vortex_momentum.txt
    python -m prompt_validator.trading_validator --model nexus prompts/nexus_reversion.txt
"""

import argparse
import json
import sys

from prompt_validator.result import ValidationResult, Category
from prompt_validator.rules import ALL_RULES as GENERIC_RULES, generate_suggestions
from prompt_validator.vortex_rules import ALL_VORTEX_RULES
from prompt_validator.nexus_rules import ALL_NEXUS_RULES
from prompt_validator.prism_rules import ALL_PRISM_RULES
from prompt_validator.flux_rules import ALL_FLUX_RULES
from prompt_validator.titan_rules import ALL_TITAN_RULES


MODEL_REGISTRY = {
    "vortex": ("VORTEX MOMENTUM/TREND SYSTEM", ALL_VORTEX_RULES),
    "nexus": ("NEXUS MEAN REVERSION SYSTEM", ALL_NEXUS_RULES),
    "prism": ("PRISM OPTIONS/GREEKS SYSTEM", ALL_PRISM_RULES),
    "flux": ("FLUX SCALPING/HFT SYSTEM", ALL_FLUX_RULES),
    "titan": ("TITAN SWING/MULTI-DAY SYSTEM", ALL_TITAN_RULES),
}


class TradingValidator:
    """Validates trading strategy prompt systems."""

    def __init__(self, model: str):
        if model not in MODEL_REGISTRY:
            raise ValueError(f"Unknown model: {model}. Available: {', '.join(MODEL_REGISTRY)}")
        self.model = model
        self.title, self.domain_rules = MODEL_REGISTRY[model]
        self.generic_rules = GENERIC_RULES

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
            domain_suggestions.append("Fix formula definitions and cross-references before deployment.")
            domain_suggestions.append("Verify all threshold values are consistent across sections.")
        if Category.STRUCTURE in cats:
            domain_suggestions.append("Ensure all required sections are present and numbered.")
        has_fsm_issue = any("fsm" in i.message.lower() for i in domain_result.issues)
        if has_fsm_issue:
            domain_suggestions.append("Review FSM transitions — every state needs entry and exit paths.")
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


def print_report(results: dict, title: str):
    generic = results["generic"]
    domain = results["domain"]
    print("=" * 70)
    print(f"  {title} — FULL VALIDATION REPORT")
    print("=" * 70)
    print(f"\n  Document: {len(generic.prompt.split())} words / {len(generic.prompt)} chars")
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
            if issue.detail: print(f"        -> {issue.detail}")
    else: print("  No issues found.")
    if generic.suggestions:
        print("\n  Suggestions:")
        for s in generic.suggestions: print(f"    * {s}")
    print()
    print("-" * 70)
    print("  PART 2: DOMAIN-SPECIFIC (TRADING STRATEGY INTEGRITY)")
    print(f"  Score: {domain.score}/100 (Grade: {domain.grade})")
    print("-" * 70)
    if domain.issues:
        for issue in domain.issues:
            icon = {"error": "[ERR]", "warning": "[WARN]", "info": "[INFO]"}[issue.severity.value]
            print(f"  {icon} [{issue.category.value}] {issue.message}")
            if issue.detail: print(f"        -> {issue.detail}")
    else: print("  No issues found.")
    if domain.suggestions:
        print("\n  Suggestions:")
        for s in domain.suggestions: print(f"    * {s}")
    print()
    print("=" * 70)
    print("  VERDICT")
    print("=" * 70)
    score = results["combined_score"]
    if score >= 85: verdict = "PASS — System is well-structured and ready for deployment."
    elif score >= 70: verdict = "CONDITIONAL PASS — Minor issues found; review before deployment."
    elif score >= 50: verdict = "NEEDS WORK — Significant issues that should be addressed."
    else: verdict = "FAIL — Critical problems detected; not ready for use."
    print(f"  {verdict}")
    print(f"  Combined: {score}/100 | Generic: {generic.score}/100 | Domain: {domain.score}/100")
    print("=" * 70)


def main():
    parser = argparse.ArgumentParser(description="Validate a trading strategy prompt system.")
    parser.add_argument("file", help="Path to the prompt file.")
    parser.add_argument("--model", required=True, choices=list(MODEL_REGISTRY.keys()),
                        help="Trading model to validate against.")
    parser.add_argument("--json", action="store_true", dest="json_output")
    args = parser.parse_args()

    try:
        with open(args.file) as f: prompt = f.read()
    except FileNotFoundError:
        print(f"Error: file not found: {args.file}", file=sys.stderr); sys.exit(1)

    validator = TradingValidator(args.model)
    results = validator.validate(prompt)

    if args.json_output:
        print(json.dumps({"combined_score": results["combined_score"], "combined_grade": results["combined_grade"],
                          "generic": results["generic"].to_dict(), "domain": results["domain"].to_dict()}, indent=2))
    else:
        print_report(results, validator.title)

    sys.exit(0 if results["combined_score"] >= 70 else 1)


if __name__ == "__main__":
    main()
