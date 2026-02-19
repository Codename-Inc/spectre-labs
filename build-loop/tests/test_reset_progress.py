"""Tests for reset_progress_file() — trims iteration logs, keeps Codebase Patterns."""

from pathlib import Path

from build_loop.prompt import reset_progress_file

PATTERNS_SECTION = """\
# Build Progress

## Codebase Patterns
- Pattern A: always use foo
- Pattern B: bar is deprecated

---
"""

ITERATION_LOG = """\
## Iteration — [1.1] Do the thing
**Status**: Complete
**What Was Done**: Did the thing.
**Files Changed**:
- src/foo.py
**Key Decisions**: None
**Blockers/Risks**: None

## Iteration — [1.2] Do the other thing
**Status**: Complete
**What Was Done**: Did the other thing.
**Files Changed**:
- src/bar.py
**Key Decisions**: None
**Blockers/Risks**: None
"""


def test_trims_iteration_logs_keeps_patterns(tmp_path: Path):
    """Core case: file with patterns + iterations → keep patterns, drop iterations."""
    progress = tmp_path / "build_progress.md"
    progress.write_text(PATTERNS_SECTION + ITERATION_LOG)

    reset_progress_file(str(progress))

    assert progress.read_text() == PATTERNS_SECTION


def test_noop_when_file_missing(tmp_path: Path):
    """No file → no error, no file created."""
    progress = tmp_path / "build_progress.md"

    reset_progress_file(str(progress))

    assert not progress.exists()


def test_noop_when_no_iterations(tmp_path: Path):
    """File with only patterns (no iteration logs) → untouched."""
    progress = tmp_path / "build_progress.md"
    progress.write_text(PATTERNS_SECTION)

    reset_progress_file(str(progress))

    assert progress.read_text() == PATTERNS_SECTION


def test_noop_when_no_separator(tmp_path: Path):
    """Malformed file without --- separator → untouched."""
    content = "# Build Progress\n\nSome content without separator\n"
    progress = tmp_path / "build_progress.md"
    progress.write_text(content)

    reset_progress_file(str(progress))

    assert progress.read_text() == content


def test_preserves_multiline_patterns(tmp_path: Path):
    """Codebase Patterns with rich content is preserved."""
    rich_patterns = """\
# Build Progress

## Codebase Patterns
- Full test suite: 309 tests, runs in ~0.8s via `pytest tests/ -v`
- `AgentRunner.run_iteration()` accepts `denied_tools: list[str] | None = None`
- Tool allow/deny lists are module-level constants in `agent.py` (global) and `loader.py` (per-pipeline)
- `CLAUDE_ALLOWED_TOOLS` feeds `--allowedTools` flag

---
"""
    progress = tmp_path / "build_progress.md"
    progress.write_text(rich_patterns + ITERATION_LOG)

    reset_progress_file(str(progress))

    assert progress.read_text() == rich_patterns


def test_handles_multiple_separators(tmp_path: Path):
    """Only splits on the first --- separator."""
    content = """\
# Build Progress

## Codebase Patterns
- Pattern A

---

## Iteration — [1.1] First
**Status**: Complete

---

## Iteration — [1.2] Second
**Status**: Complete
"""
    progress = tmp_path / "build_progress.md"
    progress.write_text(content)

    reset_progress_file(str(progress))

    expected = """\
# Build Progress

## Codebase Patterns
- Pattern A

---
"""
    assert progress.read_text() == expected


def test_empty_patterns_section(tmp_path: Path):
    """Empty patterns section with iterations below → keeps header, drops iterations."""
    content = """\
# Build Progress

## Codebase Patterns

---

## Iteration — [1.1] Do stuff
**Status**: Complete
"""
    progress = tmp_path / "build_progress.md"
    progress.write_text(content)

    reset_progress_file(str(progress))

    expected = """\
# Build Progress

## Codebase Patterns

---
"""
    assert progress.read_text() == expected
