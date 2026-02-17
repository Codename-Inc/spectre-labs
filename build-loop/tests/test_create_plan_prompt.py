"""Tests for create_plan stage prompt template."""

from pathlib import Path

from build_loop.pipeline.loader import create_plan_pipeline
from build_loop.pipeline.stage import Stage


PROMPTS_DIR = Path(__file__).parent.parent / "src" / "build_loop" / "prompts" / "planning"


class TestCreatePlanPromptContent:
    """Tests for create_plan.md prompt template content."""

    def _load_template(self) -> str:
        """Load the create_plan prompt template."""
        return (PROMPTS_DIR / "create_plan.md").read_text(encoding="utf-8")

    def test_template_contains_required_variables(self):
        """Happy: Template uses {task_context_path}, {context_files}, {depth}, and {output_dir} variables."""
        template = self._load_template()
        assert "{task_context_path}" in template
        assert "{context_files}" in template
        assert "{depth}" in template
        assert "{output_dir}" in template

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
        assert "scope" in lower or "context" in lower
        assert "read" in lower

    def test_template_specifies_plan_output_path(self):
        """Happy: Template specifies writing plan to {output_dir}/specs/plan.md."""
        template = self._load_template()
        assert "specs/plan.md" in template

    def test_template_specifies_plan_structure_sections(self):
        """Happy: Template defines required sections for plan.md (overview, technical approach, critical files)."""
        template = self._load_template()
        lower = template.lower()
        assert "overview" in lower
        assert "technical approach" in lower or "technical" in lower
        assert "critical files" in lower or "key files" in lower or "critical" in lower

    def test_template_uses_depth_for_section_detail(self):
        """Happy: Template references {depth} to determine section detail level."""
        template = self._load_template()
        lower = template.lower()
        # Must distinguish between standard and comprehensive depth
        assert "standard" in lower
        assert "comprehensive" in lower

    def test_template_contains_json_completion_block(self):
        """Happy: Template shows PLAN_COMPLETE JSON with plan_path artifact."""
        template = self._load_template()
        assert "PLAN_COMPLETE" in template
        assert "plan_path" in template
        assert '"status"' in template

    def test_template_has_step_by_step_instructions(self):
        """Happy: Template provides numbered steps for autonomous execution."""
        template = self._load_template()
        assert "Step 1" in template or "### Step" in template or "step 1" in template.lower()

    def test_template_has_sufficient_depth(self):
        """Failure: Template must be comprehensive enough for autonomous operation (>1000 chars)."""
        template = self._load_template()
        assert len(template) > 1000, (
            f"Create plan prompt is too short ({len(template)} chars) for autonomous operation; "
            "needs detailed instructions for plan generation including structure and depth guidance"
        )

    def test_template_has_guardrails(self):
        """Failure: Template must include guardrails to prevent scope creep."""
        template = self._load_template()
        assert "Do NOT" in template or "Do not" in template or "DO NOT" in template, (
            "Template should include guardrails to prevent the agent from doing work "
            "that belongs to later stages (task breakdown, code implementation, etc.)"
        )


class TestCreatePlanPromptSubstitution:
    """Tests for create_plan prompt variable substitution via Stage."""

    def test_substitution_replaces_all_variables(self):
        """Happy: All template variables are replaced when context is provided."""
        config = create_plan_pipeline()
        create_plan_config = config.stages["create_plan"]
        stage = Stage(config=create_plan_config, runner=None)

        context = {
            "task_context_path": "/tmp/plan_output/task_context.md",
            "context_files": "- `scope.md`\n- `design.md`",
            "depth": "standard",
            "output_dir": "/tmp/plan_output",
        }
        prompt = stage.build_prompt(context)

        assert "{task_context_path}" not in prompt
        assert "{context_files}" not in prompt
        assert "{depth}" not in prompt
        assert "{output_dir}" not in prompt
        # Substituted values should be present
        assert "/tmp/plan_output/task_context.md" in prompt
        assert "scope.md" in prompt
        assert "standard" in prompt
        assert "/tmp/plan_output" in prompt

    def test_substitution_missing_variable_leaves_placeholder(self):
        """Failure: Missing context variables leave {placeholder} in output."""
        config = create_plan_pipeline()
        create_plan_config = config.stages["create_plan"]
        stage = Stage(config=create_plan_config, runner=None)

        prompt = stage.build_prompt({})
        assert "{task_context_path}" in prompt
        assert "{context_files}" in prompt
        assert "{depth}" in prompt
        assert "{output_dir}" in prompt
