# Build Progress

## Codebase Patterns
<!-- Patterns discovered during build -->
- Prompt tests follow pattern in `test_clean_prompt.py`: load template, assert variables/sections/signals/depth
- `Stage.build_prompt(context)` substitutes `{key}` placeholders; missing keys leave placeholder intact
- `create_default_pipeline()` in `loader.py` wires build stage with `PromiseCompletion(extract_artifacts=True)`
- No existing `test_build_prompt.py` existed — now created with 23 tests
- flake8 uses default 79 char line limit (no `.flake8` or pyproject.toml override)
- Full test suite runs via pipx venv: `/Users/joe/.local/pipx/venvs/spectre-build/bin/python -m pytest tests/ -q`
- JSONL transcripts at `~/.claude/projects/{hash}/{session}.jsonl` use `assistant` events (NOT `result` events) with `message.usage` containing token counts
- Subagent Task tool dispatches create separate JSONL files (not embedded in parent); no `parentToolUseID` linkage from parent to child
- Stream-JSON (stdout from `claude -p --output-format stream-json`) has `system`/`result` events; JSONL (stored transcripts) has `assistant`/`user`/`progress`/`queue-operation` events — different formats

---

## Iteration — [1.1] Rewrite build.md as phase owner prompt
**Status**: Complete
**What Was Done**: Rewrote `build.md` from a per-task single-iteration prompt to a phase owner prompt that reads context once, groups tasks into waves, dispatches parallel subagents via Task tool, aggregates completion reports with scope signals, and emits PHASE_COMPLETE/BUILD_COMPLETE with enhanced artifact JSON (including `phase_task_descriptions` and `files_touched`). Created comprehensive test suite with 23 tests covering variables, substitution, phase owner sections, completion signals, and depth/guardrails.
**Files Changed**:
- `build-loop/src/build_loop/prompts/build.md` — full rewrite as phase owner prompt
- `build-loop/tests/test_build_prompt.py` — new test file (23 tests)
- `docs/tasks/main/token-efficiency/specs/tasks.md` — marked 1.1.1-1.1.5 complete
**Key Decisions**:
- Modeled subagent dispatch after `spectre:execute` wave pattern (Task tool with dynamic prompts)
- Scope signals use text labels (Complete/Minor/Significant/Blocker) instead of emoji-only for clarity
- Review fixes handled by phase owner directly (not dispatched to subagents) for simplicity
- Remediation mode bypasses subagent dispatch entirely (handled directly by phase owner)
- `TASK_COMPLETE` promise tag removed from prompt — phase owner handles task iteration internally
**Blockers/Risks**: None

## Iteration — [2.1] Update pipeline config in create_default_pipeline()
**Status**: Complete
**What Was Done**: Removed `TASK_COMPLETE` from both the build stage's `transitions` dict and `complete_signals` list in `create_default_pipeline()`. Lowered the `max_build_iterations` default from 10 to 3 since each iteration now covers a full phase (not a single task). Legacy `create_default_build_validate_pipeline()` left unchanged for backward compatibility. Created 8 TDD tests covering transitions, complete_signals, max_iterations default/override, and legacy pipeline preservation.
**Files Changed**:
- `build-loop/src/build_loop/pipeline/loader.py` — removed TASK_COMPLETE from transitions and complete_signals, changed default max_build_iterations from 10 to 3
- `build-loop/tests/test_default_pipeline_config.py` — new test file (8 tests)
- `docs/tasks/main/token-efficiency/specs/tasks.md` — marked 2.1.1-2.1.2 complete
**Key Decisions**:
- Set default max_iterations to 3 (per plan recommendation) rather than 5 — most builds have 1-3 phases
- Also removed TASK_COMPLETE from `complete_signals` (not just transitions) — the phase owner never emits it, so the stage shouldn't recognize it as a completion signal
- Pre-existing flake8 E501 violations in loader.py not addressed (not in scope of this task)
**Blockers/Risks**: None

## Iteration — [2.2] Update code review prompt for context isolation
**Status**: Complete
**What Was Done**: Removed `{tasks_file_path}`, `{progress_file_path}`, and `{additional_context_paths_or_none}` from `code_review.md`. Replaced the Files section with a Task Descriptions section using `{phase_task_descriptions}`. Updated review scope instructions and "Read First" section to direct the agent to review code quality against task descriptions only — intentional isolation from broader project context. All existing variables preserved. Created 14 TDD tests.
**Files Changed**:
- `build-loop/src/build_loop/prompts/code_review.md` — removed full context refs, added `{phase_task_descriptions}`, updated instructions
- `build-loop/tests/test_code_review_prompt.py` — new test file (14 tests)
- `docs/tasks/main/token-efficiency/specs/tasks.md` — marked 2.2.1-2.2.2 complete
**Key Decisions**:
- Removed entire Files section rather than just hiding variables — cleaner prompt, no dead references
- Added "Task Descriptions" subsection under Review Scope for clear structure
- Updated both scope preamble and "Read First" to reinforce intentional isolation
- Review categories, severity scale, and approval threshold left unchanged
**Blockers/Risks**: None

## Iteration — [3.1] Verify hooks and artifact propagation
**Status**: Complete
**What Was Done**: Traced the full artifact propagation path from phase owner build output through to code review context. Verified that `PromiseCompletion(extract_artifacts=True)` extracts `phase_task_descriptions` and `files_touched` from the JSON block, `after_stage_hook("build")` injects `changed_files`/`commit_messages`/`review_fixes_path` via git diff, and `context.update(result.artifacts)` at `executor.py:275` makes all fields available to the code review prompt. Confirmed no hook changes are needed — `collect_diff(start_commit)` uses `git diff --name-status {start}..HEAD` which captures all subagent commits. Created 16 verification tests covering artifact extraction, context propagation, prompt substitution, hook behavior with multiple commits, and end-to-end flow.
**Files Changed**:
- `build-loop/tests/test_artifact_propagation.py` — new test file (16 tests)
- `docs/tasks/main/token-efficiency/specs/tasks.md` — marked 3.1.1-3.1.2 complete
**Key Decisions**:
- No production code changes required — all existing infrastructure (hooks, completion strategies, executor) already supports the phase owner pattern correctly
- `files_touched` from build artifacts is supplementary to `changed_files` from git hooks — both are available in context but code review primarily uses the git-sourced `changed_files`
- `BUILD_COMPLETE` is NOT in pipeline end_signals (only `ALL_VALIDATED` is), so it correctly transitions to code_review rather than ending the pipeline
**Blockers/Risks**: None

## Iteration — [3.2] End-to-end dry run test
**Status**: Complete
**What Was Done**: Created comprehensive E2E integration tests with mocked AgentRunner verifying the full pipeline flow. Tests simulate a 2-phase build with scripted agent outputs for build (PHASE_COMPLETE/BUILD_COMPLETE), code review (APPROVED/CHANGES_REQUESTED), and validate (ALL_VALIDATED/VALIDATED/GAPS_FOUND) stages. Verified single-phase flow, multi-phase VALIDATED loopback, code review context isolation (phase_task_descriptions present, full doc paths absent), CHANGES_REQUESTED → build loopback with review_fixes_path, GAPS_FOUND → build loopback with remediation_tasks_path, build prompt dispatch instructions, and validate stage configuration. 16 tests covering all acceptance criteria.
**Files Changed**:
- `build-loop/tests/test_e2e_pipeline_dry_run.py` — new test file (16 tests)
- `docs/tasks/main/token-efficiency/specs/tasks.md` — marked 3.2.1 complete
**Key Decisions**:
- Used mocked AgentRunner instead of live build — tests verify pipeline wiring, hooks, artifact propagation, and context isolation without requiring actual Claude sessions
- Test fixture includes a 2-phase tasks file (Data Layer + CLI Layer) matching task requirements
- Prompt capture pattern (side_effect callback) used to verify code review receives isolated context at runtime
- All 561 tests in the full suite pass with no regressions
**Blockers/Risks**: None

## Iteration — [4.1] Add JSONL-based token tracking for subagent usage
**Status**: Complete
**What Was Done**: Created `parse_session_tokens(jsonl_path)` utility in `stats.py` that reads Claude CLI JSONL transcripts, extracts token usage from `assistant` events (the actual format — not `result` events as originally assumed), and aggregates `input_tokens`, `output_tokens`, `cache_read_input_tokens`, `cache_creation_input_tokens`. Created `find_session_jsonl(session_id, project_dir)` to locate JSONL files by session UUID. Added `session_id` and `jsonl_*` token fields to `BuildStats` with full serialization, merge, and `add_jsonl_usage()` support. Updated `process_stream_event()` in `stream.py` to capture `sessionId` from system events. 26 TDD tests across two test files.
**Files Changed**:
- `build-loop/src/build_loop/stats.py` — added `parse_session_tokens()`, `find_session_jsonl()`, `add_jsonl_usage()`, JSONL fields on BuildStats, updated `to_dict`/`from_dict`/`merge`
- `build-loop/src/build_loop/stream.py` — session ID capture from system events
- `build-loop/tests/test_parse_session_tokens.py` — new test file (10 tests)
- `build-loop/tests/test_jsonl_integration.py` — new test file (16 tests)
- `docs/tasks/main/token-efficiency/specs/tasks.md` — marked 4.1.1-4.1.2 complete
**Key Decisions**:
- JSONL transcripts use `assistant` events with `message.usage` (not `result` events as task description assumed) — adapted implementation to match real format
- Subagent sessions create separate JSONL files not linked to parent — `parse_session_tokens()` handles one file at a time, caller aggregates
- `jsonl_*` fields are separate from `total_*` fields — enables comparing stream-sourced vs JSONL-sourced token counts
- Session ID captured from `system` event with fallback to `session.sessionId` nested path
**Blockers/Risks**: None
