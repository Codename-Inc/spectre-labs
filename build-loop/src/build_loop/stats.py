"""
Build statistics tracking.

Tracks token usage, tool calls, and timing across build iterations.
"""

import time
from dataclasses import dataclass, field



# Pricing per 1M tokens (USD) by model family
# Source: https://docs.anthropic.com/en/docs/about-claude/models
_MODEL_PRICING: dict[str, dict[str, float]] = {
    "opus": {
        "input": 15.0,
        "output": 75.0,
        "cache_read": 1.50,
        "cache_write": 18.75,
    },
    "sonnet": {
        "input": 3.0,
        "output": 15.0,
        "cache_read": 0.30,
        "cache_write": 3.75,
    },
    "haiku": {
        "input": 0.80,
        "output": 4.0,
        "cache_read": 0.08,
        "cache_write": 1.0,
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
