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
from .notify import notify_build_complete, notify_build_error, notify_plan_complete

# Session file location
SESSION_FILE = ".spectre/build-session.json"

# Maximum validation cycles before forcing exit (prevent infinite loops)
MAX_VALIDATION_CYCLES = 5


def get_session_path() -> Path:
    """Get absolute path to session file in current working directory."""
    return Path.cwd() / SESSION_FILE


def save_session(
    tasks_file: str,
    context_files: list[str],
    max_iterations: int,
    agent: str = "claude",
    validate: bool = False,
    manifest_path: str | None = None,
    pipeline_path: str | None = None,
    plan: bool = False,
    plan_output_dir: str | None = None,
    plan_context: dict | None = None,
    plan_clarifications_path: str | None = None,
) -> None:
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
        "agent": agent,
        "validate": validate,
        "manifest_path": manifest_path,
        "pipeline_path": pipeline_path,
        "plan": plan,
        "plan_output_dir": plan_output_dir,
        "plan_context": plan_context,
        "plan_clarifications_path": plan_clarifications_path,
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
        f"  Agent:      {session.get('agent', 'claude')}",
    ]

    if session.get("plan"):
        lines.append("  Mode:       Planning")
    else:
        lines.append(f"  Tasks:      {session['tasks_file']}")

    if session.get("context_files"):
        for i, ctx in enumerate(session["context_files"]):
            prefix = "  Context:   " if i == 0 else "             "
            lines.append(f"{prefix} {ctx}")
    else:
        lines.append("  Context:    (none)")

    lines.append(f"  Max iter:   {session['max_iterations']}")

    if session.get("validate"):
        lines.append("  Validate:   yes")

    if session.get("manifest_path"):
        lines.append(f"  Manifest:   {session['manifest_path']}")

    if session.get("pipeline_path"):
        lines.append(f"  Pipeline:   {session['pipeline_path']}")

    if session.get("plan_output_dir"):
        lines.append(f"  Output:     {session['plan_output_dir']}")

    if session.get("plan_clarifications_path"):
        lines.append(f"  Clarif:     {session['plan_clarifications_path']}")

    if session.get("started_at"):
        lines.append(f"  Last run:   {session['started_at']}")

    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        prog="spectre-build",
        description="Execute an agent in a loop, completing one parent task per iteration.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Interactive mode (prompts for inputs)
  spectre-build

  # Flag-based invocation
  spectre-build --tasks docs/tasks.md --context docs/scope.md

  # With multiple context files and custom iteration limit
  spectre-build --tasks docs/tasks.md --context docs/scope.md docs/plan.md --max-iterations 15

  # With post-build validation
  spectre-build --tasks docs/tasks.md --context docs/scope.md --validate

  # Using a pipeline definition
  spectre-build --pipeline .spectre/pipelines/full-feature.yaml --tasks docs/tasks.md

  # From a manifest file
  spectre-build docs/tasks/feature-x/build.md

  # Resume last session (after stopping to edit files)
  spectre-build resume

  # Start the web GUI
  spectre-build serve
""",
    )

    # Positional argument for manifest file or command
    parser.add_argument(
        "manifest_or_command",
        nargs="?",
        help="Build manifest (.md file), 'resume', or 'serve' command",
    )

    parser.add_argument(
        "--tasks",
        type=str,
        help="Path to tasks.md file",
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
        "--agent",
        type=str,
        choices=["claude", "codex"],
        default="claude",
        help="Coding agent to run (default: claude)",
    )

    parser.add_argument(
        "--validate",
        action="store_true",
        help="Run post-build validation after successful build",
    )

    parser.add_argument(
        "--plan",
        action="store_true",
        help="Run planning pipeline: scope docs → build-ready manifest",
    )

    parser.add_argument(
        "--build",
        action="store_true",
        help="Auto-start build after planning completes (use with --plan)",
    )

    parser.add_argument(
        "--pipeline",
        type=str,
        help="Path to pipeline YAML definition file",
    )

    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port for web server (serve mode only, default: 8000)",
    )

    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Host for web server (serve mode only, default: 127.0.0.1)",
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


def prompt_for_agent() -> str:
    """Interactively prompt for agent selection with default."""
    default = "claude"
    print(f"Agent [claude/codex] ({default}): ", end="")
    response = input().strip().lower()

    if not response:
        return default

    if response in ("claude", "codex"):
        return response

    print(f"Invalid choice. Using default: {default}")
    return default


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


def prompt_for_validate() -> bool:
    """Interactively prompt for validation after build."""
    print("Run validation after build? [y/N]: ", end="")
    response = input().strip().lower()
    return response in ("y", "yes")


def prompt_for_mode() -> str:
    """Interactively prompt for execution mode."""
    print("Mode [build/plan] (build): ", end="")
    response = input().strip().lower()

    if not response:
        return "build"

    if response in ("build", "plan"):
        return response

    print(f"Invalid choice. Using default: build")
    return "build"


def prompt_for_plan_context() -> list[str]:
    """Interactively prompt for required scope/context files for plan mode."""
    print("Scope/context files (comma-separated): ", end="")
    response = input().strip()

    if not response:
        return []

    paths = [p.strip() for p in response.split(",")]
    return [p for p in paths if p]


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


def run_build_validate_cycle(
    tasks_file: str,
    context_files: list[str],
    max_iterations: int,
    agent: str = "claude",
    validate: bool = False,
) -> tuple[int, int]:
    """Run build loop with optional recursive validation cycles.

    When validation is enabled and gaps are found, this function:
    1. Runs the build loop with the current tasks file
    2. Runs validation to check for gaps
    3. If gaps found, uses validation_gaps.md as the new tasks file
    4. Repeats until validation passes or max cycles reached

    A single BuildStats instance is shared across all build and validation
    cycles so the final summary reflects the entire session.

    Args:
        tasks_file: Absolute path to the tasks file
        context_files: List of absolute paths to context files
        max_iterations: Maximum iterations per build loop
        agent: Agent backend to use
        validate: Whether to run validation after build

    Returns:
        Tuple of (exit_code, total_iterations_completed)
    """
    from .stats import BuildStats
    from .validate import run_validation

    total_iterations = 0
    cycle = 0
    current_tasks_file = tasks_file

    # Single stats instance for the entire build+validate session
    stats = BuildStats()

    while True:
        cycle += 1

        # Print cycle header if validating
        if validate and cycle > 1:
            print(f"\n{'='*60}")
            print(f"🔄 BUILD CYCLE {cycle} (Gap Remediation)")
            print(f"   Tasks: {current_tasks_file}")
            print(f"{'='*60}\n")

        # Run build loop — pass shared stats so tokens/tools accumulate
        exit_code, iterations = run_build_loop(
            current_tasks_file, context_files, max_iterations,
            agent=agent, stats=stats,
        )
        total_iterations += iterations

        # If build failed, print aggregate summary and exit
        if exit_code != 0:
            stats.print_summary()
            return exit_code, total_iterations

        # If validation not enabled, print summary and we're done
        if not validate:
            stats.print_summary()
            return exit_code, total_iterations

        # Run validation — pass shared stats so validation tokens count too
        val_exit_code, _, gaps_file = run_validation(
            current_tasks_file, context_files, agent=agent, stats=stats,
        )

        # If validation failed (process error), print summary and exit
        if val_exit_code != 0:
            stats.print_summary()
            return val_exit_code, total_iterations

        # If no gaps found, validation complete
        if gaps_file is None:
            print(f"\n{'='*60}")
            print(f"✅ FEATURE COMPLETE after {cycle} build cycle(s)")
            print(f"   Total iterations: {total_iterations}")
            print(f"{'='*60}\n")
            stats.print_summary()
            return 0, total_iterations

        # Gaps found - check cycle limit
        if cycle >= MAX_VALIDATION_CYCLES:
            print(f"\n{'='*60}")
            print(f"⚠️ MAX VALIDATION CYCLES ({MAX_VALIDATION_CYCLES}) REACHED")
            print(f"   Remaining gaps: {gaps_file}")
            print(f"   Review and run manually if needed")
            print(f"{'='*60}\n")
            stats.print_summary()
            return 0, total_iterations  # Exit gracefully, not an error

        # Set up next cycle with gaps file as tasks
        current_tasks_file = gaps_file
        print(f"\n{'='*60}")
        print(f"📋 STARTING REMEDIATION CYCLE {cycle + 1}")
        print(f"   Gaps to address: {gaps_file}")
        print(f"{'='*60}\n")


def run_pipeline(
    pipeline_path: str,
    tasks_file: str,
    context_files: list[str],
    agent: str = "claude",
) -> tuple[int, int]:
    """Run a pipeline from a YAML definition file.

    Args:
        pipeline_path: Path to the pipeline YAML file
        tasks_file: Path to the tasks file
        context_files: List of context file paths
        agent: Agent backend to use

    Returns:
        Tuple of (exit_code, total_iterations_completed)
    """
    from .agent import get_agent
    from .pipeline import load_pipeline
    from .pipeline.executor import PipelineExecutor, PipelineStatus
    from .stats import BuildStats

    # Load pipeline config
    try:
        config = load_pipeline(pipeline_path)
    except (FileNotFoundError, ValueError) as e:
        print(f"Error loading pipeline: {e}", file=sys.stderr)
        return 1, 0

    # Build context for prompt substitution
    if context_files:
        context_str = "\n".join(f"- `{f}`" for f in context_files)
    else:
        context_str = "None"

    context = {
        "tasks_file_path": tasks_file,
        "progress_file_path": str(Path(tasks_file).parent / "build_progress.md"),
        "additional_context_paths_or_none": context_str,
    }

    # Get agent runner
    runner = get_agent(agent)
    if not runner.check_available():
        print(f"❌ ERROR: {runner.name} CLI not found", file=sys.stderr)
        return 127, 0

    # Create and run executor
    stats = BuildStats()
    executor = PipelineExecutor(
        config=config,
        runner=runner,
        context=context,
    )

    state = executor.run(stats)

    # Return based on pipeline status
    if state.status == PipelineStatus.COMPLETED:
        return 0, state.total_iterations
    elif state.status == PipelineStatus.STOPPED:
        return 130, state.total_iterations  # Interrupted
    else:
        return 1, state.total_iterations


def run_default_pipeline(
    tasks_file: str,
    context_files: list[str],
    max_iterations: int,
    agent: str = "claude",
) -> tuple[int, int]:
    """Run the default build -> code_review -> validate pipeline.

    Creates a 3-stage pipeline with lifecycle hooks for git scope
    injection between build and code review stages.

    Args:
        tasks_file: Absolute path to the tasks file
        context_files: List of absolute paths to context files
        max_iterations: Maximum iterations for the build stage
        agent: Agent backend to use

    Returns:
        Tuple of (exit_code, total_iterations_completed)
    """
    from .agent import get_agent
    from .hooks import after_stage_hook, before_stage_hook
    from .pipeline.executor import PipelineExecutor, PipelineStatus, StageCompletedEvent
    from .pipeline.loader import create_default_pipeline
    from .stats import BuildStats

    # Create pipeline config
    config = create_default_pipeline(
        tasks_file=tasks_file,
        context_files=context_files,
        max_build_iterations=max_iterations,
    )

    # Build context for prompt substitution
    if context_files:
        context_str = "\n".join(f"- `{f}`" for f in context_files)
    else:
        context_str = "None"

    context = {
        "tasks_file_path": tasks_file,
        "progress_file_path": str(Path(tasks_file).parent / "build_progress.md"),
        "additional_context_paths_or_none": context_str,
        "review_fixes_path": str(Path(tasks_file).parent / "review_fixes.md"),
        "changed_files": "No files changed (first run)",
        "commit_messages": "No commits (first run)",
        "phase_completed": "all",
        "completed_phase_tasks": "(determined after build completes)",
        "remaining_phases": "None",
        "validated_phases": "None",
        "remediation_tasks_path": "",
        "arguments": f"Tasks file: `{tasks_file}`\nContext files:\n{context_str}",
    }

    # Get agent runner
    runner = get_agent(agent)
    if not runner.check_available():
        print(f"❌ ERROR: {runner.name} CLI not found", file=sys.stderr)
        return 127, 0

    # Stats with event-based loop counting
    stats = BuildStats()

    def on_event(event):
        if isinstance(event, StageCompletedEvent):
            if event.stage == "build":
                stats.build_loops += 1
            elif event.stage == "code_review":
                stats.review_loops += 1
            elif event.stage == "validate":
                stats.validate_loops += 1

    # Create and run executor with hooks
    executor = PipelineExecutor(
        config=config,
        runner=runner,
        on_event=on_event,
        context=context,
        before_stage=before_stage_hook,
        after_stage=after_stage_hook,
    )

    state = executor.run(stats)

    # Return based on pipeline status
    if state.status == PipelineStatus.COMPLETED:
        return 0, state.total_iterations
    elif state.status == PipelineStatus.STOPPED:
        return 130, state.total_iterations
    else:
        return 1, state.total_iterations


def run_plan_pipeline(
    context_files: list[str],
    max_iterations: int,
    agent: str = "claude",
    output_dir: str | None = None,
    resume_stage: str | None = None,
    resume_context: dict | None = None,
) -> tuple[int, int, str]:
    """Run the planning pipeline: scope docs → build-ready manifest.

    Creates a multi-stage pipeline (research → assess → [create_plan] →
    create_tasks → plan_review → req_validate) or a single-stage resume
    pipeline (update_docs) for post-clarification runs.

    Handles CLARIFICATIONS_NEEDED by saving session for later resume.

    Args:
        context_files: List of scope document paths
        max_iterations: Maximum iterations per stage
        agent: Agent backend to use
        output_dir: Output directory for artifacts (default: docs/tasks/{branch})
        resume_stage: If set, use resume pipeline starting at this stage
        resume_context: Preserved context dict from a prior session

    Returns:
        Tuple of (exit_code, total_iterations_completed, manifest_path)
    """
    import subprocess as _subprocess

    from .agent import get_agent
    from .hooks import plan_after_stage, plan_before_stage
    from .notify import notify
    from .pipeline.executor import PipelineExecutor, PipelineStatus
    from .pipeline.loader import create_plan_pipeline, create_plan_resume_pipeline
    from .stats import BuildStats, create_plan_event_handler

    # Get agent runner
    runner = get_agent(agent)
    if not runner.check_available():
        print(f"❌ ERROR: {runner.name} CLI not found", file=sys.stderr)
        return 127, 0, ""

    # Determine output directory
    if not output_dir:
        try:
            branch = _subprocess.check_output(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                text=True, stderr=_subprocess.DEVNULL,
            ).strip()
        except (FileNotFoundError, _subprocess.CalledProcessError):
            branch = "main"
        output_dir = str(Path.cwd() / "docs" / "tasks" / branch)

    # Ensure output directories exist
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    (Path(output_dir) / "specs").mkdir(parents=True, exist_ok=True)
    (Path(output_dir) / "clarifications").mkdir(parents=True, exist_ok=True)

    # Create pipeline config
    if resume_stage:
        config = create_plan_resume_pipeline()
    else:
        config = create_plan_pipeline()

    # Build context for prompt substitution
    if context_files:
        context_str = "\n".join(f"- `{f}`" for f in context_files)
    else:
        context_str = "None"

    context = resume_context or {
        "context_files": context_str,
        "output_dir": output_dir,
        "task_context_path": str(Path(output_dir) / "task_context.md"),
        "plan_path": str(Path(output_dir) / "specs" / "plan.md"),
        "tasks_path": str(Path(output_dir) / "specs" / "tasks.md"),
        "clarifications_path": "",
        "clarification_answers": "",
        "manifest_path": "",
        "depth": "standard",
        "tier": "STANDARD",
    }

    # Stats with event-based loop counting
    stats = BuildStats()
    on_event = create_plan_event_handler(stats)

    # Create and run executor with planning hooks
    executor = PipelineExecutor(
        config=config,
        runner=runner,
        on_event=on_event,
        context=context,
        before_stage=plan_before_stage,
        after_stage=plan_after_stage,
    )

    state = executor.run(stats)

    # Check if pipeline ended with CLARIFICATIONS_NEEDED
    last_signal = None
    if state.stage_history:
        last_signal = state.stage_history[-1][1]

    if last_signal == "CLARIFICATIONS_NEEDED":
        clarif_path = state.global_artifacts.get(
            "clarifications_path",
            context.get("clarifications_path", ""),
        )

        print(f"\n{'='*60}")
        print("📋 CLARIFICATIONS NEEDED")
        print(f"   Edit: {clarif_path}")
        print(f"   Then: spectre-build resume")
        print(f"{'='*60}\n")

        notify(
            message="Clarifications needed — edit the file and resume",
            subtitle="Plan Pipeline Paused",
        )

        # Save session for resume
        save_session(
            tasks_file="",
            context_files=context_files,
            max_iterations=max_iterations,
            agent=agent,
            plan=True,
            plan_output_dir=output_dir,
            plan_context=context,
            plan_clarifications_path=clarif_path,
        )

        return 0, state.total_iterations, ""

    # Pipeline completed normally
    manifest_path = state.global_artifacts.get("manifest_path", "")
    if not manifest_path:
        # Derive from output_dir if not in artifacts
        candidate = str(Path(output_dir) / "build.md")
        if Path(candidate).is_file():
            manifest_path = candidate

    if manifest_path:
        print(f"\n{'='*60}")
        print("✅ PLANNING COMPLETE")
        print(f"   Manifest: {manifest_path}")
        print(f"   Run: spectre-build {manifest_path}")
        print(f"{'='*60}\n")

    if state.status == PipelineStatus.COMPLETED:
        return 0, state.total_iterations, manifest_path
    elif state.status == PipelineStatus.STOPPED:
        return 130, state.total_iterations, ""
    else:
        return 1, state.total_iterations, ""


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
    context_files = session.get("context_files", [])
    max_iterations = session.get("max_iterations", 10)
    agent = session.get("agent", "claude")

    # Determine notification setting
    send_notification = args.notify and not args.no_notify
    project_name = Path.cwd().name

    # Track build duration
    start_time = time.time()

    # Handle planning session resume
    if session.get("plan"):
        # Update session timestamp for planning
        save_session(
            tasks_file="",
            context_files=context_files,
            max_iterations=max_iterations,
            agent=agent,
            plan=True,
            plan_output_dir=session.get("plan_output_dir"),
            plan_context=session.get("plan_context"),
            plan_clarifications_path=session.get("plan_clarifications_path"),
        )

        exit_code, iterations_completed, _manifest = run_plan_pipeline(
            context_files=context_files,
            max_iterations=max_iterations,
            agent=agent,
            output_dir=session.get("plan_output_dir"),
            resume_stage="update_docs",
            resume_context=session.get("plan_context"),
        )
    else:
        tasks_file = session["tasks_file"]
        validate = session.get("validate", False)
        manifest_path = session.get("manifest_path")
        pipeline_path = session.get("pipeline_path")

        # Validate files still exist (only for non-planning sessions)
        validate_inputs(tasks_file, context_files, max_iterations)

        # Update session timestamp
        save_session(tasks_file, context_files, max_iterations, agent=agent,
                     validate=validate, manifest_path=manifest_path, pipeline_path=pipeline_path)

        # Run build with pipeline or legacy mode
        if pipeline_path:
            exit_code, iterations_completed = run_pipeline(
                pipeline_path, tasks_file, context_files, agent=agent
            )
        elif validate:
            exit_code, iterations_completed = run_default_pipeline(
                tasks_file, context_files, max_iterations, agent=agent
            )
        else:
            exit_code, iterations_completed = run_build_validate_cycle(
                tasks_file, context_files, max_iterations,
                agent=agent, validate=False
            )

    # Calculate duration
    duration = time.time() - start_time
    duration_str = format_duration(duration)

    # Send notification if enabled
    if send_notification:
        if session.get("plan"):
            notify_plan_complete(
                stages_completed=iterations_completed,
                total_time=duration_str,
                success=(exit_code == 0),
                project=project_name,
            )
        else:
            notify_build_complete(
                tasks_completed=iterations_completed,
                total_time=duration_str,
                success=(exit_code == 0),
                project=project_name,
            )

    sys.exit(exit_code)


def run_manifest(manifest_path: str, args: argparse.Namespace) -> None:
    """Run build from a manifest file."""
    import time

    from .manifest import load_manifest

    try:
        manifest = load_manifest(manifest_path)
    except (FileNotFoundError, ValueError) as e:
        print(f"Error loading manifest: {e}", file=sys.stderr)
        sys.exit(1)

    # Extract values from manifest
    tasks_file = manifest.tasks
    context_files = manifest.context
    max_iterations = manifest.max_iterations
    agent = manifest.agent
    validate = manifest.validate

    # CLI flags can override manifest
    if args.agent != "claude":  # non-default means user specified
        agent = args.agent
    if args.validate:
        validate = True
    if args.max_iterations != 10:  # non-default means user specified
        max_iterations = args.max_iterations

    # Validate inputs
    validate_inputs(tasks_file, context_files, max_iterations)

    # Determine notification setting
    send_notification = args.notify and not args.no_notify
    project_name = Path.cwd().name

    # Save session for resume
    save_session(tasks_file, context_files, max_iterations, agent=agent,
                 validate=validate, manifest_path=manifest_path)

    # Track build duration
    start_time = time.time()

    # Run build with appropriate mode
    if validate:
        exit_code, iterations_completed = run_default_pipeline(
            tasks_file, context_files, max_iterations, agent=agent
        )
    else:
        exit_code, iterations_completed = run_build_validate_cycle(
            tasks_file, context_files, max_iterations,
            agent=agent, validate=False
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


def run_serve(args: argparse.Namespace) -> None:
    """Start the web GUI server."""
    try:
        import uvicorn
    except ImportError:
        print("Error: uvicorn not installed. Run: pip install uvicorn[standard]", file=sys.stderr)
        sys.exit(1)

    print(f"\n🚀 Starting Spectre Build GUI")
    print(f"   URL: http://{args.host}:{args.port}")
    print(f"   Press Ctrl+C to stop\n")

    uvicorn.run(
        "build_loop.server.app:app",
        host=args.host,
        port=args.port,
        reload=False,
        log_level="info",
    )


def main() -> None:
    """Main entry point for Spectre Build CLI."""
    import time

    args = parse_args()

    # Determine mode based on positional argument
    positional = args.manifest_or_command

    # Handle serve command
    if positional == "serve":
        run_serve(args)
        return

    # Handle resume command
    if positional == "resume":
        run_resume(args)
        return

    # Handle manifest file (ends with .md and isn't a command)
    if positional and positional.endswith(".md"):
        run_manifest(positional, args)
        return

    # Handle pipeline YAML file as positional argument
    if positional and (positional.endswith(".yaml") or positional.endswith(".yml")):
        args.pipeline = positional
        positional = None

    # Determine notification setting (--no-notify overrides --notify)
    send_notification = args.notify and not args.no_notify

    # Handle --plan mode
    if args.plan:
        if not args.context:
            print("Error: --plan requires --context with scope documents", file=sys.stderr)
            sys.exit(1)

        context_files = [normalize_path(f) for f in args.context]
        context_files = [str(Path(f).resolve()) for f in context_files]
        max_iterations = args.max_iterations
        agent = args.agent
        project_name = Path.cwd().name
        start_time = time.time()

        save_session("", context_files, max_iterations, agent=agent, plan=True)

        exit_code, iterations_completed, manifest_path = run_plan_pipeline(
            context_files=context_files,
            max_iterations=max_iterations,
            agent=agent,
        )

        duration = time.time() - start_time
        duration_str = format_duration(duration)

        if send_notification:
            notify_plan_complete(
                stages_completed=iterations_completed,
                total_time=duration_str,
                success=(exit_code == 0),
                project=project_name,
            )

        # Chain to build if --build flag set and plan succeeded
        if exit_code == 0 and manifest_path and args.build:
            print(f"\n🔗 Auto-starting build from manifest: {manifest_path}\n")
            run_manifest(manifest_path, args)  # calls sys.exit internally

        sys.exit(exit_code)

    # Interactive mode selection (only when no flags provided)
    if not args.plan and not args.pipeline and args.tasks is None:
        mode = prompt_for_mode()
        if mode == "plan":
            context_files = prompt_for_plan_context()
            if not context_files:
                print("Error: Plan mode requires at least one context/scope file.", file=sys.stderr)
                sys.exit(1)
            context_files = [str(Path(normalize_path(f)).resolve()) for f in context_files]
            max_iterations = prompt_for_max_iterations()
            agent = prompt_for_agent()
            project_name = Path.cwd().name
            start_time = time.time()

            save_session("", context_files, max_iterations, agent=agent, plan=True)

            exit_code, iterations_completed, manifest_path = run_plan_pipeline(
                context_files=context_files,
                max_iterations=max_iterations,
                agent=agent,
            )

            duration = time.time() - start_time
            duration_str = format_duration(duration)

            if send_notification:
                notify_plan_complete(
                    stages_completed=iterations_completed,
                    total_time=duration_str,
                    success=(exit_code == 0),
                    project=project_name,
                )

            # Prompt to chain to build if plan succeeded
            if exit_code == 0 and manifest_path:
                print("Start build now? [y/N]: ", end="")
                if input().strip().lower() in ("y", "yes"):
                    print(f"\n🔗 Starting build from manifest: {manifest_path}\n")
                    run_manifest(manifest_path, args)  # calls sys.exit internally

            sys.exit(exit_code)

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

    # Get agent choice - from args in flag mode, prompt in interactive mode
    if flag_mode:
        agent = args.agent
    else:
        agent = prompt_for_agent()

    # Get validate choice - from args in flag mode, prompt in interactive mode
    if flag_mode:
        validate = args.validate
    else:
        validate = prompt_for_validate()

    # Get project name for notification
    project_name = Path.cwd().name

    # Track build duration
    start_time = time.time()

    # Check for pipeline mode
    if args.pipeline:
        # Explicit pipeline YAML - use pipeline executor
        pipeline_path = str(Path(args.pipeline).resolve())
        save_session(tasks_file, context_files, max_iterations, agent=agent,
                     validate=validate, pipeline_path=pipeline_path)

        exit_code, iterations_completed = run_pipeline(
            pipeline_path, tasks_file, context_files, agent=agent
        )
    elif validate:
        # --validate without --pipeline → default 3-stage pipeline
        save_session(tasks_file, context_files, max_iterations, agent=agent, validate=validate)

        exit_code, iterations_completed = run_default_pipeline(
            tasks_file, context_files, max_iterations, agent=agent
        )
    else:
        # No validation - legacy build-only mode
        save_session(tasks_file, context_files, max_iterations, agent=agent, validate=validate)

        exit_code, iterations_completed = run_build_validate_cycle(
            tasks_file, context_files, max_iterations,
            agent=agent, validate=False
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
