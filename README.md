# Prompt System Validator

A Python tool to validate whether prompts are **accurate**, **efficient**, and **well-structured**.

## Features

- **Clarity checks** — detects vague language, ambiguity, missing instructions
- **Efficiency checks** — flags redundancy, excessive length, filler words
- **Accuracy checks** — validates structure, role consistency, contradictions
- **Scoring** — produces an overall quality score (0–100)
- **CLI & library usage** — use from the command line or import in your code

## Quick Start

```bash
# Validate a prompt from the command line
python -m prompt_validator "You are a helpful assistant. Answer the user question."

# Validate from a file
python -m prompt_validator --file prompts/example.txt

# JSON output
python -m prompt_validator --file prompts/example.txt --json
```

## As a Library

```python
from prompt_validator import PromptValidator

validator = PromptValidator()
result = validator.validate("You are a helpful assistant. Answer questions accurately.")

print(result.score)        # 72
print(result.grade)        # "B"
print(result.issues)       # list of detected issues
print(result.suggestions)  # list of improvement suggestions
```

## Running Tests

```bash
pytest tests/ -v
```

## Storyboard Maker

`storyboard/` holds a separate React + Vite app: a ShotDeck-style storyboard and shot-list builder with screenplay PDF import, director lens profiles, FrameThrower reference search, free AI frame generation and PDF export. See [storyboard/README.md](storyboard/README.md).

```bash
cd storyboard && npm install && npm run dev
```

