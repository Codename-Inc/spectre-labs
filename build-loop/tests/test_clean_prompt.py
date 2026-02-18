"""Tests for clean stage prompt template."""

from pathlib import Path

from build_loop.pipeline.loader import create_ship_pipeline
from build_loop.pipeline.stage import Stage


PROMPTS_DIR = Path(__file__).parent.parent / "src" / "build_loop" / "prompts" / "shipping"


class TestCleanPromptContent:
    """Tests for clean.md prompt template content."""

    def _load_template(self) -> str:
        """Load the clean prompt template."""
        return (PROMPTS_DIR / "clean.md").read_text(encoding="utf-8")

    def test_template_contains_required_variables(self):
        """Happy: Template uses {parent_branch} and {working_set_scope} variables."""
        template = self._load_template()
        assert "{parent_branch}" in template
        assert "{working_set_scope}" in template

    def test_template_contains_context_files_variable(self):
        """Happy: Template uses {context_files} variable for optional context."""
        template = self._load_template()
        assert "{context_files}" in template

    def test_template_contains_seven_tasks(self):
        """Happy: Template contains 7 numbered tasks matching the scope's clean checklist."""
        template = self._load_template()
        # Should have tasks covering: working set scope, dead code, duplication,
        # investigation subagents, validate findings, execute removals, lint compliance
        for i in range(1, 8):
            assert f"Task {i}" in template or f"## {i}" in template or f"### {i}" in template or f"**Task {i}**" in template, (
                f"Task {i} not found in clean prompt template"
            )

    def test_template_contains_clean_task_complete_signal(self):
        """Happy: Template shows CLEAN_TASK_COMPLETE JSON completion block."""
        template = self._load_template()
        assert "CLEAN_TASK_COMPLETE" in template
        assert '"status"' in template

    def test_template_contains_clean_complete_signal(self):
        """Happy: Template shows CLEAN_COMPLETE JSON completion block for final task."""
        template = self._load_template()
        assert "CLEAN_COMPLETE" in template

    def test_template_contains_stop_instructions(self):
        """Happy: Template includes clear STOP instructions between tasks."""
        template = self._load_template()
        lower = template.lower()
        assert "stop" in lower

    def test_template_covers_dead_code_analysis(self):
        """Happy: Template instructs dead code analysis of working set."""
        template = self._load_template()
        lower = template.lower()
        assert "dead code" in lower or "unused" in lower

    def test_template_covers_duplication_analysis(self):
        """Happy: Template instructs duplication analysis."""
        template = self._load_template()
        lower = template.lower()
        assert "duplic" in lower

    def test_template_covers_lint_compliance(self):
        """Happy: Template instructs lint/ESLint compliance check."""
        template = self._load_template()
        lower = template.lower()
        assert "lint" in lower

    def test_template_has_sufficient_depth(self):
        """Failure: Template must be comprehensive enough for autonomous operation (>1000 chars)."""
        template = self._load_template()
        assert len(template) > 1000, (
            f"Clean prompt is too short ({len(template)} chars) for autonomous operation"
        )

    def test_template_has_do_not_guardrails(self):
        """Failure: Template must have Do NOT guardrails to prevent scope creep."""
        template = self._load_template()
        assert "Do NOT" in template or "Do not" in template or "DO NOT" in template


class TestCleanPromptSubstitution:
    """Tests for clean prompt variable substitution via Stage."""

    def test_substitution_replaces_all_variables(self):
        """Happy: All template variables are replaced when context is provided."""
        config = create_ship_pipeline()
        clean_config = config.stages["clean_discover"]
        stage = Stage(config=clean_config, runner=None)

        context = {
            "parent_branch": "main",
            "working_set_scope": "abc123..def456",
            "context_files": "- `scope.md`\n- `design.md`",
        }
        prompt = stage.build_prompt(context)

        assert "{parent_branch}" not in prompt
        assert "{working_set_scope}" not in prompt
        assert "{context_files}" not in prompt
        assert "main" in prompt
        assert "abc123..def456" in prompt
        assert "scope.md" in prompt

    def test_substitution_missing_variable_leaves_placeholder(self):
        """Failure: Missing context variables leave {placeholder} in output."""
        config = create_ship_pipeline()
        clean_config = config.stages["clean_discover"]
        stage = Stage(config=clean_config, runner=None)

        prompt = stage.build_prompt({})
        assert "{parent_branch}" in prompt
        assert "{working_set_scope}" in prompt
        assert "{context_files}" in prompt
