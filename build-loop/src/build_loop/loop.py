"""
Main build loop logic.

Contains the core loop that invokes an agent iteratively, processing one
parent task per iteration until BUILD_COMPLETE or max iterations reached.
"""

import re
import subprocess
import sys

from .agent import get_agent
from .prompt import build_prompt
from .stats import BuildStats


def detect_promise(output: str) -> str | None:
    """
    Extract promise tag from Claude's output.

    Searches for [[PROMISE:...]] pattern and returns the promise text
    if found. Promise text is stripped of whitespace.

    Args:
        output: Full output from Claude subprocess

    Returns:
        Promise text ("TASK_COMPLETE" or "BUILD_COMPLETE") if found, None otherwise
    """
    match = re.search(r"\[\[PROMISE:(.*?)\]\]", output, re.DOTALL)
    if match:
        return match.group(1).strip()
    return None


def run_build_loop(
    tasks_file: str,
    context_files: list[str],
    max_iterations: int,
    agent: str = "claude",
    stats: BuildStats | None = None,
) -> tuple[int, int]:
    """
    Run the main build loop.

    Invokes the specified agent iteratively, processing one parent task per
    iteration until BUILD_COMPLETE or max iterations reached.

    Args:
        tasks_file: Absolute path to the tasks file
        context_files: List of absolute paths to additional context files
        max_iterations: Maximum number of iterations
        agent: Agent backend to use ("claude" or "codex")
        stats: Optional BuildStats to accumulate into. If None, creates a new
               instance and prints summary on exit. When provided externally,
               the caller is responsible for printing the final summary.

    Returns:
        Tuple of (exit_code, iterations_completed)
        - exit_code: 0 for success, non-zero for failure
        - iterations_completed: Number of successfully completed iterations
    """
    # Get the agent runner
    runner = get_agent(agent)

    # Check agent availability
    if not runner.check_available():
        print(f"\n{'='*60}", file=sys.stderr)
        print(f"❌ ERROR: {runner.name} CLI not found", file=sys.stderr)
        print(f"   The '{runner.name}' command is not installed or not in PATH.", file=sys.stderr)
        print(f"{'='*60}", file=sys.stderr)
        return 127, 0

    # Display configuration
    print("\n--- Spectre Build Configuration ---")
    print(f"Agent: {agent}")
    print(f"Tasks file: {tasks_file}")
    print(f"Context files: {context_files if context_files else 'None'}")
    print(f"Max iterations: {max_iterations}")
    print("-----------------------------------\n")

    # Use provided stats or create local instance
    # When stats is provided externally, caller owns the summary print
    owns_stats = stats is None
    if stats is None:
        stats = BuildStats()

    # Main build loop
    iteration = 0
    while iteration < max_iterations:
        iteration += 1

        # Print iteration header with promise reference
        print(f"\n{'='*60}")
        print(f"🔄 Iteration {iteration}/{max_iterations} [{agent}]")
        print(f"   Complete task: [[PROMISE:TASK_COMPLETE]]")
        print(f"   All done: [[PROMISE:BUILD_COMPLETE]]")
        print(f"{'='*60}\n")

        # Build fresh prompt each iteration
        prompt = build_prompt(tasks_file, context_files)

        # Invoke agent with constructed prompt
        try:
            exit_code, output, stderr = runner.run_iteration(prompt, stats=stats)
        except FileNotFoundError:
            print(f"\n{'='*60}", file=sys.stderr)
            print(f"❌ ERROR: {runner.name} CLI not found", file=sys.stderr)
            print(f"   Iteration: {iteration}/{max_iterations}", file=sys.stderr)
            print(f"{'='*60}", file=sys.stderr)
            if owns_stats:
                stats.print_summary()
            return 127, stats.iterations_completed  # Command not found
        except subprocess.TimeoutExpired:
            print(f"\n{'='*60}", file=sys.stderr)
            print(f"❌ ERROR: {runner.name} execution timed out", file=sys.stderr)
            print(f"   Iteration: {iteration}/{max_iterations}", file=sys.stderr)
            print("", file=sys.stderr)
            print("The agent subprocess exceeded the allowed time.", file=sys.stderr)
            print("Consider increasing timeout or breaking down tasks.", file=sys.stderr)
            print(f"{'='*60}", file=sys.stderr)
            stats.iterations_failed += 1
            if owns_stats:
                stats.print_summary()
            return 124, stats.iterations_completed  # Timeout

        # Check for promise FIRST - if agent completed its task, trust that
        promise = detect_promise(output)

        # Handle non-zero exit code, but only fail if there's no valid promise
        if exit_code != 0:
            if promise:
                # Agent completed task despite non-zero exit - warn but continue
                print(f"\n⚠ {runner.name} exited with code {exit_code}, but task completed.")
            else:
                # No promise and non-zero exit - this is a real failure
                print(f"\n{'='*60}", file=sys.stderr)
                print(f"❌ ERROR: {runner.name} exited with code {exit_code}", file=sys.stderr)
                print(f"   Iteration: {iteration}/{max_iterations}", file=sys.stderr)
                if stderr:
                    print("", file=sys.stderr)
                    print("stderr output:", file=sys.stderr)
                    print(stderr, file=sys.stderr)
                print(f"{'='*60}", file=sys.stderr)
                stats.iterations_failed += 1
                if owns_stats:
                    stats.print_summary()
                return exit_code, stats.iterations_completed

        # Handle promise-based flow control
        if promise == "BUILD_COMPLETE":
            stats.iterations_completed += 1
            print(f"\n{'='*60}")
            print("✅ BUILD COMPLETE - All tasks finished!")
            print(f"{'='*60}")
            if owns_stats:
                stats.print_summary()
            return 0, stats.iterations_completed
        elif promise == "TASK_COMPLETE":
            stats.iterations_completed += 1
            print(f"\n✓ Task complete. Continuing to next iteration...")
            # Loop continues to next iteration
        else:
            # No promise detected - Claude may need more work
            print(f"\n⚠ No promise detected. Continuing to next iteration...")
            # Loop continues to next iteration

    # Max iterations reached
    print(f"\n{'='*60}")
    print(f"⚠ Max iterations ({max_iterations}) reached. Build incomplete.")
    print("   Review build_progress.md and tasks file to assess state.")
    print(f"{'='*60}")
    if owns_stats:
        stats.print_summary()
    return 1, stats.iterations_completed
