"""Tests for create_default_pipeline() configuration.

Verifies the phase owner pattern: no TASK_COMPLETE loopback,
phase-level max_iterations, and backward-compatible legacy pipeline.
"""

from build_loop.pipeline.loader import (
    create_default_pipeline,
    create_default_build_validate_pipeline,
)
from build_loop.pipeline.completion import PromiseCompletion


class TestBuildStageTransitions:
    """Tests for build stage transition map after phase owner rewrite."""

    def test_phase_complete_transitions_to_code_review(self):
        """Happy: PHASE_COMPLETE routes to code_review."""
        config = create_default_pipeline(tasks_file="/tmp/tasks.md")
        build = config.stages["build"]
        assert build.transitions["PHASE_COMPLETE"] == "code_review"

    def test_no_task_complete_transition(self):
        """Failure: TASK_COMPLETE loopback removed."""
        config = create_default_pipeline(tasks_file="/tmp/tasks.md")
        build = config.stages["build"]
        assert "TASK_COMPLETE" not in build.transitions


class TestBuildStageCompleteSignals:
    """Tests for build stage PromiseCompletion signals."""

    def test_complete_signals_include_phase_complete(self):
        """Happy: PHASE_COMPLETE recognized as completion signal."""
        config = create_default_pipeline(tasks_file="/tmp/tasks.md")
        build = config.stages["build"]
        completion = build.completion
        assert isinstance(completion, PromiseCompletion)
        assert "PHASE_COMPLETE" in completion.complete_signals

    def test_complete_signals_exclude_task_complete(self):
        """Failure: TASK_COMPLETE not in completion signals."""
        config = create_default_pipeline(tasks_file="/tmp/tasks.md")
        build = config.stages["build"]
        completion = build.completion
        assert isinstance(completion, PromiseCompletion)
        assert "TASK_COMPLETE" not in completion.complete_signals


class TestBuildStageMaxIterations:
    """Tests for phase-level max_iterations default."""

    def test_default_max_iterations_is_3(self):
        """Happy: Default max_iterations set for phase-level iteration."""
        config = create_default_pipeline(tasks_file="/tmp/tasks.md")
        build = config.stages["build"]
        assert build.max_iterations == 3

    def test_max_iterations_override(self):
        """Failure: Caller can override max_iterations."""
        config = create_default_pipeline(
            tasks_file="/tmp/tasks.md",
            max_build_iterations=7,
        )
        build = config.stages["build"]
        assert build.max_iterations == 7


class TestLegacyPipelineUnchanged:
    """Tests that create_default_build_validate_pipeline is not modified."""

    def test_legacy_has_task_complete_transition(self):
        """Happy: Legacy pipeline still loops on TASK_COMPLETE."""
        config = create_default_build_validate_pipeline(
            tasks_file="/tmp/tasks.md"
        )
        build = config.stages["build"]
        assert "TASK_COMPLETE" in build.transitions
        assert build.transitions["TASK_COMPLETE"] == "build"

    def test_legacy_max_iterations_is_10(self):
        """Failure: Legacy pipeline keeps max_iterations=10."""
        config = create_default_build_validate_pipeline(
            tasks_file="/tmp/tasks.md"
        )
        build = config.stages["build"]
        assert build.max_iterations == 10
