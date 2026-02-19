"""Tests for BuildStats serialization and session persistence."""

import json
import time

from build_loop.stats import BuildStats


class TestBuildStatsToDict:
    """Tests for BuildStats.to_dict() serialization."""

    def test_round_trip_default_stats(self):
        """Happy: fresh stats survive round-trip serialization."""
        original = BuildStats()
        data = original.to_dict()
        restored = BuildStats.from_dict(data)

        assert restored.iterations_completed == 0
        assert restored.total_input_tokens == 0
        assert restored.total_output_tokens == 0
        assert restored.total_cost_usd == 0.0
        assert restored.model == ""
        assert restored.tool_calls == {}

    def test_round_trip_populated_stats(self):
        """Happy: populated stats survive round-trip serialization."""
        original = BuildStats()
        original.start_time = 1000000.0
        original.iterations_completed = 8
        original.iterations_failed = 1
        original.total_input_tokens = 500_000
        original.total_output_tokens = 50_000
        original.total_cache_read_tokens = 400_000
        original.total_cache_write_tokens = 10_000
        original.total_cost_usd = 22.78
        original.total_api_turns = 165
        original.model = "claude-opus-4-6-20261201"
        original.tool_calls = {"Read": 50, "Edit": 30, "Bash": 20}
        original.build_loops = 4
        original.review_loops = 2
        original.validate_loops = 2
        original.plan_loops = 3
        original.ship_loops = 5

        data = original.to_dict()
        restored = BuildStats.from_dict(data)

        assert restored.start_time == 1000000.0
        assert restored.iterations_completed == 8
        assert restored.iterations_failed == 1
        assert restored.total_input_tokens == 500_000
        assert restored.total_output_tokens == 50_000
        assert restored.total_cache_read_tokens == 400_000
        assert restored.total_cache_write_tokens == 10_000
        assert restored.total_cost_usd == 22.78
        assert restored.total_api_turns == 165
        assert restored.model == "claude-opus-4-6-20261201"
        assert restored.tool_calls == {"Read": 50, "Edit": 30, "Bash": 20}
        assert restored.build_loops == 4
        assert restored.review_loops == 2
        assert restored.validate_loops == 2
        assert restored.plan_loops == 3
        assert restored.ship_loops == 5

    def test_to_dict_is_json_serializable(self):
        """Happy: to_dict output can be serialized to JSON and back."""
        stats = BuildStats()
        stats.total_input_tokens = 100_000
        stats.tool_calls = {"Read": 10}

        json_str = json.dumps(stats.to_dict())
        data = json.loads(json_str)
        restored = BuildStats.from_dict(data)

        assert restored.total_input_tokens == 100_000
        assert restored.tool_calls == {"Read": 10}

    def test_from_dict_ignores_unknown_keys(self):
        """Forward compat: unknown keys in persisted data are ignored."""
        data = {
            "total_input_tokens": 1000,
            "future_field": "some_value",
            "another_new_thing": 42,
        }
        stats = BuildStats.from_dict(data)
        assert stats.total_input_tokens == 1000

    def test_from_dict_handles_missing_keys(self):
        """Backward compat: missing keys use defaults."""
        data = {"total_input_tokens": 5000}
        stats = BuildStats.from_dict(data)

        assert stats.total_input_tokens == 5000
        assert stats.total_output_tokens == 0
        assert stats.model == ""
        assert stats.tool_calls == {}
        assert stats.ship_loops == 0


class TestBuildStatsMerge:
    """Tests for BuildStats.merge() accumulation."""

    def test_merge_accumulates_tokens(self):
        """Happy: merge sums token counts from both sessions."""
        session1 = BuildStats()
        session1.total_input_tokens = 100_000
        session1.total_output_tokens = 10_000
        session1.total_cache_read_tokens = 80_000

        session2 = BuildStats()
        session2.total_input_tokens = 200_000
        session2.total_output_tokens = 20_000
        session2.total_cache_read_tokens = 160_000

        session1.merge(session2)

        assert session1.total_input_tokens == 300_000
        assert session1.total_output_tokens == 30_000
        assert session1.total_cache_read_tokens == 240_000

    def test_merge_keeps_earlier_start_time(self):
        """Happy: merge preserves the earlier start_time."""
        earlier = 1000000.0
        later = 2000000.0

        session1 = BuildStats()
        session1.start_time = later

        session2 = BuildStats()
        session2.start_time = earlier

        session1.merge(session2)
        assert session1.start_time == earlier

    def test_merge_accumulates_loop_counts(self):
        """Happy: merge sums all loop counters."""
        session1 = BuildStats()
        session1.build_loops = 4
        session1.review_loops = 2
        session1.validate_loops = 2
        session1.iterations_completed = 8

        session2 = BuildStats()
        session2.build_loops = 3
        session2.review_loops = 1
        session2.validate_loops = 1
        session2.iterations_completed = 5

        session1.merge(session2)

        assert session1.build_loops == 7
        assert session1.review_loops == 3
        assert session1.validate_loops == 3
        assert session1.iterations_completed == 13

    def test_merge_combines_tool_calls(self):
        """Happy: merge sums tool call counts by tool name."""
        session1 = BuildStats()
        session1.tool_calls = {"Read": 50, "Edit": 30}

        session2 = BuildStats()
        session2.tool_calls = {"Read": 20, "Bash": 10}

        session1.merge(session2)

        assert session1.tool_calls == {"Read": 70, "Edit": 30, "Bash": 10}

    def test_merge_takes_latest_model(self):
        """Happy: merge uses the other session's model if set."""
        session1 = BuildStats()
        session1.model = "claude-opus-4-5"

        session2 = BuildStats()
        session2.model = "claude-opus-4-6"

        session1.merge(session2)
        assert session1.model == "claude-opus-4-6"

    def test_merge_keeps_model_if_other_empty(self):
        """Edge: merge keeps existing model if other has none."""
        session1 = BuildStats()
        session1.model = "claude-opus-4-6"

        session2 = BuildStats()
        session2.model = ""

        session1.merge(session2)
        assert session1.model == "claude-opus-4-6"

    def test_merge_accumulates_cost(self):
        """Happy: merge sums total_cost_usd from both sessions."""
        session1 = BuildStats()
        session1.total_cost_usd = 10.50

        session2 = BuildStats()
        session2.total_cost_usd = 12.28

        session1.merge(session2)
        assert abs(session1.total_cost_usd - 22.78) < 0.01
