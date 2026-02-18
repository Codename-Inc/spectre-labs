"""Tests for planning pipeline factory functions."""

from pathlib import Path

from build_loop.pipeline.completion import JsonCompletion
from build_loop.pipeline.executor import PipelineConfig
from build_loop.pipeline.loader import (
    PLAN_DENIED_TOOLS,
    PLAN_RESEARCH_DENIED_TOOLS,
    create_plan_pipeline,
    create_plan_resume_pipeline,
)
from build_loop.pipeline.stage import StageConfig


EXPECTED_STAGES = [
    "research",
    "assess",
    "create_plan",
    "create_tasks",
    "plan_review",
    "req_validate",
    "update_docs",
]


class TestCreatePlanPipeline:
    """Tests for create_plan_pipeline() factory."""

    def test_returns_pipeline_config_with_seven_stages(self):
        """Happy: Pipeline has exactly 7 stages with correct names."""
        config = create_plan_pipeline()
        assert isinstance(config, PipelineConfig)
        assert len(config.stages) == 7
        assert set(config.stages.keys()) == set(EXPECTED_STAGES)

    def test_start_stage_is_research(self):
        """Happy: Pipeline starts at the research stage."""
        config = create_plan_pipeline()
        assert config.start_stage == "research"

    def test_end_signals(self):
        """Happy: Pipeline ends on PLAN_VALIDATED or PLAN_READY."""
        config = create_plan_pipeline()
        assert "PLAN_VALIDATED" in config.end_signals
        assert "PLAN_READY" in config.end_signals

    def test_all_stages_use_json_completion(self):
        """Happy: All stages use JsonCompletion for consistency."""
        config = create_plan_pipeline()
        for name, stage in config.stages.items():
            assert isinstance(stage.completion, JsonCompletion), (
                f"Stage '{name}' should use JsonCompletion"
            )

    def test_assess_light_transitions_to_create_tasks(self):
        """Failure-mode: LIGHT signal skips create_plan, goes to create_tasks."""
        config = create_plan_pipeline()
        assess = config.stages["assess"]
        assert assess.transitions["LIGHT"] == "create_tasks"

    def test_assess_standard_transitions_to_create_plan(self):
        """Failure-mode: STANDARD signal routes to create_plan."""
        config = create_plan_pipeline()
        assess = config.stages["assess"]
        assert assess.transitions["STANDARD"] == "create_plan"

    def test_assess_comprehensive_transitions_to_create_plan(self):
        """Failure-mode: COMPREHENSIVE signal also routes to create_plan."""
        config = create_plan_pipeline()
        assess = config.stages["assess"]
        assert assess.transitions["COMPREHENSIVE"] == "create_plan"


class TestResearchStageToolAccess:
    """Tests for research stage expanded tool access."""

    def test_research_stage_allows_web_tools(self):
        """Happy: Research stage denied_tools does not include WebSearch/WebFetch."""
        config = create_plan_pipeline()
        research = config.stages["research"]
        assert research.denied_tools is not None
        assert "WebSearch" not in research.denied_tools
        assert "WebFetch" not in research.denied_tools

    def test_non_research_stages_deny_web_tools(self):
        """Failure-mode: All non-research stages deny WebSearch and WebFetch."""
        config = create_plan_pipeline()
        non_research_stages = [
            name for name in config.stages if name != "research"
        ]
        for name in non_research_stages:
            stage = config.stages[name]
            assert stage.denied_tools is not None, (
                f"Stage '{name}' should have denied_tools set"
            )
            assert "WebSearch" in stage.denied_tools, (
                f"Stage '{name}' should deny WebSearch"
            )
            assert "WebFetch" in stage.denied_tools, (
                f"Stage '{name}' should deny WebFetch"
            )

    def test_research_still_denies_interactive_tools(self):
        """Failure-mode: Research stage still blocks AskUserQuestion, EnterPlanMode, etc."""
        config = create_plan_pipeline()
        research = config.stages["research"]
        assert "AskUserQuestion" in research.denied_tools
        assert "EnterPlanMode" in research.denied_tools

    def test_research_allows_task_tool(self):
        """Happy: Research stage allows Task for subagent dispatch."""
        config = create_plan_pipeline()
        research = config.stages["research"]
        assert "Task" not in research.denied_tools


class TestPromptTemplatePaths:
    """Tests for prompt template path wiring."""

    def test_all_stages_reference_planning_directory(self):
        """Happy: All stage prompt paths are under prompts/planning/."""
        config = create_plan_pipeline()
        for name, stage in config.stages.items():
            path = Path(stage.prompt_template)
            assert "prompts/planning" in str(path), (
                f"Stage '{name}' prompt should be in prompts/planning/"
            )

    def test_each_stage_has_named_template(self):
        """Happy: Each stage references its own .md template file."""
        config = create_plan_pipeline()
        expected_templates = {
            "research": "research.md",
            "assess": "assess.md",
            "create_plan": "create_plan.md",
            "create_tasks": "create_tasks.md",
            "plan_review": "plan_review.md",
            "req_validate": "req_validate.md",
            "update_docs": "update_docs.md",
        }
        for name, expected_file in expected_templates.items():
            stage = config.stages[name]
            assert stage.prompt_template.endswith(expected_file), (
                f"Stage '{name}' should use template '{expected_file}', "
                f"got '{stage.prompt_template}'"
            )

    def test_prompt_paths_are_absolute(self):
        """Failure-mode: All prompt template paths are absolute."""
        config = create_plan_pipeline()
        for name, stage in config.stages.items():
            assert Path(stage.prompt_template).is_absolute(), (
                f"Stage '{name}' prompt path should be absolute"
            )


class TestCreatePlanResumePipeline:
    """Tests for create_plan_resume_pipeline() factory."""

    def test_returns_single_stage_pipeline(self):
        """Happy: Resume pipeline has exactly 1 stage (update_docs)."""
        config = create_plan_resume_pipeline()
        assert isinstance(config, PipelineConfig)
        assert len(config.stages) == 1
        assert "update_docs" in config.stages

    def test_start_stage_is_update_docs(self):
        """Happy: Resume pipeline starts at update_docs."""
        config = create_plan_resume_pipeline()
        assert config.start_stage == "update_docs"

    def test_end_signals_plan_ready(self):
        """Failure-mode: Resume pipeline ends on PLAN_READY only."""
        config = create_plan_resume_pipeline()
        assert config.end_signals == ["PLAN_READY"]

    def test_update_docs_uses_json_completion(self):
        """Failure-mode: update_docs stage uses JsonCompletion with PLAN_READY."""
        config = create_plan_resume_pipeline()
        stage = config.stages["update_docs"]
        assert isinstance(stage.completion, JsonCompletion)
        assert "PLAN_READY" in stage.completion.complete_statuses
