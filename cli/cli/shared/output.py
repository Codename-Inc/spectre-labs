"""Output formatting utilities for Spectre CLI.

Provides consistent output formatting across all CLI modules:
- JSON output (pretty-printed)
- JSONL streaming output (newline-delimited JSON)
- Text/table output (human-readable)
"""

from __future__ import annotations

import json
import sys
from typing import Any, Callable, Iterator, TextIO

import click


# =============================================================================
# JSON Output
# =============================================================================


def format_json(data: Any, indent: int = 2) -> str:
    """Format data as pretty-printed JSON.

    Args:
        data: Any JSON-serializable data
        indent: Number of spaces for indentation (default 2)

    Returns:
        Pretty-printed JSON string
    """
    return json.dumps(data, indent=indent, ensure_ascii=False)


def output_json(data: Any, file: TextIO | None = None) -> None:
    """Output data as pretty-printed JSON.

    Args:
        data: Any JSON-serializable data
        file: File to write to (default: stdout via click.echo)
    """
    formatted = format_json(data)
    if file:
        file.write(formatted + "\n")
    else:
        click.echo(formatted)


# =============================================================================
# JSONL Streaming Output
# =============================================================================


def format_jsonl_line(data: Any) -> str:
    """Format a single line of JSONL (compact JSON).

    Args:
        data: Any JSON-serializable data

    Returns:
        Single-line JSON string
    """
    return json.dumps(data, ensure_ascii=False)


def output_jsonl(data: Any, file: TextIO | None = None) -> None:
    """Output a single JSONL line (newline-delimited JSON).

    Args:
        data: Any JSON-serializable data
        file: File to write to (default: stdout via click.echo)
    """
    line = format_jsonl_line(data)
    if file:
        file.write(line + "\n")
        file.flush()
    else:
        click.echo(line)


def stream_jsonl(items: Iterator[Any], file: TextIO | None = None) -> None:
    """Stream multiple items as JSONL.

    Args:
        items: Iterator of JSON-serializable items
        file: File to write to (default: stdout via click.echo)
    """
    for item in items:
        output_jsonl(item, file)


# =============================================================================
# Table Output
# =============================================================================


def format_table(
    rows: list[dict[str, Any]],
    columns: list[tuple[str, str, int]],
    truncate_long: bool = True,
) -> str:
    """Format rows as a text table.

    Args:
        rows: List of dicts, each representing a row
        columns: List of (key, header, width) tuples
        truncate_long: Whether to truncate values longer than column width

    Returns:
        Formatted table string
    """
    lines: list[str] = []

    # Header line
    header_parts = []
    for _, header, width in columns:
        header_parts.append(f"{header:<{width}}")
    lines.append(" ".join(header_parts))

    # Separator line
    total_width = sum(w for _, _, w in columns) + len(columns) - 1
    lines.append("-" * total_width)

    # Data rows
    for row in rows:
        row_parts = []
        for key, _, width in columns:
            value = str(row.get(key, ""))
            if truncate_long and len(value) > width:
                value = value[: width - 3] + "..."
            row_parts.append(f"{value:<{width}}")
        lines.append(" ".join(row_parts))

    return "\n".join(lines)


def output_table(
    rows: list[dict[str, Any]],
    columns: list[tuple[str, str, int]],
    file: TextIO | None = None,
) -> None:
    """Output rows as a text table.

    Args:
        rows: List of dicts, each representing a row
        columns: List of (key, header, width) tuples defining table structure
        file: File to write to (default: stdout via click.echo)

    Example:
        columns = [
            ("name", "NAME", 20),
            ("source", "SOURCE", 15),
            ("description", "DESCRIPTION", 40),
        ]
        output_table(agents, columns)
    """
    formatted = format_table(rows, columns)
    if file:
        file.write(formatted + "\n")
    else:
        click.echo(formatted)


# =============================================================================
# Path Display Utilities
# =============================================================================


def truncate_path(path: str, max_length: int = 45) -> str:
    """Truncate a path for display, keeping the end.

    Args:
        path: Full path string
        max_length: Maximum display length

    Returns:
        Truncated path with leading "..." if needed
    """
    if len(path) <= max_length:
        return path
    return "..." + path[-(max_length - 3) :]


def format_path_display(path: str, max_length: int = 45) -> str:
    """Format a path for column display.

    Same as truncate_path but provides a clearer name for the use case.
    """
    return truncate_path(path, max_length)


# =============================================================================
# Output Format Selection
# =============================================================================


def get_output_handler(
    output_format: str,
) -> Callable[[Any], None]:
    """Get the appropriate output handler for a format.

    Args:
        output_format: One of "json", "jsonl", "text"

    Returns:
        Function that takes data and outputs it

    Raises:
        ValueError: If format is not recognized
    """
    handlers = {
        "json": output_json,
        "jsonl": output_jsonl,
    }

    if output_format not in handlers:
        raise ValueError(f"Unknown output format: {output_format}")

    return handlers[output_format]


# =============================================================================
# Error Output
# =============================================================================


def output_error(message: str, exit_code: int | None = 1) -> None:
    """Output an error message to stderr.

    Args:
        message: Error message
        exit_code: If provided, exit with this code after outputting
    """
    click.echo(f"Error: {message}", err=True)
    if exit_code is not None:
        sys.exit(exit_code)


def output_warning(message: str) -> None:
    """Output a warning message to stderr.

    Args:
        message: Warning message
    """
    click.echo(f"Warning: {message}", err=True)
