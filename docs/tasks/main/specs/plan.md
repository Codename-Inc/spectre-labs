# Implementation Plan: Ship Loop (`--ship`)

*standard depth | Generated 2026-02-18*

## Overview

The ship loop adds a third autonomous pipeline to `spectre-build` that takes a feature branch from "works on branch" to "landed on main" without human babysitting. It automates the manual ceremony of running `/spectre:clean`, `/spectre:test`, and `/spectre:rebase` in sequence by wrapping them as three pipeline stages — clean, test, and rebase — executed by the existing `PipelineExecutor`.

After implementation, a developer finishes a build loop and runs `spectre-build --ship` (or `spectre-build ship.md` via manifest). The CLI detects the parent branch, runs the clean stage (dead code removal, lint, 7 task iterations), the test stage (coverage, risk-tiered tests, 4 task iterations), and the rebase stage (rebase onto parent, resolve conflicts, land via PR or local merge — single context window, max 3 iterations). The branch is landed, the user gets a notification with audio, and the session supports resume if interrupted. No changes are made to `PipelineExecutor`, `stage.py`, `completion.py`, `stream.py`, or `agent.py` — all ship-specific behavior lives in new prompt templates, hooks, a pipeline factory, and CLI routing.

## Out of Scope

- Chaining from `--build` to `--ship` (manual human validation sits between build and ship)
- Stage skipping flags (`--skip-clean`, `--skip-test`) — always runs all 3 stages
- Running git/gh commands from Python code — agents handle all commands via prompts
- Standalone CLI command — stays as a flag on `spectre-build`
- New completion strategies — reuses existing `JsonCompletion`
- Changes to `PipelineExecutor` — uses the existing executor as-is
- Custom ship pipeline YAML definitions
- Ship-specific code review stage

## Technical Approach

### CLI Routing and `--ship` Flag

Add `--ship` as a `store_true` argument in `parse_args()` (`cli.py:128`), placed near `--plan` (line 218) and `--validate` (line 211). In `main()` (line 1043), the `--ship` check is inserted after the `--plan` block (line 1076) but before `--validate`. The pattern mirrors `--plan`: check flag, resolve context files (optional for ship — ship works from the branch's current state), detect parent branch, save session, call `run_ship_pipeline()`, notify, exit.

Unlike `--plan`, `--ship` does NOT require `--context` or `--tasks`. Context files are optional (they help the clean/test stages focus on what matters). The ship loop generates its own work from the codebase state.

Interactive mode (no flags provided) gets a new `"ship"` option in `prompt_for_mode()` (line 1115). When selected, it prompts for optional context files, confirms the detected parent branch, and runs `run_ship_pipeline()`.

### `run_ship_pipeline()` Function

New function in `cli.py`, modeled on `run_plan_pipeline()` (line 686). Signature:

```python
def run_ship_pipeline(
    context_files: list[str],
    max_iterations: int,
    agent: str = "claude",
    resume_context: dict | None = None,
) -> tuple[int, int]:
```

Key behaviors:
1. **Parent branch detection**: Before creating the pipeline, detect the parent branch using `git merge-base --fork-point` or `git log` heuristics. This is the rebase target and is injected into context as `parent_branch`. Fail fast with a clear error if detection fails (detached HEAD, no tracking branch).
2. **Working set scope**: Compute the commit range `{parent_branch}..HEAD` and inject as `working_set_scope` so the clean/test stages know what files to focus on.
3. **Context dict**: Build `context` with keys: `parent_branch`, `working_set_scope`, `context_files` (formatted list), `clean_summary` (empty, filled by after-hook), `test_summary` (empty, filled by after-hook).
4. **Pipeline creation**: Call `create_ship_pipeline()` from `loader.py`.
5. **Executor wiring**: Create `PipelineExecutor` with `ship_before_stage` / `ship_after_stage` hooks from `hooks.py`, and an `on_event` callback from `create_ship_event_handler()` for stats.
6. **Return**: `(exit_code, total_iterations)` — no manifest path needed (unlike plan).

### Pipeline Factory (`create_ship_pipeline()`)

New function in `loader.py`, following the pattern of `create_plan_pipeline()` (line 413). Returns a `PipelineConfig` with:

- **name**: `"ship"`
- **start_stage**: `"clean"`
- **end_signals**: `["SHIP_COMPLETE"]`
- **3 stages**:

**Clean stage**: `JsonCompletion(complete_statuses=["CLEAN_TASK_COMPLETE", "CLEAN_COMPLETE"], signal_field="status")`, `max_iterations=10`, transitions `{"CLEAN_TASK_COMPLETE": "clean", "CLEAN_COMPLETE": "test"}`. Prompt at `prompts/shipping/clean.md`. Reuses `PLAN_DENIED_TOOLS` (restrictions are identical).

**Test stage**: `JsonCompletion(complete_statuses=["TEST_TASK_COMPLETE", "TEST_COMPLETE"], signal_field="status")`, `max_iterations=10`, transitions `{"TEST_TASK_COMPLETE": "test", "TEST_COMPLETE": "rebase"}`. Prompt at `prompts/shipping/test.md`.

**Rebase stage**: `JsonCompletion(complete_statuses=["SHIP_COMPLETE"], signal_field="status")`, `max_iterations=3`, transitions `{}` (end). Prompt at `prompts/shipping/rebase.md`.

All three stages use the same denied tools list. `gh` is invoked via the Bash tool which is already in the allowed list — no tool filtering changes needed.

### Inter-Stage Hooks (`hooks.py`)

Add `ship_before_stage()` and `ship_after_stage()` following the same signature as `plan_before_stage()` (line 118) and `plan_after_stage()` (line 147).

**`ship_before_stage(stage_name, context)`**:
- `"clean"`: Validate `parent_branch` is in context. Snapshot HEAD via `snapshot_head()` from `git_scope.py` so the after-hook can compute what the clean stage changed.
- `"test"`: Snapshot HEAD again for the test stage's diff tracking.
- `"rebase"`: No special before-hook needed — context already has `parent_branch`, `clean_summary`, `test_summary`.

**`ship_after_stage(stage_name, context, result)`**:
- `"clean"`: Collect git diff since the before-hook snapshot. Summarize as `clean_summary` (files removed, commits made). Store in context for the rebase prompt's PR description.
- `"test"`: Collect git diff since the before-hook snapshot. Summarize as `test_summary` (tests added, coverage changes). Store in context.
- `"rebase"`: No special after-hook needed — pipeline ends on `SHIP_COMPLETE`.

### Prompt Templates (3 new files)

**`prompts/shipping/clean.md`**: Task checklist with 7 items from the scope (working set scope, dead code analysis, duplication analysis, subagent investigation, validation, execute removals + verify + commit, ESLint compliance). Uses `{parent_branch}` and `{working_set_scope}` context variables. Each task completion emits `{"status": "CLEAN_TASK_COMPLETE"}`. Final completion emits `{"status": "CLEAN_COMPLETE"}`. Follows the iterative prompt pattern from the build prompt — clear STOP instructions between tasks.

**`prompts/shipping/test.md`**: Task checklist with 4 items (discover working set + plan, risk assessment + test plan, write tests + verify, commit). Uses `{working_set_scope}` and optional `{context_files}` variables. Emits `{"status": "TEST_TASK_COMPLETE"}` per task, `{"status": "TEST_COMPLETE"}` when done.

**`prompts/shipping/rebase.md`**: Single context window (not decomposed). Uses `{parent_branch}`, `{clean_summary}`, `{test_summary}` context variables. Covers: confirm target branch, prepare (commit uncommitted work, fetch, create safety ref branch), execute rebase, resolve conflicts if any, verify (lint + tests pass), land via PR (if remote exists — check `gh auth status` first, use repo PR template if found) or local merge (stash approval flow using `read -p` via Bash if target branch is dirty). Emits `{"status": "SHIP_COMPLETE"}`.

### Session Persistence and Resume

Add `ship: bool = False` and `ship_context: dict | None = None` parameters to `save_session()` (`cli.py:30`). All new params have defaults for backward compatibility — `load_session()` uses `.get()` with defaults (line 70), so existing sessions are unaffected.

In `run_resume()` (line 844), add `elif session.get("ship"):` after the `if session.get("plan"):` block (line 881). This calls `run_ship_pipeline()` with `resume_context=session.get("ship_context")`. The pipeline executor picks up from the last completed stage via the context dict's state.

Update `format_session_summary()` (line 87) to show "Mode: Ship" when `session.get("ship")` is true, and display `parent_branch` from `ship_context`.

### Manifest Support

Add `ship: bool = False` field to `BuildManifest` dataclass (`manifest.py:13`). Update `load_manifest()` (line 117) to parse `ship` from frontmatter — same pattern as `validate` (line 169).

In `run_manifest()` (`cli.py:954`), after loading the manifest, check `manifest.ship` and route to `run_ship_pipeline()` instead of the build pipeline. This check goes before the `validate` check.

### Stats Tracking

Add `ship_loops: int = 0` to `BuildStats` dataclass (`stats.py:48`, alongside `plan_loops` at line 64). Add `create_ship_event_handler(stats)` factory function following `create_plan_event_handler()` (line 220) — increments `ship_loops` on each `StageCompletedEvent`.

Update `print_summary()` (line 154) to display ship loop count when `ship_loops > 0`, following the plan loops pattern (lines 205-206).

### Notification

Add `notify_ship_complete()` to `notify.py`, following `notify_plan_complete()` (line 152). Same pattern: branch detection via `get_git_branch()`, subtitle formatting, success/failure messaging. Message: `"Ship complete! {stages} stages in {time}"` / `"Ship failed after {stages} stages ({time})"`.

Import and call from `run_ship_pipeline()` call sites in `main()`, `run_resume()`, and `run_manifest()`.

## Critical Files for Implementation

| File | Reason |
|------|--------|
| `build-loop/src/build_loop/cli.py` | Add `--ship` flag to `parse_args()`, new `run_ship_pipeline()` function, wire routing in `main()`, `run_resume()`, `run_manifest()`, extend `save_session()` with ship fields, update `format_session_summary()`, add ship to interactive mode |
| `build-loop/src/build_loop/pipeline/loader.py` | Add `create_ship_pipeline()` factory returning 3-stage PipelineConfig with JsonCompletion strategies and transitions |
| `build-loop/src/build_loop/hooks.py` | Add `ship_before_stage()` and `ship_after_stage()` for parent branch validation, HEAD snapshots, and clean/test summary capture |
| `build-loop/src/build_loop/prompts/shipping/clean.md` | New file. Clean stage prompt with 7-task checklist, `{parent_branch}` and `{working_set_scope}` variables, CLEAN_TASK_COMPLETE/CLEAN_COMPLETE signals |
| `build-loop/src/build_loop/prompts/shipping/test.md` | New file. Test stage prompt with 4-task checklist, `{working_set_scope}` variable, TEST_TASK_COMPLETE/TEST_COMPLETE signals |
| `build-loop/src/build_loop/prompts/shipping/rebase.md` | New file. Rebase prompt (single context window), `{parent_branch}`/`{clean_summary}`/`{test_summary}` variables, PR creation or local merge logic, SHIP_COMPLETE signal |
| `build-loop/src/build_loop/stats.py` | Add `ship_loops` field to `BuildStats`, `create_ship_event_handler()` factory, update `print_summary()` dashboard |
| `build-loop/src/build_loop/notify.py` | Add `notify_ship_complete()` function following existing notification pattern |
| `build-loop/src/build_loop/manifest.py` | Add `ship: bool = False` field to `BuildManifest`, parse from frontmatter in `load_manifest()` |

## Risks

| Risk | Mitigation |
|------|------------|
| Parent branch detection fails (detached HEAD, no tracking branch, ambiguous merge-base) | Fail fast with clear error message in `run_ship_pipeline()` config step. Provide `--parent` override flag as escape hatch if needed (future scope). |
| Clean stage removes production code incorrectly | Clean prompt enforces conservative validation (CONFIRMED_SAFE only), subagent cross-validation pattern from existing `/spectre:clean` workflow |
| Rebase conflicts cause data loss | Rebase prompt creates safety ref branch before rebase. Agent can `git rebase --abort` and restore. Safety ref documented in prompt. |
| PR creation fails (no `gh` auth, no remote) | Rebase prompt instructs agent to check `gh auth status` before attempting PR. Falls back to local merge path. Reports clearly if neither is possible. |
| Stash approval flow can't use `AskUserQuestion` (denied tool) | Agent uses `read -p "Approve stash+merge? [y/N]"` via Bash tool — shell builtin, not a Claude tool. Works because Bash is in the allowed list. |
| Token budget exceeded in clean/test stages | Task decomposition (7 clean tasks, 4 test tasks) with `max_iterations=10` cap per stage. Pipeline reports and moves on if budget exceeded. |
| Template variable mismatch between prompts and context dict | Document exact variable names in prompts and verify `run_ship_pipeline()` context dict keys match. Template variables must match exactly — typos produce literal `{variable}` in prompt text. |
| `save_session()` backward compatibility broken | All new parameters (`ship`, `ship_context`) have defaults. `load_session()` uses `.get()` with defaults. Existing sessions unaffected. |
