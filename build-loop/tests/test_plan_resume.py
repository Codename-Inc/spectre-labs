"""Tests for planning resume flow in run_resume()."""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestRunResumePlanRouting:
    """Tests for planning session detection and routing in run_resume()."""

    def _make_plan_session(self, **overrides):
        """Helper to create a planning session dict."""
        session = {
            "tasks_file": "",
            "context_files": ["scope.md", "design.md"],
            "max_iterations": 10,
            "agent": "claude",
            "validate": False,
            "manifest_path": None,
            "pipeline_path": None,
            "plan": True,
            "plan_output_dir": "/tmp/docs/tasks/main",
            "plan_context": {
                "context_files": "- `scope.md`\n- `design.md`",
                "output_dir": "/tmp/docs/tasks/main",
                "depth": "standard",
                "tier": "STANDARD",
            },
            "plan_clarifications_path": "/tmp/docs/tasks/main/clarifications/scope_clarifications.md",
            "started_at": "2026-02-17T10:00:00+00:00",
            "cwd": "/tmp",
        }
        session.update(overrides)
        return session

    def test_plan_session_routes_to_run_plan_pipeline_with_resume_stage(self):
        """Happy: run_resume with plan=True routes to run_plan_pipeline with resume_stage='update_docs'."""
        from build_loop.cli import run_resume

        session = self._make_plan_session()
        args = MagicMock()
        args.yes = True
        args.notify = False
        args.no_notify = True

        with patch("build_loop.cli.load_session", return_value=session), \
             patch("build_loop.cli.run_plan_pipeline", return_value=(0, 3)) as mock_run, \
             patch("build_loop.cli.save_session"), \
             patch("build_loop.cli.notify_build_complete"):

            with pytest.raises(SystemExit) as exc_info:
                run_resume(args)

            assert exc_info.value.code == 0
            mock_run.assert_called_once()
            call_kwargs = mock_run.call_args[1]
            assert call_kwargs["resume_stage"] == "update_docs"

    def test_non_plan_session_does_not_route_to_run_plan_pipeline(self):
        """Failure: run_resume with plan=False does not call run_plan_pipeline."""
        from build_loop.cli import run_resume

        session = {
            "tasks_file": "tasks.md",
            "context_files": ["scope.md"],
            "max_iterations": 10,
            "agent": "claude",
            "validate": True,
            "manifest_path": None,
            "pipeline_path": None,
            "started_at": "2026-02-17T10:00:00+00:00",
            "cwd": "/tmp",
        }
        args = MagicMock()
        args.yes = True
        args.notify = False
        args.no_notify = True

        with patch("build_loop.cli.load_session", return_value=session), \
             patch("build_loop.cli.run_plan_pipeline") as mock_plan, \
             patch("build_loop.cli.run_default_pipeline", return_value=(0, 5)), \
             patch("build_loop.cli.validate_inputs"), \
             patch("build_loop.cli.save_session"), \
             patch("build_loop.cli.notify_build_complete"):

            with pytest.raises(SystemExit):
                run_resume(args)

            mock_plan.assert_not_called()


class TestRunResumePlanContextPassthrough:
    """Tests for plan_context and plan_output_dir passthrough in run_resume()."""

    def _make_plan_session(self, **overrides):
        """Helper to create a planning session dict."""
        session = {
            "tasks_file": "",
            "context_files": ["scope.md"],
            "max_iterations": 10,
            "agent": "claude",
            "validate": False,
            "manifest_path": None,
            "pipeline_path": None,
            "plan": True,
            "plan_output_dir": "/tmp/docs/tasks/feature-x",
            "plan_context": {
                "context_files": "- `scope.md`",
                "output_dir": "/tmp/docs/tasks/feature-x",
                "depth": "comprehensive",
                "tier": "COMPREHENSIVE",
                "clarifications_path": "/tmp/clarif.md",
            },
            "plan_clarifications_path": "/tmp/clarif.md",
            "started_at": "2026-02-17T10:00:00+00:00",
            "cwd": "/tmp",
        }
        session.update(overrides)
        return session

    def test_plan_context_and_output_dir_passed_to_run_plan_pipeline(self):
        """Happy: run_resume passes plan_context as resume_context and plan_output_dir as output_dir."""
        from build_loop.cli import run_resume

        session = self._make_plan_session()
        args = MagicMock()
        args.yes = True
        args.notify = False
        args.no_notify = True

        with patch("build_loop.cli.load_session", return_value=session), \
             patch("build_loop.cli.run_plan_pipeline", return_value=(0, 1)) as mock_run, \
             patch("build_loop.cli.save_session"), \
             patch("build_loop.cli.notify_build_complete"):

            with pytest.raises(SystemExit):
                run_resume(args)

            call_kwargs = mock_run.call_args[1]
            assert call_kwargs["resume_context"] == session["plan_context"]
            assert call_kwargs["output_dir"] == "/tmp/docs/tasks/feature-x"
            assert call_kwargs["context_files"] == ["scope.md"]

    def test_missing_plan_context_passes_none(self):
        """Failure: run_resume with plan=True but no plan_context passes None as resume_context."""
        from build_loop.cli import run_resume

        session = self._make_plan_session(plan_context=None, plan_output_dir=None)
        args = MagicMock()
        args.yes = True
        args.notify = False
        args.no_notify = True

        with patch("build_loop.cli.load_session", return_value=session), \
             patch("build_loop.cli.run_plan_pipeline", return_value=(0, 1)) as mock_run, \
             patch("build_loop.cli.save_session"), \
             patch("build_loop.cli.notify_build_complete"):

            with pytest.raises(SystemExit):
                run_resume(args)

            call_kwargs = mock_run.call_args[1]
            assert call_kwargs["resume_context"] is None
            assert call_kwargs["output_dir"] is None


class TestRunResumePlanValidationSkip:
    """Tests for planning sessions skipping validate_inputs and updating session."""

    def _make_plan_session(self, **overrides):
        """Helper to create a planning session dict."""
        session = {
            "tasks_file": "",
            "context_files": ["scope.md"],
            "max_iterations": 10,
            "agent": "claude",
            "validate": False,
            "manifest_path": None,
            "pipeline_path": None,
            "plan": True,
            "plan_output_dir": "/tmp/docs/tasks/main",
            "plan_context": {"depth": "standard"},
            "plan_clarifications_path": "/tmp/clarif.md",
            "started_at": "2026-02-17T10:00:00+00:00",
            "cwd": "/tmp",
        }
        session.update(overrides)
        return session

    def test_plan_session_does_not_call_validate_inputs(self):
        """Happy: run_resume with plan=True skips validate_inputs (no tasks file to validate)."""
        from build_loop.cli import run_resume

        session = self._make_plan_session()
        args = MagicMock()
        args.yes = True
        args.notify = False
        args.no_notify = True

        with patch("build_loop.cli.load_session", return_value=session), \
             patch("build_loop.cli.run_plan_pipeline", return_value=(0, 1)), \
             patch("build_loop.cli.save_session"), \
             patch("build_loop.cli.validate_inputs") as mock_validate, \
             patch("build_loop.cli.notify_build_complete"):

            with pytest.raises(SystemExit):
                run_resume(args)

            mock_validate.assert_not_called()

    def test_plan_session_saves_session_with_planning_fields(self):
        """Failure: run_resume with plan=True calls save_session with all planning fields."""
        from build_loop.cli import run_resume

        session = self._make_plan_session()
        args = MagicMock()
        args.yes = True
        args.notify = False
        args.no_notify = True

        with patch("build_loop.cli.load_session", return_value=session), \
             patch("build_loop.cli.run_plan_pipeline", return_value=(0, 1)), \
             patch("build_loop.cli.save_session") as mock_save, \
             patch("build_loop.cli.notify_build_complete"):

            with pytest.raises(SystemExit):
                run_resume(args)

            mock_save.assert_called_once()
            call_kwargs = mock_save.call_args[1]
            assert call_kwargs["plan"] is True
            assert call_kwargs["plan_output_dir"] == "/tmp/docs/tasks/main"
            assert call_kwargs["plan_clarifications_path"] == "/tmp/clarif.md"
