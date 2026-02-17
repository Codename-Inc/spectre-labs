"""
Git scope utilities for capturing diffs between pipeline stages.

Provides functions to snapshot HEAD, collect diffs, and format
changed file lists and commit messages for prompt injection.
"""

import logging
import subprocess
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class GitDiff:
    """Represents a git diff between two commits.

    Attributes:
        start_commit: The starting commit SHA
        end_commit: The ending commit SHA (HEAD when collected)
        changed_files: List of changed file paths with status
        commit_messages: List of commit messages in range
    """
    start_commit: str
    end_commit: str
    changed_files: list[str] = field(default_factory=list)
    commit_messages: list[str] = field(default_factory=list)


def _run_git(args: list[str]) -> str | None:
    """Run a git command and return stdout, or None on failure."""
    try:
        result = subprocess.run(
            ["git"] + args,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            return result.stdout.strip()
        logger.debug("git %s failed (exit %d): %s", " ".join(args), result.returncode, result.stderr.strip())
        return None
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        logger.debug("git command failed: %s", e)
        return None


def snapshot_head() -> str | None:
    """Capture current HEAD SHA.

    Returns:
        Short SHA of HEAD, or None if not in a git repo.
    """
    return _run_git(["rev-parse", "--short", "HEAD"])


def collect_diff(start_commit: str) -> GitDiff | None:
    """Collect changed files and commit messages since start_commit.

    Captures both committed changes (start..HEAD) and uncommitted changes
    (staged + working tree), so agents that don't commit (e.g., Codex with
    workspace-write sandbox) still produce a meaningful diff.

    Args:
        start_commit: The commit SHA to diff from (exclusive)

    Returns:
        GitDiff with changed files and commit messages, or None on failure.
    """
    end_commit = _run_git(["rev-parse", "--short", "HEAD"])
    if not end_commit:
        return None

    changed_files = []
    commit_messages = []

    # Collect committed changes if HEAD moved
    if start_commit != end_commit:
        diff_output = _run_git(["diff", "--name-status", f"{start_commit}..HEAD"])
        if diff_output:
            changed_files.extend(_parse_name_status(diff_output))

        log_output = _run_git(["log", "--oneline", f"{start_commit}..HEAD"])
        if log_output:
            commit_messages = log_output.splitlines()

    # Collect uncommitted changes (staged + working tree)
    # This catches agents that write files without committing (e.g., Codex)
    uncommitted_output = _run_git(["diff", "--name-status", "HEAD"])
    staged_output = _run_git(["diff", "--name-status", "--cached"])

    # Merge uncommitted files, dedup against committed set
    seen = {f.rsplit(" (", 1)[0] for f in changed_files}
    for output in (uncommitted_output, staged_output):
        if output:
            for entry in _parse_name_status(output):
                filepath = entry.rsplit(" (", 1)[0]
                if filepath not in seen:
                    changed_files.append(entry)
                    seen.add(filepath)

    if not changed_files and start_commit == end_commit:
        logger.info("No committed or uncommitted changes since %s", start_commit)

    return GitDiff(
        start_commit=start_commit,
        end_commit=end_commit,
        changed_files=changed_files,
        commit_messages=commit_messages,
    )


def _parse_name_status(output: str) -> list[str]:
    """Parse git diff --name-status output into formatted file entries."""
    files = []
    for line in output.splitlines():
        parts = line.split("\t", 1)
        if len(parts) == 2:
            status, filepath = parts
            status_label = {"A": "added", "M": "modified", "D": "deleted"}.get(status, status)
            files.append(f"{filepath} ({status_label})")
    return files


def format_file_list(diff: GitDiff) -> str:
    """Format changed files as a markdown list for prompt injection.

    Args:
        diff: GitDiff containing changed files

    Returns:
        Formatted markdown string, or "No files changed" if empty.
    """
    if not diff.changed_files:
        return "No files changed"
    return "\n".join(f"- `{f}`" for f in diff.changed_files)


def format_commits(diff: GitDiff) -> str:
    """Format commit messages as a markdown list for prompt injection.

    Args:
        diff: GitDiff containing commit messages

    Returns:
        Formatted markdown string, or "No commits" if empty.
    """
    if not diff.commit_messages:
        return "No commits"
    return "\n".join(f"- {msg}" for msg in diff.commit_messages)
