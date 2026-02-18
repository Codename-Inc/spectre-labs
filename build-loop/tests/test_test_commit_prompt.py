"""Tests for test_commit sub-stage prompt template."""

from pathlib import Path

PROMPTS_DIR = Path(__file__).parent.parent / "src" / "build_loop" / "prompts" / "shipping"


class TestTestCommitPromptContent:
    """Tests for test_commit.md prompt template content."""

    def _load_template(self) -> str:
        """Load the test_commit prompt template."""
        return (PROMPTS_DIR / "test_commit.md").read_text(encoding="utf-8")

    # --- Template variables ---

    def test_template_contains_required_variables(self):
        """Happy: Template uses {working_set_scope} and {context_files} variables."""
        template = self._load_template()
        assert "{working_set_scope}" in template
        assert "{context_files}" in template

    def test_template_does_not_use_parent_branch_variable(self):
        """Failure: Template must NOT use {parent_branch} — test stage doesn't need it."""
        template = self._load_template()
        assert "{parent_branch}" not in template

    # --- Task structure ---

    def test_template_contains_staging_instruction(self):
        """Happy: Template instructs staging test files and bug fixes."""
        template = self._load_template()
        lower = template.lower()
        assert "stage" in lower
        assert "test file" in lower or "test" in lower

    def test_template_contains_commit_instruction(self):
        """Happy: Template instructs committing with a descriptive message."""
        template = self._load_template()
        lower = template.lower()
        assert "commit" in lower
        assert "descriptive" in lower or "message" in lower or "summariz" in lower

    def test_template_contains_clean_state_verification(self):
        """Happy: Template instructs verifying clean state after commit."""
        template = self._load_template()
        lower = template.lower()
        assert "clean" in lower or "unstaged" in lower or "verify" in lower

    def test_template_mentions_production_bug_fixes(self):
        """Happy: Template mentions staging production code bug fixes if any."""
        template = self._load_template()
        lower = template.lower()
        assert "bug fix" in lower or "production" in lower

    # --- Completion signals ---

    def test_template_contains_test_commit_complete_signal(self):
        """Happy: Template shows TEST_COMMIT_COMPLETE signal for stage transition."""
        template = self._load_template()
        assert "TEST_COMMIT_COMPLETE" in template

    def test_template_does_not_use_old_signal_names(self):
        """Failure: Template must NOT use old test.md signal names."""
        template = self._load_template()
        assert "TEST_TASK_COMPLETE" not in template
        assert "TEST_COMPLETE" not in template

    def test_template_does_not_use_other_stage_signals(self):
        """Failure: Template must NOT use signals from other test sub-stages."""
        template = self._load_template()
        assert "TEST_PLAN_COMPLETE" not in template
        assert "TEST_PLAN_TASK_COMPLETE" not in template
        assert "TEST_EXECUTE_COMPLETE" not in template
        assert "TEST_EXECUTE_TASK_COMPLETE" not in template
        assert "TEST_VERIFY_COMPLETE" not in template
        assert "TEST_VERIFY_TASK_COMPLETE" not in template

    # --- Max iterations hint ---

    def test_template_contains_single_iteration_hint(self):
        """Happy: Template hints at single iteration (commit should be one-shot)."""
        template = self._load_template()
        lower = template.lower()
        # Should mention single/1 iteration or that this is a one-shot operation
        assert "1" in template or "single" in lower or "one" in lower or "final" in lower

    # --- No subagent dispatch ---

    def test_template_does_not_contain_subagent_dispatch(self):
        """Failure: Template must NOT contain subagent dispatch (commit is sequential)."""
        template = self._load_template()
        assert "Subagent Prompt Template" not in template
        assert "Task tool" not in template

    # --- Negative: doesn't contain other stage responsibilities ---

    def test_template_does_not_contain_planning_instructions(self):
        """Failure: Template must NOT contain planning/discovery (those belong to test_plan)."""
        template = self._load_template()
        assert "Risk Assessment and Test Plan" not in template
        assert "Discover Working Set and Plan" not in template

    def test_template_does_not_contain_test_writing_instructions(self):
        """Failure: Template must NOT contain test writing dispatch (those belong to test_execute)."""
        template = self._load_template()
        assert "Dispatch Parallel Test Writer" not in template
        assert "Test Writer Subagent" not in template

    def test_template_does_not_contain_verification_instructions(self):
        """Failure: Template must NOT contain diagnose/fix (those belong to test_verify)."""
        template = self._load_template()
        assert "Diagnose Failures" not in template
        lower = template.lower()
        # Should not contain diagnostic taxonomy
        assert "test bug" not in lower or "production bug" not in lower

    # --- General structure ---

    def test_template_has_context_section(self):
        """Happy: Template has a Context section with working set and context files."""
        template = self._load_template()
        assert "## Context" in template

    def test_template_has_rules_section(self):
        """Happy: Template has a Rules section with guardrails."""
        template = self._load_template()
        assert "## Rules" in template

    def test_template_has_stop_instructions(self):
        """Happy: Template includes clear STOP instructions."""
        template = self._load_template()
        lower = template.lower()
        assert "stop" in lower

    def test_template_has_sufficient_depth(self):
        """Failure: Template must be comprehensive enough for autonomous operation (>400 chars)."""
        template = self._load_template()
        assert len(template) > 400, (
            f"Test commit prompt is too short ({len(template)} chars) for autonomous operation"
        )

    def test_template_identifies_as_test_commit_stage(self):
        """Happy: Template clearly identifies itself as the test_commit sub-stage."""
        template = self._load_template()
        assert "test_commit" in template or "Test Commit" in template
