"""
Stream-JSON parsing and formatting for Claude output.

Handles real-time parsing and display of stream-json events from Claude CLI.
"""

from .stats import BuildStats


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

        # Track token usage if stats provided
        if stats and "usage" in message:
            stats.add_usage(message["usage"])

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

    # Skip system events and tool_result events (too noisy)
