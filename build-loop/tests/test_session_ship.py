"""Tests for ship session persistence, resume routing, and format display."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest


class TestSaveSessionShipFields:
    """Tests for save_session() ship-specific fields (4.1.1)."""

    def test_save_session_persists_ship_fields(self, tmp_path):
        """Happy: save_session with ship=True persists ship and ship_context to JSON."""
        from build_loop.cli import save_session

        session_file = tmp_path / ".spectre" / "build-session.json"

        ship_context = {
            "parent_branch": "main",
            "working_set_scope": "main..HEAD",
            "clean_summary": "",
            "test_summary": "",
        }

        with patch("build_loop.cli.get_session_path", return_value=session_file):
            save_session(
                tasks_file="",
                context_files=["scope.md"],
                max_iterations=15,
                agent="claude",
                ship=True,
                ship_context=ship_context,
            )

        session = json.loads(session_file.read_text())
        assert session["ship"] is True
        assert session["ship_context"] == ship_context

    def test_save_session_without_ship_defaults_to_false(self, tmp_path):
        """Failure: save_session without ship kwarg defaults ship to False and ship_context to None."""
        from build_loop.cli import save_session

        session_file = tmp_path / ".spectre" / "build-session.json"

        with patch("build_loop.cli.get_session_path", return_value=session_file):
            save_session(
                tasks_file="tasks.md",
                context_files=["scope.md"],
                max_iterations=10,
            )

        session = json.loads(session_file.read_text())
        assert session["ship"] is False
        assert session["ship_context"] is None


class TestLoadSessionShipFields:
    """Tests for load_session() round-tripping ship state."""

    def test_load_session_round_trips_ship_fields(self, tmp_path):
        """Happy: load_session returns ship fields saved by save_session."""
        from build_loop.cli import load_session, save_session

        session_file = tmp_path / ".spectre" / "build-session.json"

        ship_context = {
            "parent_branch": "develop",
            "working_set_scope": "develop..HEAD",
        }

        with patch("build_loop.cli.get_session_path", return_value=session_file):
            save_session(
                tasks_file="",
                context_files=["scope.md"],
                max_iterations=15,
                agent="claude",
                ship=True,
                ship_context=ship_context,
            )

            loaded = load_session()

        assert loaded is not None
        assert loaded["ship"] is True
        assert loaded["ship_context"] == ship_context

    def test_load_session_old_format_missing_ship_fields(self, tmp_path):
        """Failure: load_session with old-format JSON (no ship fields) is safe with .get() defaults."""
        from build_loop.cli import load_session

        session_file = tmp_path / ".spectre" / "build-session.json"
        session_file.parent.mkdir(parents=True, exist_ok=True)

        old_session = {
            "tasks_file": "tasks.md",
            "context_files": ["scope.md"],
            "max_iterations": 10,
            "agent": "claude",
            "validate": True,
            "started_at": "2026-02-17T00:00:00+00:00",
            "cwd": "/tmp",
        }
        session_file.write_text(json.dumps(old_session))

        with patch("build_loop.cli.get_session_path", return_value=session_file):
            loaded = load_session()

        assert loaded is not None
        assert loaded.get("ship") is not True
        assert loaded.get("ship_context") is None


class TestRunResumeShipRouting:
    """Tests for run_resume() ship session detection and routing (4.1.2)."""

    def test_resume_routes_ship_session_to_run_ship_pipeline(self):
        """Happy: run_resume detects ship=True and calls run_ship_pipeline with resume_context."""
        from build_loop.cli import run_resume

        ship_context = {
            "parent_branch": "main",
            "working_set_scope": "main..HEAD",
        }

        session = {
            "tasks_file": "",
            "context_files": ["scope.md"],
            "max_iterations": 15,
            "agent": "claude",
            "ship": True,
            "ship_context": ship_context,
            "started_at": "2026-02-18T00:00:00+00:00",
        }

        args = MagicMock()
        args.yes = True
        args.notify = False
        args.no_notify = False

        with (
            patch("build_loop.cli.load_session", return_value=session),
            patch("build_loop.cli.save_session") as mock_save,
            patch("build_loop.cli.run_ship_pipeline", return_value=(0, 5), create=True) as mock_run,
            patch("build_loop.cli.format_duration", return_value="1m 30s"),
        ):
            with pytest.raises(SystemExit) as exc_info:
                run_resume(args)

            assert exc_info.value.code == 0

            mock_run.assert_called_once_with(
                context_files=["scope.md"],
                max_iterations=15,
                agent="claude",
                resume_context=ship_context,
            )

    def test_resume_ship_session_calls_notify_ship_complete(self):
        """Failure: run_resume for ship session calls notify_ship_complete (not notify_build_complete)."""
        from build_loop.cli import run_resume

        session = {
            "tasks_file": "",
            "context_files": [],
            "max_iterations": 10,
            "agent": "claude",
            "ship": True,
            "ship_context": {"parent_branch": "main"},
            "started_at": "2026-02-18T00:00:00+00:00",
        }

        args = MagicMock()
        args.yes = True
        args.notify = True
        args.no_notify = False

        with (
            patch("build_loop.cli.load_session", return_value=session),
            patch("build_loop.cli.save_session"),
            patch("build_loop.cli.run_ship_pipeline", return_value=(0, 3), create=True),
            patch("build_loop.cli.format_duration", return_value="45s"),
            patch("build_loop.cli.notify_ship_complete", create=True) as mock_notify,
        ):
            with pytest.raises(SystemExit):
                run_resume(args)

            mock_notify.assert_called_once()
            call_kwargs = mock_notify.call_args
            assert call_kwargs.kwargs.get("success") is True or call_kwargs[1].get("success") is True


class TestFormatSessionSummaryShip:
    """Tests for format_session_summary() with ship sessions (4.1.3)."""

    def test_format_ship_session_shows_mode_ship(self):
        """Happy: format_session_summary shows 'Mode: Ship' for ship sessions."""
        from build_loop.cli import format_session_summary

        session = {
            "tasks_file": "",
            "context_files": ["scope.md"],
            "max_iterations": 15,
            "agent": "claude",
            "ship": True,
            "ship_context": {"parent_branch": "main"},
            "started_at": "2026-02-18T10:00:00+00:00",
        }

        summary = format_session_summary(session)

        assert "Ship" in summary
        assert "main" in summary

    def test_format_non_ship_session_omits_ship_fields(self):
        """Failure: format_session_summary for non-ship session does not show ship info."""
        from build_loop.cli import format_session_summary

        session = {
            "tasks_file": "tasks.md",
            "context_files": ["scope.md"],
            "max_iterations": 10,
            "agent": "claude",
            "validate": True,
            "started_at": "2026-02-18T10:00:00+00:00",
        }

        summary = format_session_summary(session)

        assert "Ship" not in summary
        assert "Parent" not in summary
