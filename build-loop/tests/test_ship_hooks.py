"""Tests for ship-specific lifecycle hooks."""

from unittest.mock import patch

from build_loop.hooks import ship_after_stage, ship_before_stage
from build_loop.pipeline.completion import CompletionResult


# ---------------------------------------------------------------------------
# ship_before_stage
# ---------------------------------------------------------------------------


class TestShipBeforeStageClean:
    """Tests for ship_before_stage HEAD snapshot on clean stage."""

    def test_snapshots_head_for_clean_stage(self):
        """Happy: clean stage snapshots HEAD into context."""
        context: dict = {}
        with patch("build_loop.hooks.snapshot_head", return_value="abc1234"):
            ship_before_stage("clean", context)
        assert context["_phase_start_commit"] == "abc1234"

    def test_handles_snapshot_failure_for_clean(self):
        """Failure: clean stage with snapshot_head returning None does not crash."""
        context: dict = {}
        with patch("build_loop.hooks.snapshot_head", return_value=None):
            ship_before_stage("clean", context)
        assert "_phase_start_commit" not in context


class TestShipBeforeStageTest:
    """Tests for ship_before_stage HEAD snapshot on test stage."""

    def test_snapshots_head_for_test_stage(self):
        """Happy: test stage snapshots HEAD into context."""
        context: dict = {}
        with patch("build_loop.hooks.snapshot_head", return_value="def5678"):
            ship_before_stage("test", context)
        assert context["_phase_start_commit"] == "def5678"


class TestShipBeforeStageRebase:
    """Tests for ship_before_stage no-op on rebase stage."""

    def test_is_noop_for_rebase_stage(self):
        """Failure: rebase stage does not modify context."""
        context: dict = {"parent_branch": "main"}
        ship_before_stage("rebase", context)
        assert context == {"parent_branch": "main"}


# ---------------------------------------------------------------------------
# ship_after_stage
# ---------------------------------------------------------------------------


class TestShipAfterStageClean:
    """Tests for ship_after_stage clean_summary capture after clean stage."""

    def test_captures_clean_summary_from_diff(self):
        """Happy: after clean stage, context gets clean_summary from git diff."""
        from build_loop.git_scope import GitDiff

        diff = GitDiff(
            start_commit="abc1234",
            end_commit="xyz9999",
            changed_files=["src/foo.py (deleted)", "src/bar.py (modified)"],
            commit_messages=["abc1234 Remove dead code", "def5678 Fix lint"],
        )
        context: dict = {"_phase_start_commit": "abc1234"}
        result = CompletionResult(is_complete=True, signal="CLEAN_COMPLETE")

        with patch("build_loop.hooks.collect_diff", return_value=diff):
            ship_after_stage("clean", context, result)

        assert "clean_summary" in context
        assert "src/foo.py" in context["clean_summary"]
        assert "Remove dead code" in context["clean_summary"]

    def test_handles_missing_start_commit_for_clean(self):
        """Failure: after clean stage with no start commit, sets fallback clean_summary."""
        context: dict = {}
        result = CompletionResult(is_complete=True, signal="CLEAN_COMPLETE")
        ship_after_stage("clean", context, result)
        assert "clean_summary" in context
        assert context["clean_summary"] != ""


class TestShipAfterStageTest:
    """Tests for ship_after_stage test_summary capture after test stage."""

    def test_captures_test_summary_from_diff(self):
        """Happy: after test stage, context gets test_summary from git diff."""
        from build_loop.git_scope import GitDiff

        diff = GitDiff(
            start_commit="def5678",
            end_commit="ghi0000",
            changed_files=["tests/test_foo.py (added)", "tests/test_bar.py (added)"],
            commit_messages=["ghi0000 Add test coverage"],
        )
        context: dict = {"_phase_start_commit": "def5678"}
        result = CompletionResult(is_complete=True, signal="TEST_COMPLETE")

        with patch("build_loop.hooks.collect_diff", return_value=diff):
            ship_after_stage("test", context, result)

        assert "test_summary" in context
        assert "test_foo.py" in context["test_summary"]
        assert "Add test coverage" in context["test_summary"]

    def test_handles_collect_diff_failure_for_test(self):
        """Failure: after test stage with collect_diff returning None, sets fallback."""
        context: dict = {"_phase_start_commit": "def5678"}
        result = CompletionResult(is_complete=True, signal="TEST_COMPLETE")

        with patch("build_loop.hooks.collect_diff", return_value=None):
            ship_after_stage("test", context, result)

        assert "test_summary" in context
        assert context["test_summary"] != ""


class TestShipAfterStageRebase:
    """Tests for ship_after_stage no-op on rebase stage."""

    def test_is_noop_for_rebase_stage(self):
        """Failure: rebase stage does not add new keys to context."""
        context: dict = {"parent_branch": "main", "clean_summary": "...", "test_summary": "..."}
        result = CompletionResult(is_complete=True, signal="SHIP_COMPLETE")
        ship_after_stage("rebase", context, result)
        assert context == {"parent_branch": "main", "clean_summary": "...", "test_summary": "..."}


class TestShipHooksIgnoreOtherStages:
    """Tests that ship hooks are no-ops for non-ship stages."""

    def test_before_stage_ignores_build(self):
        """ship_before_stage does nothing for build stage."""
        context: dict = {"some_key": "value"}
        ship_before_stage("build", context)
        assert context == {"some_key": "value"}

    def test_after_stage_ignores_build(self):
        """ship_after_stage does nothing for build stage."""
        context: dict = {"some_key": "value"}
        result = CompletionResult(is_complete=True, signal="BUILD_COMPLETE")
        ship_after_stage("build", context, result)
        assert context == {"some_key": "value"}
