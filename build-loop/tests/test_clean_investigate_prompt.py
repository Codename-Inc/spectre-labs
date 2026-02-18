"""Tests for clean_investigate sub-stage prompt template."""

from pathlib import Path

PROMPTS_DIR = Path(__file__).parent.parent / "src" / "build_loop" / "prompts" / "shipping"


class TestCleanInvestigatePromptContent:
    """Tests for clean_investigate.md prompt template content."""

    def _load_template(self) -> str:
        """Load the clean_investigate prompt template."""
        return (PROMPTS_DIR / "clean_investigate.md").read_text(encoding="utf-8")

    # --- Template variables ---

    def test_template_contains_required_variables(self):
        """Happy: Template uses {parent_branch}, {working_set_scope}, {context_files} variables."""
        template = self._load_template()
        assert "{parent_branch}" in template
        assert "{working_set_scope}" in template
        assert "{context_files}" in template

    def test_template_does_not_use_discover_or_execute_variables(self):
        """Failure: Template should not reference git diff commands (discover's job) or lint (execute's job)."""
        template = self._load_template()
        # git diff --name-only is discover's job
        assert "git diff --name-only" not in template
        # Lint Compliance is execute's job
        assert "Lint Compliance" not in template

    # --- Task structure ---

    def test_template_contains_two_tasks(self):
        """Happy: Template contains 2 numbered tasks: investigation dispatch and validation."""
        template = self._load_template()
        assert "Task 1" in template or "Task 4" in template
        assert "Task 2" in template or "Task 5" in template
        # Should NOT have 3+ tasks (those belong to discover/execute)
        lines = template.split("\n")
        task_headers = [l for l in lines if l.strip().startswith("### Task")]
        assert len(task_headers) == 2, f"Expected 2 task headers, found {len(task_headers)}: {task_headers}"

    # --- Completion signals ---

    def test_template_contains_investigate_task_complete_signal(self):
        """Happy: Template shows CLEAN_INVESTIGATE_TASK_COMPLETE signal for per-task loop."""
        template = self._load_template()
        assert "CLEAN_INVESTIGATE_TASK_COMPLETE" in template

    def test_template_contains_investigate_complete_signal(self):
        """Happy: Template shows CLEAN_INVESTIGATE_COMPLETE signal for stage transition."""
        template = self._load_template()
        assert "CLEAN_INVESTIGATE_COMPLETE" in template

    def test_template_does_not_contain_other_stage_signals(self):
        """Failure: Template must NOT contain signals from discover or execute stages."""
        template = self._load_template()
        assert "CLEAN_DISCOVER_TASK_COMPLETE" not in template
        assert "CLEAN_DISCOVER_COMPLETE" not in template
        assert "CLEAN_EXECUTE_TASK_COMPLETE" not in template
        assert "CLEAN_EXECUTE_COMPLETE" not in template

    # --- Subagent dispatch (Task 1/investigation) ---

    def test_task1_includes_subagent_dispatch_instructions(self):
        """Happy: Task 1 includes explicit instructions to dispatch parallel investigation subagents via Task tool."""
        template = self._load_template()
        lower = template.lower()
        assert "task tool" in lower or "task(" in lower or "subagent" in lower
        assert "parallel" in lower or "dispatch" in lower

    def test_task1_includes_chunking_instructions(self):
        """Happy: Task 1 instructs chunking SUSPECT findings into groups for parallel dispatch."""
        template = self._load_template()
        lower = template.lower()
        assert "chunk" in lower or "group" in lower or "batch" in lower
        assert "suspect" in lower

    def test_task1_includes_subagent_template(self):
        """Happy: Task 1 includes investigation template with area name, file list, patterns."""
        template = self._load_template()
        # Should contain template/instructions for what each subagent receives
        assert "area" in template.lower() or "area_name" in template
        assert "file" in template.lower()

    def test_task1_includes_classification_categories(self):
        """Happy: Subagent template uses CONFIRMED_SAFE/NEEDS_VALIDATION/KEEP classification."""
        template = self._load_template()
        # These are the investigation output categories from the original spectre clean
        assert "CONFIRMED_SAFE" in template or "SAFE_TO_REMOVE" in template
        assert "NEEDS_VALIDATION" in template
        assert "KEEP" in template

    # --- Second-wave validation (Task 2) ---

    def test_task2_includes_validation_subagents(self):
        """Happy: Task 2 includes optional second-wave validation subagents for high-risk items."""
        template = self._load_template()
        lower = template.lower()
        assert "valid" in lower
        # Should mention high-risk items that warrant second-wave
        assert "high-risk" in lower or "high risk" in lower or "function" in lower or "class" in lower or "file delet" in lower

    def test_task2_includes_consolidation(self):
        """Happy: Task 2 consolidates investigation and validation results into final action plan."""
        template = self._load_template()
        lower = template.lower()
        assert "consolidat" in lower or "reconcil" in lower or "action plan" in lower

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

    def test_template_is_analysis_only(self):
        """Happy: Template is analysis/investigation only — no file modifications allowed."""
        template = self._load_template()
        lower = template.lower()
        assert "do not modify" in lower or "do not remove" in lower or "only investigate" in lower or "only reclassify" in lower

    def test_template_has_sufficient_depth(self):
        """Failure: Template must be comprehensive enough for autonomous operation (>1200 chars)."""
        template = self._load_template()
        assert len(template) > 1200, (
            f"Clean investigate prompt is too short ({len(template)} chars) — "
            "needs subagent dispatch instructions for autonomous operation"
        )

    def test_template_has_rules_section(self):
        """Happy: Template has a Rules section with guardrails."""
        template = self._load_template()
        assert "## Rules" in template or "## Rule" in template
