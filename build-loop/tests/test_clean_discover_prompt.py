"""Tests for clean_discover sub-stage prompt template."""

from pathlib import Path

PROMPTS_DIR = Path(__file__).parent.parent / "src" / "build_loop" / "prompts" / "shipping"


class TestCleanDiscoverPromptContent:
    """Tests for clean_discover.md prompt template content."""

    def _load_template(self) -> str:
        """Load the clean_discover prompt template."""
        return (PROMPTS_DIR / "clean_discover.md").read_text(encoding="utf-8")

    def test_template_contains_required_variables(self):
        """Happy: Template uses {parent_branch}, {working_set_scope}, {context_files} variables."""
        template = self._load_template()
        assert "{parent_branch}" in template
        assert "{working_set_scope}" in template
        assert "{context_files}" in template

    def test_template_contains_three_tasks(self):
        """Happy: Template contains 3 numbered tasks: scope, dead code, duplication."""
        template = self._load_template()
        assert "Task 1" in template
        assert "Task 2" in template
        assert "Task 3" in template
        # Should NOT have Tasks 4-7 (those belong to investigate/execute)
        assert "Task 4" not in template
        assert "Task 5" not in template

    def test_template_contains_clean_discover_task_complete_signal(self):
        """Happy: Template shows CLEAN_DISCOVER_TASK_COMPLETE signal for per-task loop."""
        template = self._load_template()
        assert "CLEAN_DISCOVER_TASK_COMPLETE" in template
        assert '"status"' in template

    def test_template_contains_clean_discover_complete_signal(self):
        """Happy: Template shows CLEAN_DISCOVER_COMPLETE signal for stage transition."""
        template = self._load_template()
        assert "CLEAN_DISCOVER_COMPLETE" in template

    def test_template_contains_stop_instructions(self):
        """Happy: Template includes clear STOP instructions between tasks."""
        template = self._load_template()
        lower = template.lower()
        assert "stop" in lower

    def test_template_covers_working_set_scope(self):
        """Happy: Task 1 instructs determining working set scope via git diff."""
        template = self._load_template()
        lower = template.lower()
        assert "git diff" in lower
        assert "working set" in lower

    def test_template_covers_dead_code_analysis(self):
        """Happy: Task 2 instructs dead code analysis with CONFIRMED/SUSPECT levels."""
        template = self._load_template()
        assert "CONFIRMED" in template
        assert "SUSPECT" in template

    def test_template_covers_duplication_analysis(self):
        """Happy: Task 3 instructs duplication analysis."""
        template = self._load_template()
        lower = template.lower()
        assert "duplic" in lower

    def test_template_is_analysis_only(self):
        """Happy: Rules section scopes to analysis-only — no modifications allowed."""
        template = self._load_template()
        # Should have explicit no-modify guardrails
        assert "Do NOT" in template or "Do not" in template or "DO NOT" in template
        lower = template.lower()
        assert "do not modify" in lower or "do not remove" in lower or "only analyze" in lower

    def test_template_has_one_task_per_iteration_instruction(self):
        """Happy: Template preserves one-task-per-iteration instruction."""
        template = self._load_template()
        lower = template.lower()
        assert "one task per iteration" in lower or "one task" in lower

    def test_template_has_sufficient_depth(self):
        """Failure: Template must be comprehensive enough for autonomous operation (>800 chars)."""
        template = self._load_template()
        assert len(template) > 800, (
            f"Clean discover prompt is too short ({len(template)} chars) for autonomous operation"
        )

    def test_template_does_not_contain_execute_instructions(self):
        """Failure: Template must NOT contain execute/removal instructions (those belong to clean_execute)."""
        template = self._load_template()
        # Should not contain Task 6 execution language
        assert "Execute Approved Changes" not in template
        # Should not reference lint compliance as a task
        assert "Lint Compliance" not in template
