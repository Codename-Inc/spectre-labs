"""Tests for test_verify sub-stage prompt template."""

from pathlib import Path

PROMPTS_DIR = Path(__file__).parent.parent / "src" / "build_loop" / "prompts" / "shipping"


class TestTestVerifyPromptContent:
    """Tests for test_verify.md prompt template content."""

    def _load_template(self) -> str:
        """Load the test_verify prompt template."""
        return (PROMPTS_DIR / "test_verify.md").read_text(encoding="utf-8")

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

    def test_template_contains_verification_task(self):
        """Happy: Template contains a task for running tests and diagnosing failures."""
        template = self._load_template()
        assert "Task 1" in template
        lower = template.lower()
        assert "run" in lower
        assert "test" in lower

    def test_template_contains_diagnose_failures_instruction(self):
        """Happy: Template instructs diagnosing failures as test bug vs production bug."""
        template = self._load_template()
        lower = template.lower()
        assert "diagnos" in lower or "investigat" in lower
        assert "test bug" in lower or "production bug" in lower

    def test_template_contains_fix_and_rerun_instruction(self):
        """Happy: Template instructs fixing failures and re-running to confirm."""
        template = self._load_template()
        lower = template.lower()
        assert "fix" in lower
        assert "re-run" in lower or "rerun" in lower or "run" in lower

    # --- Completion signals ---

    def test_template_contains_test_verify_complete_signal(self):
        """Happy: Template shows TEST_VERIFY_COMPLETE signal for stage transition."""
        template = self._load_template()
        assert "TEST_VERIFY_COMPLETE" in template

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
        assert "TEST_COMMIT_COMPLETE" not in template

    # --- Max iterations hint ---

    def test_template_contains_low_iteration_guidance(self):
        """Happy: Template hints at low iteration count (verification should be quick)."""
        template = self._load_template()
        lower = template.lower()
        # Should mention that this is meant to be quick / low iteration
        assert "quick" in lower or "brief" in lower or "iteration" in lower or "3" in template

    # --- No subagent dispatch ---

    def test_template_does_not_contain_subagent_dispatch(self):
        """Failure: Template must NOT contain subagent dispatch (verification is sequential)."""
        template = self._load_template()
        assert "Subagent Prompt Template" not in template
        assert "Task tool" not in template

    # --- No commit instructions ---

    def test_template_does_not_contain_commit_instructions(self):
        """Failure: Template must NOT contain commit instructions (test_commit handles that)."""
        template = self._load_template()
        assert "Stage all" not in template
        lower = template.lower()
        # Should explicitly say NOT to commit
        assert "do not" in lower and "commit" in lower

    # --- Negative: doesn't contain planning or execute instructions ---

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

    # --- Verification-specific content ---

    def test_template_scopes_tests_to_working_set(self):
        """Happy: Template instructs running tests scoped to working set, not entire repo."""
        template = self._load_template()
        lower = template.lower()
        assert "working set" in lower

    def test_template_contains_full_suite_run_instruction(self):
        """Happy: Template instructs running the full test suite (scoped to working set)."""
        template = self._load_template()
        lower = template.lower()
        assert "full" in lower or "suite" in lower or "all test" in lower

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
        """Failure: Template must be comprehensive enough for autonomous operation (>500 chars)."""
        template = self._load_template()
        assert len(template) > 500, (
            f"Test verify prompt is too short ({len(template)} chars) for autonomous operation"
        )
