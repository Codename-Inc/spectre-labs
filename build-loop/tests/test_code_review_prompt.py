"""Tests for code review prompt template (context isolation pattern)."""

from pathlib import Path

from build_loop.pipeline.loader import create_default_pipeline
from build_loop.pipeline.stage import Stage


PROMPTS_DIR = (
    Path(__file__).parent.parent / "src" / "build_loop" / "prompts"
)


class TestCodeReviewVariablesRemoved:
    """Tests that full-context variables are removed from code_review.md."""

    def _load_template(self) -> str:
        return (PROMPTS_DIR / "code_review.md").read_text(
            encoding="utf-8"
        )

    def test_tasks_file_path_removed(self):
        """Failure: {tasks_file_path} must NOT appear."""
        template = self._load_template()
        assert "{tasks_file_path}" not in template

    def test_progress_file_path_removed(self):
        """Failure: {progress_file_path} must NOT appear."""
        template = self._load_template()
        assert "{progress_file_path}" not in template

    def test_additional_context_paths_removed(self):
        """Failure: {additional_context_paths_or_none} must NOT appear."""
        template = self._load_template()
        assert "{additional_context_paths_or_none}" not in template


class TestCodeReviewVariablesPresent:
    """Tests that required variables exist in code_review.md."""

    def _load_template(self) -> str:
        return (PROMPTS_DIR / "code_review.md").read_text(
            encoding="utf-8"
        )

    def test_phase_task_descriptions_present(self):
        """Happy: {phase_task_descriptions} variable is in the template."""
        template = self._load_template()
        assert "{phase_task_descriptions}" in template

    def test_changed_files_preserved(self):
        """Happy: {changed_files} variable still present."""
        template = self._load_template()
        assert "{changed_files}" in template

    def test_commit_messages_preserved(self):
        """Happy: {commit_messages} variable still present."""
        template = self._load_template()
        assert "{commit_messages}" in template

    def test_phase_completed_preserved(self):
        """Happy: {phase_completed} variable still present."""
        template = self._load_template()
        assert "{phase_completed}" in template

    def test_validated_phases_preserved(self):
        """Happy: {validated_phases} variable still present."""
        template = self._load_template()
        assert "{validated_phases}" in template

    def test_review_fixes_path_preserved(self):
        """Happy: {review_fixes_path} variable still present."""
        template = self._load_template()
        assert "{review_fixes_path}" in template


class TestCodeReviewInstructions:
    """Tests that review instructions reflect intentional isolation."""

    def _load_template(self) -> str:
        return (PROMPTS_DIR / "code_review.md").read_text(
            encoding="utf-8"
        )

    def test_instructions_reference_task_descriptions(self):
        """Happy: Instructions reference task descriptions."""
        template = self._load_template()
        lower = template.lower()
        assert "task description" in lower

    def test_no_instruction_to_read_scope_docs(self):
        """Failure: Agent should NOT be told to read scope docs."""
        template = self._load_template()
        lower = template.lower()
        assert "read the tasks file" not in lower
        assert "read the progress file" not in lower
        assert "read all context" not in lower

    def test_template_has_sufficient_depth(self):
        """Failure: Template must be comprehensive enough (>800 chars)."""
        template = self._load_template()
        assert len(template) > 800, (
            f"Code review prompt too short ({len(template)} chars)"
        )


class TestCodeReviewSubstitution:
    """Tests for code review prompt variable substitution via Stage."""

    def test_substitution_replaces_phase_task_descriptions(self):
        """Happy: phase_task_descriptions substituted correctly."""
        config = create_default_pipeline(
            tasks_file="/tmp/tasks.md",
        )
        review_config = config.stages["code_review"]
        stage = Stage(config=review_config, runner=None)

        context = {
            "phase_task_descriptions": (
                "- [x] 1.1 Create models\n"
                "- [x] 1.2 Create store"
            ),
            "changed_files": "src/models.py\nsrc/store.py",
            "commit_messages": "feat(1.1): models\nfeat(1.2): store",
            "phase_completed": "Phase 1: Data Layer",
            "validated_phases": "None",
            "review_fixes_path": "/tmp/review_fixes.md",
        }
        prompt = stage.build_prompt(context)

        assert "{phase_task_descriptions}" not in prompt
        assert "1.1 Create models" in prompt

    def test_substitution_missing_phase_task_descriptions(self):
        """Failure: Missing phase_task_descriptions leaves placeholder."""
        config = create_default_pipeline(
            tasks_file="/tmp/tasks.md",
        )
        review_config = config.stages["code_review"]
        stage = Stage(config=review_config, runner=None)

        prompt = stage.build_prompt({})
        assert "{phase_task_descriptions}" in prompt
