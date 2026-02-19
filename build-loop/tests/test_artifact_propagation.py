"""Tests verifying artifact propagation from build to code review.

Covers:
- 3.1.1: phase_task_descriptions and files_touched flow
- 3.1.2: after_stage_hook captures subagent commits
"""

from unittest.mock import patch

from build_loop.hooks import after_stage_hook, before_stage_hook
from build_loop.pipeline.completion import CompletionResult, PromiseCompletion
from build_loop.pipeline.stage import Stage, StageConfig


# -----------------------------------------------------------------------
# 3.1.1: Artifact extraction and context propagation
# -----------------------------------------------------------------------


class TestPromiseCompletionExtractsPhaseOwnerArtifacts:
    """PromiseCompletion(extract_artifacts=True) extracts new fields."""

    PHASE_OWNER_OUTPUT = """\
## Iteration - Phase Owner: Phase 1: Data Layer
**Status**: Complete

```json
{
  "phase_completed": "Phase 1: Data Layer",
  "completed_phase_tasks": "- [x] 1.1 Create models\\n- [x] 1.2 Create store",
  "remaining_phases": "Phase 2: CLI Layer",
  "phase_task_descriptions": "1.1: Create data models with fields x, y, z",
  "files_touched": ["src/models.py", "src/store.py", "tests/test_models.py"]
}
```

[[PROMISE:PHASE_COMPLETE]]
"""

    def test_extracts_phase_task_descriptions(self):
        """Happy: phase_task_descriptions is present in extracted artifacts."""
        strategy = PromiseCompletion(
            complete_signals=["PHASE_COMPLETE", "BUILD_COMPLETE"],
            extract_artifacts=True,
        )
        result = strategy.evaluate(self.PHASE_OWNER_OUTPUT, exit_code=0)
        assert result.artifacts["phase_task_descriptions"] == (
            "1.1: Create data models with fields x, y, z"
        )

    def test_extracts_files_touched(self):
        """Happy: files_touched is present in extracted artifacts."""
        strategy = PromiseCompletion(
            complete_signals=["PHASE_COMPLETE", "BUILD_COMPLETE"],
            extract_artifacts=True,
        )
        result = strategy.evaluate(self.PHASE_OWNER_OUTPUT, exit_code=0)
        assert result.artifacts["files_touched"] == [
            "src/models.py",
            "src/store.py",
            "tests/test_models.py",
        ]

    def test_no_artifacts_without_extract_flag(self):
        """Failure: artifacts are empty when extract_artifacts is False."""
        strategy = PromiseCompletion(
            complete_signals=["PHASE_COMPLETE", "BUILD_COMPLETE"],
            extract_artifacts=False,
        )
        result = strategy.evaluate(self.PHASE_OWNER_OUTPUT, exit_code=0)
        assert result.artifacts == {}


class TestContextUpdatePropagatesArtifactsToCodeReview:
    """context.update makes fields available for prompt substitution."""

    def test_phase_task_descriptions_available_in_context(self):
        """Happy: phase_task_descriptions is substitutable."""
        artifacts = {
            "phase_completed": "Phase 1: Data Layer",
            "phase_task_descriptions": "1.1: Create models\n1.2: Create store",
            "files_touched": ["src/models.py"],
        }
        context = {
            "changed_files": "- `src/models.py (modified)`",
            "commit_messages": "- feat(1.1): create models",
            "review_fixes_path": "/tmp/review_fixes.md",
            "validated_phases": "None",
        }

        # Simulate executor.py:275
        context.update(artifacts)

        assert context["phase_task_descriptions"] == (
            "1.1: Create models\n1.2: Create store"
        )
        assert context["phase_completed"] == "Phase 1: Data Layer"

    def test_hook_values_not_overwritten_by_artifacts(self):
        """Failure: artifacts don't clobber hook-injected values."""
        context = {
            "changed_files": "- `src/models.py (modified)`",
            "commit_messages": "- feat(1.1): create models",
        }
        artifacts = {
            "phase_task_descriptions": "task text",
            "files_touched": ["src/models.py"],
        }

        context.update(artifacts)

        # Hook-injected values still present
        assert context["changed_files"] == "- `src/models.py (modified)`"
        assert context["commit_messages"] == "- feat(1.1): create models"


class TestCodeReviewPromptSubstitution:
    """Code review template correctly substitutes phase_task_descriptions."""

    def test_phase_task_descriptions_substituted(self):
        """Happy: build_prompt replaces placeholder."""
        template = (
            "Review the following:\n"
            "Task Descriptions: {phase_task_descriptions}\n"
            "Files: {changed_files}"
        )
        config = StageConfig(
            name="code_review",
            prompt_template=template,
            completion=PromiseCompletion(),
        )
        stage = Stage(config=config, runner=None)
        # Override template cache to use inline template
        stage._template_cache = template

        context = {
            "phase_task_descriptions": "1.1: Create data models",
            "changed_files": "- `src/models.py`",
        }
        prompt = stage.build_prompt(context)

        assert "1.1: Create data models" in prompt
        assert "{phase_task_descriptions}" not in prompt

    def test_missing_var_leaves_placeholder(self):
        """Failure: missing context key leaves placeholder."""
        template = "Tasks: {phase_task_descriptions}"
        config = StageConfig(
            name="code_review",
            prompt_template=template,
            completion=PromiseCompletion(),
        )
        stage = Stage(config=config, runner=None)
        stage._template_cache = template

        context = {}
        prompt = stage.build_prompt(context)
        assert "{phase_task_descriptions}" in prompt


# -----------------------------------------------------------------------
# 3.1.2: after_stage_hook captures parallel subagent commits
# -----------------------------------------------------------------------


class TestBeforeStageHookSnapshotsHead:
    """before_stage_hook captures HEAD for diff calculation."""

    @patch("build_loop.hooks.snapshot_head", return_value="abc1234")
    def test_captures_head_for_build_stage(self, mock_snap):
        """Happy: stores HEAD SHA in _phase_start_commit for build stage."""
        context = {}
        before_stage_hook("build", context)
        assert context["_phase_start_commit"] == "abc1234"

    @patch("build_loop.hooks.snapshot_head", return_value=None)
    def test_handles_snapshot_failure(self, mock_snap):
        """Failure: no _phase_start_commit set when snapshot_head fails."""
        context = {}
        before_stage_hook("build", context)
        assert "_phase_start_commit" not in context


class TestAfterStageHookCapturesSubagentCommits:
    """after_stage_hook captures diffs from multiple subagent commits."""

    @patch("build_loop.hooks.collect_diff")
    def test_captures_all_subagent_files(self, mock_diff):
        """Happy: changed_files includes multi-commit files."""
        from build_loop.git_scope import GitDiff

        mock_diff.return_value = GitDiff(
            start_commit="aaa1111",
            end_commit="ccc3333",
            changed_files=[
                "src/models.py (added)",
                "src/store.py (added)",
                "tests/test_models.py (added)",
                "tests/test_store.py (added)",
            ],
            commit_messages=[
                "abc1234 feat(1.1): create data models",
                "def5678 feat(1.2): create store module",
            ],
        )

        context = {
            "_phase_start_commit": "aaa1111",
            "tasks_file_path": "/tmp/tasks.md",
        }
        result = CompletionResult(
            is_complete=True,
            signal="PHASE_COMPLETE",
        )

        after_stage_hook("build", context, result)

        assert "src/models.py" in context["changed_files"]
        assert "src/store.py" in context["changed_files"]
        assert "tests/test_models.py" in context["changed_files"]
        assert "tests/test_store.py" in context["changed_files"]

    @patch("build_loop.hooks.collect_diff")
    def test_captures_all_subagent_commit_messages(self, mock_diff):
        """Happy: commit_messages includes all subagent commits."""
        from build_loop.git_scope import GitDiff

        mock_diff.return_value = GitDiff(
            start_commit="aaa1111",
            end_commit="ccc3333",
            changed_files=["src/models.py (added)"],
            commit_messages=[
                "abc1234 feat(1.1): create data models",
                "def5678 feat(1.2): create store module",
                "ghi9012 feat(1.3): add CLI commands",
            ],
        )

        context = {
            "_phase_start_commit": "aaa1111",
            "tasks_file_path": "/tmp/tasks.md",
        }
        result = CompletionResult(is_complete=True, signal="PHASE_COMPLETE")

        after_stage_hook("build", context, result)

        assert "feat(1.1)" in context["commit_messages"]
        assert "feat(1.2)" in context["commit_messages"]
        assert "feat(1.3)" in context["commit_messages"]

    @patch("build_loop.hooks.collect_diff")
    def test_sets_review_fixes_path(self, mock_diff):
        """Happy: review_fixes_path derived from tasks_file_path."""
        from build_loop.git_scope import GitDiff

        mock_diff.return_value = GitDiff(
            start_commit="aaa",
            end_commit="bbb",
            changed_files=["f.py (modified)"],
            commit_messages=["abc feat(1.1): task"],
        )

        context = {
            "_phase_start_commit": "aaa",
            "tasks_file_path": "/project/docs/tasks.md",
        }
        result = CompletionResult(is_complete=True, signal="PHASE_COMPLETE")

        after_stage_hook("build", context, result)

        assert context["review_fixes_path"] == "/project/docs/review_fixes.md"

    def test_handles_missing_start_commit(self):
        """Failure: gracefully handles missing _phase_start_commit."""
        context = {"tasks_file_path": "/tmp/tasks.md"}
        result = CompletionResult(is_complete=True, signal="PHASE_COMPLETE")

        after_stage_hook("build", context, result)

        assert "No files changed" in context["changed_files"]
        assert "No commits" in context["commit_messages"]

    @patch("build_loop.hooks.collect_diff", return_value=None)
    def test_handles_diff_collection_failure(self, mock_diff):
        """Failure: gracefully handles collect_diff returning None."""
        context = {
            "_phase_start_commit": "aaa1111",
            "tasks_file_path": "/tmp/tasks.md",
        }
        result = CompletionResult(is_complete=True, signal="PHASE_COMPLETE")

        after_stage_hook("build", context, result)

        assert context["changed_files"] == "No files changed"
        assert context["commit_messages"] == "No commits"


class TestEndToEndArtifactPropagation:
    """Full executor flow: build artifacts + hooks to code review."""

    @patch("build_loop.hooks.collect_diff")
    @patch("build_loop.hooks.snapshot_head", return_value="start123")
    def test_full_flow_all_variables_present(
        self, mock_snap, mock_diff
    ):
        """Happy: code review context has all expected variables."""
        from build_loop.git_scope import GitDiff

        mock_diff.return_value = GitDiff(
            start_commit="start123",
            end_commit="end456",
            changed_files=[
                "src/models.py (added)",
                "src/store.py (added)",
            ],
            commit_messages=[
                "abc feat(1.1): create data models",
                "def feat(1.2): create store module",
            ],
        )

        # Step 1: before_stage_hook snapshots HEAD
        context = {"tasks_file_path": "/project/tasks.md"}
        before_stage_hook("build", context)
        assert context["_phase_start_commit"] == "start123"

        # Step 2: Build stage completes with artifacts
        build_result = CompletionResult(
            is_complete=True,
            signal="PHASE_COMPLETE",
            artifacts={
                "phase_completed": "Phase 1: Data Layer",
                "completed_phase_tasks": (
                    "- [x] 1.1 Create models\n- [x] 1.2 Create store"
                ),
                "remaining_phases": "Phase 2: CLI Layer",
                "phase_task_descriptions": (
                    "1.1: Create data models\n1.2: Create store"
                ),
                "files_touched": ["src/models.py", "src/store.py"],
            },
        )

        # Step 3: after_stage_hook injects git diff context
        after_stage_hook("build", context, build_result)

        # Step 4: executor does context.update(result.artifacts)
        context.update(build_result.artifacts)

        # Verify ALL code review variables are present
        assert "phase_task_descriptions" in context
        assert "changed_files" in context
        assert "commit_messages" in context
        assert "review_fixes_path" in context
        assert "phase_completed" in context
        assert "files_touched" in context

        # Verify values are correct
        assert "1.1: Create data models" in context["phase_task_descriptions"]
        assert "src/models.py" in context["changed_files"]
        assert "feat(1.1)" in context["commit_messages"]
        assert context["phase_completed"] == "Phase 1: Data Layer"

    @patch("build_loop.hooks.collect_diff")
    @patch("build_loop.hooks.snapshot_head", return_value="start123")
    def test_build_complete_flows_to_code_review(
        self, mock_snap, mock_diff
    ):
        """Happy: BUILD_COMPLETE flows through code review."""
        from build_loop.git_scope import GitDiff

        mock_diff.return_value = GitDiff(
            start_commit="start123",
            end_commit="end789",
            changed_files=["src/main.py (added)"],
            commit_messages=["xyz feat(2.1): final task"],
        )

        context = {"tasks_file_path": "/project/tasks.md"}
        before_stage_hook("build", context)

        build_result = CompletionResult(
            is_complete=True,
            signal="BUILD_COMPLETE",
            artifacts={
                "phase_completed": "all",
                "completed_phase_tasks": "- [x] 2.1 Final task",
                "remaining_phases": "None",
                "phase_task_descriptions": "2.1: Implement final feature",
                "files_touched": ["src/main.py"],
            },
        )

        after_stage_hook("build", context, build_result)
        context.update(build_result.artifacts)

        # BUILD_COMPLETE not in end_signals (only ALL_VALIDATED)
        # So it transitions to code_review
        assert context["phase_task_descriptions"] == (
            "2.1: Implement final feature"
        )
        assert "src/main.py" in context["changed_files"]
