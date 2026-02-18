# Build Progress

## Codebase Patterns
- Pipeline factories follow `create_*_pipeline() -> PipelineConfig` pattern in `loader.py`
- All planning stages use `JsonCompletion` with `signal_field="status"` for consistency
- Tool filtering uses `PLAN_DENIED_TOOLS` and `PLAN_RESEARCH_DENIED_TOOLS` module-level constants
- Prompt paths resolved via `Path(__file__).parent.parent / "prompts" / "planning"` pattern
- Tests in `build-loop/tests/test_plan_pipeline.py` — run with `/Users/joe/.local/pipx/venvs/spectre-build/bin/python -m pytest tests/test_plan_pipeline.py -v`
- pytest available via `pipx inject spectre-build pytest`

---

## Iteration — [1.1] Create planning pipeline factory + [1.2] Create planning resume pipeline factory
**Status**: Complete
**What Was Done**: Implemented `create_plan_pipeline()` and `create_plan_resume_pipeline()` factory functions in `pipeline/loader.py`. The planning pipeline defines 7 stages (research, assess, create_plan, create_tasks, plan_review, req_validate, update_docs) with JsonCompletion on all stages, complexity-aware routing (LIGHT skips create_plan), and research stage expanded tool access (WebSearch/WebFetch allowed). Resume pipeline is a single update_docs stage. Created 7 placeholder prompt templates in `prompts/planning/`. Added 17 unit tests covering all requirements. Updated `__init__.py` exports and `pyproject.toml` package-data.
**Files Changed**:
- `build-loop/src/build_loop/pipeline/loader.py` (added `create_plan_pipeline`, `create_plan_resume_pipeline`, `PLAN_DENIED_TOOLS`, `PLAN_RESEARCH_DENIED_TOOLS`)
- `build-loop/src/build_loop/pipeline/__init__.py` (added exports)
- `build-loop/src/build_loop/prompts/planning/*.md` (7 new placeholder templates)
- `build-loop/pyproject.toml` (added `prompts/planning/*.md` to package-data)
- `build-loop/tests/test_plan_pipeline.py` (new, 17 tests)
- `docs/tasks/main/specs/tasks.md` (marked 1.1 and 1.2 complete)
**Key Decisions**:
- Combined tasks 1.1 and 1.2 into one iteration since they share the same file and test patterns
- Used module-level constants for denied tools lists (reusable by hooks and CLI in later phases)
- Placeholder prompts contain basic structure and variable references that Phase 2 will flesh out
**Blockers/Risks**: None

## Iteration — [2.1] Create research stage prompt
**Status**: Complete
**What Was Done**: Replaced the placeholder `research.md` prompt with a comprehensive autonomous research template. The prompt guides the agent through 4 steps: read scope documents, explore codebase using Read/Grep/Glob, write structured findings to `{output_dir}/task_context.md` (with sections for Architecture Patterns, Key Files, Dependencies, Integration Points, Existing Conventions, Constraints and Risks), and emit `RESEARCH_COMPLETE` JSON with `task_context_path` artifact. Added 10 unit tests covering template content, variable substitution, and structural requirements.
**Files Changed**:
- `build-loop/src/build_loop/prompts/planning/research.md` (replaced placeholder with full prompt)
- `build-loop/tests/test_research_prompt.py` (new, 10 tests)
- `docs/tasks/main/specs/tasks.md` (marked 2.1 complete)
**Key Decisions**:
- Prompt follows the same style as `code_review.md` — numbered steps, explicit rules, JSON output at end
- Template specifies a markdown structure for `task_context.md` output so downstream stages get consistent input
- Included "Do NOT" guardrails to prevent the agent from doing work that belongs to later stages
**Blockers/Risks**: None

## Iteration — [2.2] Create assess stage prompt
**Status**: Complete
**What Was Done**: Replaced the placeholder `assess.md` prompt with a comprehensive autonomous complexity assessment template. The prompt guides the agent through 6 steps: read task context and scope docs, score complexity across 5 dimensions (files impacted, pattern match, components crossed, data model changes, integration points) using a Low/Medium/High scoring matrix, check hard-stop conditions (new service, auth/PII, public API, new data pipeline, cross-team dependency), determine tier (LIGHT/STANDARD/COMPREHENSIVE) from total score, write architecture design section into task_context.md for COMPREHENSIVE tier, and emit JSON with status/depth/tier fields. Added 12 unit tests covering template content, variable substitution, and structural requirements.
**Files Changed**:
- `build-loop/src/build_loop/prompts/planning/assess.md` (replaced placeholder with full prompt)
- `build-loop/tests/test_assess_prompt.py` (new, 12 tests)
- `docs/tasks/main/specs/tasks.md` (marked 2.2 complete)
**Key Decisions**:
- Used a scoring matrix (5 dimensions x 3 levels = 5-15 total) to make tier determination concrete and reproducible
- Hard-stops override the score entirely — any single hard-stop forces COMPREHENSIVE
- Architecture design for COMPREHENSIVE is appended to existing task_context.md (not a separate file) so create_plan stage gets it automatically
- Follows same style as research.md — numbered steps, explicit rules, "Do NOT" guardrails, JSON output at end
**Blockers/Risks**: None

## Iteration — [2.3] Create plan generation prompt
**Status**: Complete
**What Was Done**: Replaced the placeholder `create_plan.md` prompt with a comprehensive autonomous plan generation template. The prompt guides the agent through 4 steps: read task context and scope docs, determine section depth based on `{depth}` variable (standard vs comprehensive) using a detail-level table, write the implementation plan to `{output_dir}/specs/plan.md` with required sections (Overview, Out of Scope, Technical Approach, Critical Files, Risks), and emit `PLAN_COMPLETE` JSON with `plan_path` artifact. Added 12 unit tests covering template content, variable substitution, and structural requirements.
**Files Changed**:
- `build-loop/src/build_loop/prompts/planning/create_plan.md` (replaced placeholder with full prompt)
- `build-loop/tests/test_create_plan_prompt.py` (new, 12 tests)
- `docs/tasks/main/specs/tasks.md` (marked 2.3 complete)
**Key Decisions**:
- Depth-aware detail table maps standard/comprehensive to concrete section expectations (e.g., standard = 2-3 paragraphs overview, comprehensive = full system overview with diagrams)
- Plan structure includes Out of Scope section to prevent scope creep during task breakdown
- Writing rules require grounding claims in code references from task_context.md
- Follows same style as research.md and assess.md — numbered steps, explicit rules, "Do NOT" guardrails, JSON output at end
**Blockers/Risks**: None

## Iteration — [2.4] Create task breakdown prompt
**Status**: Complete
**What Was Done**: Replaced the placeholder `create_tasks.md` prompt with a comprehensive autonomous task breakdown template. The prompt guides the agent through 7 steps: read plan (conditionally for LIGHT tier), task context, and scope docs; extract and number requirements (REQ-001 etc.); generate 4-level hierarchical task breakdown (Phase > Parent > Sub-task > Acceptance Criteria) with integration-aware Produces/Consumed by/Replaces fields; validate requirements coverage; generate sequential and parallel execution strategies; write to `{output_dir}/specs/tasks.md` with full structure including requirements tracing table, architecture context, and coverage summary; and emit `TASKS_COMPLETE` JSON with `tasks_path` artifact. Added 15 unit tests covering template content, variable substitution, and structural requirements.
**Files Changed**:
- `build-loop/src/build_loop/prompts/planning/create_tasks.md` (replaced placeholder with full prompt)
- `build-loop/tests/test_create_tasks_prompt.py` (new, 15 tests)
- `docs/tasks/main/specs/tasks.md` (marked 2.4 complete)
**Key Decisions**:
- Adapted the interactive `/spectre:create_tasks` command's integration-aware task principle (Produces/Consumed by/Replaces) for autonomous operation
- Requirements tracing table is mandatory — every task must map to a numbered requirement
- Template handles LIGHT tier gracefully (plan file may not exist)
- Follows same style as prior prompts — numbered steps, explicit rules, "Do NOT" guardrails, JSON output at end
**Blockers/Risks**: None

## Iteration — [2.5] Create plan review prompt
**Status**: Complete
**What Was Done**: Replaced the placeholder `plan_review.md` prompt with a comprehensive autonomous plan review template. The prompt guides the agent through 4 steps: read all inputs (plan, tasks, task context, scope docs), identify over-engineering across 4 categories (premature abstraction, YAGNI violations, unnecessary indirection, scope creep), apply simplifications by editing plan.md and tasks.md in-place (preserving all scope requirements), and emit `REVIEW_COMPLETE` JSON with `changes_summary`, `items_removed`, and `items_simplified` fields. Added 12 unit tests covering template content, variable substitution, and structural requirements.
**Files Changed**:
- `build-loop/src/build_loop/prompts/planning/plan_review.md` (replaced placeholder with full prompt)
- `build-loop/tests/test_plan_review_prompt.py` (new, 12 tests)
- `docs/tasks/main/specs/tasks.md` (marked 2.5 complete)
**Key Decisions**:
- Added `{task_context_path}` and `{context_files}` variables so the agent can cross-reference simplifications against actual scope requirements and codebase patterns
- Defined 4 concrete categories of over-engineering (premature abstraction, YAGNI, unnecessary indirection, scope creep) rather than vague "simplify" instructions
- Explicit "What to preserve" section prevents the agent from removing requirements while simplifying
- Follows same style as prior prompts — numbered steps, explicit rules, "Do NOT" guardrails, JSON output at end
**Blockers/Risks**: None

## Iteration — [2.6] Create requirements validation prompt
**Status**: Complete
**What Was Done**: Replaced the placeholder `req_validate.md` prompt with a comprehensive autonomous requirements validation template. The prompt guides the agent through 6 steps: read all scope docs, plan, and tasks; extract and number requirements from scope; build a coverage matrix cross-referencing requirements against tasks (Covered/GAP); determine outcome based on gaps; if all covered write build.md manifest with YAML frontmatter (including `validate: true`), if gaps found write clarification questions to `{output_dir}/clarifications/scope_clarifications.md` with `<response></response>` blocks; and emit `PLAN_VALIDATED` or `CLARIFICATIONS_NEEDED` JSON. Added 14 unit tests covering template content, variable substitution, and structural requirements.
**Files Changed**:
- `build-loop/src/build_loop/prompts/planning/req_validate.md` (replaced placeholder with full prompt)
- `build-loop/tests/test_req_validate_prompt.py` (new, 14 tests)
- `docs/tasks/main/specs/tasks.md` (marked 2.6 complete)
**Key Decisions**:
- Three gap types (Missing task, Incomplete task, Ambiguous scope) so clarification questions are appropriately framed
- Coverage matrix format matches the requirements tracing table pattern from create_tasks stage
- Manifest includes `validate: true` in YAML frontmatter so the build loop runs with the full validation pipeline
- Clarifications file uses `<response></response>` blocks for structured user input
- Follows same style as prior prompts — numbered steps, explicit rules, "Do NOT" guardrails, JSON output at end
**Blockers/Risks**: None

## Iteration — [2.7] Create update_docs prompt (resume stage)
**Status**: Complete
**What Was Done**: Replaced the placeholder `update_docs.md` prompt with a comprehensive autonomous resume stage template. The prompt guides the agent through 5 steps: read clarification answers (parsing gap types and user responses), read existing plan and tasks documents, update documents based on each answer type (new requirement, clarification, intentional exclusion, ambiguity resolution), write build.md manifest with YAML frontmatter (including `validate: true` and a "Clarifications Applied" section), and emit `PLAN_READY` JSON with `manifest_path` artifact. Added 13 unit tests covering template content, variable substitution, guardrails, and structural requirements.
**Files Changed**:
- `build-loop/src/build_loop/prompts/planning/update_docs.md` (replaced placeholder with full prompt)
- `build-loop/tests/test_update_docs_prompt.py` (new, 13 tests)
- `docs/tasks/main/specs/tasks.md` (marked 2.7 complete)
**Key Decisions**:
- Template uses `{clarification_answers}` variable (injected by `plan_before_stage` hook reading the clarifications file)
- Four concrete action types for processing answers: add new requirement, clarify existing, confirm out-of-scope, resolve ambiguity
- Explicit guardrails prevent re-researching codebase, writing code, removing existing requirements, or creating new clarification questions
- Follows same style as prior prompts — numbered steps, explicit rules, "Do NOT" guardrails, JSON output at end
**Blockers/Risks**: None

## Iteration — [3.1] Add planning-specific lifecycle hooks
**Status**: Complete
**What Was Done**: Implemented `plan_before_stage()` and `plan_after_stage()` hooks in `hooks.py`. The before hook defaults `depth` to `"standard"` for `create_plan` stage and reads/injects clarification file content for `update_docs` stage. The after hook extracts `depth`/`tier` from assess stage artifacts into context (with safe defaults) and stores `clarifications_path` when `req_validate` emits `CLARIFICATIONS_NEEDED`. Both hooks are no-ops for unrelated stages. Added 11 unit tests covering all happy/failure paths.
**Files Changed**:
- `build-loop/src/build_loop/hooks.py` (added `plan_before_stage`, `plan_after_stage`, updated module docstring)
- `build-loop/tests/test_plan_hooks.py` (new, 11 tests)
- `docs/tasks/main/specs/tasks.md` (marked 3.1 complete)
**Key Decisions**:
- Planning hooks are separate functions from build hooks (not merged into existing `before_stage_hook`/`after_stage_hook`) so each pipeline can wire its own hooks independently
- `plan_before_stage` sets `clarification_answers` to empty string when file is missing (not None) so template substitution doesn't break
- `plan_after_stage` uses `setdefault` for depth/tier so it never overwrites values already in context from a previous stage
**Blockers/Risks**: None

## Iteration — [3.2] Add planning loop counters to stats
**Status**: Complete
**What Was Done**: Added `plan_loops: int = 0` field to `BuildStats` dataclass, conditional `PLAN LOOPS` line in the dashboard (only shown when `plan_loops > 0`), and a `create_plan_event_handler()` factory function in `stats.py` that returns an `on_event` callback incrementing `plan_loops` on every `StageCompletedEvent`. This factory is ready for `run_plan_pipeline()` (task 4.1) to wire into the `PipelineExecutor`. Added 6 unit tests covering field defaults, dashboard display/omission, and event handler behavior.
**Files Changed**:
- `build-loop/src/build_loop/stats.py` (added `plan_loops` field, `PLAN LOOPS` dashboard line, `create_plan_event_handler()` factory)
- `build-loop/tests/test_plan_stats.py` (new, 6 tests)
- `docs/tasks/main/specs/tasks.md` (marked 3.2 complete)
**Key Decisions**:
- Created `create_plan_event_handler()` as a reusable factory in `stats.py` rather than an inline closure in `cli.py`, so `run_plan_pipeline()` (task 4.1) can import and use it directly
- Handler increments `plan_loops` on any `StageCompletedEvent` (not filtered by stage name) since all stages in the planning pipeline are planning stages
- `PLAN LOOPS` line is separate from the build/review/validate `LOOPS` line since they serve different pipelines
**Blockers/Risks**: None

## Iteration — [4.1] Add --plan flag and run_plan_pipeline() to CLI
**Status**: Complete
**What Was Done**: Added `--plan` CLI flag to `parse_args()`, implemented `run_plan_pipeline()` function in `cli.py`, and wired `--plan` routing in `main()`. The function creates the planning pipeline (or resume pipeline), builds the initial context dict with output directory paths, wires `plan_before_stage`/`plan_after_stage` hooks and `create_plan_event_handler` for stats, and handles the CLARIFICATIONS_NEEDED signal by saving session for `spectre-build resume`. Extended `save_session()` with `plan`, `plan_output_dir`, `plan_context`, and `plan_clarifications_path` keyword args. Added 7 unit tests covering flag parsing, pipeline creation with hook wiring, CLARIFICATIONS_NEEDED session save, agent-not-found error, main() routing, and error on --plan without --context.
**Files Changed**:
- `build-loop/src/build_loop/cli.py` (added `--plan` flag, `run_plan_pipeline()`, extended `save_session()`, wired routing in `main()`)
- `build-loop/tests/test_plan_cli.py` (new, 7 tests)
- `docs/tasks/main/specs/tasks.md` (marked 4.1 complete)
**Key Decisions**:
- `run_plan_pipeline()` auto-detects the git branch name for the output directory (`docs/tasks/{branch}/`) with fallback to "main"
- CLARIFICATIONS_NEEDED returns exit code 0 (not an error) since it's an expected pause point
- `save_session()` extended with optional planning fields (backward compatible — defaults are False/None)
- `--plan` routing placed before `--tasks` logic in `main()` so it skips tasks_file requirement
**Blockers/Risks**: None

## Iteration — [4.2] Extend session persistence for planning
**Status**: Complete
**What Was Done**: Updated `format_session_summary()` in `cli.py` to show planning-specific information when `session["plan"]` is True: displays "Mode: Planning" instead of tasks file, shows output directory and clarifications path. Verified that `save_session()` and `load_session()` already round-trip all planning fields correctly (implemented in 4.1). Added 6 unit tests covering save/load round-trip for planning fields, old-format backward compatibility, and format display for both planning and non-planning sessions.
**Files Changed**:
- `build-loop/src/build_loop/cli.py` (updated `format_session_summary()` with planning mode display)
- `build-loop/tests/test_session_planning.py` (new, 6 tests)
- `docs/tasks/main/specs/tasks.md` (marked 4.2 complete)
**Key Decisions**:
- Planning session shows "Mode: Planning" instead of the tasks file path (since tasks are generated, not provided)
- Output dir and clarifications path shown as separate lines for clarity in resume confirmation
- 4.2.1 (save_session/load_session) was already fully implemented in task 4.1 — tests confirm correct behavior
**Blockers/Risks**: None

## Iteration — [4.3] Wire planning resume flow
**Status**: Complete
**What Was Done**: Updated `run_resume()` in `cli.py` to detect planning sessions (`plan=True`) and route to `run_plan_pipeline()` with `resume_stage="update_docs"`, passing the preserved `plan_context` as `resume_context` and `plan_output_dir` as `output_dir`. Planning sessions skip `validate_inputs()` (no tasks file to validate) and save the session with all planning fields before resuming. The existing `format_session_summary()` already shows planning-specific confirmation (Mode: Planning, output dir, clarifications path). Added 6 unit tests covering routing, context passthrough, missing context fallback, validate_inputs skip, and session save.
**Files Changed**:
- `build-loop/src/build_loop/cli.py` (updated `run_resume()` with planning session detection and routing)
- `build-loop/tests/test_plan_resume.py` (new, 6 tests)
- `docs/tasks/main/specs/tasks.md` (marked 4.3 complete)
**Key Decisions**:
- Planning branch placed first in `run_resume()` to short-circuit before extracting `tasks_file` (which is empty for planning sessions)
- `validate_inputs()` skipped entirely for planning sessions since there's no tasks file to validate
- Session save includes all planning fields for consistency (even though the pipeline may overwrite on CLARIFICATIONS_NEEDED)
**Blockers/Risks**: None

## Iteration — [4.3] Stats Tracking
**Status**: Complete
**What Was Done**: Added `ship_loops: int = 0` field to `BuildStats` dataclass, `create_ship_event_handler()` factory function that increments `ship_loops` on `StageCompletedEvent`, and `SHIP LOOPS` conditional display line in `print_summary()` dashboard. All three sub-tasks follow the exact pattern established by `plan_loops` / `create_plan_event_handler()`. Added 6 unit tests covering field defaults, isolation from other counters, dashboard display/omission, and event handler behavior (happy + failure paths).
**Files Changed**:
- `build-loop/src/build_loop/stats.py` (added `ship_loops` field, `SHIP LOOPS` dashboard line, `create_ship_event_handler()` factory)
- `build-loop/tests/test_ship_stats.py` (new, 6 tests)
- `docs/tasks/main/specs/tasks.md` (marked 4.3.1, 4.3.2, 4.3.3 complete)
**Key Decisions**:
- Followed exact pattern of `create_plan_event_handler()` — factory returns callback that increments on any `StageCompletedEvent` (not filtered by stage name)
- `SHIP LOOPS` line placed after `PLAN LOOPS` in dashboard for visual consistency
- Handler increments on all stage completions since all stages in the ship pipeline are ship stages
**Blockers/Risks**: None

## Iteration — [4.4] Notification
**Status**: Complete
**What Was Done**: Added `notify_ship_complete()` function to `notify.py` following the exact pattern of `notify_plan_complete()`. Function accepts `stages_completed`, `total_time`, `success`, and optional `project` parameters. Sends "Ship complete! {stages} stages in {time}" on success and "Ship failed after {stages} stages ({time})" on failure, with branch detection for subtitle formatting and audio notification. Added 6 unit tests covering success/failure messaging, branch+project subtitle combinations, branch-only, project-only, and no-subtitle scenarios.
**Files Changed**:
- `build-loop/src/build_loop/notify.py` (added `notify_ship_complete()` function)
- `build-loop/tests/test_ship_notify.py` (new, 6 tests)
- `docs/tasks/main/specs/tasks.md` (marked 4.4.1 complete)
**Key Decisions**:
- Identical signature pattern to `notify_plan_complete()` (`stages_completed`, `total_time`, `success`, `project`) for consistency
- Wiring at call sites (main, resume, manifest) deferred to tasks 1.1.2, 4.1.2, and 4.2.2 per task design
**Blockers/Risks**: None

## Iteration — [4.1] Session Persistence and Resume
**Status**: Complete
**What Was Done**: Added `ship: bool = False` and `ship_context: dict | None = None` parameters to `save_session()` with defaults for backward compatibility. Added `elif session.get("ship"):` block in `run_resume()` after the plan block, routing to `run_ship_pipeline()` with resume context and calling `notify_ship_complete()` for notifications. Updated `format_session_summary()` to show "Mode: Ship" and parent branch from `ship_context`. Added `notify_ship_complete` import to cli.py. All 8 new tests pass (happy + failure for save/load, resume routing, notification, and format display). Existing planning session tests unaffected.
**Files Changed**:
- `build-loop/src/build_loop/cli.py` (extended `save_session()` with ship fields, added ship branch in `run_resume()`, updated notification logic, updated `format_session_summary()`, added `notify_ship_complete` import)
- `build-loop/tests/test_session_ship.py` (new, 8 tests)
- `docs/tasks/main/specs/tasks.md` (marked 4.1.1, 4.1.2, 4.1.3 complete)
**Key Decisions**:
- Ship check placed before plan check in `format_session_summary()` and notification logic to prevent ambiguity if both flags are somehow set
- `ship_context` uses `or {}` fallback when extracting `parent_branch` for safe display even with None context
- Pre-existing `test_plan_resume.py` failures (mocking 2-tuple instead of 3-tuple for `run_plan_pipeline`) noted but not in scope — not caused by this change
**Blockers/Risks**: None

## Iteration — [4.2] Manifest Support
**Status**: Complete
**What Was Done**: Added `ship: bool = False` field to `BuildManifest` dataclass and updated `load_manifest()` to parse `ship` from YAML frontmatter (same pattern as `validate`). Added `manifest.ship` routing in `run_manifest()` before the `validate` check — when `manifest.ship` is True, routes to `run_ship_pipeline()` with manifest context files and settings, calls `notify_ship_complete()`, and exits. Also added a `run_ship_pipeline()` stub function in `cli.py` (raises `NotImplementedError`) so that the resume path (task 4.1) and manifest path can reference it before the full implementation in task 1.2. Added 7 unit tests covering BuildManifest field defaults, load_manifest parsing, and run_manifest routing priority.
**Files Changed**:
- `build-loop/src/build_loop/manifest.py` (added `ship` field to `BuildManifest`, updated `load_manifest()` to parse `ship`)
- `build-loop/src/build_loop/cli.py` (added `run_ship_pipeline()` stub, added ship routing block in `run_manifest()`)
- `build-loop/tests/test_manifest_ship.py` (new, 7 tests)
- `docs/tasks/main/specs/tasks.md` (marked 4.2.1, 4.2.2 complete)
**Key Decisions**:
- `run_ship_pipeline()` is a stub (`NotImplementedError`) — full implementation deferred to task 1.2 per the execution strategy
- Ship routing in `run_manifest()` skips `validate_inputs()` since ship doesn't require a tasks file (same pattern as plan)
- Ship check placed before validate check so `ship: true` takes priority when both flags are set in frontmatter
- Ship routing saves session with `ship=True` for resume support
**Blockers/Risks**: None

## Iteration — [2.1] Create Ship Pipeline Factory
**Status**: Complete
**What Was Done**: Added `create_ship_pipeline()` factory function in `loader.py` returning a 3-stage `PipelineConfig` (clean → test → rebase) with `JsonCompletion` strategies, correct signal transitions (`CLEAN_TASK_COMPLETE`/`CLEAN_COMPLETE`, `TEST_TASK_COMPLETE`/`TEST_COMPLETE`, `SHIP_COMPLETE`), and `PLAN_DENIED_TOOLS` for all stages. Created 3 placeholder prompt templates in `prompts/shipping/` (clean.md, test.md, rebase.md). Updated `__init__.py` exports and `pyproject.toml` package-data. Added 17 unit tests covering structure, transitions, signals, iterations, tool filtering, and prompt paths.
**Files Changed**:
- `build-loop/src/build_loop/pipeline/loader.py` (added `create_ship_pipeline()` factory)
- `build-loop/src/build_loop/pipeline/__init__.py` (added `create_ship_pipeline` export)
- `build-loop/src/build_loop/prompts/shipping/clean.md` (new placeholder)
- `build-loop/src/build_loop/prompts/shipping/test.md` (new placeholder)
- `build-loop/src/build_loop/prompts/shipping/rebase.md` (new placeholder)
- `build-loop/pyproject.toml` (added `prompts/shipping/*.md` to package-data)
- `build-loop/tests/test_ship_pipeline.py` (new, 17 tests)
- `docs/tasks/main/specs/tasks.md` (marked 2.1 complete)
**Key Decisions**:
- Followed exact pattern of `create_plan_pipeline()` — factory in `loader.py`, `JsonCompletion` on all stages, `PLAN_DENIED_TOOLS` reused
- Clean/test stages use dual completion statuses (task-level + stage-level) matching the iterative pattern from build stage
- Rebase stage capped at 3 iterations (single context window) while clean/test get 10 each
- Placeholder prompts include the correct context variable references (`{parent_branch}`, `{working_set_scope}`, `{clean_summary}`, `{test_summary}`, `{context_files}`) so downstream tasks can fill them in
**Blockers/Risks**: None

## Iteration — [2.2] Implement Ship Hooks
**Status**: Complete
**What Was Done**: Added `ship_before_stage()` and `ship_after_stage()` hook functions to `hooks.py`, plus a `_collect_stage_summary()` helper. The before hook snapshots HEAD for clean and test stages (reuses `snapshot_head()` from `git_scope.py`). The after hook collects git diff via `collect_diff()` and stores formatted summaries as `clean_summary` (after clean) and `test_summary` (after test). Both hooks are no-ops for the rebase stage. A shared `_collect_stage_summary()` helper formats changed files and commit messages into a readable string, with fallbacks for missing start commits or failed diff collection. Added 11 unit tests covering all happy/failure paths.
**Files Changed**:
- `build-loop/src/build_loop/hooks.py` (added `ship_before_stage`, `ship_after_stage`, `_collect_stage_summary`, updated module docstring)
- `build-loop/tests/test_ship_hooks.py` (new, 11 tests)
- `docs/tasks/main/specs/tasks.md` (marked 2.2.1, 2.2.2 complete)
**Key Decisions**:
- Ship hooks are separate functions from build/plan hooks (same pattern as `plan_before_stage`/`plan_after_stage`) so each pipeline wires its own hooks independently
- Shared `_collect_stage_summary()` helper eliminates duplication between clean and test after-hooks
- Reuses `_phase_start_commit` context key (same as build hooks) since ship and build pipelines never run simultaneously
- Fallback messages for missing commits and failed diffs ensure context always has a string value
**Blockers/Risks**: None

## Iteration — [3.1] Create Clean Stage Prompt
**Status**: Complete
**What Was Done**: Replaced the placeholder `clean.md` prompt with a comprehensive 7-task autonomous clean stage template. The prompt decomposes the clean workflow into: (1) determine working set scope, (2) analyze dead code, (3) analyze duplication, (4) dispatch investigation subagents, (5) validate high-risk findings, (6) execute approved changes with verification, (7) lint compliance. Each task emits `CLEAN_TASK_COMPLETE` JSON, final task emits `CLEAN_COMPLETE`. Template uses `{parent_branch}`, `{working_set_scope}`, and `{context_files}` context variables. Added 13 unit tests covering template content, variable substitution, and structural requirements.
**Files Changed**:
- `build-loop/src/build_loop/prompts/shipping/clean.md` (replaced placeholder with full prompt)
- `build-loop/tests/test_clean_prompt.py` (new, 13 tests)
- `docs/tasks/main/specs/tasks.md` (marked 3.1 complete)
**Key Decisions**:
- Conservative approach: Tasks 2-5 are analysis-only (catalog findings, investigate, validate) before any modifications in Task 6
- CONFIRMED vs SUSPECT classification system prevents premature removal of code that may have external callers
- Task 6 includes per-file verification (lint + test after each modification) with automatic revert on failure
- "Do NOT" guardrails prevent scope creep outside the working set and premature modifications
**Blockers/Risks**: None

## Iteration — [3.2] Create Test Stage Prompt
**Status**: Complete
**What Was Done**: Replaced the placeholder `test.md` prompt with a comprehensive 4-task autonomous test stage template. The prompt decomposes the test workflow into: (1) discover working set and plan (categorize files, identify test gaps), (2) risk assessment and test plan (P0-P3 priority tiers with specific criteria per tier), (3) write tests and verify (implement in priority order, run lint + tests per batch), (4) commit. Each task emits `TEST_TASK_COMPLETE` JSON, final task emits `TEST_COMPLETE`. Template uses `{working_set_scope}` and `{context_files}` context variables. Added 15 unit tests covering template content, variable substitution, and structural requirements.
**Files Changed**:
- `build-loop/src/build_loop/prompts/shipping/test.md` (replaced placeholder with full prompt)
- `build-loop/tests/test_test_prompt.py` (new, 15 tests)
- `docs/tasks/main/specs/tasks.md` (marked 3.2 complete)
**Key Decisions**:
- Risk-tiered approach (P0-P3) with concrete criteria per tier: P0=core business logic/security, P1=public APIs/integration, P2=internal helpers, P3=simple getters/formatting
- P0 and P1 mandatory, P2/P3 best-effort within iteration limits
- Task 3 includes both happy and failure path testing per test opportunity
- "Do NOT" guardrails prevent modifying production code (clean stage's job) and writing tests outside working set
**Blockers/Risks**: None

## Iteration — [3.3] Create Rebase Stage Prompt
**Status**: Complete
**What Was Done**: Replaced the placeholder `rebase.md` prompt with a comprehensive single-context-window rebase stage template. The prompt guides the agent through 6 steps: (1) confirm target branch, (2) prepare (commit uncommitted work, fetch, create safety backup ref), (3) execute rebase with conflict resolution sub-step, (4) verify (lint + tests), (5) land via PR (`gh pr create` with template detection) or local merge (with stash approval flow via `read -p`), (6) clean up safety ref. Template uses `{parent_branch}`, `{clean_summary}`, `{test_summary}`, and `{context_files}` context variables. Emits `SHIP_COMPLETE` JSON. Added 18 unit tests covering template content, variable substitution, and structural requirements.
**Files Changed**:
- `build-loop/src/build_loop/prompts/shipping/rebase.md` (replaced placeholder with full prompt)
- `build-loop/tests/test_rebase_prompt.py` (new, 18 tests)
- `docs/tasks/main/specs/tasks.md` (marked 3.3 complete)
**Key Decisions**:
- Single context window design (not decomposed into tasks) because rebase needs continuous state for conflict resolution
- PR creation checks `gh auth status` before attempting, falls back to local merge if not authenticated
- Local merge uses `read -p` via Bash for stash approval (works because Bash is an allowed tool, unlike AskUserQuestion)
- Safety backup ref (`safety-backup-pre-rebase`) created before rebase and deleted only after successful landing
- Template includes `{context_files}` variable in addition to the three required variables for consistency with clean/test prompts
- "Do NOT" guardrails prevent force-pushing, skipping verification, and modifying production code during rebase
**Blockers/Risks**: None

## Iteration — [1.2] Implement `run_ship_pipeline()` Function
**Status**: Complete
**What Was Done**: Replaced the `NotImplementedError` stub with a full `run_ship_pipeline()` implementation in `cli.py`. The function detects the parent branch via `_detect_parent_branch()` (tries main/master/develop using `git merge-base`), computes working set scope as `{parent_branch}..HEAD`, assembles the context dict with all required keys (`parent_branch`, `working_set_scope`, `context_files`, `clean_summary`, `test_summary`), creates the ship pipeline via `create_ship_pipeline()`, wires `PipelineExecutor` with `ship_before_stage`/`ship_after_stage` hooks and `create_ship_event_handler` for stats, and returns `(exit_code, total_iterations)`. Resume context is used directly when provided (skips branch detection). Added 5 unit tests covering happy path, parent branch detection failure, resume context usage, agent not available, and pipeline stopped.
**Files Changed**:
- `build-loop/src/build_loop/cli.py` (replaced stub with full `run_ship_pipeline()`, added `_detect_parent_branch()` helper)
- `build-loop/tests/test_run_ship_pipeline.py` (new, 5 tests)
- `docs/tasks/main/specs/tasks.md` (marked 1.2.1 and all sub-tasks complete)
**Key Decisions**:
- `_detect_parent_branch()` extracted as private helper (same pattern as `_set_review_fixes_path`) — tries main/master/develop in order via `git merge-base`
- Resume context skips branch detection entirely (branch was already detected in the original session)
- Follows exact pattern of `run_plan_pipeline()` — same import structure, agent check, stats wiring, executor creation, return mapping
- Pre-existing `test_plan_cli.py` failures (2-tuple unpacking for 3-tuple `run_plan_pipeline`) confirmed not caused by this change
**Blockers/Risks**: None

## Iteration — [1.1] Add `--ship` Flag and Main Routing
**Status**: Complete
**What Was Done**: Added `--ship` as a `store_true` argument in `parse_args()` (placed after `--build`, near `--plan` and `--validate`) and added `--ship` routing block in `main()` after the `--plan` block but before interactive mode selection. The routing block resolves optional context files, saves session with `ship=True`, calls `run_ship_pipeline()`, calls `notify_ship_complete()`, and exits. Also updated the interactive mode guard to include `args.ship` so `--ship` skips the interactive menu. Added 7 unit tests covering flag parsing (happy + default), main routing (happy path, notification, context files, no context, session save).
**Files Changed**:
- `build-loop/src/build_loop/cli.py` (added `--ship` flag to `parse_args()`, added `--ship` routing block in `main()`, updated interactive mode guard)
- `build-loop/tests/test_ship_cli.py` (new, 7 tests)
- `docs/tasks/main/specs/tasks.md` (marked 1.1.1, 1.1.2 complete)
**Key Decisions**:
- `--ship` routing placed after `--plan` but before interactive mode selection, following the plan pattern exactly
- Context files are optional for `--ship` (no error without them) unlike `--plan` which requires `--context`
- Session saved with `ship=True` before pipeline runs, enabling resume support
- Interactive mode guard updated: `not args.ship` added to prevent `--ship` from falling through to interactive prompt
**Blockers/Risks**: None

## Iteration — [1.3] Add Ship to Interactive Mode
**Status**: Complete
**What Was Done**: Added `"ship"` as a selectable option in `prompt_for_mode()` (updated prompt text and validation set) and implemented the full interactive ship flow in `main()`. When user selects "ship" in interactive mode: prompts for optional context files, prompts for max iterations and agent, detects parent branch via `_detect_parent_branch()`, displays branch for user confirmation (Y/n), saves session with `ship=True`, calls `run_ship_pipeline()`, sends notification via `notify_ship_complete()`, and exits. Branch detection failure exits with error code 1. User declining branch confirmation cancels gracefully with exit 0. Added 9 unit tests covering prompt_for_mode ship option (accepts "ship", shows "ship" in prompt text, defaults to "build" on invalid) and interactive flow (happy path, no context, branch confirmation, branch decline, session save, branch detection failure).
**Files Changed**:
- `build-loop/src/build_loop/cli.py` (updated `prompt_for_mode()` to accept "ship", added `elif mode == "ship":` block in `main()`)
- `build-loop/tests/test_interactive_ship.py` (new, 9 tests)
- `docs/tasks/main/specs/tasks.md` (marked 1.3.1 and sub-tasks complete)
**Key Decisions**:
- Interactive ship flow prompts for branch confirmation (Y/n) before proceeding — safety measure since rebase is destructive
- Context files are optional (same as `--ship` flag mode) — ship works from branch state
- Follows exact pattern of interactive plan flow: prompt for inputs → detect state → confirm → save session → run pipeline → notify → exit
- Branch detection failure exits immediately with error (same as `run_ship_pipeline()` behavior)
**Blockers/Risks**: None
