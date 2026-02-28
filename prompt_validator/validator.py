"""Core PromptValidator class."""

from prompt_validator.result import ValidationResult
from prompt_validator.rules import ALL_RULES, generate_suggestions


class PromptValidator:
    """Validates prompts for clarity, efficiency, and accuracy.

    Usage:
        validator = PromptValidator()
        result = validator.validate("You are a helpful assistant. Summarize the text.")
        print(result.score)   # 0-100
        print(result.grade)   # A-F
        print(result.issues)  # list of Issue objects
    """

    def __init__(self, rules=None):
        self.rules = rules if rules is not None else ALL_RULES

    def validate(self, prompt: str) -> ValidationResult:
        """Run all validation rules against the given prompt and return a result."""
        result = ValidationResult(prompt=prompt)

        for rule in self.rules:
            issues = rule(prompt)
            for issue in issues:
                result.issues.append(issue)
                result.score = max(0, result.score - issue.penalty)

        result.suggestions = generate_suggestions(prompt, result.issues)
        return result

    def validate_batch(self, prompts: list[str]) -> list[ValidationResult]:
        """Validate multiple prompts and return a list of results."""
        return [self.validate(p) for p in prompts]
