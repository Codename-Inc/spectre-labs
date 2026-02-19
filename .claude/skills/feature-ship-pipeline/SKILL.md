---
name: feature-ship-pipeline
description: Use when modifying the ship pipeline, debugging ship stages, changing clean/test/rebase behavior, or understanding how spectre-build --ship works end-to-end
user-invocable: false
---

# Ship Pipeline (--ship)

**Trigger**: ship pipeline, --ship, ship loop, clean stage, test stage, rebase stage, land branch, run_ship_pipeline, create_ship_pipeline, ship hooks, notify_ship_complete
**Confidence**: high
**Created**: 2026-02-18
**Updated**: 2026-02-18
**Version**: 2

## What is the Ship Pipeline?

The `--ship` flag on `spectre-build` runs an 8-stage autonomous pipeline that takes a feature branch from "works on branch" to "landed on main" without human babysitting. It automates the manual ceremony of running `/spectre:clean`, `/spectre:test`, and `/spectre:rebase` in sequence.

The 8 stages are organized into three logical groups:
- **Clean group** (3 stages): clean_discover → clean_investigate → clean_execute
- **Test group** (4 stages): test_plan → test_execute → test_verify → test_commit
- **Rebase** (1 stage): rebase

**Key insight**: The ship loop does NOT use `--tasks` (work is generated from the branch's codebase state). It takes optional `--context` files and auto-detects the parent branch. The agent handles all git/gh commands via prompts — Python orchestrates, the agent acts.

## Why Use It?

| Problem | How Ship Pipeline Solves It |
|---------|---------------------------|
| 3 manual `/spectre:*` commands with babysitting between each | Runs autonomously: clean → test → rebase in one invocation |
| Dead code and duplication accumulate on feature branches | Clean group systematically discovers, investigates (with parallel subagents), and removes dead code/duplication |
| Test coverage gaps before landing | Test group plans risk-tiered tests (P0-P3), dispatches parallel subagents to write them, verifies, and commits |
| Rebase + PR creation is error-prone | Rebase stage handles rebase, conflict resolution, PR creation or local merge |
| Session interruptions lose progress | Session persistence + `spectre-build resume` for ship sessions |

## User Flows

### Flow 1: Flag Mode (Fully Autonomous)
```bash
spectre-build --ship --context scope.md --max-iterations 15
```
1. Detects parent branch (main/master/develop) via `git merge-base`
2. Computes working set scope (`{parent_branch}..HEAD`)
3. Runs 8 stages: clean_discover → clean_investigate → clean_execute → test_plan → test_execute → test_verify → test_commit → rebase
4. Notifies on completion with audio

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
├─ create_ship_pipeline() [loader.py:411] → PipelineConfig(name="ship")
├─ create_ship_event_handler(stats) [stats.py:245]
├─ PipelineExecutor(config, runner, on_event, context, ship_before_stage, ship_after_stage)
└─ executor.run(stats) → (exit_code, total_iterations)
```

### Stage Configs (loader.py:create_ship_pipeline)
```
create_ship_pipeline(max_iterations=10) → PipelineConfig

clean_discover:    JsonCompletion(["CLEAN_DISCOVER_TASK_COMPLETE", "CLEAN_DISCOVER_COMPLETE"])
                   transitions: TASK→clean_discover, COMPLETE→clean_investigate
                   prompt: prompts/shipping/clean_discover.md, max=max_iterations

clean_investigate: JsonCompletion(["CLEAN_INVESTIGATE_TASK_COMPLETE", "CLEAN_INVESTIGATE_COMPLETE"])
                   transitions: TASK→clean_investigate, COMPLETE→clean_execute
                   prompt: prompts/shipping/clean_investigate.md, max=max_iterations
                   ** Dispatches parallel subagents for investigation **

clean_execute:     JsonCompletion(["CLEAN_EXECUTE_TASK_COMPLETE", "CLEAN_EXECUTE_COMPLETE"])
                   transitions: TASK→clean_execute, COMPLETE→test_plan
                   prompt: prompts/shipping/clean_execute.md, max=max_iterations

test_plan:         JsonCompletion(["TEST_PLAN_TASK_COMPLETE", "TEST_PLAN_COMPLETE"])
                   transitions: TASK→test_plan, COMPLETE→test_execute
                   prompt: prompts/shipping/test_plan.md, max=max_iterations

test_execute:      JsonCompletion(["TEST_EXECUTE_TASK_COMPLETE", "TEST_EXECUTE_COMPLETE"])
                   transitions: TASK→test_execute, COMPLETE→test_verify
                   prompt: prompts/shipping/test_execute.md, max=max_iterations
                   ** Dispatches parallel @spectre:tester subagents **

test_verify:       JsonCompletion(["TEST_VERIFY_TASK_COMPLETE", "TEST_VERIFY_COMPLETE"])
                   transitions: TASK→test_verify, COMPLETE→test_commit
                   prompt: prompts/shipping/test_verify.md, max=min(max_iterations, 3)

test_commit:       JsonCompletion(["TEST_COMMIT_COMPLETE"])
                   transitions: COMPLETE→rebase
                   prompt: prompts/shipping/test_commit.md, max=1

rebase:            JsonCompletion(["SHIP_COMPLETE"])
                   transitions: {} (end)
                   prompt: prompts/shipping/rebase.md, max=min(max_iterations, 3)

start_stage: "clean_discover"
end_signals: ["SHIP_COMPLETE"]
All stages: denied_tools = PLAN_DENIED_TOOLS
```

### Inter-Stage Context Flow
```
Config (before pipeline)
  → context["parent_branch"] = detected parent
  → context["working_set_scope"] = commit range

ship_before_stage("clean_discover") → snapshot HEAD
  clean_discover → scope + dead code + duplication analysis
  clean_investigate → parallel subagent investigation of SUSPECT findings
  clean_execute → apply approved changes + lint
ship_after_stage("clean_execute") → context["clean_summary"] = git diff summary

ship_before_stage("test_plan") → snapshot HEAD
  test_plan → risk assessment + batching strategy
  test_execute → parallel subagent test writing
  test_verify → run suite, fix failures
  test_commit → stage and commit all test files
ship_after_stage("test_commit") → context["test_summary"] = git diff summary

rebase → reads parent_branch, clean_summary, test_summary
  → rebase, verify, land via PR or local merge
  → SHIP_COMPLETE → pipeline ends
```

### Hook Behavior (hooks.py)

**`ship_before_stage(stage_name, context)`**:
- `clean_discover` → snapshots HEAD (start of clean group)
- `test_plan` → snapshots HEAD (start of test group)
- All other sub-stages → no-op

**`ship_after_stage(stage_name, context, result)`**:
- `clean_execute` → captures `context["clean_summary"]` via git diff from snapshot
- `test_commit` → captures `context["test_summary"]` via git diff from snapshot
- All other sub-stages → no-op

### Subagent Dispatch Stages

Two stages use the Task tool to dispatch parallel subagents:

**clean_investigate**: Chunks SUSPECT findings into 2-5 groups, dispatches up to 4 parallel investigation subagents. Each receives area name, file list, patterns, and an investigation template. Reports: CONFIRMED_SAFE / NEEDS_VALIDATION / KEEP. Optional second wave for high-risk SAFE_TO_REMOVE items.

**test_execute**: Partitions test plan by risk tier, dispatches one @spectre:tester per batch in a SINGLE message with multiple Task tool calls. P0: 1 file/agent, P1: 2-3 files/agent, P2: 3-5 files/agent. Aims for 3-5 agents medium scope, up to 8 large scope.

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
| `build-loop/src/build_loop/pipeline/loader.py` | `create_ship_pipeline()` factory (8 stages), `PLAN_DENIED_TOOLS`, transitions, denied tools | Adding/modifying stages, changing signals or iteration limits |
| `build-loop/src/build_loop/hooks.py` | `ship_before_stage()`, `ship_after_stage()`, `_collect_stage_summary()` | Changing what context flows between stages |
| `build-loop/src/build_loop/prompts/shipping/clean_discover.md` | Scope + dead code + duplication analysis | Changing clean discovery behavior |
| `build-loop/src/build_loop/prompts/shipping/clean_investigate.md` | Parallel subagent investigation of SUSPECT findings | Changing investigation or subagent dispatch |
| `build-loop/src/build_loop/prompts/shipping/clean_execute.md` | Apply approved changes + lint compliance | Changing execution or commit behavior |
| `build-loop/src/build_loop/prompts/shipping/test_plan.md` | Risk assessment + batching strategy for parallel test writing | Changing test planning or risk tiers |
| `build-loop/src/build_loop/prompts/shipping/test_execute.md` | Parallel @spectre:tester subagent dispatch | Changing test execution or subagent dispatch |
| `build-loop/src/build_loop/prompts/shipping/test_verify.md` | Run test suite, diagnose/fix failures, re-verify | Changing verification behavior |
| `build-loop/src/build_loop/prompts/shipping/test_commit.md` | Stage and commit all test files | Changing commit behavior |
| `build-loop/src/build_loop/prompts/shipping/rebase.md` | Single-window rebase prompt, `{parent_branch}`, `{clean_summary}`, `{test_summary}` vars | Changing rebase/landing behavior, PR template logic |
| `build-loop/src/build_loop/stats.py` | `ship_loops` field, `create_ship_event_handler()`, `print_summary()` ship display | Adding ship-specific metrics |
| `build-loop/src/build_loop/notify.py` | `notify_ship_complete()` | Changing notification message or sound |
| `build-loop/src/build_loop/manifest.py` | `ship: bool` field in `BuildManifest`, parsed from frontmatter | Adding manifest fields |
| `build-loop/src/build_loop/prompts/shipping/clean.md` | **DEPRECATED** — original monolithic clean prompt, kept for custom YAML pipeline compat | Do not use for new work |
| `build-loop/src/build_loop/prompts/shipping/test.md` | **DEPRECATED** — original monolithic test prompt, kept for custom YAML pipeline compat | Do not use for new work |

## Common Tasks

### Add a New Ship Sub-Stage
1. Create prompt template in `prompts/shipping/` directory
2. Add `StageConfig` to `create_ship_pipeline()` in `loader.py` with `JsonCompletion` strategy
3. Define signal names and transitions (insert into the transition chain)
4. If sub-stage starts or ends a logical group, add logic to `ship_before_stage()`/`ship_after_stage()` in `hooks.py`
5. Update `end_signals` if the new stage is terminal
6. Update tests: `test_ship_pipeline.py`, `test_ship_hooks.py`, prompt tests

### Change Sub-Stage Behavior
- **Clean discover**: Edit `prompts/shipping/clean_discover.md` — scope, dead code, duplication analysis
- **Clean investigate**: Edit `prompts/shipping/clean_investigate.md` — subagent dispatch for investigation
- **Clean execute**: Edit `prompts/shipping/clean_execute.md` — apply changes, lint, commit
- **Test plan**: Edit `prompts/shipping/test_plan.md` — risk assessment, batching strategy
- **Test execute**: Edit `prompts/shipping/test_execute.md` — subagent dispatch for test writing
- **Test verify**: Edit `prompts/shipping/test_verify.md` — suite run, failure diagnosis
- **Test commit**: Edit `prompts/shipping/test_commit.md` — stage and commit
- **Rebase flow**: Edit `prompts/shipping/rebase.md` — single window, emits `SHIP_COMPLETE`
- **Inter-stage context**: Edit `hooks.py` `ship_after_stage()` to change what flows between groups

### Change Iteration Limits
Edit `create_ship_pipeline()` in `loader.py`:
- clean_discover, clean_investigate, clean_execute, test_plan, test_execute: `max_iterations` (default 10)
- test_verify: `min(max_iterations, 3)` — verification should be quick
- test_commit: `1` — single commit operation
- rebase: `min(max_iterations, 3)` — keep low, single context window

## Gotchas

- **No `--tasks` for ship**: Ship generates work from codebase state, unlike build which requires a tasks file. `save_session()` passes `tasks_file=""` for ship sessions.
- **Context files are optional**: Unlike `--plan` which requires `--context`, ship works without context files. They're just extra guidance for clean/test stages.
- **Parent branch detection picks nearest ancestor**: Checks `main`, `master`, `develop` and returns the one with fewest commits between merge-base and HEAD. No `--parent` override flag exists (yet). Fails on detached HEAD or non-standard branch names.
- **Rebase is single context window**: Max 3 iterations because conflict resolution needs continuous state. Don't increase this significantly.
- **Template variables must match context dict keys**: `run_ship_pipeline()` context dict (cli.py) must have keys matching all `{variable}` placeholders in all 8 sub-stage prompts + rebase.
- **Task tool is allowed**: `PLAN_DENIED_TOOLS` no longer blocks Task — this enables subagent dispatch in clean_investigate and test_execute. Per-stage `denied_tools` is wired through `Stage.run_iteration()` → `AgentRunner.run_iteration()`.
- **Hooks match on sub-stage names**: `ship_before_stage` matches `clean_discover` and `test_plan` (group starts). `ship_after_stage` matches `clean_execute` and `test_commit` (group ends). All other sub-stages are no-ops.
- **Hooks are error-safe**: `ship_before_stage`/`ship_after_stage` catch exceptions and log warnings, never crash the pipeline (PipelineExecutor wraps hook calls in try/except).
- **Old clean.md/test.md kept with deprecation headers**: For backward compat with custom YAML pipelines referencing the old monolithic prompts.
- **Notification wired in 3 places**: `notify_ship_complete()` must be called from main (cli.py:1314), resume (cli.py:1084), and manifest (cli.py:1158). Missing any one = silent completion for that entry point.
- **Resume skips branch detection**: When resuming, `resume_context` is passed directly (cli.py:897-898), bypassing `_detect_parent_branch()`. The parent branch from the original session is preserved in `ship_context`.
