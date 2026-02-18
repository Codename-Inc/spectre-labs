"""
Agent runner abstraction for multi-agent build loop support.

Provides a strategy pattern for executing build iterations with
different coding agents (Claude Code, Codex CLI).
"""

import json
import logging
import os
import shutil
import subprocess
import sys
from abc import ABC, abstractmethod

from .stats import BuildStats
from .stream import process_stream_event

logger = logging.getLogger(__name__)


class AgentRunner(ABC):
    """Base class for agent execution backends."""

    name: str

    @abstractmethod
    def check_available(self) -> bool:
        """Return True if this agent's CLI binary is on PATH."""

    @abstractmethod
    def run_iteration(
        self,
        prompt: str,
        timeout: int | None = None,
        stats: BuildStats | None = None,
    ) -> tuple[int, str, str]:
        """Execute one build iteration.

        Args:
            prompt: The full prompt to send to the agent
            timeout: Optional timeout in seconds
            stats: Optional BuildStats to track usage

        Returns:
            Tuple of (exit_code, full_text_output, error_output)

        Raises:
            FileNotFoundError: If agent CLI is not installed
            subprocess.TimeoutExpired: If timeout is exceeded
        """


# ---------------------------------------------------------------------------
# Claude Code
# ---------------------------------------------------------------------------

# Tools allowed to run without permission prompts
CLAUDE_ALLOWED_TOOLS = [
    "Bash",
    "Read",
    "Write",
    "Edit",
    "Glob",
    "Grep",
    "LS",
    "TodoRead",
    "TodoWrite",
    "Skill",
    "Task",
]

# Tools explicitly denied — block the loop from hanging
CLAUDE_DENIED_TOOLS = [
    "AskUserQuestion",
    "WebFetch",
    "WebSearch",
    "EnterPlanMode",
    "NotebookEdit",
]


class ClaudeRunner(AgentRunner):
    """Claude Code backend using `claude -p` with stream-json output."""

    name = "claude"

    def check_available(self) -> bool:
        return shutil.which("claude") is not None

    def run_iteration(self, prompt, timeout=None, stats=None):
        cmd = [
            "claude", "-p",
            "--allowedTools", ",".join(CLAUDE_ALLOWED_TOOLS),
            "--disallowedTools", ",".join(CLAUDE_DENIED_TOOLS),
            "--output-format", "stream-json",
            "--verbose",
        ]

        process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        process.stdin.write(prompt)
        process.stdin.close()

        text_buffer: list[str] = []

        for line in process.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
                process_stream_event(event, text_buffer, stats)
            except json.JSONDecodeError:
                print(line)
                text_buffer.append(line)

        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
            raise

        error_output = process.stderr.read()
        full_output = "\n".join(text_buffer)

        return process.returncode, full_output, error_output


# ---------------------------------------------------------------------------
# Codex CLI
# ---------------------------------------------------------------------------

def _format_codex_command(command: str) -> str:
    """Format a Codex command_execution for display.

    Strips the shell wrapper (e.g. '/bin/zsh -lc "..."') to show just
    the inner command, truncated for readability.
    """
    # Strip shell wrapper: /bin/zsh -lc '...' or /bin/zsh -lc "..."
    import re
    match = re.match(r'^/bin/\w+\s+-\w+\s+["\'](.+)["\']$', command, re.DOTALL)
    if match:
        command = match.group(1)

    if len(command) > 80:
        command = command[:77] + "..."
    return f"💻 Bash: {command}"


class CodexRunner(AgentRunner):
    """Codex CLI backend using `codex exec` with JSONL output."""

    name = "codex"

    def check_available(self) -> bool:
        return shutil.which("codex") is not None

    def run_iteration(self, prompt, timeout=None, stats=None):
        from .codex_env import setup_codex_home

        # Sync credentials for sandboxed execution
        codex_home = setup_codex_home()
        logger.info("Codex iteration starting, CODEX_HOME=%s", codex_home)

        env = os.environ.copy()
        env["CODEX_HOME"] = str(codex_home)

        cmd = ["codex", "exec", "--sandbox", "workspace-write", "--json"]

        process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
        )

        process.stdin.write(prompt)
        process.stdin.close()

        text_buffer: list[str] = []

        for line in process.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
                self._process_event(event, text_buffer, stats)
            except json.JSONDecodeError:
                print(line)
                text_buffer.append(line)

        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
            raise

        error_output = process.stderr.read()
        full_output = "\n".join(text_buffer)

        return process.returncode, full_output, error_output

    def _process_event(
        self,
        event: dict,
        text_buffer: list[str],
        stats: BuildStats | None,
    ) -> None:
        """Process a single Codex JSONL event.

        Codex event types:
        - item.started  / item.completed with item.type:
            - reasoning: thinking text
            - command_execution: shell commands (command, aggregated_output, exit_code)
            - agent_message: response text
        - turn.completed: contains usage (input_tokens, cached_input_tokens, output_tokens)
        """
        event_type = event.get("type")

        if event_type == "item.started":
            item = event.get("item", {})
            if item.get("type") == "command_execution":
                command = item.get("command", "")
                if command:
                    print(_format_codex_command(command))

        elif event_type == "item.completed":
            item = event.get("item", {})
            item_type = item.get("type")

            if item_type == "agent_message":
                text = item.get("text", "")
                if text.strip():
                    print(f"💬 {text}")
                    text_buffer.append(text)

            elif item_type == "reasoning":
                text = item.get("text", "")
                if text.strip():
                    print(f"🧠 {text}")

            elif item_type == "command_execution":
                # Track as tool call in stats
                if stats:
                    stats.add_tool_call("Bash")
                exit_code = item.get("exit_code")
                if exit_code is not None and exit_code != 0:
                    print(f"   ⚠ exit code: {exit_code}")

        elif event_type == "turn.completed":
            # Extract token usage
            usage = event.get("usage", {})
            if stats and usage:
                stats.add_usage({
                    "input_tokens": usage.get("input_tokens", 0),
                    "output_tokens": usage.get("output_tokens", 0),
                    "cache_read_input_tokens": usage.get("cached_input_tokens", 0),
                })


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

_AGENTS: dict[str, type[AgentRunner]] = {
    "claude": ClaudeRunner,
    "codex": CodexRunner,
}


def get_agent(name: str) -> AgentRunner:
    """Create an agent runner by name.

    Args:
        name: Agent identifier ("claude" or "codex")

    Returns:
        Configured AgentRunner instance

    Raises:
        ValueError: If agent name is unknown
    """
    cls = _AGENTS.get(name)
    if cls is None:
        raise ValueError(
            f"Unknown agent '{name}'. Available: {', '.join(_AGENTS)}"
        )
    return cls()
