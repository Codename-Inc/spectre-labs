"""E2E dry run tests for the phase owner pipeline.

Verifies full pipeline flow with mocked agent outputs:
- 3.2.1: Pipeline executes with phase owner pattern
  - Phase owner dispatches via Task tool
  - Emits correct promise tags with artifact JSON
  - Code review receives isolated context
  - Validate stage works unchanged
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

from build_loop.hooks import after_stage_hook, before_stage_hook
from build_loop.pipeline.executor import (
    PipelineExecutor,
    PipelineStatus,
)
from build_loop.pipeline.loader import create_default_pipeline


# -------------------------------------------------------------------
# Test fixture: sample tasks file content
# -------------------------------------------------------------------

FIXTURE_TASKS = """\
# Tasks — Test Project

## Phase 1: Data Layer

#### [1.1] Create data models
- [ ] **1.1.1** Create User model with fields: name, email
- [ ] **1.1.2** Create Todo model with fields: title, done

#### [1.2] Create data store
- [ ] **1.2.1** Implement in-memory store with add/list

## Phase 2: CLI Layer

#### [2.1] Add CLI commands
- [ ] **2.1.1** Implement add command
- [ ] **2.1.2** Implement list command

#### [2.2] Add output formatting
- [ ] **2.2.1** Implement table output
"""


# -------------------------------------------------------------------
# Simulated agent outputs per stage
# -------------------------------------------------------------------

PHASE1_BUILD_OUTPUT = (
    "## Phase Owner: Phase 1: Data Layer\n\n"
    "Read context, dispatching subagents for Wave 1...\n\n"
    "All tasks complete.\n\n"
    "```json\n"
    "{\n"
    '  "phase_completed": "Phase 1: Data Layer",\n'
    '  "completed_phase_tasks":'
    ' "- [x] 1.1 Create data models'
    "\\n- [x] 1.2 Create data store"
    '",\n'
    '  "remaining_phases": "Phase 2: CLI Layer",\n'
    '  "phase_task_descriptions":'
    ' "1.1: Create User and Todo data models'
    "\\n1.2: Implement in-memory store with add/list"
    '",\n'
    '  "files_touched": ['
    '"src/models.py", "src/store.py",'
    ' "tests/test_models.py", "tests/test_store.py"'
    "]\n"
    "}\n"
    "```\n\n"
    "[[PROMISE:PHASE_COMPLETE]]\n"
)

PHASE2_BUILD_OUTPUT = (
    "## Phase Owner: Phase 2: CLI Layer\n\n"
    "Dispatching subagents for Phase 2...\n\n"
    "All tasks complete.\n\n"
    "```json\n"
    "{\n"
    '  "phase_completed": "Phase 2: CLI Layer",\n'
    '  "completed_phase_tasks":'
    ' "- [x] 2.1 Add CLI commands'
    "\\n- [x] 2.2 Add output formatting"
    '",\n'
    '  "remaining_phases": "None",\n'
    '  "phase_task_descriptions":'
    ' "2.1: Implement add and list CLI commands'
    "\\n2.2: Implement table output formatting"
    '",\n'
    '  "files_touched": ['
    '"src/cli.py", "src/format.py", "tests/test_cli.py"'
    "]\n"
    "}\n"
    "```\n\n"
    "[[PROMISE:BUILD_COMPLETE]]\n"
)

CODE_REVIEW_APPROVED = (
    "## Code Review\n\n"
    "Reviewed all changed files.\n\n"
    "```json\n"
    '{"status": "APPROVED",'
    ' "summary": "All changes look good."}\n'
    "```\n"
)

CODE_REVIEW_CHANGES_REQUESTED = (
    "## Code Review\n\n"
    "Found issues.\n\n"
    "```json\n"
    '{"status": "CHANGES_REQUESTED",'
    ' "summary": "Missing error handling"}\n'
    "```\n"
)

VALIDATE_VALIDATED = (
    "## Validation\n\n"
    "Phase 1 validated.\n\n"
    "```json\n"
    '{"status": "VALIDATED",'
    ' "summary": "Phase 1 verified."}\n'
    "```\n"
)

VALIDATE_ALL_VALIDATED = (
    "## Validation\n\n"
    "All tasks validated.\n\n"
    "```json\n"
    '{"status": "ALL_VALIDATED",'
    ' "summary": "D!=C!=R confirmed."}\n'
    "```\n"
)

VALIDATE_GAPS_FOUND = (
    "## Validation\n\n"
    "Found gaps.\n\n"
    "```json\n"
    '{"status": "GAPS_FOUND",'
    ' "summary": "Missing edge case",'
    ' "gaps_file":'
    ' "/tmp/test_project/remediation_tasks.md"}\n'
    "```\n"
)


def _make_mock_runner(outputs):
    """Create a mock AgentRunner returning scripted outputs."""
    runner = MagicMock()
    runner.run_iteration = MagicMock(side_effect=outputs)
    return runner


def _build_executor(runner, context):
    """Create PipelineExecutor with real hooks and mock runner."""
    config = create_default_pipeline(
        tasks_file="/tmp/test_project/tasks.md",
        context_files=["/tmp/test_project/scope.md"],
    )
    return PipelineExecutor(
        config=config,
        runner=runner,
        context=context,
        before_stage=before_stage_hook,
        after_stage=after_stage_hook,
    )


def _default_context():
    """Return a standard test context dict."""
    return {
        "tasks_file_path": "/tmp/test_project/tasks.md",
        "progress_file_path": "/tmp/test_project/progress.md",
        "additional_context_paths_or_none": (
            "- `/tmp/test_project/scope.md`"
        ),
        "review_fixes_path": "",
        "remediation_tasks_path": "",
    }


def _make_git_diff(
    files=None, commits=None,
    start="aaa1111", end="bbb2222",
):
    """Create a GitDiff for mocking."""
    from build_loop.git_scope import GitDiff
    return GitDiff(
        start_commit=start,
        end_commit=end,
        changed_files=files or ["src/models.py (added)"],
        commit_messages=commits or [
            "abc feat(1.1): models"
        ],
    )


# -------------------------------------------------------------------
# TO1: Single-phase pipeline flow
# -------------------------------------------------------------------


class TestSinglePhasePipelineFlow:
    """Build → code_review → validate with one phase."""

    @patch("build_loop.hooks.collect_diff")
    @patch("build_loop.hooks.snapshot_head",
           return_value="aaa1111")
    def test_happy_completes_with_all_validated(
        self, mock_snap, mock_diff
    ):
        """Happy: Pipeline ends COMPLETED after one phase."""
        mock_diff.return_value = _make_git_diff(
            files=[
                "src/models.py (added)",
                "src/store.py (added)",
            ],
            commits=[
                "abc feat(1.1): create data models",
                "def feat(1.2): create data store",
            ],
        )

        runner = _make_mock_runner([
            (0, PHASE1_BUILD_OUTPUT, ""),
            (0, CODE_REVIEW_APPROVED, ""),
            (0, VALIDATE_ALL_VALIDATED, ""),
        ])

        state = _build_executor(
            runner, _default_context()
        ).run()

        assert state.status == PipelineStatus.COMPLETED
        assert len(state.stage_history) == 3
        assert state.stage_history[0] == (
            "build", "PHASE_COMPLETE"
        )
        assert state.stage_history[1] == (
            "code_review", "APPROVED"
        )
        assert state.stage_history[2] == (
            "validate", "ALL_VALIDATED"
        )

    @patch("build_loop.hooks.collect_diff",
           return_value=None)
    @patch("build_loop.hooks.snapshot_head",
           return_value=None)
    def test_failure_no_promise_exhausts_iterations(
        self, mock_snap, mock_diff
    ):
        """Failure: No promise tag → build stage not complete."""
        runner = _make_mock_runner([
            (0, "No valid output", ""),
            (0, "Still no output", ""),
            (0, "Third attempt", ""),
        ])

        state = _build_executor(
            runner, _default_context()
        ).run()

        assert state.status != PipelineStatus.COMPLETED
        assert len(state.stage_history) >= 1
        name, _ = state.stage_history[0]
        assert name == "build"


# -------------------------------------------------------------------
# TO2: Multi-phase pipeline flow
# -------------------------------------------------------------------


class TestMultiPhasePipelineFlow:
    """Two-phase build with VALIDATED loopback."""

    @patch("build_loop.hooks.collect_diff")
    @patch("build_loop.hooks.snapshot_head",
           return_value="aaa1111")
    def test_happy_two_phases_complete(
        self, mock_snap, mock_diff
    ):
        """Happy: Pipeline cycles 2 phases then ends."""
        mock_diff.side_effect = [
            _make_git_diff(
                files=["src/models.py (added)",
                       "src/store.py (added)"],
                commits=["abc feat(1.1): models",
                         "def feat(1.2): store"],
            ),
            _make_git_diff(
                files=["src/cli.py (added)",
                       "src/format.py (added)"],
                commits=["ghi feat(2.1): cli",
                         "jkl feat(2.2): format"],
                end="ccc3333",
            ),
        ]

        runner = _make_mock_runner([
            (0, PHASE1_BUILD_OUTPUT, ""),
            (0, CODE_REVIEW_APPROVED, ""),
            (0, VALIDATE_VALIDATED, ""),
            (0, PHASE2_BUILD_OUTPUT, ""),
            (0, CODE_REVIEW_APPROVED, ""),
            (0, VALIDATE_ALL_VALIDATED, ""),
        ])

        state = _build_executor(
            runner, _default_context()
        ).run()

        assert state.status == PipelineStatus.COMPLETED
        assert len(state.stage_history) == 6
        assert state.stage_history[0] == (
            "build", "PHASE_COMPLETE"
        )
        assert state.stage_history[1] == (
            "code_review", "APPROVED"
        )
        assert state.stage_history[2] == (
            "validate", "VALIDATED"
        )
        assert state.stage_history[3] == (
            "build", "BUILD_COMPLETE"
        )
        assert state.stage_history[4] == (
            "code_review", "APPROVED"
        )
        assert state.stage_history[5] == (
            "validate", "ALL_VALIDATED"
        )

    @patch("build_loop.hooks.collect_diff")
    @patch("build_loop.hooks.snapshot_head",
           return_value="aaa1111")
    def test_failure_stops_on_end_signal(
        self, mock_snap, mock_diff
    ):
        """Failure: Pipeline stops after ALL_VALIDATED."""
        mock_diff.return_value = _make_git_diff()

        runner = _make_mock_runner([
            (0, PHASE1_BUILD_OUTPUT, ""),
            (0, CODE_REVIEW_APPROVED, ""),
            (0, VALIDATE_ALL_VALIDATED, ""),
            (0, "SHOULD NOT REACH", ""),
        ])

        state = _build_executor(
            runner, _default_context()
        ).run()

        assert runner.run_iteration.call_count == 3
        assert state.status == PipelineStatus.COMPLETED


# -------------------------------------------------------------------
# TO3: Code review context isolation
# -------------------------------------------------------------------


class TestCodeReviewContextIsolation:
    """Code review gets isolated context, not full docs."""

    @patch("build_loop.hooks.collect_diff")
    @patch("build_loop.hooks.snapshot_head",
           return_value="aaa1111")
    def test_happy_receives_task_descriptions(
        self, mock_snap, mock_diff
    ):
        """Happy: Review prompt has phase_task_descriptions."""
        mock_diff.return_value = _make_git_diff()

        captured = []

        def capture(prompt, stats=None, denied_tools=None):
            captured.append(prompt)
            idx = len(captured) - 1
            outs = [
                (0, PHASE1_BUILD_OUTPUT, ""),
                (0, CODE_REVIEW_APPROVED, ""),
                (0, VALIDATE_ALL_VALIDATED, ""),
            ]
            return outs[idx] if idx < len(outs) else (0, "", "")

        runner = MagicMock()
        runner.run_iteration = MagicMock(side_effect=capture)

        _build_executor(
            runner, _default_context()
        ).run()

        assert len(captured) >= 2
        review = captured[1]
        assert "1.1: Create User and Todo" in review
        assert "src/models.py" in review

    @patch("build_loop.hooks.collect_diff")
    @patch("build_loop.hooks.snapshot_head",
           return_value="aaa1111")
    def test_failure_no_full_context_placeholders(
        self, mock_snap, mock_diff
    ):
        """Failure: Review has no full doc placeholders."""
        mock_diff.return_value = _make_git_diff()

        captured = []

        def capture(prompt, stats=None, denied_tools=None):
            captured.append(prompt)
            idx = len(captured) - 1
            outs = [
                (0, PHASE1_BUILD_OUTPUT, ""),
                (0, CODE_REVIEW_APPROVED, ""),
                (0, VALIDATE_ALL_VALIDATED, ""),
            ]
            return outs[idx] if idx < len(outs) else (0, "", "")

        runner = MagicMock()
        runner.run_iteration = MagicMock(side_effect=capture)

        _build_executor(
            runner, _default_context()
        ).run()

        assert len(captured) >= 2
        review = captured[1]
        assert "{tasks_file_path}" not in review
        assert "{progress_file_path}" not in review
        key = "{additional_context_paths_or_none}"
        assert key not in review


# -------------------------------------------------------------------
# TO4: CHANGES_REQUESTED → build loopback
# -------------------------------------------------------------------


class TestChangesRequestedLoopback:
    """CHANGES_REQUESTED routes back to build."""

    @patch("build_loop.hooks.collect_diff")
    @patch("build_loop.hooks.snapshot_head",
           return_value="aaa1111")
    def test_happy_loops_back_then_passes(
        self, mock_snap, mock_diff
    ):
        """Happy: CHANGES_REQUESTED → build → APPROVED."""
        mock_diff.return_value = _make_git_diff()

        runner = _make_mock_runner([
            (0, PHASE1_BUILD_OUTPUT, ""),
            (0, CODE_REVIEW_CHANGES_REQUESTED, ""),
            (0, PHASE1_BUILD_OUTPUT, ""),
            (0, CODE_REVIEW_APPROVED, ""),
            (0, VALIDATE_ALL_VALIDATED, ""),
        ])

        state = _build_executor(
            runner, _default_context()
        ).run()

        assert state.status == PipelineStatus.COMPLETED
        assert len(state.stage_history) == 5
        assert state.stage_history[1] == (
            "code_review", "CHANGES_REQUESTED"
        )
        assert state.stage_history[2] == (
            "build", "PHASE_COMPLETE"
        )

    @patch("build_loop.hooks.collect_diff")
    @patch("build_loop.hooks.snapshot_head",
           return_value="aaa1111")
    def test_failure_sets_review_fixes_path(
        self, mock_snap, mock_diff
    ):
        """Failure: Build gets review_fixes_path after reject."""
        mock_diff.return_value = _make_git_diff()

        captured_ctx = []

        def hook_before(stage_name, ctx):
            before_stage_hook(stage_name, ctx)
            captured_ctx.append((stage_name, dict(ctx)))

        runner = _make_mock_runner([
            (0, PHASE1_BUILD_OUTPUT, ""),
            (0, CODE_REVIEW_CHANGES_REQUESTED, ""),
            (0, PHASE1_BUILD_OUTPUT, ""),
            (0, CODE_REVIEW_APPROVED, ""),
            (0, VALIDATE_ALL_VALIDATED, ""),
        ])

        config = create_default_pipeline(
            tasks_file="/tmp/test_project/tasks.md"
        )
        PipelineExecutor(
            config=config,
            runner=runner,
            context=_default_context(),
            before_stage=hook_before,
            after_stage=after_stage_hook,
        ).run()

        builds = [
            c for n, c in captured_ctx if n == "build"
        ]
        assert len(builds) >= 2
        assert builds[1].get("review_fixes_path") != ""


# -------------------------------------------------------------------
# TO5: GAPS_FOUND → build loopback
# -------------------------------------------------------------------


class TestGapsFoundLoopback:
    """Validate GAPS_FOUND routes back to build."""

    @patch("build_loop.hooks.collect_diff")
    @patch("build_loop.hooks.snapshot_head",
           return_value="aaa1111")
    def test_happy_loops_to_build(
        self, mock_snap, mock_diff
    ):
        """Happy: GAPS_FOUND → build → validate → end."""
        mock_diff.return_value = _make_git_diff()

        runner = _make_mock_runner([
            (0, PHASE1_BUILD_OUTPUT, ""),
            (0, CODE_REVIEW_APPROVED, ""),
            (0, VALIDATE_GAPS_FOUND, ""),
            (0, PHASE1_BUILD_OUTPUT, ""),
            (0, CODE_REVIEW_APPROVED, ""),
            (0, VALIDATE_ALL_VALIDATED, ""),
        ])

        state = _build_executor(
            runner, _default_context()
        ).run()

        assert state.status == PipelineStatus.COMPLETED
        assert len(state.stage_history) == 6
        assert state.stage_history[2] == (
            "validate", "GAPS_FOUND"
        )
        assert state.stage_history[3] == (
            "build", "PHASE_COMPLETE"
        )

    @patch("build_loop.hooks.collect_diff")
    @patch("build_loop.hooks.snapshot_head",
           return_value="aaa1111")
    def test_failure_injects_remediation_path(
        self, mock_snap, mock_diff
    ):
        """Failure: Build gets remediation_tasks_path."""
        mock_diff.return_value = _make_git_diff()

        captured_ctx = []

        def hook_before(stage_name, ctx):
            before_stage_hook(stage_name, ctx)
            captured_ctx.append((stage_name, dict(ctx)))

        runner = _make_mock_runner([
            (0, PHASE1_BUILD_OUTPUT, ""),
            (0, CODE_REVIEW_APPROVED, ""),
            (0, VALIDATE_GAPS_FOUND, ""),
            (0, PHASE1_BUILD_OUTPUT, ""),
            (0, CODE_REVIEW_APPROVED, ""),
            (0, VALIDATE_ALL_VALIDATED, ""),
        ])

        config = create_default_pipeline(
            tasks_file="/tmp/test_project/tasks.md"
        )
        PipelineExecutor(
            config=config,
            runner=runner,
            context=_default_context(),
            before_stage=hook_before,
            after_stage=after_stage_hook,
        ).run()

        builds = [
            c for n, c in captured_ctx if n == "build"
        ]
        assert len(builds) >= 2
        remed = builds[1]["remediation_tasks_path"]
        assert remed == (
            "/tmp/test_project/remediation_tasks.md"
        )


# -------------------------------------------------------------------
# TO6: Build prompt dispatch instructions
# -------------------------------------------------------------------


class TestBuildPromptDispatchInstructions:
    """Build.md has subagent dispatch instructions."""

    def _load(self):
        d = (
            Path(__file__).parent.parent
            / "src" / "build_loop" / "prompts"
        )
        return (d / "build.md").read_text(encoding="utf-8")

    def test_happy_has_task_tool_dispatch(self):
        """Happy: Build prompt references Task tool."""
        t = self._load()
        assert "Task" in t
        lower = t.lower()
        assert "parallel" in lower or "concurrent" in lower

    def test_failure_no_task_complete_promise(self):
        """Failure: Phase owner never emits TASK_COMPLETE."""
        t = self._load()
        assert "[[PROMISE:TASK_COMPLETE]]" not in t


# -------------------------------------------------------------------
# TO7: Validate stage unchanged
# -------------------------------------------------------------------


class TestValidateStageUnchanged:
    """Validate config correct for phase owner pattern."""

    def test_happy_uses_composite_completion(self):
        """Happy: Validate uses CompositeCompletion."""
        from build_loop.pipeline.completion import (
            CompositeCompletion,
        )
        config = create_default_pipeline(
            tasks_file="/tmp/tasks.md"
        )
        v = config.stages["validate"]
        assert isinstance(v.completion, CompositeCompletion)

    def test_failure_has_correct_signals(self):
        """Failure: Validate recognizes expected signals."""
        from build_loop.pipeline.completion import (
            CompositeCompletion,
            JsonCompletion,
        )
        config = create_default_pipeline(
            tasks_file="/tmp/tasks.md"
        )
        v = config.stages["validate"]
        assert isinstance(v.completion, CompositeCompletion)
        js = v.completion.strategies[0]
        assert isinstance(js, JsonCompletion)
        assert "ALL_VALIDATED" in js.complete_statuses
        assert "VALIDATED" in js.complete_statuses
        assert "GAPS_FOUND" in js.complete_statuses


# -------------------------------------------------------------------
# TO8: Test fixture structure
# -------------------------------------------------------------------


class TestFixtureTasksFile:
    """Fixture tasks file has expected structure."""

    def test_happy_has_two_phases(self):
        """Happy: Fixture has 2 phases."""
        assert "## Phase 1:" in FIXTURE_TASKS
        assert "## Phase 2:" in FIXTURE_TASKS

    def test_failure_has_tasks_per_phase(self):
        """Failure: Each phase has >= 2 tasks."""
        lines = FIXTURE_TASKS.split("\n")
        p1 = [
            line for line in lines
            if line.strip().startswith("#### [")
            and "1." in line
        ]
        p2 = [
            line for line in lines
            if line.strip().startswith("#### [")
            and "2." in line
        ]
        assert len(p1) >= 2
        assert len(p2) >= 2
