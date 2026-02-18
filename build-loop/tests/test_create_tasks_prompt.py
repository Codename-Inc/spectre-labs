"""Tests for create_tasks stage prompt template."""

from pathlib import Path

from build_loop.pipeline.loader import create_plan_pipeline
from build_loop.pipeline.stage import Stage


PROMPTS_DIR = Path(__file__).parent.parent / "src" / "build_loop" / "prompts" / "planning"


class TestCreateTasksPromptContent:
    """Tests for create_tasks.md prompt template content."""

    def _load_template(self) -> str:
        """Load the create_tasks prompt template."""
        return (PROMPTS_DIR / "create_tasks.md").read_text(encoding="utf-8")

    def test_template_contains_required_variables(self):
        """Happy: Template uses {plan_path}, {task_context_path}, {context_files}, and {output_dir} variables."""
        template = self._load_template()
        assert "{plan_path}" in template
        assert "{task_context_path}" in template
        assert "{context_files}" in template
        assert "{output_dir}" in template

    def test_template_instructs_reading_plan(self):
        """Happy: Template instructs agent to read plan.md (conditionally for LIGHT tier)."""
        template = self._load_template()
        lower = template.lower()
        assert "plan" in lower
        assert "read" in lower
        # Must handle LIGHT case where plan doesn't exist
        assert "light" in lower

    def test_template_instructs_reading_task_context(self):
        """Happy: Template instructs agent to read task_context.md for research findings."""
        template = self._load_template()
        lower = template.lower()
        assert "task_context" in lower
        assert "read" in lower

    def test_template_instructs_reading_scope_docs(self):
        """Happy: Template instructs agent to read scope documents."""
        template = self._load_template()
        lower = template.lower()
        assert "scope" in lower or "context_files" in lower
        assert "read" in lower

    def test_template_specifies_tasks_output_path(self):
        """Happy: Template specifies writing tasks to {output_dir}/specs/tasks.md."""
        template = self._load_template()
        assert "specs/tasks.md" in template

    def test_template_defines_task_hierarchy(self):
        """Happy: Template defines 4-level hierarchy: Phase > Parent > Sub-task > Acceptance Criteria."""
        template = self._load_template()
        lower = template.lower()
        assert "phase" in lower
        assert "parent" in lower
        assert "sub-task" in lower or "sub task" in lower or "subtask" in lower
        assert "acceptance criteria" in lower or "criteria" in lower

    def test_template_specifies_produces_consumed_by(self):
        """Happy: Template requires Produces/Consumed by/Replaces fields for integration-aware tasks."""
        template = self._load_template()
        assert "Produces" in template
        assert "Consumed by" in template
        assert "Replaces" in template

    def test_template_includes_requirements_tracing(self):
        """Happy: Template requires cross-referencing tasks to scope requirements."""
        template = self._load_template()
        lower = template.lower()
        assert "requirement" in lower
        assert "coverage" in lower or "trace" in lower or "cross-reference" in lower or "req-" in lower

    def test_template_includes_execution_strategies(self):
        """Happy: Template instructs generating sequential and parallel execution strategies."""
        template = self._load_template()
        lower = template.lower()
        assert "sequential" in lower
        assert "parallel" in lower
        assert "wave" in lower or "concurrent" in lower

    def test_template_contains_json_completion_block(self):
        """Happy: Template shows TASKS_COMPLETE JSON with tasks_path artifact."""
        template = self._load_template()
        assert "TASKS_COMPLETE" in template
        assert "tasks_path" in template
        assert '"status"' in template

    def test_template_has_step_by_step_instructions(self):
        """Happy: Template provides numbered steps for autonomous execution."""
        template = self._load_template()
        assert "Step 1" in template or "### Step" in template or "step 1" in template.lower()

    def test_template_has_sufficient_depth(self):
        """Failure: Template must be comprehensive enough for autonomous operation (>1500 chars)."""
        template = self._load_template()
        assert len(template) > 1500, (
            f"Create tasks prompt is too short ({len(template)} chars) for autonomous operation; "
            "needs detailed instructions for hierarchical task breakdown including structure, "
            "integration-awareness, and execution strategy guidance"
        )

    def test_template_has_guardrails(self):
        """Failure: Template must include guardrails to prevent scope creep and code writing."""
        template = self._load_template()
        assert "Do NOT" in template or "Do not" in template or "DO NOT" in template, (
            "Template should include guardrails to prevent the agent from writing code, "
            "adding unrequested features, or doing work that belongs to later stages"
        )


class TestCreateTasksSubagentDispatch:
    """Tests for optional subagent dispatch in create_tasks.md."""

    def _load_template(self) -> str:
        return (PROMPTS_DIR / "create_tasks.md").read_text(encoding="utf-8")

    def test_template_contains_subagent_dispatch_instructions(self):
        """Happy: Template includes optional subagent dispatch via Task tool."""
        template = self._load_template()
        assert "Task" in template and "subagent" in template.lower(), (
            "Template should include optional subagent dispatch instructions for "
            "complex task breakdowns needing codebase location research"
        )

    def test_dispatch_references_finder_agent(self):
        """Happy: Template dispatches @finder subagents for codebase location research."""
        template = self._load_template()
        lower = template.lower()
        assert "finder" in lower, (
            "Template should reference @finder subagent type for locating files "
            "during complex task breakdowns"
        )

    def test_dispatch_is_conditional_on_complexity(self):
        """Happy: Subagent dispatch is conditional on task complexity or scope size."""
        template = self._load_template()
        lower = template.lower()
        assert "subagent" in lower and ("complex" in lower or "large" in lower or "multiple" in lower), (
            "Subagent dispatch should be conditional on complexity/scope"
        )

    def test_dispatch_is_optional_not_mandatory(self):
        """Failure: Subagent dispatch must be optional, not required for all task breakdowns."""
        template = self._load_template()
        lower = template.lower()
        assert "optional" in lower or "if" in lower or "when" in lower, (
            "Subagent dispatch should be optional/conditional, not mandatory for every task breakdown"
        )


class TestCreateTasksPromptSubstitution:
    """Tests for create_tasks prompt variable substitution via Stage."""

    def test_substitution_replaces_all_variables(self):
        """Happy: All template variables are replaced when context is provided."""
        config = create_plan_pipeline()
        create_tasks_config = config.stages["create_tasks"]
        stage = Stage(config=create_tasks_config, runner=None)

        context = {
            "plan_path": "/tmp/plan_output/specs/plan.md",
            "task_context_path": "/tmp/plan_output/task_context.md",
            "context_files": "- `scope.md`\n- `design.md`",
            "output_dir": "/tmp/plan_output",
        }
        prompt = stage.build_prompt(context)

        assert "{plan_path}" not in prompt
        assert "{task_context_path}" not in prompt
        assert "{context_files}" not in prompt
        assert "{output_dir}" not in prompt
        # Substituted values should be present
        assert "/tmp/plan_output/specs/plan.md" in prompt
        assert "/tmp/plan_output/task_context.md" in prompt
        assert "scope.md" in prompt
        assert "/tmp/plan_output" in prompt

    def test_substitution_missing_variable_leaves_placeholder(self):
        """Failure: Missing context variables leave {placeholder} in output."""
        config = create_plan_pipeline()
        create_tasks_config = config.stages["create_tasks"]
        stage = Stage(config=create_tasks_config, runner=None)

        prompt = stage.build_prompt({})
        assert "{plan_path}" in prompt
        assert "{task_context_path}" in prompt
        assert "{context_files}" in prompt
        assert "{output_dir}" in prompt
