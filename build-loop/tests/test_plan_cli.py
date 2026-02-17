"""Tests for planning pipeline CLI integration (--plan flag, run_plan_pipeline, routing)."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestParsePlanFlag:
    """Tests for --plan flag in parse_args."""

    def test_plan_flag_sets_plan_true(self):
        """Happy: --plan flag sets args.plan to True."""
        with patch("sys.argv", ["spectre-build", "--plan", "--context", "scope.md"]):
            from build_loop.cli import parse_args
            args = parse_args()
            assert args.plan is True

    def test_no_plan_flag_defaults_to_false(self):
        """Failure: Without --plan, args.plan is False."""
        with patch("sys.argv", ["spectre-build", "--tasks", "tasks.md"]):
            from build_loop.cli import parse_args
            args = parse_args()
            assert args.plan is False


class TestRunPlanPipeline:
    """Tests for run_plan_pipeline() function."""

    def test_run_plan_pipeline_creates_pipeline_and_returns_success(self):
        """Happy: run_plan_pipeline creates pipeline, wires hooks, returns (0, iterations)."""
        from build_loop.cli import run_plan_pipeline

        mock_runner = MagicMock()
        mock_runner.check_available.return_value = True

        # Mock PipelineExecutor to avoid actual execution
        mock_state = MagicMock()
        mock_state.total_iterations = 5
        mock_state.global_artifacts = {"manifest_path": "/tmp/build.md"}
        mock_state.stage_history = [
            ("research", "RESEARCH_COMPLETE"),
            ("assess", "STANDARD"),
            ("create_plan", "PLAN_COMPLETE"),
            ("create_tasks", "TASKS_COMPLETE"),
            ("plan_review", "REVIEW_COMPLETE"),
            ("req_validate", "PLAN_VALIDATED"),
        ]

        mock_executor_instance = MagicMock()
        mock_executor_instance.run.return_value = mock_state

        with patch("build_loop.agent.get_agent", return_value=mock_runner), \
             patch("build_loop.pipeline.loader.create_plan_pipeline") as mock_create, \
             patch("build_loop.pipeline.executor.PipelineExecutor", return_value=mock_executor_instance) as mock_executor_cls, \
             patch("build_loop.pipeline.executor.PipelineStatus") as mock_status:

            mock_status.COMPLETED = "completed"
            mock_status.STOPPED = "stopped"
            mock_state.status = mock_status.COMPLETED

            exit_code, iterations = run_plan_pipeline(
                context_files=["scope.md"],
                max_iterations=10,
                agent="claude",
            )

            assert exit_code == 0
            assert iterations == 5
            mock_create.assert_called_once()
            # Verify hooks were wired
            call_kwargs = mock_executor_cls.call_args[1]
            assert call_kwargs.get("before_stage") is not None
            assert call_kwargs.get("after_stage") is not None

    def test_run_plan_pipeline_clarifications_needed_saves_session_returns_zero(self):
        """Failure: CLARIFICATIONS_NEEDED signal saves session and returns exit code 0."""
        from build_loop.cli import run_plan_pipeline

        mock_runner = MagicMock()
        mock_runner.check_available.return_value = True

        # Simulate pipeline ending with CLARIFICATIONS_NEEDED
        mock_state = MagicMock()
        mock_state.total_iterations = 6
        mock_state.global_artifacts = {
            "clarifications_path": "/tmp/clarifications.md",
        }
        mock_state.stage_history = [
            ("research", "RESEARCH_COMPLETE"),
            ("assess", "STANDARD"),
            ("create_plan", "PLAN_COMPLETE"),
            ("create_tasks", "TASKS_COMPLETE"),
            ("plan_review", "REVIEW_COMPLETE"),
            ("req_validate", "CLARIFICATIONS_NEEDED"),
        ]

        mock_executor_instance = MagicMock()
        mock_executor_instance.run.return_value = mock_state

        with patch("build_loop.agent.get_agent", return_value=mock_runner), \
             patch("build_loop.pipeline.loader.create_plan_pipeline"), \
             patch("build_loop.pipeline.executor.PipelineExecutor", return_value=mock_executor_instance), \
             patch("build_loop.pipeline.executor.PipelineStatus") as mock_status, \
             patch("build_loop.cli.save_session") as mock_save:

            mock_status.COMPLETED = "completed"
            mock_status.STOPPED = "stopped"
            mock_state.status = mock_status.COMPLETED

            exit_code, iterations = run_plan_pipeline(
                context_files=["scope.md"],
                max_iterations=10,
                agent="claude",
            )

            # Should return 0 (not an error)
            assert exit_code == 0
            assert iterations == 6
            # Should save session for resume
            mock_save.assert_called_once()
            call_kwargs = mock_save.call_args[1]
            assert call_kwargs.get("plan") is True

    def test_run_plan_pipeline_agent_not_available_returns_127(self):
        """Failure: Agent not found returns exit code 127."""
        from build_loop.cli import run_plan_pipeline

        mock_runner = MagicMock()
        mock_runner.check_available.return_value = False
        mock_runner.name = "claude"

        with patch("build_loop.agent.get_agent", return_value=mock_runner):
            exit_code, iterations = run_plan_pipeline(
                context_files=["scope.md"],
                max_iterations=10,
                agent="claude",
            )
            assert exit_code == 127
            assert iterations == 0


class TestMainPlanRouting:
    """Tests for --plan routing in main()."""

    def test_main_routes_plan_to_run_plan_pipeline(self):
        """Happy: main() with --plan routes to run_plan_pipeline."""
        with patch("sys.argv", ["spectre-build", "--plan", "--context", "scope.md"]), \
             patch("build_loop.cli.run_plan_pipeline", return_value=(0, 5)) as mock_run, \
             patch("build_loop.cli.notify_build_complete"), \
             patch("build_loop.cli.save_session"):

            from build_loop.cli import main
            with pytest.raises(SystemExit) as exc_info:
                main()

            assert exc_info.value.code == 0
            mock_run.assert_called_once()
            call_kwargs = mock_run.call_args[1]
            assert "scope.md" in str(call_kwargs.get("context_files", []))

    def test_main_plan_without_context_exits_with_error(self):
        """Failure: --plan without --context exits with error message."""
        with patch("sys.argv", ["spectre-build", "--plan"]):

            from build_loop.cli import main
            with pytest.raises(SystemExit) as exc_info:
                main()

            assert exc_info.value.code == 1
