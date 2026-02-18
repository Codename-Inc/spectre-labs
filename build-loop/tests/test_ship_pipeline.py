"""Tests for ship pipeline factory function."""

from pathlib import Path

from build_loop.pipeline.completion import JsonCompletion
from build_loop.pipeline.executor import PipelineConfig
from build_loop.pipeline.loader import (
    PLAN_DENIED_TOOLS,
    create_ship_pipeline,
)
from build_loop.pipeline.stage import StageConfig


EXPECTED_STAGES = ["clean", "test", "rebase"]


class TestCreateShipPipeline:
    """Tests for create_ship_pipeline() factory."""

    def test_returns_pipeline_config_with_three_stages(self):
        """Happy: Pipeline has exactly 3 stages with correct names."""
        config = create_ship_pipeline()
        assert isinstance(config, PipelineConfig)
        assert len(config.stages) == 3
        assert set(config.stages.keys()) == set(EXPECTED_STAGES)

    def test_pipeline_name_and_start_stage(self):
        """Happy: Pipeline name is 'ship' and starts at clean."""
        config = create_ship_pipeline()
        assert config.name == "ship"
        assert config.start_stage == "clean"

    def test_end_signals(self):
        """Happy: Pipeline ends on SHIP_COMPLETE."""
        config = create_ship_pipeline()
        assert config.end_signals == ["SHIP_COMPLETE"]

    def test_all_stages_deny_interactive_tools(self):
        """Failure: All stages use PLAN_DENIED_TOOLS to block interactive/web tools."""
        config = create_ship_pipeline()
        for name, stage in config.stages.items():
            assert stage.denied_tools == PLAN_DENIED_TOOLS, (
                f"Stage '{name}' should use PLAN_DENIED_TOOLS"
            )


class TestShipStageTransitions:
    """Tests for stage transitions and completion signals."""

    def test_clean_stage_transitions(self):
        """Happy: Clean stage loops on CLEAN_TASK_COMPLETE and transitions to test on CLEAN_COMPLETE."""
        config = create_ship_pipeline()
        clean = config.stages["clean"]
        assert clean.transitions == {
            "CLEAN_TASK_COMPLETE": "clean",
            "CLEAN_COMPLETE": "test",
        }

    def test_test_stage_transitions(self):
        """Happy: Test stage loops on TEST_TASK_COMPLETE and transitions to rebase on TEST_COMPLETE."""
        config = create_ship_pipeline()
        test = config.stages["test"]
        assert test.transitions == {
            "TEST_TASK_COMPLETE": "test",
            "TEST_COMPLETE": "rebase",
        }

    def test_rebase_stage_has_no_transitions(self):
        """Happy: Rebase stage has empty transitions (end of pipeline)."""
        config = create_ship_pipeline()
        rebase = config.stages["rebase"]
        assert rebase.transitions == {}

    def test_all_stages_use_json_completion(self):
        """Happy: All stages use JsonCompletion with signal_field='status'."""
        config = create_ship_pipeline()
        for name, stage in config.stages.items():
            assert isinstance(stage.completion, JsonCompletion), (
                f"Stage '{name}' should use JsonCompletion"
            )
            assert stage.completion.signal_field == "status", (
                f"Stage '{name}' should use signal_field='status'"
            )

    def test_clean_completion_statuses(self):
        """Failure: Clean stage accepts CLEAN_TASK_COMPLETE and CLEAN_COMPLETE."""
        config = create_ship_pipeline()
        clean = config.stages["clean"]
        assert set(clean.completion.complete_statuses) == {
            "CLEAN_TASK_COMPLETE", "CLEAN_COMPLETE"
        }

    def test_test_completion_statuses(self):
        """Failure: Test stage accepts TEST_TASK_COMPLETE and TEST_COMPLETE."""
        config = create_ship_pipeline()
        test = config.stages["test"]
        assert set(test.completion.complete_statuses) == {
            "TEST_TASK_COMPLETE", "TEST_COMPLETE"
        }

    def test_rebase_completion_statuses(self):
        """Failure: Rebase stage only accepts SHIP_COMPLETE."""
        config = create_ship_pipeline()
        rebase = config.stages["rebase"]
        assert rebase.completion.complete_statuses == ["SHIP_COMPLETE"]


class TestShipStageIterations:
    """Tests for max_iterations per stage."""

    def test_clean_max_iterations_is_10(self):
        """Happy: Clean stage allows up to 10 iterations for 7 tasks."""
        config = create_ship_pipeline()
        assert config.stages["clean"].max_iterations == 10

    def test_test_max_iterations_is_10(self):
        """Happy: Test stage allows up to 10 iterations for 4 tasks."""
        config = create_ship_pipeline()
        assert config.stages["test"].max_iterations == 10

    def test_rebase_max_iterations_is_3(self):
        """Failure: Rebase stage is single context window, max 3 iterations."""
        config = create_ship_pipeline()
        assert config.stages["rebase"].max_iterations == 3


class TestShipPromptPaths:
    """Tests for prompt template path wiring."""

    def test_all_stages_reference_shipping_directory(self):
        """Happy: All stage prompt paths are under prompts/shipping/."""
        config = create_ship_pipeline()
        for name, stage in config.stages.items():
            assert "prompts/shipping" in stage.prompt_template, (
                f"Stage '{name}' prompt should be in prompts/shipping/"
            )

    def test_each_stage_has_named_template(self):
        """Happy: Each stage references its own .md template file."""
        config = create_ship_pipeline()
        expected_templates = {
            "clean": "clean.md",
            "test": "test.md",
            "rebase": "rebase.md",
        }
        for name, expected_file in expected_templates.items():
            stage = config.stages[name]
            assert stage.prompt_template.endswith(expected_file), (
                f"Stage '{name}' should use template '{expected_file}', "
                f"got '{stage.prompt_template}'"
            )

    def test_prompt_paths_are_absolute(self):
        """Failure: All prompt template paths are absolute."""
        config = create_ship_pipeline()
        for name, stage in config.stages.items():
            assert Path(stage.prompt_template).is_absolute(), (
                f"Stage '{name}' prompt path should be absolute"
            )
