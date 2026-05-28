#!/usr/bin/env python3
"""Generate Step Definition Skeleton from Feature File

Reads a Gherkin feature file and generates a Python file with
skeleton step definitions for all Given/When/Then steps.

Usage:
    python generate_step_skeleton.py path/to/feature.feature
    python generate_step_skeleton.py path/to/feature.feature --output path/to/test_steps.py
"""

import argparse
import operator
import re
from pathlib import Path


def parse_feature_file(feature_path):
    """Parse feature file and extract unique steps."""
    with Path(feature_path).open(encoding="utf-8") as f:
        content = f.read()

    # Find all Given/When/Then/And/But steps
    pattern = r"^\s*(Given|When|Then|And|But)\s+(.+)$"
    steps = []

    for line in content.split("\n"):
        match = re.match(pattern, line.strip())
        if match:
            keyword = match.group(1)
            text = match.group(2).strip()

            # Convert And/But to previous keyword type
            if keyword in {"And", "But"}:
                keyword = steps[-1]["keyword"] if steps else "Given"

            steps.append({"keyword": keyword, "text": text, "original": line.strip()})

    # Remove duplicates while preserving order
    unique_steps = []
    seen = set()
    for step in steps:
        key = (step["keyword"], step["text"])
        if key not in seen:
            seen.add(key)
            unique_steps.append(step)

    return unique_steps


def detect_parameters(step_text):
    """Detect potential parameters in step text."""
    # Common patterns for parameters
    patterns = [
        (r'"([^"]+)"', "quoted string"),
        (r"'([^']+)'", "quoted string"),
        (r"\d+", "number"),
        (r"\b\d+\.\d+\b", "decimal"),
    ]

    params = []
    for pattern, param_type in patterns:
        matches = re.finditer(pattern, step_text)
        params.extend({"value": match.group(0), "type": param_type, "position": match.start()} for match in matches)

    return params


def generate_step_function_name(step_text):
    """Generate Python function name from step text."""
    # Remove quotes and special characters
    text = re.sub(r'["\']', "", step_text)
    text = re.sub(r"[^\w\s]", "", text)

    # Convert to snake_case
    words = text.lower().split()

    # Limit length
    if len(words) > 5:
        words = words[:5]

    return "_".join(words)


def generate_step_definition(step):
    """Generate step definition code."""
    keyword = step["keyword"].lower()
    text = step["text"]
    func_name = generate_step_function_name(text)

    # Detect parameters
    params = detect_parameters(text)

    # Generate decorator
    if params:
        # Use parsers for parameterized steps
        # Replace parameters with placeholders
        param_text = text
        param_names = []

        for i, param in enumerate(sorted(params, key=operator.itemgetter("position"), reverse=True)):
            if param["type"] == "quoted string":
                # Replace quoted string with parameter
                param_name = f"value{i + 1}" if len(params) > 1 else "value"
                param_text = param_text.replace(param["value"], f'"{{{param_name}}}"', 1)
                param_names.append(param_name)
            elif param["type"] in {"number", "decimal"}:
                param_name = f"count{i + 1}" if len(params) > 1 else "count"
                param_text = param_text.replace(param["value"], f"{{{param_name}}}", 1)
                param_names.append(param_name)

        decorator = f"@{keyword}(parsers.parse('{param_text}'))"
        function_params = ", ".join(["browser", *param_names])
    else:
        # Simple step without parameters
        decorator = f'@{keyword}("{text}")'
        function_params = "browser"

    # Generate function
    return f'''{decorator}
def {func_name}({function_params}):
    """TODO: Implement step."""
    raise NotImplementedError("Step not implemented: {text}")
'''


def generate_step_file(feature_path, output_path=None):
    """Generate complete step definition file."""
    feature_name = Path(feature_path).stem

    if output_path is None:
        output_path = Path(feature_path).parent.parent / "step_defs" / f"test_{feature_name}.py"
    else:
        output_path = Path(output_path)

    # Parse feature file
    steps = parse_feature_file(feature_path)

    if not steps:
        print(f"No steps found in {feature_path}")
        return

    # Generate header
    header = f'''"""Step definitions for {feature_name} feature."""
import pytest
from pytest_bdd import scenarios, given, when, then, parsers

# Load all scenarios from {feature_name}.feature
scenarios('../features/{feature_name}.feature')


# TODO: Add custom fixtures here if needed

'''

    # Group steps by keyword
    given_steps = [s for s in steps if s["keyword"] == "Given"]
    when_steps = [s for s in steps if s["keyword"] == "When"]
    then_steps = [s for s in steps if s["keyword"] == "Then"]

    # Generate step definitions
    code = header

    if given_steps:
        code += "# Given steps - setup\n\n"
        for step in given_steps:
            code += generate_step_definition(step)
            code += "\n\n"

    if when_steps:
        code += "# When steps - actions\n\n"
        for step in when_steps:
            code += generate_step_definition(step)
            code += "\n\n"

    if then_steps:
        code += "# Then steps - assertions\n\n"
        for step in then_steps:
            code += generate_step_definition(step)
            code += "\n\n"

    # Write to file
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if output_path.exists():
        print(f"WARNING: {output_path} already exists")
        response = input("Overwrite? (y/N): ")
        if response.lower() != "y":
            print("Cancelled")
            return

    with Path(output_path).open("w", encoding="utf-8") as f:
        f.write(code)

    print(f"✓ Generated step definitions: {output_path}")
    print(f"✓ Found {len(steps)} unique steps")
    print("\nNext steps:")
    print("  1. Review generated step definitions")
    print("  2. Implement step logic (replace NotImplementedError)")
    print("  3. Add necessary fixtures in conftest.py")
    print("  4. Run tests: pytest " + str(output_path))


def main():
    parser = argparse.ArgumentParser(description="Generate step definition skeleton from feature file")
    parser.add_argument("feature_file", help="Path to .feature file")
    parser.add_argument(
        "--output",
        "-o",
        help="Output path for step definitions (default: auto-generated)",
    )

    args = parser.parse_args()

    feature_path = Path(args.feature_file)

    if not feature_path.exists():
        print(f"ERROR: Feature file not found: {feature_path}")
        return 1

    if feature_path.suffix != ".feature":
        print("WARNING: File does not have .feature extension")

    generate_step_file(feature_path, args.output)
    return 0


if __name__ == "__main__":
    exit(main())
