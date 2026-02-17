"""Tests for planning loop counters in BuildStats."""

from io import StringIO
from unittest.mock import patch

from build_loop.pipeline.executor import StageCompletedEvent
from build_loop.stats import BuildStats, create_plan_event_handler


class TestPlanLoopsField:
    """Tests for plan_loops field on BuildStats."""

    def test_plan_loops_defaults_to_zero(self):
        """Happy: BuildStats has plan_loops field initialized to 0."""
        stats = BuildStats()
        assert stats.plan_loops == 0

    def test_plan_loops_is_incrementable(self):
        """Happy: plan_loops can be incremented like other loop counters."""
        stats = BuildStats()
        stats.plan_loops += 1
        stats.plan_loops += 1
        assert stats.plan_loops == 2


class TestPlanLoopsDashboard:
    """Tests for plan_loops display in print_summary dashboard."""

    def test_dashboard_shows_plan_loops_when_nonzero(self):
        """Happy: Dashboard shows PLAN LOOPS line when plan_loops > 0."""
        stats = BuildStats()
        stats.plan_loops = 5

        output = StringIO()
        with patch("sys.stdout", output):
            stats.print_summary()

        dashboard = output.getvalue()
        assert "PLAN LOOPS" in dashboard
        assert "5" in dashboard

    def test_dashboard_omits_plan_loops_when_zero(self):
        """Failure: Dashboard does NOT show PLAN LOOPS when plan_loops is 0."""
        stats = BuildStats()
        stats.plan_loops = 0

        output = StringIO()
        with patch("sys.stdout", output):
            stats.print_summary()

        dashboard = output.getvalue()
        assert "PLAN LOOPS" not in dashboard


class TestPlanEventHandler:
    """Tests for create_plan_event_handler callback factory."""

    def test_increments_plan_loops_on_stage_completed(self):
        """Happy: Handler increments plan_loops on any StageCompletedEvent."""
        stats = BuildStats()
        handler = create_plan_event_handler(stats)

        handler(StageCompletedEvent(stage="research", signal="RESEARCH_COMPLETE", iterations=1))
        handler(StageCompletedEvent(stage="assess", signal="STANDARD", iterations=1))
        handler(StageCompletedEvent(stage="create_plan", signal="PLAN_COMPLETE", iterations=1))

        assert stats.plan_loops == 3

    def test_ignores_non_stage_completed_events(self):
        """Failure: Handler does not increment plan_loops for other event types."""
        from build_loop.pipeline.executor import StageStartedEvent

        stats = BuildStats()
        handler = create_plan_event_handler(stats)

        handler(StageStartedEvent(stage="research"))
        handler(StageStartedEvent(stage="assess"))

        assert stats.plan_loops == 0
