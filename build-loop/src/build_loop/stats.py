"""
Build statistics tracking.

Tracks token usage, tool calls, and timing across build iterations.
"""

import time
from dataclasses import dataclass, field


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
    tool_calls: dict = field(default_factory=dict)

    def add_usage(self, usage: dict) -> None:
        """Add token usage from an assistant message."""
        self.total_input_tokens += usage.get("input_tokens", 0)
        self.total_output_tokens += usage.get("output_tokens", 0)
        self.total_cache_read_tokens += usage.get("cache_read_input_tokens", 0)
        self.total_cache_write_tokens += usage.get("cache_creation_input_tokens", 0)

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
        print("│                                      │")
        print("│  ─────────────────────────────────   │")
        print(f"│  RANK: {rank:<5}              exit 0   │")
        print("╰──────────────────────────────────────╯")
        print()
