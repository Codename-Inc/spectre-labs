"""
Stream-JSON parsing and formatting for Claude output.

Handles real-time parsing and display of stream-json events from Claude CLI.
"""

import logging

from .stats import BuildStats

logger = logging.getLogger(__name__)


def format_tool_call(name: str, input_data: dict) -> str:
    """Format a tool call for display."""
    if name == "Read":
        path = input_data.get("file_path", "?")
        # Shorten path for display
        if len(path) > 50:
            path = "..." + path[-47:]
        return f"📄 Read: {path}"
    elif name == "Edit":
        path = input_data.get("file_path", "?")
        if len(path) > 50:
            path = "..." + path[-47:]
        return f"✏️  Edit: {path}"
    elif name == "Write":
        path = input_data.get("file_path", "?")
        if len(path) > 50:
            path = "..." + path[-47:]
        return f"📝 Write: {path}"
    elif name == "Bash":
        cmd = input_data.get("command", "?")
        # Truncate long commands
        if len(cmd) > 60:
            cmd = cmd[:57] + "..."
        return f"💻 Bash: {cmd}"
    elif name == "Glob":
        pattern = input_data.get("pattern", "?")
        return f"🔍 Glob: {pattern}"
    elif name == "Grep":
        pattern = input_data.get("pattern", "?")
        return f"🔎 Grep: {pattern}"
    elif name == "TodoWrite":
        return "📋 TodoWrite"
    else:
        return f"🔧 {name}"


def process_stream_event(
    event: dict, text_buffer: list[str], stats: BuildStats | None = None
) -> None:
    """
    Process a single stream-json event and display formatted output.

    Args:
        event: Parsed JSON event from Claude stream
        text_buffer: List to accumulate assistant text for promise detection
        stats: Optional BuildStats to track token usage and tool calls
    """
    event_type = event.get("type")

    if event_type == "assistant":
        # Assistant message - may contain text and/or tool_use
        message = event.get("message", {})
        content = message.get("content", [])

        # Note: usage from individual assistant events is intentionally
        # NOT tracked here. The authoritative totals come from the
        # "result" event at the end of the session (see below).

        for item in content:
            item_type = item.get("type")

            if item_type == "text":
                text = item.get("text", "")
                if text.strip():
                    print(f"💬 {text}")
                    text_buffer.append(text)

            elif item_type == "tool_use":
                tool_name = item.get("name", "?")
                tool_input = item.get("input", {})
                formatted = format_tool_call(tool_name, tool_input)
                print(formatted)
                # Track tool call
                if stats:
                    stats.add_tool_call(tool_name)

    elif event_type == "system":
        # System event fires at session start — capture model for cost calc
        if stats and not stats.model:
            model = event.get("model", "")
            if not model:
                # Some formats nest under subtype=init
                model = event.get("session", {}).get("model", "")
            if model:
                stats.model = model

    elif event_type == "result":
        # Result event fires once at end of session with authoritative
        # totals for all API turns in this iteration

        # [🪳 TEMP STATS] Log full result event to diagnose token counting
        usage = event.get("usage", {})
        logger.info(
            "[🪳 TEMP STATS] result event: usage_keys=%s usage=%s "
            "total_cost_usd=%s num_turns=%s",
            list(usage.keys()),
            {k: v for k, v in usage.items() if isinstance(v, (int, float))},
            event.get("total_cost_usd"),
            event.get("num_turns"),
        )
        if stats:
            # [🪳 TEMP STATS] Log pre-update state
            logger.info(
                "[🪳 TEMP STATS] pre-update: input=%d output=%d "
                "cache_read=%d cache_write=%d cost_usd=%.4f",
                stats.total_input_tokens,
                stats.total_output_tokens,
                stats.total_cache_read_tokens,
                stats.total_cache_write_tokens,
                stats.total_cost_usd,
            )

        if stats and usage:
            stats.add_usage(usage)
        # Capture cost if available
        if stats and "total_cost_usd" in event:
            stats.total_cost_usd += event["total_cost_usd"]
        # Capture API turn count if available
        if stats and "num_turns" in event:
            stats.total_api_turns += event["num_turns"]

        if stats:
            # [🪳 TEMP STATS] Log post-update state
            logger.info(
                "[🪳 TEMP STATS] post-update: input=%d output=%d "
                "cache_read=%d cache_write=%d cost_usd=%.4f "
                "calculated_cost=%.4f",
                stats.total_input_tokens,
                stats.total_output_tokens,
                stats.total_cache_read_tokens,
                stats.total_cache_write_tokens,
                stats.total_cost_usd,
                stats.calculate_cost(),
            )

    # Skip user and tool_result events (too noisy)
