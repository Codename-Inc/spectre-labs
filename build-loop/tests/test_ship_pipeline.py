"""Tests for ship pipeline factory function — 8 sub-stage architecture."""

from pathlib import Path

from build_loop.pipeline.completion import JsonCompletion
from build_loop.pipeline.executor import PipelineConfig
from build_loop.pipeline.loader import (
    PLAN_DENIED_TOOLS,
    create_ship_pipeline,
)
from build_loop.pipeline.stage import StageConfig


EXPECTED_STAGES = [
    "clean_discover",
    "clean_investigate",
    "clean_execute",
    "test_plan",
    "test_execute",
    "test_verify",
    "test_commit",
    "rebase",
]


class TestCreateShipPipeline:
    """Tests for create_ship_pipeline() factory — basic config."""

    def test_returns_pipeline_config_with_eight_stages(self):
        """Happy: Pipeline has exactly 8 stages with correct names."""
        config = create_ship_pipeline()
        assert isinstance(config, PipelineConfig)
        assert len(config.stages) == 8
        assert set(config.stages.keys()) == set(EXPECTED_STAGES)

    def test_pipeline_name_and_start_stage(self):
        """Happy: Pipeline name is 'ship' and starts at clean_discover."""
        config = create_ship_pipeline()
        assert config.name == "ship"
        assert config.start_stage == "clean_discover"

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

    def test_task_tool_not_in_any_denied_tools(self):
        """Failure: Task tool must not be denied in any stage (unblocked in Phase 1)."""
        config = create_ship_pipeline()
        for name, stage in config.stages.items():
            assert "Task" not in stage.denied_tools, (
                f"Stage '{name}' should not deny Task tool"
            )


class TestShipStageTransitions:
    """Tests for stage transitions forming the full 8-stage chain."""

    def test_clean_discover_transitions(self):
        """Happy: clean_discover loops on task complete, transitions to clean_investigate."""
        config = create_ship_pipeline()
        stage = config.stages["clean_discover"]
        assert stage.transitions == {
            "CLEAN_DISCOVER_TASK_COMPLETE": "clean_discover",
            "CLEAN_DISCOVER_COMPLETE": "clean_investigate",
        }

    def test_clean_investigate_transitions(self):
        """Happy: clean_investigate loops on task complete, transitions to clean_execute."""
        config = create_ship_pipeline()
        stage = config.stages["clean_investigate"]
        assert stage.transitions == {
            "CLEAN_INVESTIGATE_TASK_COMPLETE": "clean_investigate",
            "CLEAN_INVESTIGATE_COMPLETE": "clean_execute",
        }

    def test_clean_execute_transitions(self):
        """Happy: clean_execute loops on task complete, transitions to test_plan."""
        config = create_ship_pipeline()
        stage = config.stages["clean_execute"]
        assert stage.transitions == {
            "CLEAN_EXECUTE_TASK_COMPLETE": "clean_execute",
            "CLEAN_EXECUTE_COMPLETE": "test_plan",
        }

    def test_test_plan_transitions(self):
        """Happy: test_plan loops on task complete, transitions to test_execute."""
        config = create_ship_pipeline()
        stage = config.stages["test_plan"]
        assert stage.transitions == {
            "TEST_PLAN_TASK_COMPLETE": "test_plan",
            "TEST_PLAN_COMPLETE": "test_execute",
        }

    def test_test_execute_transitions(self):
        """Happy: test_execute loops on task complete, transitions to test_verify."""
        config = create_ship_pipeline()
        stage = config.stages["test_execute"]
        assert stage.transitions == {
            "TEST_EXECUTE_TASK_COMPLETE": "test_execute",
            "TEST_EXECUTE_COMPLETE": "test_verify",
        }

    def test_test_verify_transitions(self):
        """Happy: test_verify loops on task complete, transitions to test_commit."""
        config = create_ship_pipeline()
        stage = config.stages["test_verify"]
        assert stage.transitions == {
            "TEST_VERIFY_TASK_COMPLETE": "test_verify",
            "TEST_VERIFY_COMPLETE": "test_commit",
        }

    def test_test_commit_transitions(self):
        """Happy: test_commit transitions to rebase on complete."""
        config = create_ship_pipeline()
        stage = config.stages["test_commit"]
        assert stage.transitions == {
            "TEST_COMMIT_COMPLETE": "rebase",
        }

    def test_rebase_stage_has_no_transitions(self):
        """Happy: Rebase stage has empty transitions (end of pipeline)."""
        config = create_ship_pipeline()
        rebase = config.stages["rebase"]
        assert rebase.transitions == {}

    def test_full_transition_chain(self):
        """Failure: Verify entire chain from clean_discover to rebase end."""
        config = create_ship_pipeline()
        expected_chain = [
            ("clean_discover", "CLEAN_DISCOVER_COMPLETE", "clean_investigate"),
            ("clean_investigate", "CLEAN_INVESTIGATE_COMPLETE", "clean_execute"),
            ("clean_execute", "CLEAN_EXECUTE_COMPLETE", "test_plan"),
            ("test_plan", "TEST_PLAN_COMPLETE", "test_execute"),
            ("test_execute", "TEST_EXECUTE_COMPLETE", "test_verify"),
            ("test_verify", "TEST_VERIFY_COMPLETE", "test_commit"),
            ("test_commit", "TEST_COMMIT_COMPLETE", "rebase"),
        ]
        for stage_name, signal, target in expected_chain:
            stage = config.stages[stage_name]
            assert stage.transitions.get(signal) == target, (
                f"Stage '{stage_name}' signal '{signal}' should transition to '{target}'"
            )

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


class TestShipCompletionStatuses:
    """Tests for completion statuses per stage."""

    def test_clean_discover_statuses(self):
        """Happy: clean_discover accepts task complete and stage complete signals."""
        config = create_ship_pipeline()
        stage = config.stages["clean_discover"]
        assert set(stage.completion.complete_statuses) == {
            "CLEAN_DISCOVER_TASK_COMPLETE", "CLEAN_DISCOVER_COMPLETE"
        }

    def test_clean_investigate_statuses(self):
        """Happy: clean_investigate accepts task complete and stage complete signals."""
        config = create_ship_pipeline()
        stage = config.stages["clean_investigate"]
        assert set(stage.completion.complete_statuses) == {
            "CLEAN_INVESTIGATE_TASK_COMPLETE", "CLEAN_INVESTIGATE_COMPLETE"
        }

    def test_clean_execute_statuses(self):
        """Happy: clean_execute accepts task complete and stage complete signals."""
        config = create_ship_pipeline()
        stage = config.stages["clean_execute"]
        assert set(stage.completion.complete_statuses) == {
            "CLEAN_EXECUTE_TASK_COMPLETE", "CLEAN_EXECUTE_COMPLETE"
        }

    def test_test_plan_statuses(self):
        """Happy: test_plan accepts task complete and stage complete signals."""
        config = create_ship_pipeline()
        stage = config.stages["test_plan"]
        assert set(stage.completion.complete_statuses) == {
            "TEST_PLAN_TASK_COMPLETE", "TEST_PLAN_COMPLETE"
        }

    def test_test_execute_statuses(self):
        """Happy: test_execute accepts task complete and stage complete signals."""
        config = create_ship_pipeline()
        stage = config.stages["test_execute"]
        assert set(stage.completion.complete_statuses) == {
            "TEST_EXECUTE_TASK_COMPLETE", "TEST_EXECUTE_COMPLETE"
        }

    def test_test_verify_statuses(self):
        """Happy: test_verify accepts task complete and stage complete signals."""
        config = create_ship_pipeline()
        stage = config.stages["test_verify"]
        assert set(stage.completion.complete_statuses) == {
            "TEST_VERIFY_TASK_COMPLETE", "TEST_VERIFY_COMPLETE"
        }

    def test_test_commit_statuses(self):
        """Failure: test_commit only accepts TEST_COMMIT_COMPLETE."""
        config = create_ship_pipeline()
        stage = config.stages["test_commit"]
        assert stage.completion.complete_statuses == ["TEST_COMMIT_COMPLETE"]

    def test_rebase_statuses(self):
        """Failure: Rebase stage only accepts SHIP_COMPLETE."""
        config = create_ship_pipeline()
        rebase = config.stages["rebase"]
        assert rebase.completion.complete_statuses == ["SHIP_COMPLETE"]


class TestShipStageIterations:
    """Tests for max_iterations per stage."""

    def test_clean_discover_uses_max_iterations(self):
        """Happy: clean_discover uses the provided max_iterations."""
        config = create_ship_pipeline(max_iterations=15)
        assert config.stages["clean_discover"].max_iterations == 15

    def test_clean_investigate_uses_max_iterations(self):
        """Happy: clean_investigate uses the provided max_iterations."""
        config = create_ship_pipeline(max_iterations=15)
        assert config.stages["clean_investigate"].max_iterations == 15

    def test_clean_execute_uses_max_iterations(self):
        """Happy: clean_execute uses the provided max_iterations."""
        config = create_ship_pipeline(max_iterations=15)
        assert config.stages["clean_execute"].max_iterations == 15

    def test_test_plan_uses_max_iterations(self):
        """Happy: test_plan uses the provided max_iterations."""
        config = create_ship_pipeline(max_iterations=15)
        assert config.stages["test_plan"].max_iterations == 15

    def test_test_execute_uses_max_iterations(self):
        """Happy: test_execute uses the provided max_iterations."""
        config = create_ship_pipeline(max_iterations=15)
        assert config.stages["test_execute"].max_iterations == 15

    def test_test_verify_capped_at_3(self):
        """Failure: test_verify is capped at min(max_iterations, 3)."""
        config = create_ship_pipeline(max_iterations=15)
        assert config.stages["test_verify"].max_iterations == 3

    def test_test_verify_uses_max_when_lower(self):
        """Failure: test_verify uses max_iterations when it's lower than 3."""
        config = create_ship_pipeline(max_iterations=2)
        assert config.stages["test_verify"].max_iterations == 2

    def test_test_commit_always_1(self):
        """Failure: test_commit is always 1 iteration."""
        config = create_ship_pipeline(max_iterations=15)
        assert config.stages["test_commit"].max_iterations == 1

    def test_rebase_capped_at_3(self):
        """Failure: Rebase stage is capped at min(max_iterations, 3)."""
        config = create_ship_pipeline(max_iterations=15)
        assert config.stages["rebase"].max_iterations == 3

    def test_default_max_iterations_is_10(self):
        """Happy: Default max_iterations is 10 for uncapped stages."""
        config = create_ship_pipeline()
        assert config.stages["clean_discover"].max_iterations == 10
        assert config.stages["test_execute"].max_iterations == 10


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
            "clean_discover": "clean_discover.md",
            "clean_investigate": "clean_investigate.md",
            "clean_execute": "clean_execute.md",
            "test_plan": "test_plan.md",
            "test_execute": "test_execute.md",
            "test_verify": "test_verify.md",
            "test_commit": "test_commit.md",
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
