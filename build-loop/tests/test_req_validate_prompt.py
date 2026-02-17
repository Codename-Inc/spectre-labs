"""Tests for req_validate stage prompt template."""

from pathlib import Path

from build_loop.pipeline.loader import create_plan_pipeline
from build_loop.pipeline.stage import Stage


PROMPTS_DIR = Path(__file__).parent.parent / "src" / "build_loop" / "prompts" / "planning"


class TestReqValidatePromptContent:
    """Tests for req_validate.md prompt template content."""

    def _load_template(self) -> str:
        """Load the req_validate prompt template."""
        return (PROMPTS_DIR / "req_validate.md").read_text(encoding="utf-8")

    def test_template_contains_required_variables(self):
        """Happy: Template uses {context_files}, {plan_path}, {tasks_path}, {output_dir}."""
        template = self._load_template()
        assert "{context_files}" in template
        assert "{plan_path}" in template
        assert "{tasks_path}" in template
        assert "{output_dir}" in template

    def test_template_instructs_reading_scope_and_plan(self):
        """Happy: Template instructs agent to read scope docs, plan, and tasks."""
        template = self._load_template()
        lower = template.lower()
        assert "scope" in lower
        assert "plan" in lower
        assert "tasks" in lower
        assert "read" in lower

    def test_template_defines_coverage_analysis(self):
        """Happy: Template defines how to cross-reference requirements against tasks."""
        template = self._load_template()
        lower = template.lower()
        assert "requirement" in lower
        assert "coverage" in lower or "cross-reference" in lower or "trace" in lower

    def test_template_defines_validated_output(self):
        """Happy: Template shows PLAN_VALIDATED JSON with manifest_path artifact."""
        template = self._load_template()
        assert "PLAN_VALIDATED" in template
        assert "manifest_path" in template
        assert '"status"' in template

    def test_template_defines_clarifications_output(self):
        """Happy: Template shows CLARIFICATIONS_NEEDED JSON with clarifications_path."""
        template = self._load_template()
        assert "CLARIFICATIONS_NEEDED" in template
        assert "clarifications_path" in template

    def test_template_instructs_manifest_creation(self):
        """Happy: Template instructs writing build.md manifest with YAML frontmatter."""
        template = self._load_template()
        lower = template.lower()
        assert "manifest" in lower or "build.md" in lower
        assert "yaml" in lower or "frontmatter" in lower

    def test_template_instructs_clarifications_file(self):
        """Happy: Template instructs writing clarifications file with response blocks."""
        template = self._load_template()
        lower = template.lower()
        assert "clarification" in lower
        assert "<response>" in lower or "response" in lower

    def test_template_has_step_by_step_instructions(self):
        """Happy: Template provides numbered steps for autonomous execution."""
        template = self._load_template()
        assert "Step 1" in template or "### Step" in template

    def test_template_has_sufficient_depth(self):
        """Failure: Template must be comprehensive enough for autonomous operation (>1000 chars)."""
        template = self._load_template()
        assert len(template) > 1000, (
            f"Req validate prompt is too short ({len(template)} chars) for autonomous operation; "
            "needs detailed instructions for requirements validation, manifest generation, and clarifications"
        )

    def test_template_has_guardrails(self):
        """Failure: Template must include guardrails to prevent out-of-scope work."""
        template = self._load_template()
        assert "Do NOT" in template or "Do not" in template or "DO NOT" in template, (
            "Template should include guardrails to prevent the agent from doing work "
            "that belongs to other stages (code implementation, simplification, etc.)"
        )

    def test_template_does_not_instruct_code_changes(self):
        """Failure: Template must not instruct agent to write or modify source code."""
        template = self._load_template()
        # Should only write manifest and clarifications, not source code
        assert "write code" not in template.lower() or "do not write code" in template.lower() or "Do NOT" in template

    def test_template_manifest_includes_validate_flag(self):
        """Happy: Manifest YAML frontmatter example includes validate: true."""
        template = self._load_template()
        assert "validate: true" in template or "validate:" in template


class TestReqValidatePromptSubstitution:
    """Tests for req_validate prompt variable substitution via Stage."""

    def test_substitution_replaces_all_variables(self):
        """Happy: All template variables are replaced when context is provided."""
        config = create_plan_pipeline()
        req_validate_config = config.stages["req_validate"]
        stage = Stage(config=req_validate_config, runner=None)

        context = {
            "context_files": "- `scope.md`\n- `design.md`",
            "plan_path": "/tmp/plan_output/specs/plan.md",
            "tasks_path": "/tmp/plan_output/specs/tasks.md",
            "output_dir": "/tmp/plan_output",
        }
        prompt = stage.build_prompt(context)

        assert "{context_files}" not in prompt
        assert "{plan_path}" not in prompt
        assert "{tasks_path}" not in prompt
        assert "{output_dir}" not in prompt
        # Substituted values should be present
        assert "/tmp/plan_output/specs/plan.md" in prompt
        assert "/tmp/plan_output/specs/tasks.md" in prompt
        assert "/tmp/plan_output" in prompt

    def test_substitution_missing_variable_leaves_placeholder(self):
        """Failure: Missing context variables leave {placeholder} in output."""
        config = create_plan_pipeline()
        req_validate_config = config.stages["req_validate"]
        stage = Stage(config=req_validate_config, runner=None)

        prompt = stage.build_prompt({})
        assert "{context_files}" in prompt
        assert "{plan_path}" in prompt
        assert "{tasks_path}" in prompt
        assert "{output_dir}" in prompt
