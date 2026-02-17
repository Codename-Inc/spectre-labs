"""Tests for plan_review stage prompt template."""

from pathlib import Path

from build_loop.pipeline.loader import create_plan_pipeline
from build_loop.pipeline.stage import Stage


PROMPTS_DIR = Path(__file__).parent.parent / "src" / "build_loop" / "prompts" / "planning"


class TestPlanReviewPromptContent:
    """Tests for plan_review.md prompt template content."""

    def _load_template(self) -> str:
        """Load the plan_review prompt template."""
        return (PROMPTS_DIR / "plan_review.md").read_text(encoding="utf-8")

    def test_template_contains_required_variables(self):
        """Happy: Template uses {plan_path}, {tasks_path}, and {task_context_path} variables."""
        template = self._load_template()
        assert "{plan_path}" in template
        assert "{tasks_path}" in template
        assert "{task_context_path}" in template

    def test_template_instructs_reading_plan_and_tasks(self):
        """Happy: Template instructs agent to read plan.md and tasks.md."""
        template = self._load_template()
        lower = template.lower()
        assert "plan" in lower
        assert "tasks" in lower
        assert "read" in lower

    def test_template_defines_simplification_categories(self):
        """Happy: Template defines specific categories of over-engineering to look for."""
        template = self._load_template()
        lower = template.lower()
        # Must identify concrete anti-patterns, not just say "simplify"
        assert "abstraction" in lower or "indirection" in lower
        assert "yagni" in lower or "premature" in lower

    def test_template_instructs_editing_in_place(self):
        """Happy: Template instructs agent to edit plan.md and tasks.md in-place."""
        template = self._load_template()
        lower = template.lower()
        assert "in-place" in lower or "in place" in lower
        assert "edit" in lower

    def test_template_contains_json_completion_block(self):
        """Happy: Template shows REVIEW_COMPLETE JSON with changes_summary."""
        template = self._load_template()
        assert "REVIEW_COMPLETE" in template
        assert "changes_summary" in template
        assert '"status"' in template

    def test_template_has_step_by_step_instructions(self):
        """Happy: Template provides numbered steps for autonomous execution."""
        template = self._load_template()
        assert "Step 1" in template or "### Step" in template or "step 1" in template.lower()

    def test_template_preserves_requirements(self):
        """Happy: Template explicitly warns not to remove requirements or functionality."""
        template = self._load_template()
        lower = template.lower()
        assert "requirement" in lower
        # Must distinguish simplification from deletion
        assert "remov" in lower or "delet" in lower or "drop" in lower

    def test_template_has_sufficient_depth(self):
        """Failure: Template must be comprehensive enough for autonomous operation (>1000 chars)."""
        template = self._load_template()
        assert len(template) > 1000, (
            f"Plan review prompt is too short ({len(template)} chars) for autonomous operation; "
            "needs detailed instructions for identifying over-engineering and applying simplifications"
        )

    def test_template_has_guardrails(self):
        """Failure: Template must include guardrails to prevent out-of-scope work."""
        template = self._load_template()
        assert "Do NOT" in template or "Do not" in template or "DO NOT" in template, (
            "Template should include guardrails to prevent the agent from doing work "
            "that belongs to later stages (code implementation, validation, etc.)"
        )

    def test_template_does_not_instruct_code_changes(self):
        """Failure: Template must not instruct agent to write or modify code files."""
        template = self._load_template()
        # Should only edit plan.md and tasks.md, not source code
        assert "write code" not in template.lower() or "do not write code" in template.lower() or "Do NOT" in template


class TestPlanReviewPromptSubstitution:
    """Tests for plan_review prompt variable substitution via Stage."""

    def test_substitution_replaces_all_variables(self):
        """Happy: All template variables are replaced when context is provided."""
        config = create_plan_pipeline()
        plan_review_config = config.stages["plan_review"]
        stage = Stage(config=plan_review_config, runner=None)

        context = {
            "plan_path": "/tmp/plan_output/specs/plan.md",
            "tasks_path": "/tmp/plan_output/specs/tasks.md",
            "task_context_path": "/tmp/plan_output/task_context.md",
            "context_files": "- `scope.md`\n- `design.md`",
        }
        prompt = stage.build_prompt(context)

        assert "{plan_path}" not in prompt
        assert "{tasks_path}" not in prompt
        assert "{task_context_path}" not in prompt
        # Substituted values should be present
        assert "/tmp/plan_output/specs/plan.md" in prompt
        assert "/tmp/plan_output/specs/tasks.md" in prompt
        assert "/tmp/plan_output/task_context.md" in prompt

    def test_substitution_missing_variable_leaves_placeholder(self):
        """Failure: Missing context variables leave {placeholder} in output."""
        config = create_plan_pipeline()
        plan_review_config = config.stages["plan_review"]
        stage = Stage(config=plan_review_config, runner=None)

        prompt = stage.build_prompt({})
        assert "{plan_path}" in prompt
        assert "{tasks_path}" in prompt
        assert "{task_context_path}" in prompt
