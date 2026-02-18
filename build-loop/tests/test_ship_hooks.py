"""Tests for ship-specific lifecycle hooks.

Tests the 8 sub-stage ship pipeline hook behavior:
- ship_before_stage: snapshots HEAD at clean_discover and test_plan
- ship_after_stage: captures clean_summary after clean_execute,
  test_summary after test_commit
"""

from unittest.mock import patch

import pytest

from build_loop.hooks import ship_after_stage, ship_before_stage
from build_loop.pipeline.completion import CompletionResult


# ---------------------------------------------------------------------------
# ship_before_stage
# ---------------------------------------------------------------------------


class TestShipBeforeStageCleanDiscover:
    """Tests for ship_before_stage HEAD snapshot on clean_discover stage."""

    def test_snapshots_head_for_clean_discover_stage(self):
        """Happy: clean_discover stage snapshots HEAD into context."""
        context: dict = {}
        with patch("build_loop.hooks.snapshot_head", return_value="abc1234"):
            ship_before_stage("clean_discover", context)
        assert context["_phase_start_commit"] == "abc1234"

    def test_handles_snapshot_failure_for_clean_discover(self):
        """Failure: clean_discover with snapshot_head returning None does not crash."""
        context: dict = {}
        with patch("build_loop.hooks.snapshot_head", return_value=None):
            ship_before_stage("clean_discover", context)
        assert "_phase_start_commit" not in context


class TestShipBeforeStageTestPlan:
    """Tests for ship_before_stage HEAD snapshot on test_plan stage."""

    def test_snapshots_head_for_test_plan_stage(self):
        """Happy: test_plan stage snapshots HEAD into context."""
        context: dict = {}
        with patch("build_loop.hooks.snapshot_head", return_value="def5678"):
            ship_before_stage("test_plan", context)
        assert context["_phase_start_commit"] == "def5678"

    def test_handles_snapshot_failure_for_test_plan(self):
        """Failure: test_plan with snapshot_head returning None does not crash."""
        context: dict = {}
        with patch("build_loop.hooks.snapshot_head", return_value=None):
            ship_before_stage("test_plan", context)
        assert "_phase_start_commit" not in context


class TestShipBeforeStageNoOps:
    """Tests that ship_before_stage is no-op for non-snapshot sub-stages."""

    @pytest.mark.parametrize(
        "stage_name",
        [
            "clean_investigate",
            "clean_execute",
            "test_execute",
            "test_verify",
            "test_commit",
            "rebase",
        ],
    )
    def test_is_noop_for_non_snapshot_stages(self, stage_name):
        """Failure: non-snapshot sub-stages do not modify context."""
        context: dict = {"parent_branch": "main"}
        ship_before_stage(stage_name, context)
        assert context == {"parent_branch": "main"}

    def test_is_noop_for_unrelated_stages(self):
        """ship_before_stage does nothing for non-ship stages like build."""
        context: dict = {"some_key": "value"}
        ship_before_stage("build", context)
        assert context == {"some_key": "value"}


# ---------------------------------------------------------------------------
# ship_after_stage
# ---------------------------------------------------------------------------


class TestShipAfterStageCleanExecute:
    """Tests for ship_after_stage clean_summary capture after clean_execute."""

    def test_captures_clean_summary_from_diff(self):
        """Happy: after clean_execute, context gets clean_summary from git diff."""
        from build_loop.git_scope import GitDiff

        diff = GitDiff(
            start_commit="abc1234",
            end_commit="xyz9999",
            changed_files=["src/foo.py (deleted)", "src/bar.py (modified)"],
            commit_messages=["abc1234 Remove dead code", "def5678 Fix lint"],
        )
        context: dict = {"_phase_start_commit": "abc1234"}
        result = CompletionResult(is_complete=True, signal="CLEAN_EXECUTE_COMPLETE")

        with patch("build_loop.hooks.collect_diff", return_value=diff):
            ship_after_stage("clean_execute", context, result)

        assert "clean_summary" in context
        assert "src/foo.py" in context["clean_summary"]
        assert "Remove dead code" in context["clean_summary"]

    def test_handles_missing_start_commit_for_clean_execute(self):
        """Failure: after clean_execute with no start commit, sets fallback clean_summary."""
        context: dict = {}
        result = CompletionResult(is_complete=True, signal="CLEAN_EXECUTE_COMPLETE")
        ship_after_stage("clean_execute", context, result)
        assert "clean_summary" in context
        assert context["clean_summary"] != ""

    def test_handles_collect_diff_failure_for_clean_execute(self):
        """Failure: after clean_execute with diff failure, sets fallback clean_summary."""
        context: dict = {"_phase_start_commit": "abc1234"}
        result = CompletionResult(is_complete=True, signal="CLEAN_EXECUTE_COMPLETE")

        with patch("build_loop.hooks.collect_diff", return_value=None):
            ship_after_stage("clean_execute", context, result)

        assert "clean_summary" in context
        assert context["clean_summary"] != ""


class TestShipAfterStageTestCommit:
    """Tests for ship_after_stage test_summary capture after test_commit."""

    def test_captures_test_summary_from_diff(self):
        """Happy: after test_commit, context gets test_summary from git diff."""
        from build_loop.git_scope import GitDiff

        diff = GitDiff(
            start_commit="def5678",
            end_commit="ghi0000",
            changed_files=["tests/test_foo.py (added)", "tests/test_bar.py (added)"],
            commit_messages=["ghi0000 Add test coverage"],
        )
        context: dict = {"_phase_start_commit": "def5678"}
        result = CompletionResult(is_complete=True, signal="TEST_COMMIT_COMPLETE")

        with patch("build_loop.hooks.collect_diff", return_value=diff):
            ship_after_stage("test_commit", context, result)

        assert "test_summary" in context
        assert "test_foo.py" in context["test_summary"]
        assert "Add test coverage" in context["test_summary"]

    def test_handles_collect_diff_failure_for_test_commit(self):
        """Failure: after test_commit with collect_diff returning None, sets fallback."""
        context: dict = {"_phase_start_commit": "def5678"}
        result = CompletionResult(is_complete=True, signal="TEST_COMMIT_COMPLETE")

        with patch("build_loop.hooks.collect_diff", return_value=None):
            ship_after_stage("test_commit", context, result)

        assert "test_summary" in context
        assert context["test_summary"] != ""

    def test_handles_missing_start_commit_for_test_commit(self):
        """Failure: after test_commit with no start commit, sets fallback test_summary."""
        context: dict = {}
        result = CompletionResult(is_complete=True, signal="TEST_COMMIT_COMPLETE")
        ship_after_stage("test_commit", context, result)
        assert "test_summary" in context
        assert context["test_summary"] != ""


class TestShipAfterStageNoOps:
    """Tests that ship_after_stage is no-op for non-summary sub-stages."""

    @pytest.mark.parametrize(
        "stage_name,signal",
        [
            ("clean_discover", "CLEAN_DISCOVER_COMPLETE"),
            ("clean_investigate", "CLEAN_INVESTIGATE_COMPLETE"),
            ("test_plan", "TEST_PLAN_COMPLETE"),
            ("test_execute", "TEST_EXECUTE_COMPLETE"),
            ("test_verify", "TEST_VERIFY_COMPLETE"),
            ("rebase", "SHIP_COMPLETE"),
        ],
    )
    def test_is_noop_for_non_summary_stages(self, stage_name, signal):
        """Failure: non-summary sub-stages do not add keys to context."""
        context: dict = {"parent_branch": "main", "clean_summary": "...", "test_summary": "..."}
        result = CompletionResult(is_complete=True, signal=signal)
        ship_after_stage(stage_name, context, result)
        assert context == {"parent_branch": "main", "clean_summary": "...", "test_summary": "..."}

    def test_is_noop_for_unrelated_stages(self):
        """ship_after_stage does nothing for non-ship stages like build."""
        context: dict = {"some_key": "value"}
        result = CompletionResult(is_complete=True, signal="BUILD_COMPLETE")
        ship_after_stage("build", context, result)
        assert context == {"some_key": "value"}
