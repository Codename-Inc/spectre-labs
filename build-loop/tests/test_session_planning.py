"""Tests for planning session persistence (save/load/format)."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest


class TestSaveSessionPlanningFields:
    """Tests for save_session() planning-specific fields."""

    def test_save_session_persists_all_planning_fields(self, tmp_path):
        """Happy: save_session with plan=True persists all planning state to JSON."""
        from build_loop.cli import save_session

        session_file = tmp_path / ".spectre" / "build-session.json"

        with patch("build_loop.cli.get_session_path", return_value=session_file):
            save_session(
                tasks_file="",
                context_files=["scope.md", "design.md"],
                max_iterations=10,
                agent="claude",
                plan=True,
                plan_output_dir="/tmp/docs/tasks/main",
                plan_context={"depth": "standard", "tier": "STANDARD"},
                plan_clarifications_path="/tmp/clarifications.md",
            )

        session = json.loads(session_file.read_text())
        assert session["plan"] is True
        assert session["plan_output_dir"] == "/tmp/docs/tasks/main"
        assert session["plan_context"] == {"depth": "standard", "tier": "STANDARD"}
        assert session["plan_clarifications_path"] == "/tmp/clarifications.md"

    def test_save_session_without_plan_defaults_to_false(self, tmp_path):
        """Failure: save_session without plan kwarg defaults plan to False."""
        from build_loop.cli import save_session

        session_file = tmp_path / ".spectre" / "build-session.json"

        with patch("build_loop.cli.get_session_path", return_value=session_file):
            save_session(
                tasks_file="tasks.md",
                context_files=["scope.md"],
                max_iterations=10,
            )

        session = json.loads(session_file.read_text())
        assert session["plan"] is False
        assert session["plan_output_dir"] is None
        assert session["plan_context"] is None
        assert session["plan_clarifications_path"] is None


class TestLoadSessionPlanningFields:
    """Tests for load_session() round-tripping planning state."""

    def test_load_session_round_trips_planning_fields(self, tmp_path):
        """Happy: load_session returns planning fields saved by save_session."""
        from build_loop.cli import load_session, save_session

        session_file = tmp_path / ".spectre" / "build-session.json"

        plan_context = {
            "context_files": "- `scope.md`",
            "output_dir": "/tmp/output",
            "depth": "comprehensive",
            "tier": "COMPREHENSIVE",
        }

        with patch("build_loop.cli.get_session_path", return_value=session_file):
            save_session(
                tasks_file="",
                context_files=["scope.md"],
                max_iterations=10,
                agent="claude",
                plan=True,
                plan_output_dir="/tmp/output",
                plan_context=plan_context,
                plan_clarifications_path="/tmp/clarif.md",
            )

            loaded = load_session()

        assert loaded is not None
        assert loaded["plan"] is True
        assert loaded["plan_output_dir"] == "/tmp/output"
        assert loaded["plan_context"] == plan_context
        assert loaded["plan_clarifications_path"] == "/tmp/clarif.md"

    def test_load_session_old_format_missing_planning_fields(self, tmp_path):
        """Failure: load_session with old-format JSON (no planning fields) returns session without planning keys."""
        from build_loop.cli import load_session

        session_file = tmp_path / ".spectre" / "build-session.json"
        session_file.parent.mkdir(parents=True, exist_ok=True)

        # Write old-format session without planning fields
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
        # Old sessions should not have plan=True
        assert loaded.get("plan") is not True
        # Should be safe to use .get() with defaults
        assert loaded.get("plan_output_dir") is None
        assert loaded.get("plan_context") is None
        assert loaded.get("plan_clarifications_path") is None


class TestFormatSessionSummaryPlanning:
    """Tests for format_session_summary() with planning sessions."""

    def test_format_planning_session_shows_mode_and_clarifications(self):
        """Happy: format_session_summary shows planning mode, output dir, and clarifications path."""
        from build_loop.cli import format_session_summary

        session = {
            "tasks_file": "",
            "context_files": ["scope.md", "design.md"],
            "max_iterations": 10,
            "agent": "claude",
            "plan": True,
            "plan_output_dir": "/tmp/docs/tasks/main",
            "plan_clarifications_path": "/tmp/docs/tasks/main/clarifications/scope_clarifications.md",
            "started_at": "2026-02-17T10:00:00+00:00",
        }

        summary = format_session_summary(session)

        assert "Planning" in summary
        assert "/tmp/docs/tasks/main" in summary
        assert "scope_clarifications.md" in summary

    def test_format_non_planning_session_omits_planning_fields(self):
        """Failure: format_session_summary for non-planning session does not show planning info."""
        from build_loop.cli import format_session_summary

        session = {
            "tasks_file": "tasks.md",
            "context_files": ["scope.md"],
            "max_iterations": 10,
            "agent": "claude",
            "validate": True,
            "started_at": "2026-02-17T10:00:00+00:00",
        }

        summary = format_session_summary(session)

        assert "Planning" not in summary
        assert "Output" not in summary
        assert "Clarif" not in summary
