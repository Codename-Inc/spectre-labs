"""
Stage lifecycle hooks for pipeline execution.

Provides before_stage and after_stage callbacks that capture git state
and inject review context between build and code review stages.
"""

import logging
from pathlib import Path
from typing import Any

from .git_scope import collect_diff, format_commits, format_file_list, snapshot_head
from .pipeline.completion import CompletionResult

logger = logging.getLogger(__name__)


def before_stage_hook(stage_name: str, context: dict[str, Any]) -> None:
    """Hook called before each stage runs.

    For build stages, snapshots HEAD so we can compute the diff afterward.

    Args:
        stage_name: Name of the stage about to run
        context: Mutable pipeline context dictionary
    """
    if stage_name == "build":
        head = snapshot_head()
        if head:
            context["_phase_start_commit"] = head
            logger.info("Snapshotted HEAD at %s for build stage", head)
        else:
            logger.warning("Could not snapshot HEAD before build stage")


def after_stage_hook(
    stage_name: str,
    context: dict[str, Any],
    result: CompletionResult,
) -> None:
    """Hook called after each stage completes.

    For build stages, computes the git diff and injects changed_files,
    commit_messages, and review_fixes_path into context for the code
    review prompt.

    Args:
        stage_name: Name of the stage that just completed
        context: Mutable pipeline context dictionary
        result: CompletionResult from the stage
    """
    if stage_name == "build":
        start_commit = context.get("_phase_start_commit")
        if not start_commit:
            logger.warning("No _phase_start_commit found, skipping diff collection")
            context["changed_files"] = "No files changed (no start commit captured)"
            context["commit_messages"] = "No commits (no start commit captured)"
            _set_review_fixes_path(context)
            return

        diff = collect_diff(start_commit)
        if diff:
            context["changed_files"] = format_file_list(diff)
            context["commit_messages"] = format_commits(diff)
            logger.info(
                "Collected diff: %d files changed, %d commits (%s..%s)",
                len(diff.changed_files),
                len(diff.commit_messages),
                diff.start_commit,
                diff.end_commit,
            )
        else:
            context["changed_files"] = "No files changed"
            context["commit_messages"] = "No commits"
            logger.warning("Failed to collect diff from %s", start_commit)

        _set_review_fixes_path(context)

    elif stage_name == "validate":
        if result.signal == "GAPS_FOUND":
            # Inject gaps file as remediation tasks for the next build iteration
            gaps_file = result.artifacts.get("gaps_file", "")
            if gaps_file:
                context["remediation_tasks_path"] = gaps_file
                logger.info("Validation gaps found, remediation file: %s", gaps_file)
            else:
                logger.warning("GAPS_FOUND signal but no gaps_file in artifacts")

        elif result.signal in ("VALIDATED", "ALL_VALIDATED"):
            # Clear remediation path — validation passed
            context["remediation_tasks_path"] = ""

            # Track which phases have been validated
            phase = context.get("phase_completed", "")
            validated = context.setdefault("_validated_phases", [])
            if phase and phase != "all" and phase not in validated:
                validated.append(phase)
                logger.info("Phase validated: %s", phase)
            context["validated_phases"] = ", ".join(validated) if validated else "None"


def _set_review_fixes_path(context: dict[str, Any]) -> None:
    """Set the review_fixes_path in context based on tasks file location."""
    tasks_file = context.get("tasks_file_path", "")
    if tasks_file:
        review_fixes = str(Path(tasks_file).parent / "review_fixes.md")
    else:
        review_fixes = "review_fixes.md"
    context["review_fixes_path"] = review_fixes
