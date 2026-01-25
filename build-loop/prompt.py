"""
Prompt template and construction for build iterations.

The prompt is loaded from an external markdown file for easy iteration.
Only file paths are substituted at runtime.
"""

from pathlib import Path


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
