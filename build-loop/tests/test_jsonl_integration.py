"""Tests for JSONL-based token tracking integration into BuildStats."""

import json
import os
import tempfile

from build_loop.stats import (
    BuildStats,
    find_session_jsonl,
)


def _write_jsonl(events: list[dict], path: str | None = None) -> str:
    """Write events to a JSONL file and return its path."""
    if path is None:
        fd, path = tempfile.mkstemp(suffix=".jsonl")
        os.close(fd)
    with open(path, "w") as f:
        for event in events:
            f.write(json.dumps(event) + "\n")
    return path


class TestFindSessionJsonlHappy:
    """Happy path tests for find_session_jsonl."""

    def test_finds_existing_jsonl(self, tmp_path):
        """Locates JSONL file when session ID and project dir match."""
        session_id = "abc-123-def"
        jsonl_path = tmp_path / f"{session_id}.jsonl"
        jsonl_path.write_text("{}\n")

        result = find_session_jsonl(session_id, str(tmp_path))
        assert result == str(jsonl_path)

    def test_returns_absolute_path(self, tmp_path):
        """Returned path is absolute."""
        session_id = "test-session"
        jsonl_path = tmp_path / f"{session_id}.jsonl"
        jsonl_path.write_text("{}\n")

        result = find_session_jsonl(session_id, str(tmp_path))
        assert os.path.isabs(result)


class TestFindSessionJsonlFailure:
    """Failure/edge case tests for find_session_jsonl."""

    def test_returns_none_when_not_found(self, tmp_path):
        """Returns None when JSONL file doesn't exist."""
        result = find_session_jsonl("nonexistent", str(tmp_path))
        assert result is None

    def test_returns_none_for_none_session_id(self, tmp_path):
        """Returns None when session_id is None."""
        result = find_session_jsonl(None, str(tmp_path))
        assert result is None

    def test_returns_none_for_empty_session_id(self, tmp_path):
        """Returns None when session_id is empty string."""
        result = find_session_jsonl("", str(tmp_path))
        assert result is None

    def test_returns_none_for_bad_dir(self):
        """Returns None when project dir doesn't exist."""
        result = find_session_jsonl(
            "abc-123", "/tmp/nonexistent_project_dir"
        )
        assert result is None


class TestBuildStatsAddJsonlUsageHappy:
    """Happy path tests for BuildStats.add_jsonl_usage()."""

    def test_adds_jsonl_tokens_to_stats(self):
        """JSONL tokens are added to total counts."""
        events = [
            {
                "type": "assistant",
                "message": {
                    "model": "claude-opus-4-6",
                    "usage": {
                        "input_tokens": 1000,
                        "output_tokens": 500,
                        "cache_read_input_tokens": 800,
                        "cache_creation_input_tokens": 200,
                    },
                    "content": [],
                },
            },
        ]
        path = _write_jsonl(events)
        try:
            stats = BuildStats()
            stats.add_jsonl_usage(path)
            assert stats.jsonl_input_tokens == 1000
            assert stats.jsonl_output_tokens == 500
            assert stats.jsonl_cache_read_tokens == 800
            assert stats.jsonl_cache_write_tokens == 200
        finally:
            os.unlink(path)

    def test_accumulates_across_multiple_calls(self):
        """Multiple add_jsonl_usage calls accumulate."""
        events1 = [
            {
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
            },
        ]
        events2 = [
            {
                "type": "assistant",
                "message": {
                    "usage": {
                        "input_tokens": 200,
                        "output_tokens": 100,
                        "cache_read_input_tokens": 0,
                        "cache_creation_input_tokens": 0,
                    },
                    "content": [],
                },
            },
        ]
        path1 = _write_jsonl(events1)
        path2 = _write_jsonl(events2)
        try:
            stats = BuildStats()
            stats.add_jsonl_usage(path1)
            stats.add_jsonl_usage(path2)
            assert stats.jsonl_input_tokens == 300
            assert stats.jsonl_output_tokens == 150
        finally:
            os.unlink(path1)
            os.unlink(path2)


class TestBuildStatsAddJsonlUsageFailure:
    """Failure/edge case tests for BuildStats.add_jsonl_usage()."""

    def test_nonexistent_file_is_noop(self):
        """Non-existent JSONL path doesn't crash, counters stay 0."""
        stats = BuildStats()
        stats.add_jsonl_usage("/tmp/no_such_file.jsonl")
        assert stats.jsonl_input_tokens == 0
        assert stats.jsonl_output_tokens == 0


class TestBuildStatsJsonlSerializationHappy:
    """Tests that JSONL fields survive round-trip serialization."""

    def test_jsonl_fields_in_to_dict(self):
        """JSONL token fields are included in to_dict output."""
        stats = BuildStats()
        stats.jsonl_input_tokens = 5000
        stats.jsonl_output_tokens = 1000
        stats.jsonl_cache_read_tokens = 4000
        stats.jsonl_cache_write_tokens = 500

        data = stats.to_dict()
        assert data["jsonl_input_tokens"] == 5000
        assert data["jsonl_output_tokens"] == 1000
        assert data["jsonl_cache_read_tokens"] == 4000
        assert data["jsonl_cache_write_tokens"] == 500

    def test_jsonl_fields_round_trip(self):
        """JSONL fields survive to_dict → from_dict round trip."""
        stats = BuildStats()
        stats.jsonl_input_tokens = 5000
        stats.jsonl_output_tokens = 1000
        stats.jsonl_cache_read_tokens = 4000
        stats.jsonl_cache_write_tokens = 500

        restored = BuildStats.from_dict(stats.to_dict())
        assert restored.jsonl_input_tokens == 5000
        assert restored.jsonl_output_tokens == 1000
        assert restored.jsonl_cache_read_tokens == 4000
        assert restored.jsonl_cache_write_tokens == 500


class TestBuildStatsJsonlSerializationFailure:
    """Backward-compat tests for JSONL fields in from_dict."""

    def test_missing_jsonl_fields_default_to_zero(self):
        """Old persisted data without JSONL fields loads cleanly."""
        data = {"total_input_tokens": 5000}
        stats = BuildStats.from_dict(data)
        assert stats.jsonl_input_tokens == 0
        assert stats.jsonl_output_tokens == 0
        assert stats.jsonl_cache_read_tokens == 0
        assert stats.jsonl_cache_write_tokens == 0


class TestBuildStatsMergeJsonlHappy:
    """Tests that merge() handles JSONL fields."""

    def test_merge_accumulates_jsonl_tokens(self):
        """merge() sums JSONL token fields from both sessions."""
        s1 = BuildStats()
        s1.jsonl_input_tokens = 1000
        s1.jsonl_output_tokens = 500

        s2 = BuildStats()
        s2.jsonl_input_tokens = 2000
        s2.jsonl_output_tokens = 1000

        s1.merge(s2)
        assert s1.jsonl_input_tokens == 3000
        assert s1.jsonl_output_tokens == 1500


class TestSessionIdCaptureHappy:
    """Tests for session ID capture from stream events."""

    def test_session_id_captured_from_system_event(self):
        """process_stream_event captures sessionId from system."""
        from build_loop.stream import process_stream_event

        stats = BuildStats()
        event = {
            "type": "system",
            "sessionId": "abc-123-def",
            "model": "claude-opus-4-6",
        }
        process_stream_event(event, [], stats)
        assert stats.session_id == "abc-123-def"

    def test_session_id_from_nested_session_field(self):
        """Captures sessionId from session sub-object."""
        from build_loop.stream import process_stream_event

        stats = BuildStats()
        event = {
            "type": "system",
            "session": {
                "sessionId": "xyz-789",
                "model": "claude-opus-4-6",
            },
        }
        process_stream_event(event, [], stats)
        assert stats.session_id == "xyz-789"


class TestSessionIdCaptureFailure:
    """Failure cases for session ID capture."""

    def test_no_session_id_stays_empty(self):
        """Stats session_id stays empty if not in event."""
        from build_loop.stream import process_stream_event

        stats = BuildStats()
        event = {
            "type": "system",
            "model": "claude-opus-4-6",
        }
        process_stream_event(event, [], stats)
        assert stats.session_id == ""
