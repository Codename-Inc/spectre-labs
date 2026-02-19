"""Tests for parse_session_tokens() JSONL transcript parsing."""

import json
import os
import tempfile

from build_loop.stats import parse_session_tokens


def _write_jsonl(events: list[dict]) -> str:
    """Write events to a temp JSONL file and return its path."""
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd, "w") as f:
        for event in events:
            f.write(json.dumps(event) + "\n")
    return path


class TestParseSessionTokensHappy:
    """Happy path tests for parse_session_tokens."""

    def test_single_assistant_event(self):
        """Single assistant event with usage is aggregated correctly."""
        events = [
            {
                "type": "assistant",
                "message": {
                    "model": "claude-opus-4-6",
                    "role": "assistant",
                    "usage": {
                        "input_tokens": 100,
                        "output_tokens": 50,
                        "cache_read_input_tokens": 80,
                        "cache_creation_input_tokens": 20,
                    },
                    "content": [{"type": "text", "text": "Hello"}],
                },
            }
        ]
        path = _write_jsonl(events)
        try:
            result = parse_session_tokens(path)
            assert result["input_tokens"] == 100
            assert result["output_tokens"] == 50
            assert result["cache_read_input_tokens"] == 80
            assert result["cache_creation_input_tokens"] == 20
        finally:
            os.unlink(path)

    def test_multiple_assistant_events_aggregated(self):
        """Multiple assistant events have their usage summed."""
        events = [
            {
                "type": "assistant",
                "message": {
                    "usage": {
                        "input_tokens": 100,
                        "output_tokens": 50,
                        "cache_read_input_tokens": 80,
                        "cache_creation_input_tokens": 20,
                    },
                    "content": [],
                },
            },
            {"type": "user", "message": {"content": "next"}},
            {
                "type": "assistant",
                "message": {
                    "usage": {
                        "input_tokens": 200,
                        "output_tokens": 100,
                        "cache_read_input_tokens": 160,
                        "cache_creation_input_tokens": 40,
                    },
                    "content": [],
                },
            },
        ]
        path = _write_jsonl(events)
        try:
            result = parse_session_tokens(path)
            assert result["input_tokens"] == 300
            assert result["output_tokens"] == 150
            assert result["cache_read_input_tokens"] == 240
            assert result["cache_creation_input_tokens"] == 60
        finally:
            os.unlink(path)

    def test_non_assistant_events_ignored(self):
        """User, progress, and queue-operation events don't affect totals."""
        events = [
            {"type": "queue-operation", "operation": "enqueue"},
            {"type": "queue-operation", "operation": "dequeue"},
            {"type": "progress", "data": {"type": "hook_progress"}},
            {
                "type": "assistant",
                "message": {
                    "usage": {
                        "input_tokens": 500,
                        "output_tokens": 200,
                        "cache_read_input_tokens": 400,
                        "cache_creation_input_tokens": 100,
                    },
                    "content": [],
                },
            },
            {"type": "user", "message": {"content": "ok"}},
        ]
        path = _write_jsonl(events)
        try:
            result = parse_session_tokens(path)
            assert result["input_tokens"] == 500
            assert result["output_tokens"] == 200
        finally:
            os.unlink(path)

    def test_returns_model_from_first_assistant(self):
        """Model ID extracted from the first assistant event's message."""
        events = [
            {
                "type": "assistant",
                "message": {
                    "model": "claude-opus-4-6",
                    "usage": {
                        "input_tokens": 10,
                        "output_tokens": 5,
                        "cache_read_input_tokens": 0,
                        "cache_creation_input_tokens": 0,
                    },
                    "content": [],
                },
            },
        ]
        path = _write_jsonl(events)
        try:
            result = parse_session_tokens(path)
            assert result["model"] == "claude-opus-4-6"
        finally:
            os.unlink(path)


class TestParseSessionTokensFailure:
    """Failure/edge case tests for parse_session_tokens."""

    def test_empty_file_returns_zeros(self):
        """An empty JSONL file returns zero tokens."""
        path = _write_jsonl([])
        try:
            result = parse_session_tokens(path)
            assert result["input_tokens"] == 0
            assert result["output_tokens"] == 0
            assert result["cache_read_input_tokens"] == 0
            assert result["cache_creation_input_tokens"] == 0
        finally:
            os.unlink(path)

    def test_file_not_found_returns_zeros(self):
        """Non-existent file path returns zero tokens without raising."""
        result = parse_session_tokens("/tmp/nonexistent_session.jsonl")
        assert result["input_tokens"] == 0
        assert result["output_tokens"] == 0

    def test_malformed_json_lines_skipped(self):
        """Malformed JSON lines are skipped without crashing."""
        fd, path = tempfile.mkstemp(suffix=".jsonl")
        with os.fdopen(fd, "w") as f:
            f.write("not valid json\n")
            f.write(json.dumps({
                "type": "assistant",
                "message": {
                    "usage": {
                        "input_tokens": 100,
                        "output_tokens": 50,
                        "cache_read_input_tokens": 0,
                        "cache_creation_input_tokens": 0,
                    },
                    "content": [],
                },
            }) + "\n")
            f.write("{broken\n")
        try:
            result = parse_session_tokens(path)
            assert result["input_tokens"] == 100
            assert result["output_tokens"] == 50
        finally:
            os.unlink(path)

    def test_assistant_without_usage_skipped(self):
        """Assistant events missing usage field are safely skipped."""
        events = [
            {
                "type": "assistant",
                "message": {
                    "content": [{"type": "text", "text": "hi"}],
                },
            },
            {
                "type": "assistant",
                "message": {
                    "usage": {
                        "input_tokens": 50,
                        "output_tokens": 25,
                        "cache_read_input_tokens": 0,
                        "cache_creation_input_tokens": 0,
                    },
                    "content": [],
                },
            },
        ]
        path = _write_jsonl(events)
        try:
            result = parse_session_tokens(path)
            assert result["input_tokens"] == 50
            assert result["output_tokens"] == 25
        finally:
            os.unlink(path)

    def test_missing_model_returns_empty_string(self):
        """If no assistant event has a model field, model is empty."""
        events = [
            {
                "type": "assistant",
                "message": {
                    "usage": {
                        "input_tokens": 10,
                        "output_tokens": 5,
                        "cache_read_input_tokens": 0,
                        "cache_creation_input_tokens": 0,
                    },
                    "content": [],
                },
            },
        ]
        path = _write_jsonl(events)
        try:
            result = parse_session_tokens(path)
            assert result["model"] == ""
        finally:
            os.unlink(path)

    def test_partial_usage_fields_handled(self):
        """Usage dict missing some token fields treats them as 0."""
        events = [
            {
                "type": "assistant",
                "message": {
                    "usage": {
                        "input_tokens": 100,
                        "output_tokens": 50,
                    },
                    "content": [],
                },
            },
        ]
        path = _write_jsonl(events)
        try:
            result = parse_session_tokens(path)
            assert result["input_tokens"] == 100
            assert result["output_tokens"] == 50
            assert result["cache_read_input_tokens"] == 0
            assert result["cache_creation_input_tokens"] == 0
        finally:
            os.unlink(path)
