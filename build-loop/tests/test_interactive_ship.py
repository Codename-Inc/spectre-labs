"""Tests for ship option in interactive mode (prompt_for_mode + main() flow)."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestPromptForModeShip:
    """Tests for 'ship' option in prompt_for_mode()."""

    def test_prompt_for_mode_returns_ship_when_user_types_ship(self):
        """Happy: prompt_for_mode returns 'ship' when user enters 'ship'."""
        from build_loop.cli import prompt_for_mode

        with patch("builtins.input", return_value="ship"):
            result = prompt_for_mode()
        assert result == "ship"

    def test_prompt_for_mode_defaults_to_build_on_invalid_input(self):
        """Failure: prompt_for_mode returns 'build' on unrecognized input."""
        from build_loop.cli import prompt_for_mode

        with patch("builtins.input", return_value="invalid"):
            result = prompt_for_mode()
        assert result == "build"

    def test_prompt_for_mode_shows_ship_in_prompt_text(self):
        """Happy: prompt_for_mode includes 'ship' in the displayed prompt."""
        from build_loop.cli import prompt_for_mode

        with patch("builtins.input", return_value="build") as mock_input, \
             patch("builtins.print") as mock_print:
            prompt_for_mode()

        # The print call should mention ship as an option
        printed_text = mock_print.call_args[0][0]
        assert "ship" in printed_text


class TestInteractiveShipFlow:
    """Tests for interactive ship flow in main()."""

    def test_interactive_ship_calls_run_ship_pipeline(self):
        """Happy: interactive ship mode prompts, confirms branch, calls run_ship_pipeline."""
        # Simulate: no flags → prompt_for_mode returns "ship" → context prompt → agent → max_iter
        with patch("sys.argv", ["spectre-build"]), \
             patch("build_loop.cli.prompt_for_mode", return_value="ship"), \
             patch("build_loop.cli.prompt_for_context_files", return_value=["scope.md"]), \
             patch("build_loop.cli.prompt_for_max_iterations", return_value=10), \
             patch("build_loop.cli.prompt_for_agent", return_value="claude"), \
             patch("build_loop.cli._detect_parent_branch", return_value="main"), \
             patch("builtins.input", return_value="y"), \
             patch("build_loop.cli.run_ship_pipeline", return_value=(0, 3)) as mock_run, \
             patch("build_loop.cli.notify_ship_complete"), \
             patch("build_loop.cli.save_session"):

            from build_loop.cli import main
            with pytest.raises(SystemExit) as exc_info:
                main()

            assert exc_info.value.code == 0
            mock_run.assert_called_once()
            call_kwargs = mock_run.call_args[1]
            assert call_kwargs["agent"] == "claude"

    def test_interactive_ship_no_context_files_still_works(self):
        """Failure: interactive ship mode works when user provides no context files."""
        with patch("sys.argv", ["spectre-build"]), \
             patch("build_loop.cli.prompt_for_mode", return_value="ship"), \
             patch("build_loop.cli.prompt_for_context_files", return_value=[]), \
             patch("build_loop.cli.prompt_for_max_iterations", return_value=10), \
             patch("build_loop.cli.prompt_for_agent", return_value="claude"), \
             patch("build_loop.cli._detect_parent_branch", return_value="main"), \
             patch("builtins.input", return_value="y"), \
             patch("build_loop.cli.run_ship_pipeline", return_value=(0, 3)) as mock_run, \
             patch("build_loop.cli.notify_ship_complete"), \
             patch("build_loop.cli.save_session"):

            from build_loop.cli import main
            with pytest.raises(SystemExit):
                main()

            mock_run.assert_called_once()
            call_kwargs = mock_run.call_args[1]
            assert call_kwargs["context_files"] == []

    def test_interactive_ship_shows_branch_for_confirmation(self):
        """Happy: interactive ship shows detected parent branch before proceeding."""
        with patch("sys.argv", ["spectre-build"]), \
             patch("build_loop.cli.prompt_for_mode", return_value="ship"), \
             patch("build_loop.cli.prompt_for_context_files", return_value=[]), \
             patch("build_loop.cli.prompt_for_max_iterations", return_value=10), \
             patch("build_loop.cli.prompt_for_agent", return_value="claude"), \
             patch("build_loop.cli._detect_parent_branch", return_value="main"), \
             patch("builtins.input", return_value="y") as mock_input, \
             patch("builtins.print") as mock_print, \
             patch("build_loop.cli.run_ship_pipeline", return_value=(0, 3)), \
             patch("build_loop.cli.notify_ship_complete"), \
             patch("build_loop.cli.save_session"):

            from build_loop.cli import main
            with pytest.raises(SystemExit):
                main()

            # Check that the parent branch was displayed for confirmation
            all_printed = " ".join(
                str(call) for call in mock_print.call_args_list
            )
            assert "main" in all_printed

    def test_interactive_ship_aborts_when_user_declines_branch(self):
        """Failure: user declining branch confirmation aborts ship."""
        with patch("sys.argv", ["spectre-build"]), \
             patch("build_loop.cli.prompt_for_mode", return_value="ship"), \
             patch("build_loop.cli.prompt_for_context_files", return_value=[]), \
             patch("build_loop.cli.prompt_for_max_iterations", return_value=10), \
             patch("build_loop.cli.prompt_for_agent", return_value="claude"), \
             patch("build_loop.cli._detect_parent_branch", return_value="main"), \
             patch("builtins.input", return_value="n"), \
             patch("build_loop.cli.run_ship_pipeline", return_value=(0, 3)) as mock_run, \
             patch("build_loop.cli.notify_ship_complete"), \
             patch("build_loop.cli.save_session"):

            from build_loop.cli import main
            with pytest.raises(SystemExit) as exc_info:
                main()

            assert exc_info.value.code == 0
            mock_run.assert_not_called()

    def test_interactive_ship_saves_session_with_ship_flag(self):
        """Happy: interactive ship mode saves session with ship=True."""
        with patch("sys.argv", ["spectre-build"]), \
             patch("build_loop.cli.prompt_for_mode", return_value="ship"), \
             patch("build_loop.cli.prompt_for_context_files", return_value=[]), \
             patch("build_loop.cli.prompt_for_max_iterations", return_value=10), \
             patch("build_loop.cli.prompt_for_agent", return_value="claude"), \
             patch("build_loop.cli._detect_parent_branch", return_value="main"), \
             patch("builtins.input", return_value="y"), \
             patch("build_loop.cli.run_ship_pipeline", return_value=(0, 3)), \
             patch("build_loop.cli.notify_ship_complete"), \
             patch("build_loop.cli.save_session") as mock_save:

            from build_loop.cli import main
            with pytest.raises(SystemExit):
                main()

            mock_save.assert_called_once()
            call_kwargs = mock_save.call_args[1]
            assert call_kwargs.get("ship") is True

    def test_interactive_ship_branch_detection_failure_exits(self):
        """Failure: branch detection failure in interactive mode exits with error."""
        with patch("sys.argv", ["spectre-build"]), \
             patch("build_loop.cli.prompt_for_mode", return_value="ship"), \
             patch("build_loop.cli.prompt_for_context_files", return_value=[]), \
             patch("build_loop.cli.prompt_for_max_iterations", return_value=10), \
             patch("build_loop.cli.prompt_for_agent", return_value="claude"), \
             patch("build_loop.cli._detect_parent_branch", return_value=None), \
             patch("build_loop.cli.run_ship_pipeline") as mock_run, \
             patch("build_loop.cli.save_session"):

            from build_loop.cli import main
            with pytest.raises(SystemExit) as exc_info:
                main()

            assert exc_info.value.code == 1
            mock_run.assert_not_called()
