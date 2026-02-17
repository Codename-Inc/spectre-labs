"""Tests for planning-specific lifecycle hooks."""

import tempfile
from pathlib import Path

from build_loop.hooks import plan_after_stage, plan_before_stage
from build_loop.pipeline.completion import CompletionResult


class TestPlanBeforeStageDepth:
    """Tests for plan_before_stage depth handling on create_plan stage."""

    def test_defaults_depth_when_missing(self):
        """Happy: create_plan stage gets depth='standard' when not in context."""
        context: dict = {}
        plan_before_stage("create_plan", context)
        assert context["depth"] == "standard"

    def test_preserves_existing_depth(self):
        """Failure: does not overwrite depth if already set."""
        context = {"depth": "comprehensive"}
        plan_before_stage("create_plan", context)
        assert context["depth"] == "comprehensive"


class TestPlanBeforeStageClarifications:
    """Tests for plan_before_stage clarification injection on update_docs stage."""

    def test_injects_clarification_answers_from_file(self):
        """Happy: reads clarifications file and injects content as clarification_answers."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False
        ) as f:
            f.write("## Clarification 1\nAnswer: yes\n")
            f.flush()
            clarif_path = f.name

        context = {"clarifications_path": clarif_path}
        plan_before_stage("update_docs", context)
        assert context["clarification_answers"] == "## Clarification 1\nAnswer: yes\n"

        # Cleanup
        Path(clarif_path).unlink()

    def test_handles_missing_clarifications_file(self):
        """Failure: sets empty string when clarifications file doesn't exist."""
        context = {"clarifications_path": "/nonexistent/path/clarifications.md"}
        plan_before_stage("update_docs", context)
        assert context["clarification_answers"] == ""

    def test_handles_no_clarifications_path_in_context(self):
        """Failure: sets empty string when clarifications_path not in context."""
        context: dict = {}
        plan_before_stage("update_docs", context)
        assert context["clarification_answers"] == ""


class TestPlanAfterStageAssess:
    """Tests for plan_after_stage depth/tier extraction from assess artifacts."""

    def test_extracts_depth_and_tier_from_artifacts(self):
        """Happy: assess stage artifacts flow depth and tier into context."""
        context: dict = {}
        result = CompletionResult(
            is_complete=True,
            signal="STANDARD",
            artifacts={"depth": "standard", "tier": "STANDARD"},
        )
        plan_after_stage("assess", context, result)
        assert context["depth"] == "standard"
        assert context["tier"] == "STANDARD"

    def test_defaults_depth_and_tier_when_artifacts_missing(self):
        """Failure: defaults depth='standard' and tier='STANDARD' when artifacts empty."""
        context: dict = {}
        result = CompletionResult(
            is_complete=True,
            signal="STANDARD",
            artifacts={},
        )
        plan_after_stage("assess", context, result)
        assert context["depth"] == "standard"
        assert context["tier"] == "STANDARD"


class TestPlanAfterStageClarifications:
    """Tests for plan_after_stage clarifications_path handling on req_validate."""

    def test_stores_clarifications_path_on_clarifications_needed(self):
        """Happy: CLARIFICATIONS_NEEDED signal stores path from artifacts."""
        context: dict = {}
        result = CompletionResult(
            is_complete=True,
            signal="CLARIFICATIONS_NEEDED",
            artifacts={"clarifications_path": "/path/to/clarifications.md"},
        )
        plan_after_stage("req_validate", context, result)
        assert context["clarifications_path"] == "/path/to/clarifications.md"

    def test_does_not_store_path_on_plan_validated(self):
        """Failure: PLAN_VALIDATED signal does not set clarifications_path."""
        context: dict = {}
        result = CompletionResult(
            is_complete=True,
            signal="PLAN_VALIDATED",
            artifacts={"manifest_path": "/path/to/build.md"},
        )
        plan_after_stage("req_validate", context, result)
        assert "clarifications_path" not in context


class TestPlanHooksIgnoreOtherStages:
    """Tests that planning hooks are no-ops for non-planning stages."""

    def test_before_stage_ignores_build(self):
        """plan_before_stage does nothing for build stage."""
        context: dict = {"some_key": "value"}
        plan_before_stage("build", context)
        assert context == {"some_key": "value"}

    def test_after_stage_ignores_build(self):
        """plan_after_stage does nothing for build stage."""
        context: dict = {"some_key": "value"}
        result = CompletionResult(is_complete=True, signal="BUILD_COMPLETE")
        plan_after_stage("build", context, result)
        assert context == {"some_key": "value"}
