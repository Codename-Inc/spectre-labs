---
name: feature-ship-pipeline
description: Use when modifying the ship pipeline, debugging ship stages, changing clean/test/rebase behavior, or understanding how spectre-build --ship works end-to-end
user-invocable: false
---

# Ship Pipeline (--ship)

**Trigger**: ship pipeline, --ship, ship loop, clean stage, test stage, rebase stage, land branch, run_ship_pipeline, create_ship_pipeline
**Confidence**: high
**Created**: 2026-02-18
**Updated**: 2026-02-18
**Version**: 1

## What is the Ship Pipeline?

The `--ship` flag on `spectre-build` runs a 3-stage autonomous pipeline (clean → test → rebase) that takes a feature branch from "works on branch" to "landed on main" without human babysitting. It automates the manual ceremony of running `/spectre:clean`, `/spectre:test`, and `/spectre:rebase` in sequence.

**Key insight**: The ship loop does NOT use `--tasks` (work is generated from the branch's codebase state). It takes optional `--context` files and auto-detects the parent branch. The agent handles all git/gh commands via prompts — Python orchestrates, the agent acts.

## Why Use It?

| Problem | How Ship Pipeline Solves It |
|---------|---------------------------|
| 3 manual `/spectre:*` commands with babysitting between each | Runs autonomously: clean → test → rebase in one invocation |
| Dead code and duplication accumulate on feature branches | Clean stage systematically removes dead code and duplication |
| Test coverage gaps before landing | Test stage writes risk-tiered tests (P0-P3) for the working set |
| Rebase + PR creation is error-prone | Rebase stage handles rebase, conflict resolution, PR creation or local merge |
| Session interruptions lose progress | Session persistence + `spectre-build resume` for ship sessions |

## User Flows

### Flow 1: Flag Mode (Fully Autonomous)
```bash
spectre-build --ship --context scope.md --max-iterations 15
```
1. Detects parent branch (main/master/develop) via `git merge-base`
2. Computes working set scope (`{parent_branch}..HEAD`)
3. Runs clean stage (7 tasks, max 10 iterations)
4. Runs test stage (4 tasks, max 10 iterations)
5. Runs rebase stage (single context window, max 3 iterations)
6. Notifies on completion with audio

### Flow 2: Interactive Mode
```bash
spectre-build
# Select "ship" from mode prompt
# Prompted for optional context files
# Confirms detected parent branch
```

### Flow 3: Manifest Mode
```bash
spectre-build ship.md
```
Where `ship.md` has YAML frontmatter: `ship: true`

### Flow 4: Resume Interrupted Session
```bash
spectre-build resume      # prompts for confirmation
spectre-build resume -y   # skip confirmation
```

## Technical Design

### Execution Routing (cli.py:main())
```
parse_args()
├─ --ship → run_ship_pipeline() [cli.py:1294]
├─ interactive "ship" → _detect_parent_branch() + confirm + run_ship_pipeline() [cli.py:1365]
├─ manifest.ship → run_ship_pipeline() [cli.py:1143]
└─ resume session.get("ship") → run_ship_pipeline(resume_context=...) [cli.py:1032]
```

### Pipeline Architecture
```
run_ship_pipeline() [cli.py:859]
├─ _detect_parent_branch() → fail fast if None
├─ working_set_scope = f"{parent_branch}..HEAD"
├─ context dict: parent_branch, working_set_scope, context_files, clean_summary, test_summary
├─ create_ship_pipeline() [loader.py:413] → PipelineConfig(name="ship")
├─ create_ship_event_handler(stats) [stats.py:245]
├─ PipelineExecutor(config, runner, on_event, context, ship_before_stage, ship_after_stage)
└─ executor.run(stats) → (exit_code, total_iterations)
```

### Stage Configs (loader.py:create_ship_pipeline)
```
create_ship_pipeline(max_iterations=10) → PipelineConfig

Clean:  JsonCompletion(["CLEAN_TASK_COMPLETE", "CLEAN_COMPLETE"]), max=max_iterations
        transitions: CLEAN_TASK_COMPLETE→clean, CLEAN_COMPLETE→test
        prompt: prompts/shipping/clean.md

Test:   JsonCompletion(["TEST_TASK_COMPLETE", "TEST_COMPLETE"]), max=max_iterations
        transitions: TEST_TASK_COMPLETE→test, TEST_COMPLETE→rebase
        prompt: prompts/shipping/test.md

Rebase: JsonCompletion(["SHIP_COMPLETE"]), max=min(max_iterations, 3)
        transitions: {} (end)
        prompt: prompts/shipping/rebase.md

end_signals: ["SHIP_COMPLETE"]
All stages: denied_tools = PLAN_DENIED_TOOLS
```

### Inter-Stage Context Flow
```
Config (before pipeline)
  → context["parent_branch"] = detected parent
  → context["working_set_scope"] = commit range

ship_before_stage("clean") → snapshot HEAD
Clean stage → 7 tasks via clean.md
ship_after_stage("clean") → context["clean_summary"] = git diff summary

ship_before_stage("test") → snapshot HEAD
Test stage → 4 tasks via test.md
ship_after_stage("test") → context["test_summary"] = git diff summary

Rebase stage → reads parent_branch, clean_summary, test_summary
  → rebase, verify, land via PR or local merge
  → SHIP_COMPLETE → pipeline ends
```

### Parent Branch Detection (_detect_parent_branch)
Tries `git merge-base {candidate} HEAD` for each of: `main`, `master`, `develop`. For each candidate with a merge-base, counts commits between the merge-base and HEAD via `git rev-list --count`. Returns the candidate with the fewest commits (nearest ancestor), or `None` (fail fast with clear error).

### Landing Logic (in rebase prompt, agent-executed)
- **Remote + gh auth**: `gh pr create --base {parent_branch}` with PR template detection
- **No remote / no gh**: Local `git merge --ff-only` with stash approval via `read -p` if target branch is dirty
- Safety backup branch created before rebase: `git branch safety-backup-pre-rebase`

## Key Files

| File | Purpose | When to Modify |
|------|---------|----------------|
| `build-loop/src/build_loop/cli.py` | `--ship` flag, `run_ship_pipeline()`, `_detect_parent_branch()`, ship routing in main/resume/manifest/interactive, session save/load, format_session_summary | Adding CLI flags, changing orchestration, modifying session fields |
| `build-loop/src/build_loop/pipeline/loader.py` | `create_ship_pipeline()` factory, stage configs, transitions, denied tools | Adding/modifying stages, changing signals or iteration limits |
| `build-loop/src/build_loop/hooks.py` | `ship_before_stage()`, `ship_after_stage()`, `_collect_stage_summary()` | Changing what context flows between stages |
| `build-loop/src/build_loop/prompts/shipping/clean.md` | 7-task clean stage prompt, `{parent_branch}` and `{working_set_scope}` vars | Changing clean behavior, adding/removing tasks |
| `build-loop/src/build_loop/prompts/shipping/test.md` | 4-task test stage prompt, `{working_set_scope}` and `{context_files}` vars | Changing test strategy, risk tiers |
| `build-loop/src/build_loop/prompts/shipping/rebase.md` | Single-window rebase prompt, `{parent_branch}`, `{clean_summary}`, `{test_summary}` vars | Changing rebase/landing behavior, PR template logic |
| `build-loop/src/build_loop/stats.py` | `ship_loops` field, `create_ship_event_handler()`, `print_summary()` ship display | Adding ship-specific metrics |
| `build-loop/src/build_loop/notify.py` | `notify_ship_complete()` | Changing notification message or sound |
| `build-loop/src/build_loop/manifest.py` | `ship: bool` field in `BuildManifest`, parsed from frontmatter | Adding manifest fields |

## Common Tasks

### Add a New Ship Stage
1. Create prompt template in `prompts/shipping/` directory
2. Add `StageConfig` to `create_ship_pipeline()` in `loader.py`
3. Define `JsonCompletion` strategy with signal names and transitions
4. If stage needs inter-stage context, add logic to `ship_before_stage()`/`ship_after_stage()` in `hooks.py`
5. Update `end_signals` if the new stage is terminal

### Change Stage Behavior
- **Clean tasks**: Edit `prompts/shipping/clean.md` — 7 numbered tasks, each emits `CLEAN_TASK_COMPLETE`, last emits `CLEAN_COMPLETE`
- **Test tasks**: Edit `prompts/shipping/test.md` — 4 numbered tasks, each emits `TEST_TASK_COMPLETE`, last emits `TEST_COMPLETE`
- **Rebase flow**: Edit `prompts/shipping/rebase.md` — single window, emits `SHIP_COMPLETE`
- **Inter-stage context**: Edit `hooks.py` `ship_after_stage()` to change what flows between stages

### Change Iteration Limits
Edit `create_ship_pipeline()` in `loader.py`:
- Clean: `max_iterations=10` (line 435)
- Test: `max_iterations=10` (line 449)
- Rebase: `max_iterations=3` (line 463) — keep low, single context window

## Gotchas

- **No `--tasks` for ship**: Ship generates work from codebase state, unlike build which requires a tasks file. `save_session()` passes `tasks_file=""` for ship sessions.
- **Context files are optional**: Unlike `--plan` which requires `--context`, ship works without context files. They're just extra guidance for clean/test stages.
- **Parent branch detection picks nearest ancestor**: Checks `main`, `master`, `develop` and returns the one with fewest commits between merge-base and HEAD. No `--parent` override flag exists (yet). Fails on detached HEAD or non-standard branch names.
- **Rebase is single context window**: Max 3 iterations because conflict resolution needs continuous state. Don't increase this significantly.
- **Template variables must match context dict keys**: `run_ship_pipeline()` context dict (cli.py:916-922) must have keys matching all `{variable}` placeholders in all 3 prompts.
- **Denied tools same as plan**: Uses `PLAN_DENIED_TOOLS` from `loader.py` — blocks AskUserQuestion, WebFetch, WebSearch, Task, EnterPlanMode, NotebookEdit. `gh` works via the Bash tool which is allowed.
- **Hooks are error-safe**: `ship_before_stage`/`ship_after_stage` catch exceptions and log warnings, never crash the pipeline (PipelineExecutor wraps hook calls in try/except).
- **No core engine changes**: Ship loop was designed as a scope constraint — zero modifications to `PipelineExecutor`, `stage.py`, `completion.py`, `stream.py`, or `agent.py`.
- **Notification wired in 3 places**: `notify_ship_complete()` must be called from main (cli.py:1314), resume (cli.py:1084), and manifest (cli.py:1158). Missing any one = silent completion for that entry point.
- **Resume skips branch detection**: When resuming, `resume_context` is passed directly (cli.py:897-898), bypassing `_detect_parent_branch()`. The parent branch from the original session is preserved in `ship_context`.
