"""Tests for rebase stage prompt template."""

from pathlib import Path

from build_loop.pipeline.loader import create_ship_pipeline
from build_loop.pipeline.stage import Stage


PROMPTS_DIR = Path(__file__).parent.parent / "src" / "build_loop" / "prompts" / "shipping"


class TestRebasePromptContent:
    """Tests for rebase.md prompt template content."""

    def _load_template(self) -> str:
        """Load the rebase prompt template."""
        return (PROMPTS_DIR / "rebase.md").read_text(encoding="utf-8")

    def test_template_contains_parent_branch_variable(self):
        """Happy: Template uses {parent_branch} variable."""
        template = self._load_template()
        assert "{parent_branch}" in template

    def test_template_contains_clean_summary_variable(self):
        """Happy: Template uses {clean_summary} variable."""
        template = self._load_template()
        assert "{clean_summary}" in template

    def test_template_contains_test_summary_variable(self):
        """Happy: Template uses {test_summary} variable."""
        template = self._load_template()
        assert "{test_summary}" in template

    def test_template_contains_ship_complete_signal(self):
        """Happy: Template shows SHIP_COMPLETE JSON completion block."""
        template = self._load_template()
        assert "SHIP_COMPLETE" in template
        assert '"status"' in template

    def test_template_is_single_context_window(self):
        """Happy: Template is NOT decomposed into numbered tasks — single context window."""
        template = self._load_template()
        # Should NOT have SHIP_TASK_COMPLETE signals (not decomposed)
        assert "SHIP_TASK_COMPLETE" not in template
        # Should not have numbered tasks like the clean/test prompts
        assert "### Task 1:" not in template
        assert "### Task 2:" not in template

    def test_template_covers_pr_creation(self):
        """Happy: Template includes PR creation logic with gh pr create."""
        template = self._load_template()
        assert "gh pr create" in template

    def test_template_covers_gh_auth_check(self):
        """Happy: Template includes gh auth status check before PR creation."""
        template = self._load_template()
        assert "gh auth status" in template

    def test_template_covers_pr_template_detection(self):
        """Happy: Template includes PR template detection."""
        template = self._load_template()
        lower = template.lower()
        assert "pull_request_template" in lower or "pr template" in lower

    def test_template_covers_local_merge_fallback(self):
        """Happy: Template includes local merge fallback when no remote."""
        template = self._load_template()
        lower = template.lower()
        assert "merge" in lower
        assert "local" in lower or "no remote" in lower or "fallback" in lower

    def test_template_covers_safety_ref(self):
        """Happy: Template instructs creating a safety ref before rebase."""
        template = self._load_template()
        lower = template.lower()
        assert "safety" in lower
        assert "ref" in lower or "branch" in lower or "backup" in lower

    def test_template_covers_rebase_execution(self):
        """Happy: Template instructs executing the rebase."""
        template = self._load_template()
        lower = template.lower()
        assert "git rebase" in lower

    def test_template_covers_conflict_resolution(self):
        """Happy: Template addresses conflict resolution during rebase."""
        template = self._load_template()
        lower = template.lower()
        assert "conflict" in lower

    def test_template_covers_verification(self):
        """Happy: Template instructs running lint and tests after rebase."""
        template = self._load_template()
        lower = template.lower()
        assert "lint" in lower
        assert "test" in lower

    def test_template_has_sufficient_depth(self):
        """Failure: Template must be comprehensive enough for autonomous operation (>1000 chars)."""
        template = self._load_template()
        assert len(template) > 1000, (
            f"Rebase prompt is too short ({len(template)} chars) for autonomous operation"
        )

    def test_template_has_do_not_guardrails(self):
        """Failure: Template must have Do NOT guardrails to prevent scope creep."""
        template = self._load_template()
        assert "Do NOT" in template or "Do not" in template or "DO NOT" in template

    def test_template_covers_stash_approval(self):
        """Happy: Template includes stash approval flow for dirty target branch."""
        template = self._load_template()
        lower = template.lower()
        assert "stash" in lower


class TestRebasePromptSubstitution:
    """Tests for rebase prompt variable substitution via Stage."""

    def test_substitution_replaces_all_variables(self):
        """Happy: All template variables are replaced when context is provided."""
        config = create_ship_pipeline()
        rebase_config = config.stages["rebase"]
        stage = Stage(config=rebase_config, runner=None)

        context = {
            "parent_branch": "main",
            "clean_summary": "Removed 3 dead imports, 1 unused function",
            "test_summary": "Added 12 tests (P0: 4, P1: 5, P2: 3), all passing",
            "context_files": "- `scope.md`",
        }
        prompt = stage.build_prompt(context)

        assert "{parent_branch}" not in prompt
        assert "{clean_summary}" not in prompt
        assert "{test_summary}" not in prompt
        assert "main" in prompt
        assert "Removed 3 dead imports" in prompt
        assert "Added 12 tests" in prompt

    def test_substitution_missing_variable_leaves_placeholder(self):
        """Failure: Missing context variables leave {placeholder} in output."""
        config = create_ship_pipeline()
        rebase_config = config.stages["rebase"]
        stage = Stage(config=rebase_config, runner=None)

        prompt = stage.build_prompt({})
        assert "{parent_branch}" in prompt
        assert "{clean_summary}" in prompt
        assert "{test_summary}" in prompt
