"""
Prompt template and construction for build iterations.

The prompt is loaded from an external markdown file for easy iteration.
Only file paths are substituted at runtime.
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def _get_prompt_path() -> Path:
    """Get the path to the build prompt template file."""
    return Path(__file__).parent / "prompts" / "build.md"


def _load_prompt_template() -> str:
    """Load the prompt template from the markdown file.

    Returns:
        The raw prompt template with {variable} placeholders.

    Raises:
        FileNotFoundError: If the prompt file is missing.
    """
    prompt_path = _get_prompt_path()
    if not prompt_path.is_file():
        raise FileNotFoundError(
            f"Build prompt template not found at: {prompt_path}\n"
            "Expected file: cli/build/prompts/build.md"
        )
    return prompt_path.read_text(encoding="utf-8")


def reset_progress_file(progress_path: str) -> None:
    """Reset a build progress file, keeping only the Codebase Patterns section.

    On subsequent builds in the same workspace, iteration logs bloat the context
    window. This trims everything below the '---' separator after Codebase Patterns,
    preserving discovered patterns while starting fresh for new iteration logs.

    If the file doesn't exist, this is a no-op.
    """
    path = Path(progress_path)
    if not path.is_file():
        return

    content = path.read_text(encoding="utf-8")

    # Find the '---' separator that ends the Codebase Patterns section
    # The expected structure is:
    #   # Build Progress
    #   ## Codebase Patterns
    #   ...patterns...
    #   ---
    #   ## Iteration — ...
    separator = "\n---\n"
    sep_idx = content.find(separator)
    if sep_idx == -1:
        # No separator found — file may be malformed or empty of iterations
        return

    # Keep everything up to and including the separator
    trimmed = content[:sep_idx + len(separator)]

    # Only write if we actually trimmed something
    after_separator = content[sep_idx + len(separator):].strip()
    if after_separator:
        path.write_text(trimmed, encoding="utf-8")
        logger.info("Reset progress file: kept Codebase Patterns, trimmed iteration logs")


def build_prompt(tasks_file: str, context_files: list[str]) -> str:
    """
    Build the iteration prompt from the template.

    The prompt is loaded from cli/build/prompts/build.md and substituted
    with file paths at runtime.

    Args:
        tasks_file: Absolute path to the tasks file
        context_files: List of absolute paths to additional context files

    Returns:
        The constructed prompt string ready to send to Claude
    """
    # Derive progress file path (same directory as tasks file, named build_progress.md)
    tasks_path = Path(tasks_file)
    progress_file = str(tasks_path.parent / "build_progress.md")

    # Format additional context paths or "None"
    if context_files:
        additional_context = ", ".join(f"`{f}`" for f in context_files)
    else:
        additional_context = "None"

    # Load template from file and substitute variables
    template = _load_prompt_template()
    prompt = template.format(
        tasks_file_path=tasks_file,
        progress_file_path=progress_file,
        additional_context_paths_or_none=additional_context,
    )

    return prompt
