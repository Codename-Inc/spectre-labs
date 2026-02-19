"""
Stream-JSON parsing and formatting for Claude output.

Handles real-time parsing and display of stream-json events from Claude CLI.
"""

import logging

from .stats import BuildStats

logger = logging.getLogger(__name__)

# Track pending tool_use calls by ID for correlating with tool_results.
# Cleared on each new session (system event).
_pending_tools: dict[str, dict] = {}


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
    elif name == "Task":
        subagent = input_data.get("subagent_type", "?")
        desc = input_data.get("description", "")
        bg = " [bg]" if input_data.get("run_in_background") else ""
        if desc:
            return f"🚀 Task({subagent}){bg}: {desc}"
        return f"🚀 Task({subagent}){bg}"
    elif name == "Skill":
        skill = input_data.get("skill", "?")
        return f"📚 Skill: {skill}"
    else:
        return f"🔧 {name}"


def _extract_tool_result_text(content) -> str:
    """Extract text from a tool_result content field.

    Content can be a plain string or a list of content blocks.
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
        return " ".join(parts)
    return str(content) if content else ""


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
                # Track pending tool calls for result correlation
                tool_id = item.get("id")
                if tool_id:
                    _pending_tools[tool_id] = {
                        "name": tool_name,
                        "input": tool_input,
                    }
                formatted = format_tool_call(tool_name, tool_input)
                print(formatted)
                # Track tool call
                if stats:
                    stats.add_tool_call(tool_name)

    elif event_type == "user":
        # Process tool_result events for errors and Task/Skill completions
        message = event.get("message", {})
        content = message.get("content", [])

        for item in content:
            if not isinstance(item, dict) or item.get("type") != "tool_result":
                continue

            tool_use_id = item.get("tool_use_id")
            is_error = item.get("is_error", False)
            pending = _pending_tools.pop(tool_use_id, None) if tool_use_id else None
            tool_name = pending["name"] if pending else "unknown"

            if is_error:
                # Surface ALL tool errors — permission denials, failures, etc.
                result_text = _extract_tool_result_text(item.get("content", ""))
                if len(result_text) > 120:
                    result_text = result_text[:117] + "..."
                print(f"❌ {tool_name} error: {result_text}")
            elif pending and pending["name"] == "Task":
                # Show Task subagent completion
                inp = pending.get("input", {})
                subagent = inp.get("subagent_type", "?")
                desc = inp.get("description", "")
                print(f"✅ Task({subagent}) done: {desc}")

    elif event_type == "system":
        # New session — clear pending tool tracking
        _pending_tools.clear()
        # System event fires at session start — capture model
        # and session ID for JSONL transcript lookup
        if stats and not stats.model:
            model = event.get("model", "")
            if not model:
                # Some formats nest under subtype=init
                session_obj = event.get("session", {})
                model = session_obj.get("model", "")
            if model:
                stats.model = model

        if stats and not stats.session_id:
            sid = event.get("sessionId", "")
            if not sid:
                sid = event.get(
                    "session", {}
                ).get("sessionId", "")
            if sid:
                stats.session_id = sid

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

    # Skip other event types (tool_result successes for non-Task tools are too noisy)
