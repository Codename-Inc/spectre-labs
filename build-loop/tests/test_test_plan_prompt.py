"""Tests for test_plan sub-stage prompt template."""

from pathlib import Path

PROMPTS_DIR = Path(__file__).parent.parent / "src" / "build_loop" / "prompts" / "shipping"


class TestTestPlanPromptContent:
    """Tests for test_plan.md prompt template content."""

    def _load_template(self) -> str:
        """Load the test_plan prompt template."""
        return (PROMPTS_DIR / "test_plan.md").read_text(encoding="utf-8")

    def test_template_contains_required_variables(self):
        """Happy: Template uses {working_set_scope} and {context_files} variables."""
        template = self._load_template()
        assert "{working_set_scope}" in template
        assert "{context_files}" in template

    def test_template_contains_two_tasks(self):
        """Happy: Template contains Tasks 1-2 (discover + risk assessment)."""
        template = self._load_template()
        assert "Task 1" in template
        assert "Task 2" in template
        # Should NOT have Tasks 3-4 (those belong to test_execute/verify/commit)
        assert "Task 3" not in template
        assert "Task 4" not in template

    def test_template_contains_test_plan_task_complete_signal(self):
        """Happy: Template shows TEST_PLAN_TASK_COMPLETE signal for per-task loop."""
        template = self._load_template()
        assert "TEST_PLAN_TASK_COMPLETE" in template
        assert '"status"' in template

    def test_template_contains_test_plan_complete_signal(self):
        """Happy: Template shows TEST_PLAN_COMPLETE signal for stage transition."""
        template = self._load_template()
        assert "TEST_PLAN_COMPLETE" in template

    def test_template_contains_stop_instructions(self):
        """Happy: Template includes clear STOP instructions between tasks."""
        template = self._load_template()
        lower = template.lower()
        assert "stop" in lower

    def test_template_covers_working_set_discovery(self):
        """Happy: Task 1 instructs discovering working set via git diff."""
        template = self._load_template()
        lower = template.lower()
        assert "git diff" in lower
        assert "working set" in lower

    def test_template_contains_risk_tier_definitions(self):
        """Happy: Template includes full P0-P3 risk tier definitions."""
        template = self._load_template()
        assert "P0" in template
        assert "P1" in template
        assert "P2" in template
        assert "P3" in template
        # Should define what each tier means
        lower = template.lower()
        assert "critical" in lower
        assert "skip" in lower or "no test" in lower

    def test_template_contains_test_quality_requirements(self):
        """Happy: Template includes test quality requirements from test.md framework."""
        template = self._load_template()
        lower = template.lower()
        assert "mutation" in lower  # mutation testing mindset
        assert "refactor" in lower  # refactor-resilient

    def test_template_contains_batching_heuristics(self):
        """Happy: Task 2 includes batching heuristics for parallelization strategy."""
        template = self._load_template()
        # P0: 1 file/agent, P1: 2-3, P2: 3-5, P3: SKIP
        assert "1 file" in template or "1 agent" in template or "one file" in template.lower()
        assert "2-3" in template
        assert "3-5" in template

    def test_template_contains_agent_count_guidance(self):
        """Happy: Template includes guidance on target number of parallel agents."""
        template = self._load_template()
        lower = template.lower()
        assert "3-5" in template  # medium scope
        assert "agent" in lower

    def test_template_is_analysis_only(self):
        """Happy: Template scopes to analysis and planning only — no test writing."""
        template = self._load_template()
        assert "Do NOT" in template or "Do not" in template or "DO NOT" in template
        lower = template.lower()
        assert "do not write" in lower or "do not implement" in lower or "only analyze" in lower or "only plan" in lower

    def test_template_has_one_task_per_iteration_instruction(self):
        """Happy: Template preserves one-task-per-iteration instruction."""
        template = self._load_template()
        lower = template.lower()
        assert "one task per iteration" in lower or "one task" in lower

    def test_template_has_sufficient_depth(self):
        """Failure: Template must be comprehensive enough for autonomous operation (>800 chars)."""
        template = self._load_template()
        assert len(template) > 800, (
            f"Test plan prompt is too short ({len(template)} chars) for autonomous operation"
        )

    def test_template_does_not_contain_test_writing_instructions(self):
        """Failure: Template must NOT contain test writing instructions (those belong to test_execute)."""
        template = self._load_template()
        # Should not contain write-test-specific language from Task 3 of test.md
        assert "Create the test file" not in template
        assert "Write the test following" not in template

    def test_template_does_not_contain_commit_instructions(self):
        """Failure: Template must NOT contain commit instructions (those belong to test_commit)."""
        template = self._load_template()
        # Should not have commit-specific language from Task 4 of test.md
        assert "Stage all new and modified test files" not in template
        assert "Commit with a descriptive message" not in template

    def test_template_does_not_use_old_signal_names(self):
        """Failure: Template must NOT use old test.md signal names."""
        template = self._load_template()
        assert "TEST_TASK_COMPLETE" not in template
        assert "TEST_COMPLETE" not in template

    def test_template_contains_rules_section(self):
        """Happy: Template has a Rules section with guardrails."""
        template = self._load_template()
        assert "## Rules" in template or "## Rule" in template

    def test_template_has_context_section(self):
        """Happy: Template has a Context section with working set and context files."""
        template = self._load_template()
        assert "## Context" in template
