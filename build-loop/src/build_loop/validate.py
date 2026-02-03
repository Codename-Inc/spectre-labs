"""
Post-build validation for spectre-build.

Runs a validation pass after the build loop completes to verify
implementation against requirements. Supports recursive validation
cycles when gaps are found.
"""

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from .agent import get_agent
from .stats import BuildStats


@dataclass
class ValidationResult:
    """Structured result from validation agent."""
    status: str  # "COMPLETE" or "GAPS_FOUND"
    gaps_file: str | None  # Absolute path to validation_gaps.md, or None
    summary: str  # Brief summary text
    requirements_total: int
    requirements_delivered: int
    gaps_count: int


def _get_validate_prompt_path() -> Path:
    """Get the path to the validation prompt template file."""
    return Path(__file__).parent / "prompts" / "validate.md"


def _load_validate_template() -> str:
    """Load the validation prompt template.

    Returns:
        The raw prompt template with {variable} placeholders.

    Raises:
        FileNotFoundError: If the prompt file is missing.
    """
    prompt_path = _get_validate_prompt_path()
    if not prompt_path.is_file():
        raise FileNotFoundError(
            f"Validation prompt template not found at: {prompt_path}\n"
            "Expected file: build_loop/prompts/validate.md"
        )
    return prompt_path.read_text(encoding="utf-8")


def build_validation_prompt(tasks_file: str, context_files: list[str]) -> str:
    """Build the validation prompt from the template.

    Args:
        tasks_file: Absolute path to the tasks file
        context_files: List of absolute paths to additional context files

    Returns:
        The constructed prompt string ready to send to the agent
    """
    # Format context paths
    if context_files:
        context_str = "\n".join(f"- `{f}`" for f in context_files)
    else:
        context_str = "None provided"

    # Build ARGUMENTS section
    arguments = f"Tasks file: `{tasks_file}`\n"
    if context_files:
        arguments += f"Context files:\n{context_str}"
    else:
        arguments += "Context files: None"

    # Load template and substitute
    template = _load_validate_template()
    prompt = template.replace("{arguments}", arguments)
    prompt = prompt.replace("{tasks_file_path}", tasks_file)

    return prompt


def parse_validation_json(output: str) -> ValidationResult | None:
    """Parse the JSON validation result from agent output.

    Looks for a ```json code block at the end of the output containing
    the structured validation result.

    Args:
        output: Full text output from the validation agent

    Returns:
        ValidationResult if JSON found and valid, None otherwise
    """
    # Find the last ```json ... ``` block in the output
    json_pattern = r'```json\s*\n(.*?)\n```'
    matches = list(re.finditer(json_pattern, output, re.DOTALL))

    if not matches:
        return None

    # Use the last JSON block (the validation result should be at the end)
    json_str = matches[-1].group(1).strip()

    try:
        data = json.loads(json_str)
    except json.JSONDecodeError:
        return None

    # Extract fields with defaults
    status = data.get("status", "").upper()
    if status not in ("COMPLETE", "GAPS_FOUND"):
        return None

    gaps_file = data.get("gaps_file")
    if gaps_file:
        # Resolve to absolute path if relative
        gaps_path = Path(gaps_file)
        if not gaps_path.is_absolute():
            gaps_path = Path.cwd() / gaps_path
        gaps_file = str(gaps_path.resolve()) if gaps_path.exists() else None

    stats = data.get("stats", {})

    return ValidationResult(
        status=status,
        gaps_file=gaps_file,
        summary=data.get("summary", ""),
        requirements_total=stats.get("requirements_total", 0),
        requirements_delivered=stats.get("requirements_delivered", 0),
        gaps_count=stats.get("gaps_count", 0),
    )


def fallback_detect_result(output: str, tasks_file: str) -> ValidationResult | None:
    """Fallback detection using legacy signal patterns.

    Used when JSON parsing fails. Looks for [[VALIDATION:...]] signals
    and tries to find gaps file by pattern matching.

    Args:
        output: Full text output from the validation agent
        tasks_file: Original tasks file path

    Returns:
        ValidationResult if signals detected, None otherwise
    """
    # Check for legacy signals
    if "[[VALIDATION:COMPLETE]]" in output:
        return ValidationResult(
            status="COMPLETE",
            gaps_file=None,
            summary="Validation complete (legacy signal)",
            requirements_total=0,
            requirements_delivered=0,
            gaps_count=0,
        )

    if "[[VALIDATION:GAPS_FOUND]]" in output:
        # Try to find gaps file
        gaps_file = None

        # Look for backtick-quoted path
        match = re.search(r'`([^`]*validation_gaps\.md)`', output)
        if match:
            gaps_path = Path(match.group(1))
            if not gaps_path.is_absolute():
                gaps_path = Path.cwd() / gaps_path
            if gaps_path.is_file():
                gaps_file = str(gaps_path.resolve())

        # Fall back to standard location
        if not gaps_file:
            tasks_dir = Path(tasks_file).parent
            standard_path = tasks_dir / "validation" / "validation_gaps.md"
            if standard_path.is_file():
                gaps_file = str(standard_path.resolve())

        return ValidationResult(
            status="GAPS_FOUND",
            gaps_file=gaps_file,
            summary="Gaps found (legacy signal)",
            requirements_total=0,
            requirements_delivered=0,
            gaps_count=0,
        )

    return None


def run_validation(
    tasks_file: str,
    context_files: list[str],
    agent: str = "claude",
) -> tuple[int, str, str | None]:
    """Run post-build validation using the full spectre validate prompt.

    Spawns a fresh agent session that validates the implementation against
    the requirements in the tasks and context files.

    Args:
        tasks_file: Absolute path to the tasks file
        context_files: List of absolute paths to additional context files
        agent: Agent backend to use ("claude" or "codex")

    Returns:
        Tuple of (exit_code, output_text, gaps_file_path)
        - exit_code: 0 for success, non-zero for failure
        - output_text: Full agent output
        - gaps_file_path: Path to validation_gaps.md if gaps found, None if complete
    """
    # Print validation header
    print(f"\n{'='*60}")
    print("🔍 POST-BUILD VALIDATION")
    print(f"   Agent: {agent}")
    print(f"   Tasks: {tasks_file}")
    if context_files:
        print(f"   Context: {', '.join(context_files)}")
    print(f"{'='*60}\n")

    # Get the agent runner
    runner = get_agent(agent)

    if not runner.check_available():
        print(f"❌ ERROR: {runner.name} CLI not found", file=sys.stderr)
        return 127, "", None

    # Build the validation prompt
    prompt = build_validation_prompt(tasks_file, context_files)

    # Run single iteration (not a loop)
    stats = BuildStats()

    try:
        exit_code, output, stderr = runner.run_iteration(prompt, stats=stats)
    except FileNotFoundError:
        print(f"❌ ERROR: {runner.name} CLI not found", file=sys.stderr)
        return 127, "", None
    except Exception as e:
        print(f"❌ ERROR: Validation failed: {e}", file=sys.stderr)
        return 1, "", None

    # Parse validation result from JSON (with fallback to legacy signals)
    result = parse_validation_json(output)
    if result is None:
        result = fallback_detect_result(output, tasks_file)

    if result is None:
        # No valid result detected
        print(f"\n{'='*60}")
        print("⚠️ VALIDATION OUTPUT NOT PARSEABLE")
        print("   Could not find JSON result or legacy signals in output")
        print(f"{'='*60}\n")
        return exit_code, output, None

    # Print result summary
    if result.status == "GAPS_FOUND" and result.gaps_file:
        print(f"\n{'='*60}")
        print("⚠️ VALIDATION FOUND GAPS")
        print(f"   Status: {result.status}")
        print(f"   Delivered: {result.requirements_delivered}/{result.requirements_total}")
        print(f"   Gaps: {result.gaps_count}")
        print(f"   Gaps file: {result.gaps_file}")
        if result.summary:
            print(f"   Summary: {result.summary}")
        print(f"{'='*60}\n")
    else:
        print(f"\n{'='*60}")
        print("✅ VALIDATION COMPLETE - All requirements verified")
        print(f"   Delivered: {result.requirements_delivered}/{result.requirements_total}")
        if result.summary:
            print(f"   Summary: {result.summary}")
        print(f"{'='*60}\n")

    return exit_code, output, result.gaps_file
