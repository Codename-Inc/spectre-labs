"""
Build statistics tracking.

Tracks token usage, tool calls, and timing across build iterations.
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable

logger = logging.getLogger(__name__)


# Pricing per 1M tokens (USD) by model family
# Source: https://docs.anthropic.com/en/docs/about-claude/models
# Updated 2026-02-18 for Opus 4.5+/Sonnet 4.5+/Haiku 4.5 pricing
_MODEL_PRICING: dict[str, dict[str, float]] = {
    "opus": {
        "input": 5.0,
        "output": 25.0,
        "cache_read": 0.50,
        "cache_write": 6.25,
    },
    "sonnet": {
        "input": 3.0,
        "output": 15.0,
        "cache_read": 0.30,
        "cache_write": 3.75,
    },
    "haiku": {
        "input": 1.0,
        "output": 5.0,
        "cache_read": 0.10,
        "cache_write": 1.25,
    },
}


def _resolve_model_family(model_id: str) -> str:
    """Map a model ID to a pricing family key."""
    model_id = model_id.lower()
    for family in ("opus", "haiku", "sonnet"):
        if family in model_id:
            return family
    # Default to sonnet pricing if unknown
    return "sonnet"


@dataclass
class BuildStats:
    """Track statistics across the build."""
    start_time: float = field(default_factory=time.time)
    iterations_completed: int = 0
    iterations_failed: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cache_read_tokens: int = 0
    total_cache_write_tokens: int = 0
    total_cost_usd: float = 0.0
    total_api_turns: int = 0
    model: str = ""
    tool_calls: dict = field(default_factory=dict)
    build_loops: int = 0
    review_loops: int = 0
    validate_loops: int = 0
    plan_loops: int = 0
    ship_loops: int = 0

    def to_dict(self) -> dict:
        """Serialize stats to a JSON-compatible dict for session persistence."""
        return {
            "start_time": self.start_time,
            "iterations_completed": self.iterations_completed,
            "iterations_failed": self.iterations_failed,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_cache_read_tokens": self.total_cache_read_tokens,
            "total_cache_write_tokens": self.total_cache_write_tokens,
            "total_cost_usd": self.total_cost_usd,
            "total_api_turns": self.total_api_turns,
            "model": self.model,
            "tool_calls": dict(self.tool_calls),
            "build_loops": self.build_loops,
            "review_loops": self.review_loops,
            "validate_loops": self.validate_loops,
            "plan_loops": self.plan_loops,
            "ship_loops": self.ship_loops,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "BuildStats":
        """Restore stats from a persisted dict.

        Unknown keys are ignored for forward compatibility.
        """
        stats = cls()
        stats.start_time = data.get("start_time", stats.start_time)
        stats.iterations_completed = data.get("iterations_completed", 0)
        stats.iterations_failed = data.get("iterations_failed", 0)
        stats.total_input_tokens = data.get("total_input_tokens", 0)
        stats.total_output_tokens = data.get("total_output_tokens", 0)
        stats.total_cache_read_tokens = data.get("total_cache_read_tokens", 0)
        stats.total_cache_write_tokens = data.get("total_cache_write_tokens", 0)
        stats.total_cost_usd = data.get("total_cost_usd", 0.0)
        stats.total_api_turns = data.get("total_api_turns", 0)
        stats.model = data.get("model", "")
        stats.tool_calls = dict(data.get("tool_calls", {}))
        stats.build_loops = data.get("build_loops", 0)
        stats.review_loops = data.get("review_loops", 0)
        stats.validate_loops = data.get("validate_loops", 0)
        stats.plan_loops = data.get("plan_loops", 0)
        stats.ship_loops = data.get("ship_loops", 0)
        return stats

    def merge(self, other: "BuildStats") -> None:
        """Merge another BuildStats into this one (for resume accumulation).

        Keeps the earlier start_time so elapsed time spans both sessions.
        Accumulates all counters. Takes the latest model string.
        """
        self.start_time = min(self.start_time, other.start_time)
        self.iterations_completed += other.iterations_completed
        self.iterations_failed += other.iterations_failed
        self.total_input_tokens += other.total_input_tokens
        self.total_output_tokens += other.total_output_tokens
        self.total_cache_read_tokens += other.total_cache_read_tokens
        self.total_cache_write_tokens += other.total_cache_write_tokens
        self.total_cost_usd += other.total_cost_usd
        self.total_api_turns += other.total_api_turns
        if other.model:
            self.model = other.model
        for tool, count in other.tool_calls.items():
            self.tool_calls[tool] = self.tool_calls.get(tool, 0) + count
        self.build_loops += other.build_loops
        self.review_loops += other.review_loops
        self.validate_loops += other.validate_loops
        self.plan_loops += other.plan_loops
        self.ship_loops += other.ship_loops

    def add_usage(self, usage: dict) -> None:
        """Add token usage from a result event."""
        self.total_input_tokens += usage.get("input_tokens", 0)
        self.total_output_tokens += usage.get("output_tokens", 0)
        self.total_cache_read_tokens += usage.get("cache_read_input_tokens", 0)
        self.total_cache_write_tokens += usage.get("cache_creation_input_tokens", 0)

    def calculate_cost(self) -> float:
        """Calculate cost from token counts and model pricing.

        Uses the tracked model to look up per-token rates.
        Input tokens from the API include cache reads, so we subtract
        those to get the non-cached input count.
        """
        family = _resolve_model_family(self.model)
        rates = _MODEL_PRICING[family]

        # input_tokens from the API is total input INCLUDING cache reads,
        # so non-cached input = input_tokens - cache_read_tokens
        non_cached_input = max(0, self.total_input_tokens - self.total_cache_read_tokens)

        cost = (
            (non_cached_input / 1_000_000) * rates["input"]
            + (self.total_output_tokens / 1_000_000) * rates["output"]
            + (self.total_cache_read_tokens / 1_000_000) * rates["cache_read"]
            + (self.total_cache_write_tokens / 1_000_000) * rates["cache_write"]
        )
        return cost

    def add_tool_call(self, tool_name: str) -> None:
        """Track a tool call."""
        self.tool_calls[tool_name] = self.tool_calls.get(tool_name, 0) + 1

    def elapsed_time(self) -> str:
        """Get formatted elapsed time."""
        elapsed = time.time() - self.start_time
        hours, remainder = divmod(int(elapsed), 3600)
        minutes, seconds = divmod(remainder, 60)
        if hours > 0:
            return f"{hours}h {minutes}m {seconds}s"
        elif minutes > 0:
            return f"{minutes}m {seconds}s"
        else:
            return f"{seconds}s"

    def _progress_bar(self, value: float, width: int = 16) -> str:
        """Generate a progress bar string."""
        filled = int(value * width)
        empty = width - filled
        return "█" * filled + "░" * empty

    def _format_tokens(self, count: int) -> str:
        """Format token count for display (e.g., 1,337,066 or 1.3M)."""
        if count >= 1_000_000:
            return f"{count / 1_000_000:.1f}M"
        elif count >= 1_000:
            return f"{count:,}"
        else:
            return str(count)

    def _format_cost(self, cost: float) -> str:
        """Format USD cost for display."""
        if cost >= 1.0:
            return f"${cost:.2f}"
        elif cost > 0:
            return f"${cost:.4f}"
        else:
            return "—"

    def _calculate_rank(self) -> str:
        """Calculate a rank based on build performance."""
        total = self.iterations_completed + self.iterations_failed
        if total == 0:
            return "?"
        success_rate = self.iterations_completed / total
        if success_rate == 1.0 and self.iterations_completed >= 5:
            return "S+"
        elif success_rate == 1.0:
            return "S"
        elif success_rate >= 0.9:
            return "A"
        elif success_rate >= 0.7:
            return "B"
        elif success_rate >= 0.5:
            return "C"
        else:
            return "D"

    def print_summary(self, total_tasks: int | None = None) -> None:
        """Print a summary dashboard in shareable format."""
        # Calculate derived stats
        total_tokens = self.total_input_tokens + self.total_output_tokens
        total_cache = self.total_cache_read_tokens + self.total_cache_write_tokens
        cache_rate = self.total_cache_read_tokens / total_cache if total_cache > 0 else 0
        total_tool_calls = sum(self.tool_calls.values())
        rank = self._calculate_rank()

        # Task progress (use iterations as proxy if total_tasks not provided)
        tasks_done = self.iterations_completed
        tasks_total = total_tasks if total_tasks else tasks_done
        task_pct = tasks_done / tasks_total if tasks_total > 0 else 1.0

        # Format elapsed time for display (H:MM:SS format)
        elapsed = time.time() - self.start_time
        hours, remainder = divmod(int(elapsed), 3600)
        minutes, seconds = divmod(remainder, 60)
        time_str = f"{hours}:{minutes:02d}:{seconds:02d}"

        # Print the dashboard
        tasks_str = f"{self._progress_bar(task_pct)} {tasks_done}/{tasks_total}"
        cache_str = f"{self._progress_bar(cache_rate, 10)} {cache_rate*100:.0f}%"

        # Calculate cost from token counts (always available)
        # Prefer calculated cost since it uses our tracked token breakdowns;
        # fall back to result-event cost if token data is missing
        calculated_cost = self.calculate_cost()
        cost = calculated_cost if calculated_cost > 0 else self.total_cost_usd
        cost_str = self._format_cost(cost)

        # [🪳 TEMP STATS] Log cost decision and token breakdown
        logger.info(
            "[🪳 TEMP STATS] summary: model=%s calculated_cost=%.4f "
            "result_event_cost=%.4f using=%s "
            "input=%d output=%d cache_read=%d cache_write=%d",
            self.model, calculated_cost, self.total_cost_usd,
            "calculated" if calculated_cost > 0 else "result_event",
            self.total_input_tokens, self.total_output_tokens,
            self.total_cache_read_tokens, self.total_cache_write_tokens,
        )

        # Format turns line (only show if we have turn data)
        turns_str = str(self.total_api_turns) if self.total_api_turns > 0 else "—"

        print()
        print("╭──────────────────────────────────────╮")
        print("│  $ spectre-build                     │")
        print("│                                      │")
        print("│  ══ MISSION COMPLETE ══              │")
        print("│                                      │")
        print(f"│  TIME       {time_str:<25}│")
        print(f"│  TASKS      {tasks_str:<25}│")
        print(f"│  COMMITS    {self.iterations_completed:<25}│")

        # Show loop type counts if any were tracked
        total_loops = self.build_loops + self.review_loops + self.validate_loops
        if total_loops > 0:
            loops_str = f"B:{self.build_loops}  R:{self.review_loops}  V:{self.validate_loops}"
            print(f"│  LOOPS      {loops_str:<25}│")

        # Show planning loop count if any were tracked
        if self.plan_loops > 0:
            print(f"│  PLAN LOOPS {self.plan_loops:<25}│")

        # Show ship loop count if any were tracked
        if self.ship_loops > 0:
            print(f"│  SHIP LOOPS {self.ship_loops:<25}│")

        print(f"│  TOKENS     {self._format_tokens(total_tokens):<25}│")
        print(f"│  CACHE      {cache_str:<25}│")
        print(f"│  TOOLS      {total_tool_calls:<25}│")
        print(f"│  TURNS      {turns_str:<25}│")
        print(f"│  COST       {cost_str:<25}│")
        print("│                                      │")
        print("│  ─────────────────────────────────   │")
        print(f"│  RANK: {rank:<5}              exit 0   │")
        print("╰──────────────────────────────────────╯")
        print()


def create_plan_event_handler(stats: "BuildStats") -> Callable[[Any], None]:
    """Create an on_event callback that increments plan_loops on stage completions.

    Used by run_plan_pipeline() to track planning stage iterations.

    Args:
        stats: BuildStats instance to update

    Returns:
        Callback function suitable for PipelineExecutor's on_event parameter
    """
    from .pipeline.executor import StageCompletedEvent

    def handler(event: Any) -> None:
        if isinstance(event, StageCompletedEvent):
            stats.plan_loops += 1

    return handler


def create_ship_event_handler(stats: "BuildStats") -> Callable[[Any], None]:
    """Create an on_event callback that increments ship_loops on stage completions.

    Used by run_ship_pipeline() to track ship stage iterations.

    Args:
        stats: BuildStats instance to update

    Returns:
        Callback function suitable for PipelineExecutor's on_event parameter
    """
    from .pipeline.executor import StageCompletedEvent

    def handler(event: Any) -> None:
        if isinstance(event, StageCompletedEvent):
            stats.ship_loops += 1

    return handler
