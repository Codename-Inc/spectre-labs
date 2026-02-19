"""E2E dry-run test for the full plan clarification round-trip.

Exercises: plan pipeline → CLARIFICATIONS_NEEDED → save session →
user edits file → resume → update_docs reads clarifications → build chains.
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from build_loop.cli import (
    load_session,
    run_plan_pipeline,
    save_session,
)
from build_loop.hooks import plan_before_stage


class TestClarificationRoundTrip:
    """Full round-trip: plan → clarify → resume → build."""

    def _setup_output_dir(self, tmp_path):
        """Create the output directory structure that run_plan_pipeline expects."""
        output_dir = tmp_path / "docs" / "tasks" / "main" / "my_scope"
        output_dir.mkdir(parents=True)
        (output_dir / "specs").mkdir()
        (output_dir / "clarifications").mkdir()
        return str(output_dir)

    def test_full_clarification_round_trip(self, tmp_path):
        """E2E: plan → CLARIFICATIONS_NEEDED → save → edit → resume → update_docs reads answers → build chains.

        This test verifies the entire flow without running Claude:
        1. run_plan_pipeline exits with CLARIFICATIONS_NEEDED and saves session
        2. Session contains clarifications_path in plan_context
        3. On resume, clarifications_path is injected from session
        4. plan_before_stage("update_docs") reads the file and injects answers
        5. auto_build preference survives the round-trip
        """
        output_dir = self._setup_output_dir(tmp_path)
        session_file = tmp_path / ".spectre" / "build-session.json"
        clarif_file = Path(output_dir) / "clarifications" / "scope_clarifications.md"

        # --- Phase 1: Initial plan run hits CLARIFICATIONS_NEEDED ---

        mock_runner = MagicMock()
        mock_runner.check_available.return_value = True

        mock_state = MagicMock()
        mock_state.total_iterations = 6
        mock_state.global_artifacts = {
            "clarifications_path": str(clarif_file),
        }
        mock_state.stage_history = [
            ("research", "RESEARCH_COMPLETE"),
            ("assess", "STANDARD"),
            ("create_plan", "PLAN_COMPLETE"),
            ("create_tasks", "TASKS_COMPLETE"),
            ("plan_review", "REVIEW_COMPLETE"),
            ("req_validate", "CLARIFICATIONS_NEEDED"),
        ]

        mock_executor = MagicMock()
        mock_executor.run.return_value = mock_state

        with patch("build_loop.agent.get_agent", return_value=mock_runner), \
             patch("build_loop.pipeline.loader.create_plan_pipeline"), \
             patch("build_loop.pipeline.executor.PipelineExecutor", return_value=mock_executor), \
             patch("build_loop.pipeline.executor.PipelineStatus") as mock_status, \
             patch("build_loop.cli.get_session_path", return_value=session_file), \
             patch("build_loop.cli.save_stats"), \
             patch("build_loop.cli.load_stats", return_value=None), \
             patch("build_loop.notify.notify"):

            mock_status.COMPLETED = "completed"
            mock_status.STOPPED = "stopped"
            mock_state.status = mock_status.COMPLETED

            exit_code, iterations, manifest = run_plan_pipeline(
                context_files=["scope.md"],
                max_iterations=10,
                output_dir=output_dir,
                scope_name="my_scope",
                auto_build=True,
            )

        assert exit_code == 0
        assert manifest == ""  # No manifest yet, just clarifications

        # --- Verify session was saved correctly ---
        session = json.loads(session_file.read_text())
        assert session["plan"] is True
        assert session["plan_clarifications_path"] == str(clarif_file)
        assert session["plan_auto_build"] is True
        # Fix A: plan_context contains clarifications_path
        assert session["plan_context"]["clarifications_path"] == str(clarif_file)

        # --- Phase 2: User edits clarifications file ---
        clarif_content = """## Scope Clarifications

### Gap 1: Missing error handling spec
- **Requirement**: R3 - Error states
- **Gap Type**: Missing task
- **Context**: No tasks cover error state rendering

<response>
Add a new task in Phase 2 for error state rendering. Show a retry button
and a "something went wrong" message when API calls fail.
</response>
"""
        clarif_file.write_text(clarif_content)

        # --- Phase 3: Resume → plan_before_stage reads clarifications ---

        # Simulate what run_resume does: load session and inject clarifications
        with patch("build_loop.cli.get_session_path", return_value=session_file):
            loaded = load_session()

        resume_ctx = loaded["plan_context"]
        # Fix B: defensive injection
        if loaded.get("plan_clarifications_path"):
            resume_ctx["clarifications_path"] = loaded["plan_clarifications_path"]

        assert resume_ctx["clarifications_path"] == str(clarif_file)

        # The before_stage hook should read the file and inject answers
        plan_before_stage("update_docs", resume_ctx)

        assert "clarification_answers" in resume_ctx
        assert "Missing error handling spec" in resume_ctx["clarification_answers"]
        assert "<response>" in resume_ctx["clarification_answers"]
        assert "retry button" in resume_ctx["clarification_answers"]

        # --- Phase 4: Verify auto_build survives ---
        assert loaded.get("plan_auto_build") is True

    def test_round_trip_without_clarifications(self, tmp_path):
        """E2E: plan validates successfully → no clarifications → direct to manifest."""
        output_dir = self._setup_output_dir(tmp_path)
        session_file = tmp_path / ".spectre" / "build-session.json"
        manifest_file = Path(output_dir) / "build.md"
        manifest_file.write_text("---\ntasks: tasks.md\n---\n")

        mock_runner = MagicMock()
        mock_runner.check_available.return_value = True

        mock_state = MagicMock()
        mock_state.total_iterations = 6
        mock_state.global_artifacts = {
            "manifest_path": str(manifest_file),
        }
        mock_state.stage_history = [
            ("req_validate", "PLAN_VALIDATED"),
        ]

        mock_executor = MagicMock()
        mock_executor.run.return_value = mock_state

        with patch("build_loop.agent.get_agent", return_value=mock_runner), \
             patch("build_loop.pipeline.loader.create_plan_pipeline"), \
             patch("build_loop.pipeline.executor.PipelineExecutor", return_value=mock_executor), \
             patch("build_loop.pipeline.executor.PipelineStatus") as mock_status, \
             patch("build_loop.cli.save_stats"), \
             patch("build_loop.cli.load_stats", return_value=None), \
             patch("build_loop.cli.clear_stats"):

            mock_status.COMPLETED = "completed"
            mock_status.STOPPED = "stopped"
            mock_state.status = mock_status.COMPLETED

            exit_code, iterations, manifest = run_plan_pipeline(
                context_files=["scope.md"],
                max_iterations=10,
                output_dir=output_dir,
            )

        assert exit_code == 0
        assert manifest == str(manifest_file)

    def test_resume_auto_build_chains_full_flow(self, tmp_path):
        """E2E: resume with auto_build=True chains to run_manifest after plan completes."""
        from build_loop.cli import run_resume

        session_file = tmp_path / ".spectre" / "build-session.json"

        session = {
            "tasks_file": "",
            "context_files": ["scope.md"],
            "max_iterations": 10,
            "agent": "claude",
            "validate": False,
            "manifest_path": None,
            "pipeline_path": None,
            "plan": True,
            "plan_output_dir": "/tmp/output",
            "plan_context": {
                "context_files": "- `scope.md`",
                "output_dir": "/tmp/output",
                "clarifications_path": "/tmp/output/clarifications/scope.md",
                "clarification_answers": "",
            },
            "plan_clarifications_path": "/tmp/output/clarifications/scope.md",
            "plan_scope_name": "my_scope",
            "plan_auto_build": True,
            "started_at": "2026-02-19T06:00:00+00:00",
            "cwd": "/tmp",
        }

        args = MagicMock()
        args.yes = True
        args.notify = False
        args.no_notify = True

        with patch("build_loop.cli.load_session", return_value=session), \
             patch("build_loop.cli.get_session_path", return_value=session_file), \
             patch("build_loop.cli.run_plan_pipeline", return_value=(0, 1, "/tmp/output/build.md")) as mock_plan, \
             patch("build_loop.cli.run_manifest") as mock_manifest, \
             patch("build_loop.cli.save_session"), \
             patch("build_loop.cli.notify_plan_complete"):

            mock_manifest.side_effect = SystemExit(0)

            with pytest.raises(SystemExit):
                run_resume(args)

            # Verify plan pipeline was called with auto_build
            plan_kwargs = mock_plan.call_args[1]
            assert plan_kwargs["auto_build"] is True

            # Verify chaining to run_manifest happened
            mock_manifest.assert_called_once_with("/tmp/output/build.md", args)

            # Verify clarifications_path was injected into resume context
            assert plan_kwargs["resume_context"]["clarifications_path"] == \
                "/tmp/output/clarifications/scope.md"
