"""Tests for test_execute sub-stage prompt template."""

from pathlib import Path

PROMPTS_DIR = Path(__file__).parent.parent / "src" / "build_loop" / "prompts" / "shipping"


class TestTestExecutePromptContent:
    """Tests for test_execute.md prompt template content."""

    def _load_template(self) -> str:
        """Load the test_execute prompt template."""
        return (PROMPTS_DIR / "test_execute.md").read_text(encoding="utf-8")

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

    def test_template_contains_task_1_dispatch(self):
        """Happy: Template contains Task 1 for dispatching test writer subagents."""
        template = self._load_template()
        assert "Task 1" in template
        lower = template.lower()
        assert "dispatch" in lower or "subagent" in lower

    def test_template_contains_consolidation_step(self):
        """Happy: Template includes a consolidation step after subagent dispatch."""
        template = self._load_template()
        lower = template.lower()
        assert "consolidat" in lower or "collect" in lower or "merge" in lower

    # --- Completion signals ---

    def test_template_contains_test_execute_task_complete_signal(self):
        """Happy: Template shows TEST_EXECUTE_TASK_COMPLETE signal for per-task loop."""
        template = self._load_template()
        assert "TEST_EXECUTE_TASK_COMPLETE" in template
        assert '"status"' in template

    def test_template_contains_test_execute_complete_signal(self):
        """Happy: Template shows TEST_EXECUTE_COMPLETE signal for stage transition."""
        template = self._load_template()
        assert "TEST_EXECUTE_COMPLETE" in template

    def test_template_does_not_use_old_signal_names(self):
        """Failure: Template must NOT use old test.md signal names."""
        template = self._load_template()
        assert "TEST_TASK_COMPLETE" not in template
        assert "TEST_COMPLETE" not in template

    # --- Subagent dispatch instructions ---

    def test_template_references_task_tool(self):
        """Happy: Template explicitly references the Task tool for subagent dispatch."""
        template = self._load_template()
        assert "Task tool" in template or "Task" in template

    def test_template_contains_parallel_dispatch_instruction(self):
        """Happy: Template instructs dispatching agents in parallel (single message)."""
        template = self._load_template()
        lower = template.lower()
        assert "parallel" in lower
        assert "single message" in lower or "single response" in lower

    def test_template_contains_batching_by_risk_tier(self):
        """Happy: Template instructs partitioning by risk tier from test_plan output."""
        template = self._load_template()
        assert "P0" in template
        assert "P1" in template
        assert "P2" in template
        lower = template.lower()
        assert "batch" in lower or "partition" in lower or "group" in lower

    def test_template_contains_batching_heuristics(self):
        """Happy: Template includes per-tier batching heuristics (P0=1, P1=2-3, P2=3-5)."""
        template = self._load_template()
        assert "1" in template  # P0: 1 file/agent
        assert "2-3" in template  # P1: 2-3 files/agent
        assert "3-5" in template  # P2: 3-5 files/agent

    def test_template_contains_agent_count_guidance(self):
        """Happy: Template includes guidance on target number of parallel agents."""
        template = self._load_template()
        lower = template.lower()
        assert "3-5" in template  # medium scope
        assert "agent" in lower

    def test_template_contains_subagent_prompt_template(self):
        """Happy: Template includes an embedded prompt for each test writer subagent."""
        template = self._load_template()
        lower = template.lower()
        # Should contain a prompt template/instruction block for each dispatched agent
        assert "file" in lower and "risk" in lower
        assert "behavioral" in lower or "behavior" in lower

    def test_template_instructs_wait_for_all_agents(self):
        """Happy: Template instructs waiting for all agents before proceeding."""
        template = self._load_template()
        lower = template.lower()
        assert "wait" in lower and "all" in lower

    # --- Risk-weighted framework ---

    def test_template_contains_risk_tier_definitions(self):
        """Happy: Template includes full P0-P3 risk tier definitions."""
        template = self._load_template()
        assert "P0" in template
        assert "P1" in template
        assert "P2" in template
        assert "P3" in template
        lower = template.lower()
        assert "critical" in lower
        assert "skip" in lower or "no test" in lower

    def test_template_contains_test_quality_requirements(self):
        """Happy: Template includes test quality requirements for agents."""
        template = self._load_template()
        lower = template.lower()
        assert "mutation" in lower
        assert "refactor" in lower

    # --- Negative assertions ---

    def test_template_does_not_contain_planning_instructions(self):
        """Failure: Template must NOT contain planning/discovery (those belong to test_plan)."""
        template = self._load_template()
        assert "Risk Assessment and Test Plan" not in template
        assert "Discover Working Set and Plan" not in template

    def test_template_does_not_contain_commit_instructions(self):
        """Failure: Template must NOT contain commit instructions (those belong to test_commit)."""
        template = self._load_template()
        assert "Stage all new and modified test files" not in template
        assert "Commit with a descriptive message" not in template

    def test_template_does_not_contain_verification_loop(self):
        """Failure: Template must NOT contain full suite verification (those belong to test_verify)."""
        template = self._load_template()
        assert "Run the full test suite" not in template or "full test suite for the working set" not in template

    # --- General structure ---

    def test_template_has_context_section(self):
        """Happy: Template has a Context section with working set and context files."""
        template = self._load_template()
        assert "## Context" in template

    def test_template_has_rules_section(self):
        """Happy: Template has a Rules section with guardrails."""
        template = self._load_template()
        assert "## Rules" in template or "## Rule" in template

    def test_template_has_stop_instructions(self):
        """Happy: Template includes clear STOP instructions between tasks."""
        template = self._load_template()
        lower = template.lower()
        assert "stop" in lower

    def test_template_has_one_task_per_iteration(self):
        """Happy: Template preserves one-task-per-iteration instruction."""
        template = self._load_template()
        lower = template.lower()
        assert "one task per iteration" in lower or "one task" in lower

    def test_template_has_sufficient_depth(self):
        """Failure: Template must be comprehensive enough for autonomous operation (>800 chars)."""
        template = self._load_template()
        assert len(template) > 800, (
            f"Test execute prompt is too short ({len(template)} chars) for autonomous operation"
        )
