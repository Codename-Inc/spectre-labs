"""Tests for clean_execute sub-stage prompt template."""

from pathlib import Path

PROMPTS_DIR = Path(__file__).parent.parent / "src" / "build_loop" / "prompts" / "shipping"


class TestCleanExecutePromptContent:
    """Tests for clean_execute.md prompt template content."""

    def _load_template(self) -> str:
        """Load the clean_execute prompt template."""
        return (PROMPTS_DIR / "clean_execute.md").read_text(encoding="utf-8")

    # --- Template variables ---

    def test_template_contains_required_variables(self):
        """Happy: Template uses {parent_branch}, {working_set_scope}, {context_files} variables."""
        template = self._load_template()
        assert "{parent_branch}" in template
        assert "{working_set_scope}" in template
        assert "{context_files}" in template

    def test_template_does_not_use_discover_or_investigate_variables(self):
        """Failure: Template should not reference git diff --name-only (discover's job) or subagent dispatch."""
        template = self._load_template()
        # git diff --name-only is discover's job
        assert "git diff --name-only" not in template
        # Subagent dispatch is investigate's job
        assert "Investigation Subagent Prompt Template" not in template

    # --- Task structure ---

    def test_template_contains_two_tasks(self):
        """Happy: Template contains 2 numbered tasks: execute changes and lint compliance."""
        template = self._load_template()
        lines = template.split("\n")
        task_headers = [l for l in lines if l.strip().startswith("### Task")]
        assert len(task_headers) == 2, f"Expected 2 task headers, found {len(task_headers)}: {task_headers}"

    def test_template_contains_execute_task(self):
        """Happy: Template contains an execute/apply changes task."""
        template = self._load_template()
        lower = template.lower()
        assert "execute" in lower or "apply" in lower
        assert "approved" in lower or "action plan" in lower

    def test_template_contains_lint_task(self):
        """Happy: Template contains a lint compliance task."""
        template = self._load_template()
        lower = template.lower()
        assert "lint" in lower

    # --- Completion signals ---

    def test_template_contains_execute_task_complete_signal(self):
        """Happy: Template shows CLEAN_EXECUTE_TASK_COMPLETE signal for per-task loop."""
        template = self._load_template()
        assert "CLEAN_EXECUTE_TASK_COMPLETE" in template

    def test_template_contains_execute_complete_signal(self):
        """Happy: Template shows CLEAN_EXECUTE_COMPLETE signal for stage transition."""
        template = self._load_template()
        assert "CLEAN_EXECUTE_COMPLETE" in template

    def test_template_does_not_contain_other_stage_signals(self):
        """Failure: Template must NOT contain signals from discover or investigate stages."""
        template = self._load_template()
        assert "CLEAN_DISCOVER_TASK_COMPLETE" not in template
        assert "CLEAN_DISCOVER_COMPLETE" not in template
        assert "CLEAN_INVESTIGATE_TASK_COMPLETE" not in template
        assert "CLEAN_INVESTIGATE_COMPLETE" not in template

    # --- Task 1: Execute Approved Changes ---

    def test_task1_includes_revert_on_failure(self):
        """Happy: Task 1 instructs reverting changes if tests fail."""
        template = self._load_template()
        lower = template.lower()
        assert "revert" in lower

    def test_task1_includes_test_after_change(self):
        """Happy: Task 1 instructs running tests after each modification."""
        template = self._load_template()
        lower = template.lower()
        assert "test" in lower

    def test_task1_includes_commit_instruction(self):
        """Happy: Task 1 includes commit instruction for executed changes."""
        template = self._load_template()
        lower = template.lower()
        assert "commit" in lower

    # --- Task 2: Lint Compliance ---

    def test_task2_includes_commit_instruction(self):
        """Happy: Task 2 includes commit instruction for lint fixes."""
        template = self._load_template()
        # Find Task 2 section and check for commit in it
        parts = template.split("### Task 2")
        assert len(parts) == 2, "Expected exactly one '### Task 2' header"
        task2_section = parts[1]
        lower = task2_section.lower()
        assert "commit" in lower

    def test_task2_scopes_to_working_set(self):
        """Happy: Task 2 lint pass is scoped to working set files."""
        template = self._load_template()
        parts = template.split("### Task 2")
        assert len(parts) == 2
        task2_section = parts[1]
        lower = task2_section.lower()
        assert "working set" in lower

    # --- Execution permissions (this stage DOES modify files) ---

    def test_template_allows_file_modifications(self):
        """Happy: Unlike discover/investigate, this stage explicitly allows modifying files."""
        template = self._load_template()
        lower = template.lower()
        # Should NOT contain analysis-only restrictions
        assert "analysis-only" not in lower
        assert "investigation-only" not in lower
        # Should contain execution language
        assert "remove" in lower or "delete" in lower or "clean up" in lower

    # --- General quality ---

    def test_template_has_stop_instructions(self):
        """Happy: Template includes clear STOP instructions between tasks."""
        template = self._load_template()
        lower = template.lower()
        assert "stop" in lower

    def test_template_has_one_task_per_iteration_instruction(self):
        """Happy: Template preserves one-task-per-iteration instruction."""
        template = self._load_template()
        lower = template.lower()
        assert "one task per iteration" in lower or "one task" in lower

    def test_template_has_rules_section(self):
        """Happy: Template has a Rules section with guardrails."""
        template = self._load_template()
        assert "## Rules" in template

    def test_template_scopes_to_working_set(self):
        """Happy: Rules section restricts work to working set files only."""
        template = self._load_template()
        # Find Rules section
        parts = template.split("## Rules")
        assert len(parts) >= 2
        rules_section = parts[1]
        lower = rules_section.lower()
        assert "working set" in lower

    def test_template_has_sufficient_depth(self):
        """Failure: Template must be comprehensive enough for autonomous operation (>800 chars)."""
        template = self._load_template()
        assert len(template) > 800, (
            f"Clean execute prompt is too short ({len(template)} chars) for autonomous operation"
        )
