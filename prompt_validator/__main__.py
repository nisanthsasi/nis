"""CLI entry point: python -m prompt_validator"""

import argparse
import json
import sys

from prompt_validator.validator import PromptValidator


def main():
    parser = argparse.ArgumentParser(
        description="Validate whether a prompt system is accurate and efficient.",
    )
    parser.add_argument(
        "prompt",
        nargs="?",
        help="The prompt text to validate (inline).",
    )
    parser.add_argument(
        "-f", "--file",
        help="Path to a file containing the prompt text.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output results as JSON.",
    )
    args = parser.parse_args()

    # Determine prompt source
    if args.file:
        try:
            with open(args.file) as f:
                prompt_text = f.read()
        except FileNotFoundError:
            print(f"Error: file not found: {args.file}", file=sys.stderr)
            sys.exit(1)
    elif args.prompt:
        prompt_text = args.prompt
    else:
        # Read from stdin if no argument given
        if not sys.stdin.isatty():
            prompt_text = sys.stdin.read()
        else:
            parser.print_help()
            sys.exit(1)

    validator = PromptValidator()
    result = validator.validate(prompt_text)

    if args.json_output:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print("=" * 60)
        print("  PROMPT SYSTEM VALIDATION REPORT")
        print("=" * 60)
        print()
        prompt_preview = prompt_text[:120].replace("\n", " ")
        if len(prompt_text) > 120:
            prompt_preview += "..."
        print(f"Prompt: {prompt_preview}")
        print(f"Length: {len(prompt_text.split())} words / {len(prompt_text)} chars")
        print()
        print(result.summary())
        print()
        print("=" * 60)

    sys.exit(0 if result.is_valid else 1)


if __name__ == "__main__":
    main()
