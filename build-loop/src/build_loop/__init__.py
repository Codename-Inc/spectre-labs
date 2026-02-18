# cli/build - Build loop module
"""
Spectre Build CLI - Execute an agent in a loop, one parent task per iteration.

The CLI handles the loop; the agent handles task tracking and progress writing.
"""

from .agent import get_agent, CLAUDE_ALLOWED_TOOLS, CLAUDE_DENIED_TOOLS
from .loop import run_build_loop
from .prompt import build_prompt
from .stats import BuildStats
from .stream import format_tool_call, process_stream_event


__all__ = [
    "main",
    "run_build_loop",
    "build_prompt",
    "BuildStats",
    "format_tool_call",
    "process_stream_event",
    "get_agent",
    "CLAUDE_ALLOWED_TOOLS",
    "CLAUDE_DENIED_TOOLS",
]


def main() -> None:
    """Main entry point for Spectre Build CLI."""
    from .cli import main as cli_main
    try:
        cli_main()
    except KeyboardInterrupt:
        print()
        raise SystemExit(130)
