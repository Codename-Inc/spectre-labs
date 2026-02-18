"""Tests for per-stage tool filtering: denied_tools flows from StageConfig through Stage to AgentRunner."""

from unittest.mock import MagicMock, patch, call
import subprocess

import pytest

from build_loop.agent import (
    AgentRunner,
    ClaudeRunner,
    CodexRunner,
    CLAUDE_ALLOWED_TOOLS,
    CLAUDE_DENIED_TOOLS,
)
from build_loop.pipeline.stage import Stage, StageConfig
from build_loop.pipeline.completion import CompletionResult, CompletionStrategy


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _FakeCompletion(CompletionStrategy):
    """Completion strategy that always returns complete."""

    def evaluate(self, output: str, exit_code: int = 0) -> CompletionResult:
        return CompletionResult(is_complete=True, signal="DONE")


def _make_stage(runner, denied_tools=None):
    """Create a Stage with a minimal config."""
    config = StageConfig(
        name="test_stage",
        prompt_template="Hello {name}",
        completion=_FakeCompletion(),
        max_iterations=1,
        denied_tools=denied_tools,
    )
    return Stage(config=config, runner=runner)


# ===========================================================================
# 1.2.1 — AgentRunner.run_iteration() accepts denied_tools
# ===========================================================================


class TestAgentRunnerSignature:
    """Abstract base accepts denied_tools parameter."""

    def test_happy_claude_runner_accepts_denied_tools_kwarg(self):
        """Happy: ClaudeRunner.run_iteration() accepts denied_tools without TypeError."""
        runner = ClaudeRunner()
        # Should not raise TypeError — just mock Popen so it doesn't actually run
        with patch("subprocess.Popen") as mock_popen:
            proc = MagicMock()
            proc.stdin = MagicMock()
            proc.stdout = iter([])
            proc.stderr = MagicMock(read=MagicMock(return_value=""))
            proc.returncode = 0
            proc.wait = MagicMock()
            mock_popen.return_value = proc

            _exit, _out, _err = runner.run_iteration(
                "test prompt", denied_tools=["WebFetch"]
            )
            assert _exit == 0

    def test_happy_codex_runner_accepts_denied_tools_kwarg(self):
        """Happy: CodexRunner.run_iteration() accepts denied_tools without TypeError."""
        runner = CodexRunner()
        with patch("subprocess.Popen") as mock_popen, \
             patch("build_loop.agent.CodexRunner.check_available", return_value=True), \
             patch("build_loop.codex_env.setup_codex_home", return_value="/tmp/codex"):
            proc = MagicMock()
            proc.stdin = MagicMock()
            proc.stdout = iter([])
            proc.stderr = MagicMock(read=MagicMock(return_value=""))
            proc.returncode = 0
            proc.wait = MagicMock()
            mock_popen.return_value = proc

            _exit, _out, _err = runner.run_iteration(
                "test prompt", denied_tools=["SomeTool"]
            )
            assert _exit == 0


# ===========================================================================
# 1.2.2 — ClaudeRunner uses denied_tools when provided, falls back otherwise
# ===========================================================================


class TestClaudeRunnerDeniedTools:
    """ClaudeRunner command construction honors per-stage denied_tools."""

    def _run_with_denied(self, denied_tools):
        """Helper: run ClaudeRunner with given denied_tools, return Popen cmd."""
        runner = ClaudeRunner()
        with patch("subprocess.Popen") as mock_popen:
            proc = MagicMock()
            proc.stdin = MagicMock()
            proc.stdout = iter([])
            proc.stderr = MagicMock(read=MagicMock(return_value=""))
            proc.returncode = 0
            proc.wait = MagicMock()
            mock_popen.return_value = proc

            runner.run_iteration("prompt", denied_tools=denied_tools)

            cmd = mock_popen.call_args[0][0]
            return cmd

    def test_happy_uses_per_stage_denied_tools_when_provided(self):
        """Happy: When denied_tools is a list, --disallowedTools uses that list."""
        custom_deny = ["WebFetch", "WebSearch"]
        cmd = self._run_with_denied(custom_deny)

        # Find --disallowedTools value in cmd
        idx = cmd.index("--disallowedTools")
        denied_str = cmd[idx + 1]
        assert denied_str == "WebFetch,WebSearch"

    def test_failure_falls_back_to_global_when_none(self):
        """Failure: When denied_tools is None, --disallowedTools uses CLAUDE_DENIED_TOOLS."""
        cmd = self._run_with_denied(None)

        idx = cmd.index("--disallowedTools")
        denied_str = cmd[idx + 1]
        assert denied_str == ",".join(CLAUDE_DENIED_TOOLS)


# ===========================================================================
# 1.2.3 — CodexRunner accepts denied_tools (ignores it)
# ===========================================================================


class TestCodexRunnerDeniedTools:
    """CodexRunner accepts denied_tools but doesn't use it (Codex has no equivalent)."""

    def test_happy_codex_ignores_denied_tools_no_crash(self):
        """Happy: CodexRunner doesn't crash when denied_tools is passed."""
        runner = CodexRunner()
        with patch("subprocess.Popen") as mock_popen, \
             patch("build_loop.codex_env.setup_codex_home", return_value="/tmp/codex"):
            proc = MagicMock()
            proc.stdin = MagicMock()
            proc.stdout = iter([])
            proc.stderr = MagicMock(read=MagicMock(return_value=""))
            proc.returncode = 0
            proc.wait = MagicMock()
            mock_popen.return_value = proc

            # Should NOT appear in the command
            _exit, _out, _err = runner.run_iteration(
                "prompt", denied_tools=["Task", "WebFetch"]
            )
            assert _exit == 0

            # Verify no --disallowedTools in codex command
            cmd = mock_popen.call_args[0][0]
            assert "--disallowedTools" not in cmd


# ===========================================================================
# 1.2.4 — Stage.run_iteration() passes config.denied_tools to runner
# ===========================================================================


class TestStageDeniedToolsWiring:
    """Stage passes its config's denied_tools through to the runner."""

    def test_happy_stage_passes_denied_tools_from_config_to_runner(self):
        """Happy: When StageConfig has denied_tools, Stage.run_iteration() passes them to runner."""
        mock_runner = MagicMock()
        mock_runner.run_iteration.return_value = (0, "output [[PROMISE:DONE]]", "")

        custom_deny = ["AskUserQuestion", "EnterPlanMode"]
        stage = _make_stage(mock_runner, denied_tools=custom_deny)

        stage.run_iteration(context={"name": "world"})

        # Verify runner.run_iteration was called with denied_tools
        mock_runner.run_iteration.assert_called_once()
        call_kwargs = mock_runner.run_iteration.call_args[1]
        assert call_kwargs.get("denied_tools") == custom_deny

    def test_failure_stage_passes_none_when_config_has_no_denied_tools(self):
        """Failure: When StageConfig.denied_tools is None, runner gets denied_tools=None explicitly."""
        mock_runner = MagicMock()
        mock_runner.run_iteration.return_value = (0, "output [[PROMISE:DONE]]", "")

        stage = _make_stage(mock_runner, denied_tools=None)

        stage.run_iteration(context={"name": "world"})

        # Verify runner.run_iteration was called with denied_tools=None EXPLICITLY as a kwarg
        mock_runner.run_iteration.assert_called_once()
        call_kwargs = mock_runner.run_iteration.call_args[1]
        assert "denied_tools" in call_kwargs, "denied_tools must be explicitly passed as a keyword argument"
        assert call_kwargs["denied_tools"] is None
