"""Tests for plan clarification resume fixes (A, B, C).

Fix A: Context sync — clarifications_path flows from global_artifacts to saved plan_context
Fix B: Defensive injection — plan_clarifications_path injected into resume_context on resume
Fix C: Auto-build persistence — plan_auto_build saved to session, chains on resume
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest


# ===================================================================
# Fix A: Context sync on CLARIFICATIONS_NEEDED save
# ===================================================================

class TestFixA_ContextSyncOnSave:
    """Verify saved plan_context includes clarifications_path from global_artifacts."""

    def test_saved_plan_context_contains_clarifications_path(self):
        """Happy: when CLARIFICATIONS_NEEDED, saved plan_context has clarifications_path from artifacts."""
        from build_loop.cli import run_plan_pipeline

        mock_runner = MagicMock()
        mock_runner.check_available.return_value = True

        mock_state = MagicMock()
        mock_state.total_iterations = 6
        mock_state.global_artifacts = {
            "clarifications_path": "/tmp/output/clarifications/scope_clarifications.md",
        }
        mock_state.stage_history = [
            ("research", "RESEARCH_COMPLETE"),
            ("req_validate", "CLARIFICATIONS_NEEDED"),
        ]

        mock_executor = MagicMock()
        mock_executor.run.return_value = mock_state

        with patch("build_loop.agent.get_agent", return_value=mock_runner), \
             patch("build_loop.pipeline.loader.create_plan_pipeline"), \
             patch("build_loop.pipeline.executor.PipelineExecutor", return_value=mock_executor), \
             patch("build_loop.pipeline.executor.PipelineStatus") as mock_status, \
             patch("build_loop.cli.save_session") as mock_save, \
             patch("build_loop.cli.save_stats"), \
             patch("build_loop.cli.load_stats", return_value=None), \
             patch("build_loop.notify.notify"):

            mock_status.COMPLETED = "completed"
            mock_status.STOPPED = "stopped"
            mock_state.status = mock_status.COMPLETED

            exit_code, _, _ = run_plan_pipeline(
                context_files=["scope.md"],
                max_iterations=10,
            )

            assert exit_code == 0
            mock_save.assert_called_once()
            saved_context = mock_save.call_args[1]["plan_context"]
            assert saved_context["clarifications_path"] == \
                "/tmp/output/clarifications/scope_clarifications.md"

    def test_saved_plan_context_empty_when_no_artifacts_path(self):
        """Failure: when artifacts lack clarifications_path, saved context has empty string."""
        from build_loop.cli import run_plan_pipeline

        mock_runner = MagicMock()
        mock_runner.check_available.return_value = True

        mock_state = MagicMock()
        mock_state.total_iterations = 6
        mock_state.global_artifacts = {}  # No clarifications_path
        mock_state.stage_history = [
            ("req_validate", "CLARIFICATIONS_NEEDED"),
        ]

        mock_executor = MagicMock()
        mock_executor.run.return_value = mock_state

        with patch("build_loop.agent.get_agent", return_value=mock_runner), \
             patch("build_loop.pipeline.loader.create_plan_pipeline"), \
             patch("build_loop.pipeline.executor.PipelineExecutor", return_value=mock_executor), \
             patch("build_loop.pipeline.executor.PipelineStatus") as mock_status, \
             patch("build_loop.cli.save_session") as mock_save, \
             patch("build_loop.cli.save_stats"), \
             patch("build_loop.cli.load_stats", return_value=None), \
             patch("build_loop.notify.notify"):

            mock_status.COMPLETED = "completed"
            mock_status.STOPPED = "stopped"
            mock_state.status = mock_status.COMPLETED

            run_plan_pipeline(context_files=["scope.md"], max_iterations=10)

            saved_context = mock_save.call_args[1]["plan_context"]
            # clarifications_path should still be the empty string default
            assert saved_context["clarifications_path"] == ""


# ===================================================================
# Fix B: Defensive injection on resume
# ===================================================================

class TestFixB_ResumeInjectsClarificationsPath:
    """Verify run_resume injects plan_clarifications_path into resume_context."""

    def _make_plan_session(self, **overrides):
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
                "clarifications_path": "",  # Bug: empty from original save
                "clarification_answers": "",
                "depth": "standard",
                "tier": "STANDARD",
            },
            "plan_clarifications_path": "/tmp/output/clarifications/scope_clarifications.md",
            "plan_scope_name": "my_scope",
            "started_at": "2026-02-19T06:00:00+00:00",
            "cwd": "/tmp",
        }
        session.update(overrides)
        return session

    def test_resume_injects_clarifications_path_from_session(self):
        """Happy: run_resume patches resume_context with plan_clarifications_path before calling pipeline."""
        from build_loop.cli import run_resume

        session = self._make_plan_session()
        args = MagicMock()
        args.yes = True
        args.notify = False
        args.no_notify = True

        with patch("build_loop.cli.load_session", return_value=session), \
             patch("build_loop.cli.run_plan_pipeline", return_value=(0, 1, "/tmp/build.md")) as mock_run, \
             patch("build_loop.cli.save_session"), \
             patch("build_loop.cli.notify_plan_complete"):

            with pytest.raises(SystemExit):
                run_resume(args)

            call_kwargs = mock_run.call_args[1]
            resume_ctx = call_kwargs["resume_context"]
            assert resume_ctx["clarifications_path"] == \
                "/tmp/output/clarifications/scope_clarifications.md"

    def test_resume_no_clarifications_path_leaves_context_unchanged(self):
        """Failure: when no plan_clarifications_path in session, resume_context is unchanged."""
        from build_loop.cli import run_resume

        session = self._make_plan_session(plan_clarifications_path=None)
        args = MagicMock()
        args.yes = True
        args.notify = False
        args.no_notify = True

        with patch("build_loop.cli.load_session", return_value=session), \
             patch("build_loop.cli.run_plan_pipeline", return_value=(0, 1, "")) as mock_run, \
             patch("build_loop.cli.save_session"), \
             patch("build_loop.cli.notify_plan_complete"):

            with pytest.raises(SystemExit):
                run_resume(args)

            call_kwargs = mock_run.call_args[1]
            resume_ctx = call_kwargs["resume_context"]
            # Should remain as the original empty string from plan_context
            assert resume_ctx["clarifications_path"] == ""


# ===================================================================
# Fix C: Auto-build persistence and chaining on resume
# ===================================================================

class TestFixC_AutoBuildPersistence:
    """Verify plan_auto_build is saved to session and chains on resume."""

    def test_save_session_persists_plan_auto_build(self, tmp_path):
        """Happy: save_session stores plan_auto_build field in session JSON."""
        from build_loop.cli import save_session

        session_file = tmp_path / ".spectre" / "build-session.json"

        with patch("build_loop.cli.get_session_path", return_value=session_file):
            save_session(
                tasks_file="",
                context_files=["scope.md"],
                max_iterations=10,
                plan=True,
                plan_auto_build=True,
            )

        session = json.loads(session_file.read_text())
        assert session["plan_auto_build"] is True

    def test_save_session_defaults_plan_auto_build_to_false(self, tmp_path):
        """Failure: save_session without plan_auto_build defaults to False."""
        from build_loop.cli import save_session

        session_file = tmp_path / ".spectre" / "build-session.json"

        with patch("build_loop.cli.get_session_path", return_value=session_file):
            save_session(
                tasks_file="",
                context_files=["scope.md"],
                max_iterations=10,
                plan=True,
            )

        session = json.loads(session_file.read_text())
        assert session.get("plan_auto_build") is False


class TestFixC_AutoBuildChainingOnResume:
    """Verify run_resume chains to run_manifest when plan_auto_build is True."""

    def _make_plan_session(self, auto_build=True, **overrides):
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
                "clarifications_path": "",
                "clarification_answers": "",
            },
            "plan_clarifications_path": None,
            "plan_scope_name": "my_scope",
            "plan_auto_build": auto_build,
            "started_at": "2026-02-19T06:00:00+00:00",
            "cwd": "/tmp",
        }
        session.update(overrides)
        return session

    def test_resume_chains_to_run_manifest_when_auto_build_true(self):
        """Happy: run_resume with plan_auto_build=True chains to run_manifest after plan completes."""
        from build_loop.cli import run_resume

        session = self._make_plan_session(auto_build=True)
        args = MagicMock()
        args.yes = True
        args.notify = False
        args.no_notify = True

        with patch("build_loop.cli.load_session", return_value=session), \
             patch("build_loop.cli.run_plan_pipeline", return_value=(0, 1, "/tmp/output/build.md")) as mock_plan, \
             patch("build_loop.cli.run_manifest") as mock_manifest, \
             patch("build_loop.cli.save_session"), \
             patch("build_loop.cli.notify_plan_complete"):

            # run_manifest calls sys.exit internally, so we catch that
            mock_manifest.side_effect = SystemExit(0)

            with pytest.raises(SystemExit) as exc_info:
                run_resume(args)

            mock_manifest.assert_called_once_with("/tmp/output/build.md", args)

    def test_resume_does_not_chain_when_auto_build_false(self):
        """Failure: run_resume with plan_auto_build=False does not chain to run_manifest."""
        from build_loop.cli import run_resume

        session = self._make_plan_session(auto_build=False)
        args = MagicMock()
        args.yes = True
        args.notify = False
        args.no_notify = True

        with patch("build_loop.cli.load_session", return_value=session), \
             patch("build_loop.cli.run_plan_pipeline", return_value=(0, 1, "/tmp/output/build.md")), \
             patch("build_loop.cli.run_manifest") as mock_manifest, \
             patch("build_loop.cli.save_session"), \
             patch("build_loop.cli.notify_plan_complete"):

            with pytest.raises(SystemExit):
                run_resume(args)

            mock_manifest.assert_not_called()

    def test_resume_does_not_chain_when_plan_fails(self):
        """Failure: even with auto_build=True, non-zero exit does not chain."""
        from build_loop.cli import run_resume

        session = self._make_plan_session(auto_build=True)
        args = MagicMock()
        args.yes = True
        args.notify = False
        args.no_notify = True

        with patch("build_loop.cli.load_session", return_value=session), \
             patch("build_loop.cli.run_plan_pipeline", return_value=(1, 1, "")), \
             patch("build_loop.cli.run_manifest") as mock_manifest, \
             patch("build_loop.cli.save_session"), \
             patch("build_loop.cli.notify_plan_complete"):

            with pytest.raises(SystemExit):
                run_resume(args)

            mock_manifest.assert_not_called()

    def test_resume_does_not_chain_when_no_manifest(self):
        """Failure: auto_build=True but empty manifest path — no chaining."""
        from build_loop.cli import run_resume

        session = self._make_plan_session(auto_build=True)
        args = MagicMock()
        args.yes = True
        args.notify = False
        args.no_notify = True

        with patch("build_loop.cli.load_session", return_value=session), \
             patch("build_loop.cli.run_plan_pipeline", return_value=(0, 1, "")), \
             patch("build_loop.cli.run_manifest") as mock_manifest, \
             patch("build_loop.cli.save_session"), \
             patch("build_loop.cli.notify_plan_complete"):

            with pytest.raises(SystemExit):
                run_resume(args)

            mock_manifest.assert_not_called()
