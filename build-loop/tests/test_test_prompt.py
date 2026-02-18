"""Tests for test stage prompt template."""

from pathlib import Path

from build_loop.pipeline.loader import create_ship_pipeline
from build_loop.pipeline.stage import Stage


PROMPTS_DIR = Path(__file__).parent.parent / "src" / "build_loop" / "prompts" / "shipping"


class TestTestPromptContent:
    """Tests for test.md prompt template content."""

    def _load_template(self) -> str:
        """Load the test prompt template."""
        return (PROMPTS_DIR / "test.md").read_text(encoding="utf-8")

    def test_template_contains_working_set_scope_variable(self):
        """Happy: Template uses {working_set_scope} variable."""
        template = self._load_template()
        assert "{working_set_scope}" in template

    def test_template_contains_context_files_variable(self):
        """Happy: Template uses {context_files} variable for optional context."""
        template = self._load_template()
        assert "{context_files}" in template

    def test_template_contains_four_tasks(self):
        """Happy: Template contains 4 numbered tasks matching the scope's test checklist."""
        template = self._load_template()
        for i in range(1, 5):
            assert (
                f"Task {i}" in template
                or f"## {i}" in template
                or f"### {i}" in template
                or f"**Task {i}**" in template
            ), f"Task {i} not found in test prompt template"

    def test_template_does_not_have_task_five(self):
        """Failure: Template should have exactly 4 tasks, not 5."""
        template = self._load_template()
        # Should not have a Task 5 heading
        assert "Task 5" not in template or "### Task 5" not in template

    def test_template_contains_test_task_complete_signal(self):
        """Happy: Template shows TEST_TASK_COMPLETE JSON completion block."""
        template = self._load_template()
        assert "TEST_TASK_COMPLETE" in template
        assert '"status"' in template

    def test_template_contains_test_complete_signal(self):
        """Happy: Template shows TEST_COMPLETE JSON completion block for final task."""
        template = self._load_template()
        assert "TEST_COMPLETE" in template

    def test_template_contains_stop_instructions(self):
        """Happy: Template includes clear STOP instructions between tasks."""
        template = self._load_template()
        lower = template.lower()
        assert "stop" in lower

    def test_template_covers_discovery_and_planning(self):
        """Happy: Task 1 instructs discovering working set and planning."""
        template = self._load_template()
        lower = template.lower()
        assert "discover" in lower or "working set" in lower

    def test_template_covers_risk_assessment(self):
        """Happy: Task 2 instructs risk assessment with priority tiers."""
        template = self._load_template()
        lower = template.lower()
        assert "risk" in lower
        # Should have priority tiers
        assert "p0" in lower or "p1" in lower or "critical" in lower

    def test_template_covers_write_tests(self):
        """Happy: Task 3 instructs writing tests and verifying."""
        template = self._load_template()
        lower = template.lower()
        assert "write test" in lower or "write the test" in lower or "implement test" in lower or "create test" in lower

    def test_template_covers_commit(self):
        """Happy: Task 4 instructs committing test changes."""
        template = self._load_template()
        lower = template.lower()
        assert "commit" in lower

    def test_template_has_sufficient_depth(self):
        """Failure: Template must be comprehensive enough for autonomous operation (>1000 chars)."""
        template = self._load_template()
        assert len(template) > 1000, (
            f"Test prompt is too short ({len(template)} chars) for autonomous operation"
        )

    def test_template_has_do_not_guardrails(self):
        """Failure: Template must have Do NOT guardrails to prevent scope creep."""
        template = self._load_template()
        assert "Do NOT" in template or "Do not" in template or "DO NOT" in template


class TestTestPromptSubstitution:
    """Tests for test prompt variable substitution via Stage."""

    def test_substitution_replaces_all_variables(self):
        """Happy: All template variables are replaced when context is provided."""
        config = create_ship_pipeline()
        test_config = config.stages["test_plan"]
        stage = Stage(config=test_config, runner=None)

        context = {
            "working_set_scope": "abc123..def456",
            "context_files": "- `scope.md`\n- `design.md`",
        }
        prompt = stage.build_prompt(context)

        assert "{working_set_scope}" not in prompt
        assert "{context_files}" not in prompt
        assert "abc123..def456" in prompt
        assert "scope.md" in prompt

    def test_substitution_missing_variable_leaves_placeholder(self):
        """Failure: Missing context variables leave {placeholder} in output."""
        config = create_ship_pipeline()
        test_config = config.stages["test_plan"]
        stage = Stage(config=test_config, runner=None)

        prompt = stage.build_prompt({})
        assert "{working_set_scope}" in prompt
        assert "{context_files}" in prompt
