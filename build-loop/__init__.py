# cli/build - Build loop module
"""
Spectre Build CLI - Execute Claude in a loop, one parent task per iteration.

The CLI handles the loop; Claude handles task tracking and progress writing.
"""

from .loop import run_build_loop, ALLOWED_TOOLS, DENIED_TOOLS
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
    "ALLOWED_TOOLS",
    "DENIED_TOOLS",
]


def main() -> None:
    """Main entry point for Spectre Build CLI."""
    from .cli import main as cli_main
    cli_main()
