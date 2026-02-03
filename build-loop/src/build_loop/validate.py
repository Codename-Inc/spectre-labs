"""
Post-build validation for spectre-build.

Runs a validation pass after the build loop completes to verify
implementation against requirements. Supports recursive validation
cycles when gaps are found.
"""

import re
import sys
from pathlib import Path

from .agent import get_agent
from .stats import BuildStats


# Validation result signals embedded in agent output
VALIDATION_COMPLETE = "[[VALIDATION:COMPLETE]]"
VALIDATION_GAPS_FOUND = "[[VALIDATION:GAPS_FOUND]]"


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


def detect_validation_result(output: str) -> str | None:
    """Detect validation result signal from agent output.

    Args:
        output: Full text output from the validation agent

    Returns:
        "COMPLETE" if requirements validated, "GAPS_FOUND" if gaps identified,
        None if no signal detected
    """
    if VALIDATION_COMPLETE in output:
        return "COMPLETE"
    if VALIDATION_GAPS_FOUND in output:
        return "GAPS_FOUND"
    return None


def find_gaps_file(output: str, tasks_file: str) -> str | None:
    """Extract the validation_gaps.md file path from agent output.

    Looks for the generated gaps file path in the output. Falls back to
    standard location based on git branch if not found.

    Args:
        output: Full text output from the validation agent
        tasks_file: Original tasks file path (used to derive default location)

    Returns:
        Absolute path to validation_gaps.md if found/exists, None otherwise
    """
    # Try to find path mentioned in output
    # Look for patterns like: `docs/tasks/main/validation/validation_gaps.md`
    match = re.search(r'`([^`]*validation_gaps\.md)`', output)
    if match:
        gaps_path = Path(match.group(1))
        if not gaps_path.is_absolute():
            gaps_path = Path.cwd() / gaps_path
        if gaps_path.is_file():
            return str(gaps_path.resolve())

    # Fall back to standard location
    tasks_dir = Path(tasks_file).parent
    standard_path = tasks_dir / "validation" / "validation_gaps.md"
    if standard_path.is_file():
        return str(standard_path.resolve())

    return None


def has_remediation_tasks(gaps_file: str) -> bool:
    """Check if the gaps file contains actual remediation tasks.

    Looks for task checkboxes (- [ ]) in the Gap Remediation Tasks section.

    Args:
        gaps_file: Path to validation_gaps.md

    Returns:
        True if there are unchecked tasks, False otherwise
    """
    try:
        content = Path(gaps_file).read_text(encoding="utf-8")

        # Look for the Gap Remediation Tasks section
        if "## Gap Remediation Tasks" not in content:
            return False

        # Extract the section
        tasks_section = content.split("## Gap Remediation Tasks")[1]
        if "---" in tasks_section:
            tasks_section = tasks_section.split("---")[0]

        # Check for unchecked task boxes
        unchecked = re.findall(r'- \[ \]', tasks_section)
        return len(unchecked) > 0

    except (OSError, IndexError):
        return False


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

    # Detect validation result
    result = detect_validation_result(output)
    gaps_file = None

    if result == "GAPS_FOUND":
        gaps_file = find_gaps_file(output, tasks_file)
        if gaps_file and has_remediation_tasks(gaps_file):
            print(f"\n{'='*60}")
            print("⚠️ VALIDATION FOUND GAPS")
            print(f"   Gaps file: {gaps_file}")
            print(f"{'='*60}\n")
        else:
            # Gaps file exists but no actual tasks
            gaps_file = None
            result = "COMPLETE"

    if result == "COMPLETE" or gaps_file is None:
        print(f"\n{'='*60}")
        print("✅ VALIDATION COMPLETE - All requirements verified")
        print(f"{'='*60}\n")

    return exit_code, output, gaps_file
