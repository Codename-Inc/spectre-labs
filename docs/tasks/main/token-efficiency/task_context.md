# Task Context — Token-Efficient Build Loop (Phase Owner Pattern)

## Architecture Patterns

### Current Build Stage Iteration Model
The build stage (in `pipeline/stage.py`) runs a loop: each call to `run_iteration()` starts a **fresh Claude session** via `AgentRunner.run_iteration()`. The agent reads all docs, completes one task, emits a promise tag, and exits. The stage evaluates the signal:
- `TASK_COMPLETE` → loops back to build (another fresh session, re-reads everything)
- `PHASE_COMPLETE` → transitions to code_review
- `BUILD_COMPLETE` → transitions to code_review

**This is where token waste occurs**: each `run_iteration()` is a new Claude session that re-reads all scope/plan/tasks/context files. For 8 tasks in a phase, that's 8 full context reads.

### Pipeline Orchestration (executor.py)
`PipelineExecutor.run()` manages stage transitions. It calls `stage.run()` which internally loops iterations, then checks the final signal against the transitions map. The executor also calls `before_stage`/`after_stage` hooks. The hooks for "build" snapshot HEAD before and collect git diff after.

### Code Review Context Injection (hooks.py)
`after_stage_hook("build")` collects git diff since `_phase_start_commit`:
- `format_file_list(diff)` → injected as `{changed_files}` in code_review prompt
- `format_commits(diff)` → injected as `{commit_messages}` in code_review prompt
- Also sets `review_fixes_path` for remediation file location

The code review prompt also receives `{tasks_file_path}`, `{progress_file_path}`, and `{additional_context_paths_or_none}` — these are the full context reads we want to eliminate.

### Token Tracking (stream.py + stats.py)
- `process_stream_event()` captures tokens from `result` events only (authoritative end-of-session totals)
- `BuildStats.add_usage()` accumulates input/output/cache tokens
- Cost calculated from token counts + model family pricing
- Subagent tokens dispatched via Task tool are invisible — they run inside Claude's session and their token usage is part of Claude's session, but the JSONL would have the full breakdown

### Tool Filtering
Per CLAUDE.md update, Task and Skill are now allowed in the pipeline (needed for subagent dispatch). `PLAN_DENIED_TOOLS` in loader.py blocks: AskUserQuestion, WebFetch, WebSearch, EnterPlanMode, NotebookEdit.

### spectre:execute Pattern (Reference Implementation)
The spectre:execute command in `/Dev/spectre` implements the exact pattern we want:
- Primary agent reads scope docs once
- Groups tasks into batches (up to 3 sequential tasks per subagent)
- Dispatches parallel `@dev` subagents via Task tool (single message, multiple calls)
- Each subagent receives: task batch + SCOPE_DOCS paths + completion reports from prior waves
- Subagents return structured completion reports: files changed, scope signals (⚪/🟡/🟠/🔴), implementation insights
- Primary agent marks tasks complete, reviews for E2E gaps, adapts future tasks
- TDD enforced via @skill-spectre:spectre-tdd

## Dependencies

### Files That Need Changes
| File | Change | Complexity |
|------|--------|------------|
| `prompts/build.md` | Rewrite as phase owner prompt (dispatch subagents, aggregate results) | High |
| `prompts/code_review.md` | Remove full context reads, add explicit task descriptions | Low |
| `hooks.py` | Phase owner may need to write review context; git hooks still capture diff | Medium |
| `stats.py` | Add subagent token tracking field + JSONL parsing | Medium |
| `pipeline/loader.py` | May need to adjust TASK_COMPLETE loopback behavior | Low |

### Files That Stay Unchanged
| File | Reason |
|------|--------|
| `pipeline/executor.py` | Orchestration logic is correct as-is |
| `pipeline/completion.py` | Completion strategies unchanged |
| `pipeline/stage.py` | Stage iteration model works (just fewer iterations) |
| `cli.py` | No new CLI flags; routing unchanged |
| `manifest.py` | No new manifest fields |

## Implementation Approaches

### Approach A: Prompt-Only Change (Minimal Infrastructure)
**Core idea**: Rewrite `build.md` so the agent acts as a phase owner. Keep all pipeline/stage/hook infrastructure as-is.

**How it works**:
1. Build stage starts → fresh Claude session (phase owner)
2. Phase owner reads all docs ONCE, identifies tasks in current phase
3. Phase owner dispatches parallel subagents via Task tool for each wave
4. Subagents execute, commit, write progress, return completion reports
5. Phase owner aggregates, adapts remaining waves, repeats until phase done
6. Phase owner emits `PHASE_COMPLETE` (or `BUILD_COMPLETE` if last phase)
7. Stage transitions to code_review as before

**Key changes**:
- `build.md` → full rewrite as phase owner prompt
- `code_review.md` → remove tasks/progress/context path references, add `{phase_task_descriptions}`
- `hooks.py` → phase owner writes a review context file with task descriptions + files, hook still captures git diff
- Git hooks still work because subagent commits are visible in the repo
- TASK_COMPLETE → build loopback becomes unused (phase owner handles task iteration internally)

**Pros**: Minimal infrastructure changes, backward compatible, proven pattern from spectre:execute
**Cons**: TASK_COMPLETE loopback is dead code in the pipeline config

### Approach B: Pipeline Factory + Prompt Changes
**Core idea**: Create `create_phase_owner_pipeline()` as a new pipeline factory alongside existing `create_default_pipeline()`.

**How it works**:
- New pipeline config: build stage has NO `TASK_COMPLETE` loopback, only `PHASE_COMPLETE` → code_review and `BUILD_COMPLETE` → code_review
- CLI auto-selects phase owner pipeline by default; `--legacy` flag for old behavior
- New prompt template for phase owner

**Pros**: Clean separation, no dead code, explicit pipeline intent
**Cons**: More infrastructure, new CLI flag, two pipeline factories to maintain

### Approach C: Hybrid (SELECTED)
**Core idea**: Prompt changes (like A) + small, targeted pipeline adjustments to keep things clean.

**How it works**:
1. Rewrite `build.md` as phase owner prompt
2. Update `create_default_pipeline()` — remove TASK_COMPLETE → build loopback (phase owner doesn't emit it)
3. Update code review prompt for isolation
4. Keep git hooks as-is (they work)
5. Add token tracking from JSONL

**Key difference from A**: Rather than leaving dead code (TASK_COMPLETE loopback), just remove it from the default pipeline config. One line change in `loader.py`.

**Pros**: Clean, minimal, no dead code
**Cons**: Very slightly less backward compatible (old build.md wouldn't work with new pipeline)

## Impact Summary

| Area | Impact |
|------|--------|
| Token efficiency | 60-80% reduction in input tokens (3 phase reads vs 24 task reads) |
| Build speed | Significant improvement from parallel wave dispatch |
| Code quality | Maintained or improved (same review + validate stages) |
| Infrastructure changes | Minimal (primarily prompt changes) |
| Backward compatibility | Legacy mode (`run_build_validate_cycle`) unaffected |

## External Research

Not applicable — this is an internal architecture optimization. The reference implementation (spectre:execute) is the primary prior art.
