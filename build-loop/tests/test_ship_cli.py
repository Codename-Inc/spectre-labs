"""Tests for --ship flag CLI integration (parse_args, main routing, notification)."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestParseShipFlag:
    """Tests for --ship flag in parse_args."""

    def test_ship_flag_sets_ship_true(self):
        """Happy: --ship flag sets args.ship to True."""
        with patch("sys.argv", ["spectre-build", "--ship"]):
            from build_loop.cli import parse_args
            args = parse_args()
            assert args.ship is True

    def test_no_ship_flag_defaults_to_false(self):
        """Failure: Without --ship, args.ship is False."""
        with patch("sys.argv", ["spectre-build", "--tasks", "tasks.md"]):
            from build_loop.cli import parse_args
            args = parse_args()
            assert args.ship is False


class TestMainShipRouting:
    """Tests for --ship routing in main()."""

    def test_main_routes_ship_to_run_ship_pipeline(self):
        """Happy: main() with --ship routes to run_ship_pipeline."""
        with patch("sys.argv", ["spectre-build", "--ship"]), \
             patch("build_loop.cli.run_ship_pipeline", return_value=(0, 3)) as mock_run, \
             patch("build_loop.cli.notify_ship_complete"), \
             patch("build_loop.cli.save_session"):

            from build_loop.cli import main
            with pytest.raises(SystemExit) as exc_info:
                main()

            assert exc_info.value.code == 0
            mock_run.assert_called_once()

    def test_main_ship_calls_notify_ship_complete(self):
        """Failure: main() with --ship calls notify_ship_complete with correct args."""
        with patch("sys.argv", ["spectre-build", "--ship"]), \
             patch("build_loop.cli.run_ship_pipeline", return_value=(0, 3)) as mock_run, \
             patch("build_loop.cli.notify_ship_complete") as mock_notify, \
             patch("build_loop.cli.save_session"), \
             patch("time.time", side_effect=[100.0, 160.0]):

            from build_loop.cli import main
            with pytest.raises(SystemExit):
                main()

            mock_notify.assert_called_once()
            call_kwargs = mock_notify.call_args[1]
            assert call_kwargs["stages_completed"] == 3
            assert call_kwargs["success"] is True

    def test_main_ship_with_context_passes_context_files(self):
        """Happy: --ship with --context passes context files to run_ship_pipeline."""
        with patch("sys.argv", ["spectre-build", "--ship", "--context", "scope.md", "plan.md"]), \
             patch("build_loop.cli.run_ship_pipeline", return_value=(0, 3)) as mock_run, \
             patch("build_loop.cli.notify_ship_complete"), \
             patch("build_loop.cli.save_session"):

            from build_loop.cli import main
            with pytest.raises(SystemExit):
                main()

            mock_run.assert_called_once()
            call_kwargs = mock_run.call_args[1]
            context_files = call_kwargs.get("context_files", [])
            # Should contain resolved paths for scope.md and plan.md
            assert len(context_files) == 2

    def test_main_ship_without_context_still_works(self):
        """Happy: --ship without --context is valid (context optional for ship)."""
        with patch("sys.argv", ["spectre-build", "--ship"]), \
             patch("build_loop.cli.run_ship_pipeline", return_value=(0, 3)) as mock_run, \
             patch("build_loop.cli.notify_ship_complete"), \
             patch("build_loop.cli.save_session"):

            from build_loop.cli import main
            with pytest.raises(SystemExit):
                main()

            mock_run.assert_called_once()
            call_kwargs = mock_run.call_args[1]
            context_files = call_kwargs.get("context_files", [])
            assert context_files == []

    def test_main_ship_saves_session_with_ship_flag(self):
        """Failure: --ship saves session with ship=True."""
        with patch("sys.argv", ["spectre-build", "--ship"]), \
             patch("build_loop.cli.run_ship_pipeline", return_value=(0, 3)), \
             patch("build_loop.cli.notify_ship_complete"), \
             patch("build_loop.cli.save_session") as mock_save:

            from build_loop.cli import main
            with pytest.raises(SystemExit):
                main()

            mock_save.assert_called_once()
            call_kwargs = mock_save.call_args[1]
            assert call_kwargs.get("ship") is True
