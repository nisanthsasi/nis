"""Data classes for validation results."""

from dataclasses import dataclass, field
from enum import Enum


class Severity(Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class Category(Enum):
    CLARITY = "clarity"
    EFFICIENCY = "efficiency"
    ACCURACY = "accuracy"
    STRUCTURE = "structure"


@dataclass
class Issue:
    message: str
    severity: Severity
    category: Category
    detail: str = ""
    penalty: int = 0

    def to_dict(self):
        return {
            "message": self.message,
            "severity": self.severity.value,
            "category": self.category.value,
            "detail": self.detail,
            "penalty": self.penalty,
        }


@dataclass
class ValidationResult:
    prompt: str
    score: int = 100
    issues: list = field(default_factory=list)
    suggestions: list = field(default_factory=list)

    @property
    def grade(self) -> str:
        if self.score >= 90:
            return "A"
        elif self.score >= 80:
            return "B"
        elif self.score >= 70:
            return "C"
        elif self.score >= 60:
            return "D"
        else:
            return "F"

    @property
    def is_valid(self) -> bool:
        return not any(i.severity == Severity.ERROR for i in self.issues)

    @property
    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == Severity.ERROR)

    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == Severity.WARNING)

    def to_dict(self):
        return {
            "score": self.score,
            "grade": self.grade,
            "is_valid": self.is_valid,
            "errors": self.error_count,
            "warnings": self.warning_count,
            "issues": [i.to_dict() for i in self.issues],
            "suggestions": self.suggestions,
        }

    def summary(self) -> str:
        lines = [
            f"Score: {self.score}/100 (Grade: {self.grade})",
            f"Valid: {'Yes' if self.is_valid else 'No'}",
            f"Errors: {self.error_count} | Warnings: {self.warning_count}",
        ]
        if self.issues:
            lines.append("\nIssues:")
            for issue in self.issues:
                icon = {"error": "[ERR]", "warning": "[WARN]", "info": "[INFO]"}[
                    issue.severity.value
                ]
                lines.append(f"  {icon} [{issue.category.value}] {issue.message}")
                if issue.detail:
                    lines.append(f"        -> {issue.detail}")
        if self.suggestions:
            lines.append("\nSuggestions:")
            for s in self.suggestions:
                lines.append(f"  * {s}")
        return "\n".join(lines)
