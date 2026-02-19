"""Tests for build stage prompt template (phase owner pattern)."""

from pathlib import Path

from build_loop.pipeline.loader import create_default_pipeline
from build_loop.pipeline.stage import Stage


PROMPTS_DIR = (
    Path(__file__).parent.parent / "src" / "build_loop" / "prompts"
)


class TestBuildPromptVariables:
    """Tests for build.md template variable placeholders."""

    def _load_template(self) -> str:
        """Load the build prompt template."""
        return (PROMPTS_DIR / "build.md").read_text(
            encoding="utf-8"
        )

    def test_template_contains_tasks_file_path(self):
        """Happy: Template uses {tasks_file_path}."""
        template = self._load_template()
        assert "{tasks_file_path}" in template

    def test_template_contains_progress_file_path(self):
        """Happy: Template uses {progress_file_path}."""
        template = self._load_template()
        assert "{progress_file_path}" in template

    def test_template_contains_additional_context(self):
        """Happy: Template uses context paths variable."""
        template = self._load_template()
        assert "{additional_context_paths_or_none}" in template

    def test_template_contains_review_fixes_path(self):
        """Happy: Template uses {review_fixes_path}."""
        template = self._load_template()
        assert "{review_fixes_path}" in template

    def test_template_contains_remediation_tasks_path(self):
        """Happy: Template uses {remediation_tasks_path}."""
        template = self._load_template()
        assert "{remediation_tasks_path}" in template


class TestBuildPromptSubstitution:
    """Tests for build prompt variable substitution."""

    def test_substitution_replaces_all_variables(self):
        """Happy: All variables replaced when context provided."""
        config = create_default_pipeline(
            tasks_file="/tmp/tasks.md",
            context_files=["/tmp/scope.md"],
        )
        build_config = config.stages["build"]
        stage = Stage(config=build_config, runner=None)

        context = {
            "tasks_file_path": "/tmp/tasks.md",
            "progress_file_path": "/tmp/progress.md",
            "additional_context_paths_or_none": (
                "- `/tmp/scope.md`"
            ),
            "review_fixes_path": "/tmp/fixes.md",
            "remediation_tasks_path": "/tmp/remed.md",
        }
        prompt = stage.build_prompt(context)

        assert "{tasks_file_path}" not in prompt
        assert "{progress_file_path}" not in prompt
        key = "{additional_context_paths_or_none}"
        assert key not in prompt
        assert "/tmp/tasks.md" in prompt
        assert "/tmp/progress.md" in prompt
        assert "/tmp/scope.md" in prompt

    def test_missing_variable_leaves_placeholder(self):
        """Failure: Missing variables leave {placeholder}."""
        config = create_default_pipeline(
            tasks_file="/tmp/tasks.md",
        )
        build_config = config.stages["build"]
        stage = Stage(config=build_config, runner=None)

        prompt = stage.build_prompt({})
        assert "{tasks_file_path}" in prompt
        assert "{progress_file_path}" in prompt


class TestBuildPromptPhaseOwnerSections:
    """Tests for phase owner prompt structure."""

    def _load_template(self) -> str:
        return (PROMPTS_DIR / "build.md").read_text(
            encoding="utf-8"
        )

    def test_context_gathering_section(self):
        """Happy: Template has context gathering (once)."""
        template = self._load_template()
        lower = template.lower()
        assert "context" in lower
        assert "once" in lower or "phase" in lower

    def test_wave_planning_section(self):
        """Happy: Template has wave planning for parallel."""
        template = self._load_template()
        lower = template.lower()
        assert "wave" in lower
        assert "parallel" in lower or "concurrent" in lower

    def test_subagent_dispatch_section(self):
        """Happy: Template dispatches subagents via Task."""
        template = self._load_template()
        assert "Task" in template
        lower = template.lower()
        assert "subagent" in lower or "sub-agent" in lower

    def test_tdd_skill_reference(self):
        """Happy: Template references spectre-tdd skill."""
        template = self._load_template()
        assert (
            "spectre-tdd" in template
            or "spectre:spectre-tdd" in template
        )

    def test_completion_report_template(self):
        """Happy: Template has completion report structure."""
        template = self._load_template()
        lower = template.lower()
        assert "completion report" in lower
        assert (
            "files changed" in lower
            or "files_changed" in lower
        )

    def test_scope_signals(self):
        """Happy: Template has scope signal definitions."""
        template = self._load_template()
        lower = template.lower()
        assert (
            "scope signal" in lower
            or "scope_signal" in lower
        )

    def test_aggregation_section(self):
        """Happy: Template has aggregation/adaptive section."""
        template = self._load_template()
        lower = template.lower()
        assert "aggregat" in lower or "adapt" in lower

    def test_commit_format_instructions(self):
        """Happy: Template uses conventional commit format."""
        template = self._load_template()
        assert "feat(" in template


class TestBuildPromptCompletionSignals:
    """Tests for PHASE_COMPLETE and BUILD_COMPLETE signals."""

    def _load_template(self) -> str:
        return (PROMPTS_DIR / "build.md").read_text(
            encoding="utf-8"
        )

    def test_phase_complete_signal(self):
        """Happy: Template references PHASE_COMPLETE."""
        template = self._load_template()
        assert "PHASE_COMPLETE" in template

    def test_build_complete_signal(self):
        """Happy: Template references BUILD_COMPLETE."""
        template = self._load_template()
        assert "BUILD_COMPLETE" in template

    def test_enhanced_artifact_json(self):
        """Happy: Template has phase_task_descriptions."""
        template = self._load_template()
        assert "phase_task_descriptions" in template
        assert "files_touched" in template

    def test_phase_metadata_fields(self):
        """Happy: Template has phase metadata fields."""
        template = self._load_template()
        assert "phase_completed" in template
        assert "completed_phase_tasks" in template
        assert "remaining_phases" in template

    def test_promise_tag_format(self):
        """Happy: Template shows [[PROMISE:...]] format."""
        template = self._load_template()
        assert "[[PROMISE:PHASE_COMPLETE]]" in template
        assert "[[PROMISE:BUILD_COMPLETE]]" in template

    def test_no_task_complete_promise(self):
        """Failure: Phase owner does not emit TASK_COMPLETE."""
        template = self._load_template()
        assert "[[PROMISE:TASK_COMPLETE]]" not in template


class TestBuildPromptDepth:
    """Tests for prompt completeness and guardrails."""

    def _load_template(self) -> str:
        return (PROMPTS_DIR / "build.md").read_text(
            encoding="utf-8"
        )

    def test_sufficient_depth(self):
        """Failure: Template must be >2000 chars."""
        template = self._load_template()
        assert len(template) > 2000, (
            f"Build prompt too short ({len(template)} chars)"
        )

    def test_has_guardrails(self):
        """Failure: Template must have Do NOT guardrails."""
        template = self._load_template()
        assert (
            "Do NOT" in template
            or "Do not" in template
            or "DO NOT" in template
        )
