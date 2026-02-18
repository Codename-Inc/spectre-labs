"""Tests for run_ship_pipeline() function in cli.py."""

import subprocess
from unittest.mock import MagicMock, patch

import pytest


class TestRunShipPipelineHappy:
    """Tests for run_ship_pipeline() happy path."""

    def test_detects_parent_branch_assembles_context_wires_pipeline_returns_success(self):
        """Happy: Detects parent branch, computes working set, creates pipeline with hooks/stats, returns (0, iterations)."""
        from build_loop.cli import run_ship_pipeline

        mock_runner = MagicMock()
        mock_runner.check_available.return_value = True

        mock_state = MagicMock()
        mock_state.total_iterations = 3
        mock_state.status = "completed"

        mock_executor_instance = MagicMock()
        mock_executor_instance.run.return_value = mock_state

        # Mock subprocess for parent branch detection and working set scope
        def mock_check_output(cmd, **kwargs):
            if "merge-base" in cmd:
                return "abc1234\n"
            if "rev-parse" in cmd and "--abbrev-ref" in cmd:
                return "feature-branch\n"
            if "log" in cmd and "--oneline" in cmd:
                return "abc1234 feat: something\ndef5678 fix: another\n"
            return "\n"

        with patch("build_loop.agent.get_agent", return_value=mock_runner), \
             patch("build_loop.pipeline.loader.create_ship_pipeline") as mock_create, \
             patch("build_loop.pipeline.executor.PipelineExecutor", return_value=mock_executor_instance) as mock_executor_cls, \
             patch("build_loop.pipeline.executor.PipelineStatus") as mock_status, \
             patch("subprocess.check_output", side_effect=mock_check_output):

            mock_status.COMPLETED = "completed"
            mock_status.STOPPED = "stopped"

            exit_code, iterations = run_ship_pipeline(
                context_files=["scope.md"],
                max_iterations=10,
                agent="claude",
            )

            assert exit_code == 0
            assert iterations == 3
            mock_create.assert_called_once()

            # Verify hooks were wired
            call_kwargs = mock_executor_cls.call_args[1]
            assert call_kwargs.get("before_stage") is not None
            assert call_kwargs.get("after_stage") is not None
            assert call_kwargs.get("on_event") is not None

            # Verify context has required keys
            context = call_kwargs.get("context", {})
            assert "parent_branch" in context
            assert "working_set_scope" in context
            assert "context_files" in context
            assert "clean_summary" in context
            assert "test_summary" in context


class TestRunShipPipelineFailure:
    """Tests for run_ship_pipeline() failure paths."""

    def test_fails_fast_when_parent_branch_detection_fails(self):
        """Failure: Returns non-zero exit code when parent branch cannot be detected."""
        from build_loop.cli import run_ship_pipeline

        mock_runner = MagicMock()
        mock_runner.check_available.return_value = True

        # All git commands fail
        with patch("build_loop.agent.get_agent", return_value=mock_runner), \
             patch("subprocess.check_output", side_effect=subprocess.CalledProcessError(1, "git")):

            exit_code, iterations = run_ship_pipeline(
                context_files=[],
                max_iterations=10,
                agent="claude",
            )

            assert exit_code == 1
            assert iterations == 0

    def test_uses_resume_context_when_provided(self):
        """Happy: Uses resume_context instead of building fresh context."""
        from build_loop.cli import run_ship_pipeline

        mock_runner = MagicMock()
        mock_runner.check_available.return_value = True

        mock_state = MagicMock()
        mock_state.total_iterations = 2
        mock_state.status = "completed"

        mock_executor_instance = MagicMock()
        mock_executor_instance.run.return_value = mock_state

        resume_ctx = {
            "parent_branch": "main",
            "working_set_scope": "main..HEAD",
            "context_files": "- scope.md",
            "clean_summary": "Already cleaned",
            "test_summary": "",
        }

        with patch("build_loop.agent.get_agent", return_value=mock_runner), \
             patch("build_loop.pipeline.loader.create_ship_pipeline"), \
             patch("build_loop.pipeline.executor.PipelineExecutor", return_value=mock_executor_instance) as mock_executor_cls, \
             patch("build_loop.pipeline.executor.PipelineStatus") as mock_status:

            mock_status.COMPLETED = "completed"
            mock_status.STOPPED = "stopped"

            exit_code, iterations = run_ship_pipeline(
                context_files=["scope.md"],
                max_iterations=10,
                agent="claude",
                resume_context=resume_ctx,
            )

            assert exit_code == 0
            assert iterations == 2

            # Verify resume context was used (not fresh context)
            call_kwargs = mock_executor_cls.call_args[1]
            context = call_kwargs.get("context", {})
            assert context["parent_branch"] == "main"
            assert context["clean_summary"] == "Already cleaned"

    def test_returns_127_when_agent_not_available(self):
        """Failure: Returns 127 when agent CLI not found."""
        from build_loop.cli import run_ship_pipeline

        mock_runner = MagicMock()
        mock_runner.check_available.return_value = False
        mock_runner.name = "claude"

        with patch("build_loop.agent.get_agent", return_value=mock_runner):
            exit_code, iterations = run_ship_pipeline(
                context_files=[],
                max_iterations=10,
                agent="claude",
            )

            assert exit_code == 127
            assert iterations == 0

    def test_returns_130_on_pipeline_stopped(self):
        """Failure: Returns 130 when pipeline is interrupted/stopped."""
        from build_loop.cli import run_ship_pipeline

        mock_runner = MagicMock()
        mock_runner.check_available.return_value = True

        mock_state = MagicMock()
        mock_state.total_iterations = 1
        mock_state.status = "stopped"

        mock_executor_instance = MagicMock()
        mock_executor_instance.run.return_value = mock_state

        def mock_check_output(cmd, **kwargs):
            if "merge-base" in cmd:
                return "abc1234\n"
            if "rev-parse" in cmd and "--abbrev-ref" in cmd:
                return "feature-branch\n"
            if "log" in cmd and "--oneline" in cmd:
                return "abc1234 feat: something\n"
            return "\n"

        with patch("build_loop.agent.get_agent", return_value=mock_runner), \
             patch("build_loop.pipeline.loader.create_ship_pipeline"), \
             patch("build_loop.pipeline.executor.PipelineExecutor", return_value=mock_executor_instance), \
             patch("build_loop.pipeline.executor.PipelineStatus") as mock_status, \
             patch("subprocess.check_output", side_effect=mock_check_output):

            mock_status.COMPLETED = "completed"
            mock_status.STOPPED = "stopped"

            exit_code, iterations = run_ship_pipeline(
                context_files=[],
                max_iterations=10,
                agent="claude",
            )

            assert exit_code == 130
            assert iterations == 1
