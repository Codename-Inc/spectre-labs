"""Tests for research stage prompt template."""

from pathlib import Path

from build_loop.pipeline.loader import create_plan_pipeline
from build_loop.pipeline.stage import Stage


PROMPTS_DIR = Path(__file__).parent.parent / "src" / "build_loop" / "prompts" / "planning"


class TestResearchPromptContent:
    """Tests for research.md prompt template content."""

    def _load_template(self) -> str:
        """Load the research prompt template."""
        return (PROMPTS_DIR / "research.md").read_text(encoding="utf-8")

    def test_template_contains_required_variables(self):
        """Happy: Template uses {context_files} and {output_dir} variables."""
        template = self._load_template()
        assert "{context_files}" in template
        assert "{output_dir}" in template

    def test_template_instructs_structured_output_file(self):
        """Happy: Template specifies structured sections for task_context.md output."""
        template = self._load_template()
        lower = template.lower()
        # Must instruct writing to task_context.md with structured sections
        assert "task_context.md" in template
        # Must require architecture/patterns section
        assert "pattern" in lower
        # Must require dependencies section
        assert "dependenc" in lower
        # Must require integration points section
        assert "integration" in lower
        # Must require constraints/risks section
        assert "constraint" in lower or "risk" in lower

    def test_template_contains_json_completion_block(self):
        """Happy: Template shows RESEARCH_COMPLETE JSON with task_context_path artifact."""
        template = self._load_template()
        assert "RESEARCH_COMPLETE" in template
        assert "task_context_path" in template
        assert '"status"' in template

    def test_template_instructs_codebase_exploration_tools(self):
        """Happy: Template tells agent to use Read, Grep, Glob for exploration."""
        template = self._load_template()
        assert "Read" in template
        # At least one search tool mentioned
        assert "Grep" in template or "Glob" in template

    def test_template_instructs_reading_scope_docs(self):
        """Happy: Template explicitly instructs agent to read all scope documents."""
        template = self._load_template()
        lower = template.lower()
        assert "scope" in lower or "context" in lower
        assert "read" in lower

    def test_template_has_autonomous_instructions(self):
        """Happy: Template gives clear step-by-step instructions for autonomous execution."""
        template = self._load_template()
        # Should have numbered steps or clear sections for autonomous agent
        # At minimum: read docs, explore codebase, write findings, emit JSON
        lower = template.lower()
        assert "read" in lower
        assert "explore" in lower or "search" in lower or "investigate" in lower
        assert "write" in lower or "output" in lower

    def test_template_has_sufficient_depth(self):
        """Failure: Template must be comprehensive enough for autonomous operation (>500 chars)."""
        template = self._load_template()
        # A proper autonomous prompt needs meaningful instructions, not just a skeleton
        assert len(template) > 500, (
            f"Research prompt is too short ({len(template)} chars) for autonomous operation"
        )

    def test_template_specifies_task_context_file_structure(self):
        """Failure: Template must describe the expected structure of task_context.md."""
        template = self._load_template()
        # Should specify what sections to include in the output file
        # The task requires: architecture patterns, dependencies, integration points
        assert "##" in template or "###" in template or "section" in template.lower(), (
            "Template should specify structured sections for task_context.md output"
        )


class TestResearchPromptSubstitution:
    """Tests for research prompt variable substitution via Stage."""

    def test_substitution_replaces_all_variables(self):
        """Happy: All template variables are replaced when context is provided."""
        config = create_plan_pipeline()
        research_config = config.stages["research"]
        stage = Stage(config=research_config, runner=None)

        context = {
            "context_files": "- `scope.md`\n- `design.md`",
            "output_dir": "/tmp/plan_output",
        }
        prompt = stage.build_prompt(context)

        assert "{context_files}" not in prompt
        assert "{output_dir}" not in prompt
        # Substituted values should be present
        assert "scope.md" in prompt
        assert "/tmp/plan_output" in prompt

    def test_substitution_missing_variable_leaves_placeholder(self):
        """Failure: Missing context variables leave {placeholder} in output."""
        config = create_plan_pipeline()
        research_config = config.stages["research"]
        stage = Stage(config=research_config, runner=None)

        prompt = stage.build_prompt({})
        assert "{context_files}" in prompt
        assert "{output_dir}" in prompt
