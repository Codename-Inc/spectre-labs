"""
CLI argument parsing and interactive prompts for spectre-build.

This module handles command-line interface concerns separate from
the core build loop logic.
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from .loop import run_build_loop
from ..notify import notify_build_complete, notify_build_error

# Session file location
SESSION_FILE = ".spectre/build-session.json"


def get_session_path() -> Path:
    """Get absolute path to session file in current working directory."""
    return Path.cwd() / SESSION_FILE


def save_session(tasks_file: str, context_files: list[str], max_iterations: int) -> None:
    """
    Save current build session to disk for later resume.

    Creates .spectre directory if it doesn't exist.
    """
    session_path = get_session_path()
    session_path.parent.mkdir(parents=True, exist_ok=True)

    session = {
        "tasks_file": tasks_file,
        "context_files": context_files,
        "max_iterations": max_iterations,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "cwd": str(Path.cwd()),
    }

    session_path.write_text(json.dumps(session, indent=2))


def load_session() -> dict | None:
    """
    Load saved session from disk.

    Returns None if no session file exists or if it's invalid.
    """
    session_path = get_session_path()

    if not session_path.exists():
        return None

    try:
        return json.loads(session_path.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def format_session_summary(session: dict) -> str:
    """Format session details for confirmation prompt."""
    lines = [
        f"  Tasks:      {session['tasks_file']}",
    ]

    if session.get("context_files"):
        for i, ctx in enumerate(session["context_files"]):
            prefix = "  Context:   " if i == 0 else "             "
            lines.append(f"{prefix} {ctx}")
    else:
        lines.append("  Context:    (none)")

    lines.append(f"  Max iter:   {session['max_iterations']}")

    if session.get("started_at"):
        lines.append(f"  Last run:   {session['started_at']}")

    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        prog="spectre-build",
        description="Execute Claude in a loop, completing one parent task per iteration.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Interactive mode (prompts for inputs)
  spectre-build

  # Flag-based invocation
  spectre-build --tasks docs/tasks.md --context docs/scope.md

  # With multiple context files and custom iteration limit
  spectre-build --tasks docs/tasks.md --context docs/scope.md docs/plan.md --max-iterations 15

  # Resume last session (after stopping to edit files)
  spectre-build resume
""",
    )

    # Subcommand for resume
    parser.add_argument(
        "command",
        nargs="?",
        choices=["resume"],
        help="Use 'resume' to restart the last build session",
    )

    parser.add_argument(
        "--tasks",
        type=str,
        help="Path to tasks.md file (required)",
    )

    parser.add_argument(
        "--context",
        type=str,
        nargs="*",
        default=[],
        help="Additional context file paths (optional, can specify multiple)",
    )

    parser.add_argument(
        "--max-iterations",
        type=int,
        default=10,
        help="Maximum number of iterations (default: 10)",
    )

    parser.add_argument(
        "--notify",
        action="store_true",
        default=True,
        help="Send macOS notification on completion (default: enabled)",
    )

    parser.add_argument(
        "--no-notify",
        action="store_true",
        help="Disable completion notifications",
    )

    parser.add_argument(
        "-y", "--yes",
        action="store_true",
        help="Skip confirmation prompt (for resume)",
    )

    return parser.parse_args()


def normalize_path(path: str) -> str:
    """
    Normalize a file path by stripping @ prefix if present.

    The @ prefix is a common convention meaning "relative to current directory".
    This function strips it so paths like @docs/file.md work as docs/file.md.

    Args:
        path: File path, possibly with @ prefix

    Returns:
        Path with @ prefix removed (if present)
    """
    if path.startswith("@"):
        return path[1:]
    return path


def prompt_for_tasks_file() -> str:
    """Interactively prompt for tasks file path."""
    while True:
        tasks_path = input("Tasks file path: ").strip()
        if tasks_path:
            return tasks_path
        print("Tasks file path is required.")


def prompt_for_context_files() -> list[str]:
    """Interactively prompt for optional context files."""
    print("Additional context files (comma-separated, or Enter to skip): ", end="")
    response = input().strip()

    if not response:
        return []

    # Split by comma and clean up each path
    paths = [p.strip() for p in response.split(",")]
    return [p for p in paths if p]  # Filter empty strings


def prompt_for_max_iterations() -> int:
    """Interactively prompt for max iterations with default."""
    default = 10
    print(f"Max iterations [{default}]: ", end="")
    response = input().strip()

    if not response:
        return default

    try:
        value = int(response)
        if value > 0:
            return value
        print(f"Must be positive. Using default: {default}")
        return default
    except ValueError:
        print(f"Invalid number. Using default: {default}")
        return default


def validate_inputs(
    tasks_file: str, context_files: list[str], max_iterations: int
) -> bool:
    """
    Validate all inputs before starting build loop.

    Returns True if valid, exits with error message if not.
    """
    errors = []

    # Check tasks file exists and is readable
    tasks_path = Path(tasks_file)
    if not tasks_path.exists():
        errors.append(f"Tasks file not found: {tasks_file}")
    elif not tasks_path.is_file():
        errors.append(f"Tasks path is not a file: {tasks_file}")
    elif not os.access(tasks_path, os.R_OK):
        errors.append(f"Tasks file is not readable: {tasks_file}")

    # Check context files exist if provided
    for ctx_file in context_files:
        ctx_path = Path(ctx_file)
        if not ctx_path.exists():
            errors.append(f"Context file not found: {ctx_file}")
        elif not ctx_path.is_file():
            errors.append(f"Context path is not a file: {ctx_file}")
        elif not os.access(ctx_path, os.R_OK):
            errors.append(f"Context file is not readable: {ctx_file}")

    # Check max-iterations is positive
    if max_iterations <= 0:
        errors.append(f"Max iterations must be positive: {max_iterations}")

    # Report errors and exit if any
    if errors:
        print("Validation errors:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        sys.exit(1)

    return True


def format_duration(seconds: float) -> str:
    """Format duration in human-readable form."""
    if seconds < 60:
        return f"{int(seconds)}s"
    elif seconds < 3600:
        mins = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{mins}m {secs}s"
    else:
        hours = int(seconds // 3600)
        mins = int((seconds % 3600) // 60)
        return f"{hours}h {mins}m"


def run_resume(args: argparse.Namespace) -> None:
    """Handle the 'resume' subcommand."""
    import time

    session = load_session()

    if not session:
        print("No previous session found.", file=sys.stderr)
        print(f"Session file: {get_session_path()}", file=sys.stderr)
        print("\nStart a new build with:", file=sys.stderr)
        print("  spectre build --tasks docs/tasks.md --context docs/scope.md", file=sys.stderr)
        sys.exit(1)

    # Show session details and confirm
    print("\n--- Resume Build Session ---")
    print(format_session_summary(session))
    print("----------------------------\n")

    if not args.yes:
        response = input("Resume this session? [Y/n] ").strip().lower()
        if response and response not in ("y", "yes"):
            print("Cancelled.")
            sys.exit(0)

    # Extract session values
    tasks_file = session["tasks_file"]
    context_files = session.get("context_files", [])
    max_iterations = session.get("max_iterations", 10)

    # Validate files still exist
    validate_inputs(tasks_file, context_files, max_iterations)

    # Determine notification setting
    send_notification = args.notify and not args.no_notify
    project_name = Path.cwd().name

    # Update session timestamp
    save_session(tasks_file, context_files, max_iterations)

    # Track build duration
    start_time = time.time()

    # Run the build loop
    exit_code, iterations_completed = run_build_loop(
        tasks_file, context_files, max_iterations
    )

    # Calculate duration
    duration = time.time() - start_time
    duration_str = format_duration(duration)

    # Send notification if enabled
    if send_notification:
        notify_build_complete(
            tasks_completed=iterations_completed,
            total_time=duration_str,
            success=(exit_code == 0),
            project=project_name,
        )

    sys.exit(exit_code)


def main() -> None:
    """Main entry point for Spectre Build CLI."""
    import time

    args = parse_args()

    # Handle resume subcommand
    if args.command == "resume":
        run_resume(args)
        return  # run_resume calls sys.exit

    # Determine notification setting (--no-notify overrides --notify)
    send_notification = args.notify and not args.no_notify

    # Get tasks file - from args or interactive prompt
    tasks_file = args.tasks
    if not tasks_file:
        tasks_file = prompt_for_tasks_file()

    # Determine if running in flag mode (--tasks provided) or interactive mode
    flag_mode = args.tasks is not None

    # Get context files - from args in flag mode, prompt in interactive mode
    context_files = args.context if flag_mode else prompt_for_context_files()

    # Get max iterations - from args or interactive prompt (only if interactive mode)
    if flag_mode:
        # Flag mode - use args value directly
        max_iterations = args.max_iterations
    else:
        # Interactive mode - prompt for confirmation/override
        max_iterations = prompt_for_max_iterations()

    # Normalize paths (strip @ prefix if present)
    tasks_file = normalize_path(tasks_file)
    context_files = [normalize_path(f) for f in context_files]

    # Validate all inputs before proceeding
    validate_inputs(tasks_file, context_files, max_iterations)

    # Convert to absolute paths for consistency
    tasks_file = str(Path(tasks_file).resolve())
    context_files = [str(Path(f).resolve()) for f in context_files]

    # Save session for future resume
    save_session(tasks_file, context_files, max_iterations)

    # Get project name for notification
    project_name = Path.cwd().name

    # Track build duration
    start_time = time.time()

    # Run the build loop
    exit_code, iterations_completed = run_build_loop(
        tasks_file, context_files, max_iterations
    )

    # Calculate duration
    duration = time.time() - start_time
    duration_str = format_duration(duration)

    # Send notification if enabled
    if send_notification:
        notify_build_complete(
            tasks_completed=iterations_completed,
            total_time=duration_str,
            success=(exit_code == 0),
            project=project_name,
        )

    sys.exit(exit_code)
