"""
Stage lifecycle hooks for pipeline execution.

Provides before_stage and after_stage callbacks for the build pipeline
(git scope injection between build and code review stages), the planning
pipeline (depth defaults, clarification injection, artifact flow), and the
ship pipeline (HEAD snapshots, clean/test summary capture).
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


# ---------------------------------------------------------------------------
# Planning Pipeline Hooks
# ---------------------------------------------------------------------------


def plan_before_stage(stage_name: str, context: dict[str, Any]) -> None:
    """Hook called before each planning pipeline stage runs.

    For create_plan stage: ensures depth is in context (defaults to 'standard').
    For update_docs stage: reads clarifications file and injects content
    as clarification_answers.

    Args:
        stage_name: Name of the stage about to run
        context: Mutable pipeline context dictionary
    """
    if stage_name == "create_plan":
        if "depth" not in context:
            context["depth"] = "standard"
            logger.info("Defaulted depth to 'standard' for create_plan stage")

    elif stage_name == "update_docs":
        clarif_path = context.get("clarifications_path")
        if clarif_path and Path(clarif_path).exists():
            context["clarification_answers"] = Path(clarif_path).read_text()
            logger.info("Injected clarification answers from %s", clarif_path)
        else:
            context["clarification_answers"] = ""
            if clarif_path:
                logger.warning("Clarifications file not found: %s", clarif_path)
            else:
                logger.info("No clarifications_path in context for update_docs")


def plan_after_stage(
    stage_name: str,
    context: dict[str, Any],
    result: CompletionResult,
) -> None:
    """Hook called after each planning pipeline stage completes.

    For assess stage: ensures depth and tier from artifacts flow into context.
    For req_validate stage with CLARIFICATIONS_NEEDED: stores clarifications
    path in context for session save.

    Args:
        stage_name: Name of the stage that just completed
        context: Mutable pipeline context dictionary
        result: CompletionResult from the stage
    """
    if stage_name == "assess":
        context.setdefault("depth", result.artifacts.get("depth", "standard"))
        context.setdefault("tier", result.artifacts.get("tier", "STANDARD"))
        logger.info(
            "Assess stage complete: depth=%s, tier=%s",
            context["depth"],
            context["tier"],
        )

    elif stage_name == "req_validate":
        if result.signal == "CLARIFICATIONS_NEEDED":
            clarif_path = result.artifacts.get("clarifications_path", "")
            if clarif_path:
                context["clarifications_path"] = clarif_path
                logger.info("Clarifications needed, path: %s", clarif_path)


# ---------------------------------------------------------------------------
# Ship Pipeline Hooks
# ---------------------------------------------------------------------------


def ship_before_stage(stage_name: str, context: dict[str, Any]) -> None:
    """Hook called before each ship pipeline stage runs.

    Snapshots HEAD at the start of each logical group (clean_discover,
    test_plan) so the after-hook can compute what changed across the group.

    Args:
        stage_name: Name of the stage about to run
        context: Mutable pipeline context dictionary
    """
    if stage_name in ("clean_discover", "test_plan"):
        head = snapshot_head()
        if head:
            context["_phase_start_commit"] = head
            logger.info("Snapshotted HEAD at %s for ship %s stage", head, stage_name)
        else:
            logger.warning("Could not snapshot HEAD before ship %s stage", stage_name)


def ship_after_stage(
    stage_name: str,
    context: dict[str, Any],
    result: CompletionResult,
) -> None:
    """Hook called after each ship pipeline stage completes.

    Captures summaries at the end of each logical group:
    - clean_execute: collects git diff as clean_summary
    - test_commit: collects git diff as test_summary

    Args:
        stage_name: Name of the stage that just completed
        context: Mutable pipeline context dictionary
        result: CompletionResult from the stage
    """
    if stage_name == "clean_execute":
        context["clean_summary"] = _collect_stage_summary(context)
        logger.info("Captured clean_summary for ship pipeline")

    elif stage_name == "test_commit":
        context["test_summary"] = _collect_stage_summary(context)
        logger.info("Captured test_summary for ship pipeline")


def _collect_stage_summary(context: dict[str, Any]) -> str:
    """Collect a git diff summary for a ship stage.

    Returns a formatted string with changed files and commit messages,
    or a fallback message if no start commit was captured.
    """
    start_commit = context.get("_phase_start_commit")
    if not start_commit:
        return "No changes captured (no start commit)"

    diff = collect_diff(start_commit)
    if not diff:
        return "No changes captured (diff collection failed)"

    parts = []
    if diff.changed_files:
        parts.append("Files changed:")
        parts.extend(f"  - {f}" for f in diff.changed_files)
    if diff.commit_messages:
        parts.append("Commits:")
        parts.extend(f"  - {msg}" for msg in diff.commit_messages)

    return "\n".join(parts) if parts else "No changes detected"
