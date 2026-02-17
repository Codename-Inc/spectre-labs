"""Tests for update_docs stage prompt template."""

from pathlib import Path

from build_loop.pipeline.loader import create_plan_pipeline, create_plan_resume_pipeline
from build_loop.pipeline.stage import Stage


PROMPTS_DIR = Path(__file__).parent.parent / "src" / "build_loop" / "prompts" / "planning"


class TestUpdateDocsPromptContent:
    """Tests for update_docs.md prompt template content."""

    def _load_template(self) -> str:
        """Load the update_docs prompt template."""
        return (PROMPTS_DIR / "update_docs.md").read_text(encoding="utf-8")

    def test_template_contains_required_variables(self):
        """Happy: Template uses {clarification_answers}, {context_files}, {plan_path}, {tasks_path}, {output_dir}."""
        template = self._load_template()
        assert "{clarification_answers}" in template
        assert "{context_files}" in template
        assert "{plan_path}" in template
        assert "{tasks_path}" in template
        assert "{output_dir}" in template

    def test_template_instructs_reading_clarifications(self):
        """Happy: Template instructs agent to read clarification answers."""
        template = self._load_template()
        lower = template.lower()
        assert "clarification" in lower
        assert "answer" in lower or "response" in lower

    def test_template_instructs_updating_docs(self):
        """Happy: Template instructs updating scope docs, plan, and tasks based on answers."""
        template = self._load_template()
        lower = template.lower()
        assert "update" in lower or "modify" in lower or "incorporate" in lower
        assert "plan" in lower
        assert "task" in lower

    def test_template_instructs_manifest_creation(self):
        """Happy: Template instructs writing build.md manifest with YAML frontmatter."""
        template = self._load_template()
        lower = template.lower()
        assert "manifest" in lower or "build.md" in lower
        assert "yaml" in lower or "frontmatter" in lower

    def test_template_defines_plan_ready_output(self):
        """Happy: Template shows PLAN_READY JSON with manifest_path artifact."""
        template = self._load_template()
        assert "PLAN_READY" in template
        assert "manifest_path" in template
        assert '"status"' in template

    def test_template_manifest_includes_validate_flag(self):
        """Happy: Manifest YAML frontmatter example includes validate: true."""
        template = self._load_template()
        assert "validate: true" in template

    def test_template_has_step_by_step_instructions(self):
        """Happy: Template provides numbered steps for autonomous execution."""
        template = self._load_template()
        assert "Step 1" in template or "### Step" in template

    def test_template_has_sufficient_depth(self):
        """Failure: Template must be comprehensive enough for autonomous operation (>1000 chars)."""
        template = self._load_template()
        assert len(template) > 1000, (
            f"Update docs prompt is too short ({len(template)} chars) for autonomous operation; "
            "needs detailed instructions for incorporating clarifications, updating docs, and manifest generation"
        )

    def test_template_has_guardrails(self):
        """Failure: Template must include guardrails to prevent out-of-scope work."""
        template = self._load_template()
        assert "Do NOT" in template or "Do not" in template or "DO NOT" in template, (
            "Template should include guardrails to prevent the agent from doing work "
            "that belongs to other stages (code implementation, research, etc.)"
        )

    def test_template_does_not_instruct_code_changes(self):
        """Failure: Template must not instruct agent to write or modify source code."""
        template = self._load_template()
        assert "write code" not in template.lower() or "do not write code" in template.lower() or "Do NOT" in template

    def test_template_does_not_instruct_new_research(self):
        """Failure: Template must not instruct agent to re-research the codebase."""
        template = self._load_template()
        lower = template.lower()
        # Should focus on incorporating answers, not doing research
        has_guardrail = "do not" in lower and ("research" in lower or "explore" in lower)
        no_research_instruction = "explore the codebase" not in lower
        assert has_guardrail or no_research_instruction


class TestUpdateDocsPromptSubstitution:
    """Tests for update_docs prompt variable substitution via Stage."""

    def test_substitution_replaces_all_variables(self):
        """Happy: All template variables are replaced when context is provided."""
        config = create_plan_resume_pipeline()
        update_docs_config = config.stages["update_docs"]
        stage = Stage(config=update_docs_config, runner=None)

        context = {
            "clarification_answers": "## Gap 1\nAnswer: Use OAuth2 for auth.\n## Gap 2\nAnswer: Skip for MVP.",
            "context_files": "- `scope.md`\n- `design.md`",
            "plan_path": "/tmp/plan_output/specs/plan.md",
            "tasks_path": "/tmp/plan_output/specs/tasks.md",
            "output_dir": "/tmp/plan_output",
        }
        prompt = stage.build_prompt(context)

        assert "{clarification_answers}" not in prompt
        assert "{context_files}" not in prompt
        assert "{plan_path}" not in prompt
        assert "{tasks_path}" not in prompt
        assert "{output_dir}" not in prompt
        # Substituted values should be present
        assert "Use OAuth2 for auth." in prompt
        assert "/tmp/plan_output/specs/plan.md" in prompt
        assert "/tmp/plan_output/specs/tasks.md" in prompt
        assert "/tmp/plan_output" in prompt

    def test_substitution_missing_variable_leaves_placeholder(self):
        """Failure: Missing context variables leave {placeholder} in output."""
        config = create_plan_resume_pipeline()
        update_docs_config = config.stages["update_docs"]
        stage = Stage(config=update_docs_config, runner=None)

        prompt = stage.build_prompt({})
        assert "{clarification_answers}" in prompt
        assert "{context_files}" in prompt
        assert "{plan_path}" in prompt
        assert "{tasks_path}" in prompt
        assert "{output_dir}" in prompt
