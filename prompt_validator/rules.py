"""Validation rules for checking prompt quality."""

import re
from prompt_validator.result import Issue, Severity, Category


# ---------------------------------------------------------------------------
# 1. CLARITY CHECKS
# ---------------------------------------------------------------------------

VAGUE_PHRASES = [
    "do something",
    "do stuff",
    "figure it out",
    "you know what i mean",
    "etc",
    "and so on",
    "whatever",
    "things like that",
    "somehow",
    "kind of",
    "sort of",
    "maybe do",
    "try to maybe",
    "if possible maybe",
]

AMBIGUOUS_PRONOUNS_PATTERN = re.compile(
    r"\b(it|this|that|they|them|those|these)\b(?!\s+(is|are|was|were|will|should|must|can|could|shall))",
    re.IGNORECASE,
)


def check_empty_prompt(prompt: str) -> list[Issue]:
    text = prompt.strip()
    if not text:
        return [
            Issue(
                message="Prompt is empty",
                severity=Severity.ERROR,
                category=Category.CLARITY,
                detail="An empty prompt cannot produce meaningful output.",
                penalty=100,
            )
        ]
    return []


def check_too_short(prompt: str) -> list[Issue]:
    word_count = len(prompt.split())
    if 0 < word_count < 3:
        return [
            Issue(
                message="Prompt is extremely short",
                severity=Severity.WARNING,
                category=Category.CLARITY,
                detail=f"Only {word_count} word(s). Short prompts often lack context.",
                penalty=15,
            )
        ]
    return []


def check_vague_language(prompt: str) -> list[Issue]:
    issues = []
    lower = prompt.lower()
    found = [p for p in VAGUE_PHRASES if p in lower]
    if found:
        issues.append(
            Issue(
                message="Vague language detected",
                severity=Severity.WARNING,
                category=Category.CLARITY,
                detail=f"Found vague phrases: {', '.join(repr(f) for f in found)}",
                penalty=5 * len(found),
            )
        )
    return issues


def check_missing_task(prompt: str) -> list[Issue]:
    """Check if the prompt lacks a clear action verb / task directive."""
    action_verbs = [
        "write", "create", "generate", "explain", "summarize", "list",
        "describe", "analyze", "translate", "compare", "help", "answer",
        "provide", "build", "design", "implement", "review", "evaluate",
        "suggest", "recommend", "convert", "calculate", "solve", "find",
        "tell", "show", "give", "make", "respond", "act", "return",
        "output", "extract", "classify", "identify", "define", "clarify",
    ]
    lower = prompt.lower()
    has_verb = any(v in lower.split() or v in lower for v in action_verbs)
    has_question = "?" in prompt
    if not has_verb and not has_question:
        return [
            Issue(
                message="No clear task or question detected",
                severity=Severity.WARNING,
                category=Category.CLARITY,
                detail="The prompt doesn't contain a recognisable action verb or question.",
                penalty=10,
            )
        ]
    return []


def check_no_context(prompt: str) -> list[Issue]:
    """Flag prompts that give no context or role."""
    word_count = len(prompt.split())
    role_keywords = ["you are", "act as", "role", "context", "background", "given"]
    lower = prompt.lower()
    has_role = any(k in lower for k in role_keywords)
    if word_count > 5 and not has_role:
        return [
            Issue(
                message="No role or context provided",
                severity=Severity.INFO,
                category=Category.CLARITY,
                detail="Adding a role or context (e.g. 'You are a ...') can improve output quality.",
                penalty=3,
            )
        ]
    return []


# ---------------------------------------------------------------------------
# 2. EFFICIENCY CHECKS
# ---------------------------------------------------------------------------

FILLER_WORDS = [
    "basically", "actually", "really", "very", "just", "quite",
    "literally", "honestly", "seriously", "obviously", "certainly",
    "definitely", "absolutely", "simply", "merely",
]


def _is_structured_spec(prompt: str) -> bool:
    """Detect whether the prompt is a structured system specification.

    Structured specs (with numbered sections, formulas, state machines) are
    inherently long by design.  Length penalties should be reduced for these.
    """
    section_headers = len(re.findall(r"SECTION\s+\d+", prompt, re.IGNORECASE))
    has_formulas = bool(re.search(r"[A-Z_]+\s*=\s*", prompt))
    return section_headers >= 3 and has_formulas


def check_excessive_length(prompt: str) -> list[Issue]:
    word_count = len(prompt.split())
    structured = _is_structured_spec(prompt)

    if word_count > 2000:
        if structured:
            return [
                Issue(
                    message="Structured specification is long",
                    severity=Severity.INFO,
                    category=Category.EFFICIENCY,
                    detail=f"{word_count} words across {len(re.findall(r'SECTION', prompt, re.IGNORECASE))} sections. "
                           f"Length is expected for a system specification; verify no unnecessary duplication.",
                    penalty=3,
                )
            ]
        return [
            Issue(
                message="Prompt is excessively long",
                severity=Severity.WARNING,
                category=Category.EFFICIENCY,
                detail=f"{word_count} words. Very long prompts increase cost and may dilute focus.",
                penalty=15,
            )
        ]
    elif word_count > 1000:
        return [
            Issue(
                message="Prompt is quite long",
                severity=Severity.INFO,
                category=Category.EFFICIENCY,
                detail=f"{word_count} words. Consider whether all content is necessary.",
                penalty=5,
            )
        ]
    return []


def check_filler_words(prompt: str) -> list[Issue]:
    words = prompt.lower().split()
    found = [w for w in FILLER_WORDS if w in words]
    if len(found) >= 3:
        return [
            Issue(
                message="Multiple filler words detected",
                severity=Severity.WARNING,
                category=Category.EFFICIENCY,
                detail=f"Filler words: {', '.join(repr(w) for w in found)}. Removing them makes the prompt more concise.",
                penalty=3 * len(found),
            )
        ]
    elif found:
        return [
            Issue(
                message="Filler words detected",
                severity=Severity.INFO,
                category=Category.EFFICIENCY,
                detail=f"Filler words: {', '.join(repr(w) for w in found)}.",
                penalty=1 * len(found),
            )
        ]
    return []


def check_repeated_sentences(prompt: str) -> list[Issue]:
    # Only consider fragments with 3+ words as real sentences.
    # Single words/numbers from version strings or list items are not duplicates.
    sentences = [
        s.strip().lower()
        for s in re.split(r'[.!?]+', prompt)
        if s.strip() and len(s.strip().split()) >= 3
    ]
    seen = set()
    duplicates = set()
    for s in sentences:
        if s in seen:
            duplicates.add(s)
        seen.add(s)
    if duplicates:
        return [
            Issue(
                message="Repeated sentences detected",
                severity=Severity.WARNING,
                category=Category.EFFICIENCY,
                detail=f"{len(duplicates)} sentence(s) are duplicated. Remove repetition to save tokens.",
                penalty=8 * len(duplicates),
            )
        ]
    return []


def check_redundant_instructions(prompt: str) -> list[Issue]:
    """Detect common redundant patterns like 'please please' or restated directives."""
    issues = []
    lower = prompt.lower()
    # Repeated please
    if lower.count("please") > 2:
        issues.append(
            Issue(
                message="Excessive use of 'please'",
                severity=Severity.INFO,
                category=Category.EFFICIENCY,
                detail="Using 'please' more than twice adds no value for an AI system.",
                penalty=3,
            )
        )
    # "I want you to" repeated
    if lower.count("i want you to") > 1:
        issues.append(
            Issue(
                message="Repeated 'I want you to' phrasing",
                severity=Severity.INFO,
                category=Category.EFFICIENCY,
                detail="State the instruction once; repetition wastes tokens.",
                penalty=3,
            )
        )
    return issues


# ---------------------------------------------------------------------------
# 3. ACCURACY / STRUCTURE CHECKS
# ---------------------------------------------------------------------------

def check_contradictions(prompt: str) -> list[Issue]:
    """Detect obvious contradictory instructions."""
    contradiction_pairs = [
        ("be concise", "be detailed"),
        ("be brief", "be thorough"),
        ("short answer", "long answer"),
        ("do not explain", "explain in detail"),
        ("ignore all", "follow all"),
        ("never use", "always use"),
        ("be formal", "be casual"),
    ]
    lower = prompt.lower()
    issues = []
    for a, b in contradiction_pairs:
        if a in lower and b in lower:
            issues.append(
                Issue(
                    message="Contradictory instructions detected",
                    severity=Severity.ERROR,
                    category=Category.ACCURACY,
                    detail=f"'{a}' conflicts with '{b}'.",
                    penalty=20,
                )
            )
    return issues


def check_role_consistency(prompt: str) -> list[Issue]:
    """Check for multiple conflicting role assignments."""
    role_patterns = re.findall(
        r"(?:you are|act as|role:\s*|pretend to be|behave as)\s+(?:a |an )?(\w[\w\s]{0,30})",
        prompt,
        re.IGNORECASE,
    )
    if len(role_patterns) > 1:
        unique_roles = set(r.strip().lower() for r in role_patterns)
        if len(unique_roles) > 1:
            return [
                Issue(
                    message="Multiple conflicting roles assigned",
                    severity=Severity.ERROR,
                    category=Category.ACCURACY,
                    detail=f"Roles found: {', '.join(repr(r) for r in unique_roles)}. Use one clear role.",
                    penalty=20,
                )
            ]
    return []


def check_output_format_specified(prompt: str) -> list[Issue]:
    """Check whether the prompt specifies an output format."""
    format_keywords = [
        "json", "xml", "csv", "markdown", "bullet", "numbered list",
        "table", "format:", "output format", "respond in", "reply in",
        "answer in", "return as", "structured as",
    ]
    lower = prompt.lower()
    has_format = any(k in lower for k in format_keywords)
    word_count = len(prompt.split())
    if word_count > 20 and not has_format:
        return [
            Issue(
                message="No output format specified",
                severity=Severity.INFO,
                category=Category.STRUCTURE,
                detail="Consider specifying the desired output format for more predictable results.",
                penalty=3,
            )
        ]
    return []


def check_injection_risk(prompt: str) -> list[Issue]:
    """Flag patterns that look like prompt injection attempts."""
    risky_patterns = [
        "ignore previous instructions",
        "ignore all previous",
        "disregard above",
        "forget everything",
        "override your instructions",
        "new instructions:",
        "system prompt:",
        "reveal your prompt",
        "show your instructions",
    ]
    lower = prompt.lower()
    found = [p for p in risky_patterns if p in lower]
    if found:
        return [
            Issue(
                message="Potential prompt injection pattern detected",
                severity=Severity.ERROR,
                category=Category.ACCURACY,
                detail=f"Suspicious patterns: {', '.join(repr(p) for p in found)}",
                penalty=25,
            )
        ]
    return []


def check_all_caps(prompt: str) -> list[Issue]:
    """Flag prompts written entirely or mostly in ALL CAPS."""
    words = prompt.split()
    if len(words) < 3:
        return []
    caps_words = sum(1 for w in words if w.isupper() and len(w) > 1)
    ratio = caps_words / len(words)
    if ratio > 0.5:
        return [
            Issue(
                message="Excessive use of ALL CAPS",
                severity=Severity.WARNING,
                category=Category.CLARITY,
                detail=f"{caps_words}/{len(words)} words are in ALL CAPS. This reduces readability.",
                penalty=8,
            )
        ]
    return []


# ---------------------------------------------------------------------------
# Aggregate all rules
# ---------------------------------------------------------------------------

ALL_RULES = [
    check_empty_prompt,
    check_too_short,
    check_vague_language,
    check_missing_task,
    check_no_context,
    check_excessive_length,
    check_filler_words,
    check_repeated_sentences,
    check_redundant_instructions,
    check_contradictions,
    check_role_consistency,
    check_output_format_specified,
    check_injection_risk,
    check_all_caps,
]


def generate_suggestions(prompt: str, issues: list[Issue]) -> list[str]:
    """Produce actionable suggestions based on the issues found."""
    suggestions = []
    categories_hit = set(i.category for i in issues)

    if Category.CLARITY in categories_hit:
        suggestions.append(
            "Add a clear role definition, e.g. 'You are a senior Python developer.'"
        )
        suggestions.append(
            "Include specific action verbs like 'Write', 'Explain', 'Summarize'."
        )

    if Category.EFFICIENCY in categories_hit:
        suggestions.append(
            "Remove filler words and redundant phrases to reduce token usage."
        )
        suggestions.append(
            "Break very long prompts into sections with clear headings."
        )

    if Category.ACCURACY in categories_hit:
        suggestions.append(
            "Ensure instructions don't contradict each other."
        )
        suggestions.append(
            "Assign a single, clear role to the model."
        )

    if Category.STRUCTURE in categories_hit:
        suggestions.append(
            "Specify the desired output format (JSON, bullet list, table, etc.)."
        )

    word_count = len(prompt.split())
    if word_count > 50 and not any("section" in s for s in suggestions):
        suggestions.append(
            "Consider using sections (## Task, ## Context, ## Output Format) for complex prompts."
        )

    return suggestions
