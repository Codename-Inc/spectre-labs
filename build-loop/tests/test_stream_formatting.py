"""Tests for stream.py tool call formatting and tool_result processing."""

from unittest.mock import patch

from build_loop.stream import (
    _extract_tool_result_text,
    _pending_tools,
    format_tool_call,
    process_stream_event,
)


class TestFormatToolCall:
    """Tests for format_tool_call with Task and Skill tools."""

    def test_task_with_subagent_and_description(self):
        result = format_tool_call("Task", {
            "subagent_type": "Explore",
            "description": "Research navigation patterns",
        })
        assert result == "🚀 Task(Explore): Research navigation patterns"

    def test_task_without_description(self):
        result = format_tool_call("Task", {"subagent_type": "Bash"})
        assert result == "🚀 Task(Bash)"

    def test_task_background(self):
        result = format_tool_call("Task", {
            "subagent_type": "general-purpose",
            "description": "Long research",
            "run_in_background": True,
        })
        assert result == "🚀 Task(general-purpose) [bg]: Long research"

    def test_task_missing_subagent(self):
        result = format_tool_call("Task", {})
        assert result == "🚀 Task(?)"

    def test_skill(self):
        result = format_tool_call("Skill", {"skill": "feature-build-loop"})
        assert result == "📚 Skill: feature-build-loop"

    def test_skill_missing_name(self):
        result = format_tool_call("Skill", {})
        assert result == "📚 Skill: ?"

    def test_existing_tools_unchanged(self):
        """Verify existing tool formatting still works."""
        assert format_tool_call("Read", {"file_path": "/a/b.py"}).startswith("📄 Read:")
        assert format_tool_call("Bash", {"command": "ls"}).startswith("💻 Bash:")
        assert format_tool_call("Glob", {"pattern": "*.py"}).startswith("🔍 Glob:")
        assert format_tool_call("Grep", {"pattern": "foo"}).startswith("🔎 Grep:")

    def test_unknown_tool_fallback(self):
        result = format_tool_call("SomethingNew", {})
        assert result == "🔧 SomethingNew"


class TestExtractToolResultText:
    """Tests for _extract_tool_result_text helper."""

    def test_string_content(self):
        assert _extract_tool_result_text("error message") == "error message"

    def test_list_content(self):
        content = [
            {"type": "text", "text": "part one"},
            {"type": "text", "text": "part two"},
        ]
        assert _extract_tool_result_text(content) == "part one part two"

    def test_empty_content(self):
        assert _extract_tool_result_text("") == ""
        assert _extract_tool_result_text(None) == ""
        assert _extract_tool_result_text([]) == ""


class TestToolResultProcessing:
    """Tests for user event processing (tool errors and Task completions)."""

    def setup_method(self):
        _pending_tools.clear()

    def test_tool_error_surfaced(self, capsys):
        """Permission denials / tool errors are printed."""
        # Simulate a tool_use event first
        tool_use_event = {
            "type": "assistant",
            "message": {
                "content": [{
                    "type": "tool_use",
                    "id": "tu_123",
                    "name": "Task",
                    "input": {"subagent_type": "Explore", "description": "test"},
                }],
            },
        }
        process_stream_event(tool_use_event, [])

        # Simulate error tool_result
        error_event = {
            "type": "user",
            "message": {
                "content": [{
                    "type": "tool_result",
                    "tool_use_id": "tu_123",
                    "is_error": True,
                    "content": "Tool 'Task' is not allowed",
                }],
            },
        }
        process_stream_event(error_event, [])

        output = capsys.readouterr().out
        assert "❌ Task error: Tool 'Task' is not allowed" in output

    def test_task_completion_shown(self, capsys):
        """Successful Task completions show subagent details."""
        tool_use_event = {
            "type": "assistant",
            "message": {
                "content": [{
                    "type": "tool_use",
                    "id": "tu_456",
                    "name": "Task",
                    "input": {
                        "subagent_type": "spectre:dev",
                        "description": "Implement auth flow",
                    },
                }],
            },
        }
        process_stream_event(tool_use_event, [])

        result_event = {
            "type": "user",
            "message": {
                "content": [{
                    "type": "tool_result",
                    "tool_use_id": "tu_456",
                    "content": "Task completed successfully...",
                }],
            },
        }
        process_stream_event(result_event, [])

        output = capsys.readouterr().out
        assert "✅ Task(spectre:dev) done: Implement auth flow" in output

    def test_non_task_success_silent(self, capsys):
        """Successful non-Task tool results are NOT printed (too noisy)."""
        tool_use_event = {
            "type": "assistant",
            "message": {
                "content": [{
                    "type": "tool_use",
                    "id": "tu_789",
                    "name": "Read",
                    "input": {"file_path": "/a/b.py"},
                }],
            },
        }
        process_stream_event(tool_use_event, [])

        result_event = {
            "type": "user",
            "message": {
                "content": [{
                    "type": "tool_result",
                    "tool_use_id": "tu_789",
                    "content": "file contents...",
                }],
            },
        }
        process_stream_event(result_event, [])

        output = capsys.readouterr().out
        # Should only have the Read dispatch line, no result line
        lines = [l for l in output.strip().split("\n") if l.strip()]
        assert len(lines) == 1
        assert lines[0].startswith("📄 Read:")

    def test_system_event_clears_pending(self):
        """System event resets pending tool tracking."""
        _pending_tools["stale_id"] = {"name": "Read", "input": {}}
        assert len(_pending_tools) == 1

        process_stream_event({"type": "system"}, [])
        assert len(_pending_tools) == 0

    def test_error_text_truncated(self, capsys):
        """Long error messages are truncated."""
        _pending_tools["tu_long"] = {"name": "Bash", "input": {}}

        long_error = "x" * 200
        error_event = {
            "type": "user",
            "message": {
                "content": [{
                    "type": "tool_result",
                    "tool_use_id": "tu_long",
                    "is_error": True,
                    "content": long_error,
                }],
            },
        }
        process_stream_event(error_event, [])

        output = capsys.readouterr().out
        assert "..." in output
        # Truncated to 120 chars max
        error_line = [l for l in output.strip().split("\n") if "❌" in l][0]
        # The error text portion should be ≤120 chars
        error_text = error_line.split("error: ", 1)[1]
        assert len(error_text) <= 120
