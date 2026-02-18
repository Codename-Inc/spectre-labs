"""Tests for ship loop counters in BuildStats."""

from io import StringIO
from unittest.mock import patch

from build_loop.pipeline.executor import StageCompletedEvent
from build_loop.stats import BuildStats, create_ship_event_handler


class TestShipLoopsField:
    """Tests for ship_loops field on BuildStats."""

    def test_ship_loops_defaults_to_zero(self):
        """Happy: BuildStats has ship_loops field initialized to 0."""
        stats = BuildStats()
        assert stats.ship_loops == 0

    def test_ship_loops_is_incrementable(self):
        """Failure: ship_loops can be incremented without affecting other counters."""
        stats = BuildStats()
        stats.build_loops = 3
        stats.ship_loops += 1
        stats.ship_loops += 1
        assert stats.ship_loops == 2
        assert stats.build_loops == 3


class TestShipLoopsDashboard:
    """Tests for ship_loops display in print_summary dashboard."""

    def test_dashboard_shows_ship_loops_when_nonzero(self):
        """Happy: Dashboard shows SHIP LOOPS line when ship_loops > 0."""
        stats = BuildStats()
        stats.ship_loops = 4

        output = StringIO()
        with patch("sys.stdout", output):
            stats.print_summary()

        dashboard = output.getvalue()
        assert "SHIP LOOPS" in dashboard
        assert "4" in dashboard

    def test_dashboard_omits_ship_loops_when_zero(self):
        """Failure: Dashboard does NOT show SHIP LOOPS when ship_loops is 0."""
        stats = BuildStats()
        stats.ship_loops = 0

        output = StringIO()
        with patch("sys.stdout", output):
            stats.print_summary()

        dashboard = output.getvalue()
        assert "SHIP LOOPS" not in dashboard


class TestShipEventHandler:
    """Tests for create_ship_event_handler callback factory."""

    def test_increments_ship_loops_on_stage_completed(self):
        """Happy: Handler increments ship_loops on any StageCompletedEvent."""
        stats = BuildStats()
        handler = create_ship_event_handler(stats)

        handler(StageCompletedEvent(stage="clean", signal="CLEAN_COMPLETE", iterations=3))
        handler(StageCompletedEvent(stage="test", signal="TEST_COMPLETE", iterations=2))
        handler(StageCompletedEvent(stage="rebase", signal="SHIP_COMPLETE", iterations=1))

        assert stats.ship_loops == 3

    def test_ignores_non_stage_completed_events(self):
        """Failure: Handler does not increment ship_loops for other event types."""
        from build_loop.pipeline.executor import StageStartedEvent

        stats = BuildStats()
        handler = create_ship_event_handler(stats)

        handler(StageStartedEvent(stage="clean"))
        handler(StageStartedEvent(stage="test"))

        assert stats.ship_loops == 0
