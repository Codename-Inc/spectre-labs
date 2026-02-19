# Implementation Plan: Token-Efficient Build Loop (Phase Owner Pattern)

**Approach**: Hybrid (C) — Prompt rewrite + targeted pipeline cleanup
**Depth**: Standard
**Date**: 2026-02-18

---

## Overview

Replace the per-task fresh-session build model with a phase owner pattern. Currently, each of N tasks in a phase starts a new Claude session that re-reads all scope/plan/tasks/context files. With the phase owner pattern, one session per phase reads context once and dispatches parallel subagents for individual tasks.

**Token savings**: For a 3-phase, 24-task build, context reads drop from 24 to 3 (one per phase owner session).

**Speed gains**: Tasks within a wave execute in parallel via Task tool dispatch.

---

## Desired End State

1. **Build stage** runs one iteration per phase. The phase owner reads all context, identifies tasks in the current phase, groups them into waves, and dispatches parallel subagents. Each subagent receives only its task context + build progress path. Subagents commit independently and return completion reports. Phase owner aggregates results and emits `PHASE_COMPLETE` or `BUILD_COMPLETE` with enhanced artifact JSON.

2. **Code review stage** receives explicit task descriptions and git diff — no scope/plan/tasks file reads. The phase owner's artifact JSON includes `phase_task_descriptions` which flows into the code review prompt via `context.update(result.artifacts)`.

3. **Validate stage** continues to work as-is (already dispatches subagents). Optimization is prompt-level: ensure the validate agent reads context once and gives targeted slices to subagents.

4. **Pipeline config** has no `TASK_COMPLETE → build` loopback (phase owner handles task iteration internally).

5. **Token tracking** captures subagent usage from JSONL transcripts for accurate cost reporting.

---

## Out of Scope

- Plan loop optimization
- Output token reduction
- Pipeline executor/stage/completion strategy changes
- CLI flags, manifest fields, session/resume logic
- Validate dispatch pattern changes (already works)

---

## Technical Approach

### 1. Phase Owner Build Prompt (`prompts/build.md`)

Full rewrite. The new prompt instructs the agent to:

**Step 1 — Context Gathering** (same as today, but done ONCE per phase):
- Read progress file, context files, tasks file
- Identify current phase (first phase with incomplete tasks)

**Step 2 — Wave Planning**:
- Extract all tasks in current phase
- Group into parallelizable waves based on task doc structure
- For each wave, identify which tasks can run concurrently (no file conflicts)

**Step 3 — Subagent Dispatch** (per wave):
- For each task in the wave, construct a Task tool call with:
  - Task description (full text from tasks file)
  - Relevant context snippets (not full docs — phase owner extracts what's needed)
  - Build progress file path (subagents read for work context, append their log)
  - Dynamic instructions: implement task, run TDD via `@skill-spectre:spectre-tdd`, commit with conventional format, return completion report
- Dispatch all tasks in the wave simultaneously (single message, multiple Task tool calls)
- Wait for all subagents to complete

**Step 4 — Aggregation**:
- Read completion reports from all subagents
- Review scope signals (⚪/🟡/🟠/🔴) — adapt future waves if needed
- Mark tasks `[x]` in tasks file
- Update build progress with phase-level summary

**Step 5 — Next Wave or Complete**:
- If more waves remain in current phase → repeat Step 3
- If phase complete → proceed to Step 6

**Step 6 — STOP**:
- Emit `PHASE_COMPLETE` (if more phases) or `BUILD_COMPLETE` (if last phase)
- Include enhanced artifact JSON:
```json
{
  "phase_completed": "Phase 1: Data Layer",
  "completed_phase_tasks": "- [x] 1.1 Create models\n- [x] 1.2 Create store",
  "remaining_phases": "Phase 2: CLI Layer",
  "phase_task_descriptions": "Full text of tasks completed in this phase...",
  "files_touched": ["src/models.py", "src/store.py", "tests/test_models.py"]
}
```

**Subagent prompt pattern** (modeled after spectre:execute):
```
You are a build subagent. Execute the following task:

## Task
{task_description}

## Context
{relevant_context_snippet}

## Working Files
- Progress: {progress_file_path}

## Instructions
- Load @skill-spectre:spectre-tdd and follow TDD methodology
- Commit after completing the task: `feat({task_id}): {description}`
- Append your iteration log to the progress file
- Return a completion report:

## Completion Report
**Completed**: [task title]
**Files changed**: [path + description for each]
**Scope signal**: [⚪/🟡/🟠/🔴] - [justification]
**Discoveries**: [anything unexpected]
**Guidance**: [what downstream tasks should know]
```

### 2. Code Review Prompt (`prompts/code_review.md`)

Remove full context reads. The prompt currently has:
```
- **Tasks**: `{tasks_file_path}`
- **Progress**: `{progress_file_path}`
- **Additional Context**: {additional_context_paths_or_none}
```

Replace with:
```
- **Phase Task Descriptions**: {phase_task_descriptions}
```

Keep existing variables that already work:
- `{changed_files}` — from git hooks (still works, subagent commits visible)
- `{commit_messages}` — from git hooks
- `{phase_completed}` — from build artifacts
- `{validated_phases}` — from validate stage
- `{review_fixes_path}` — from hooks

The code review agent reads changed files and judges code quality against the task descriptions, without broader project context. This is intentional isolation.

### 3. Pipeline Config (`pipeline/loader.py`)

In `create_default_pipeline()`, update the build stage transitions:

**Before**:
```python
transitions={
    "TASK_COMPLETE": "build",      # ← remove this
    "PHASE_COMPLETE": "code_review",
    "BUILD_COMPLETE": "code_review",
},
```

**After**:
```python
transitions={
    "PHASE_COMPLETE": "code_review",
    "BUILD_COMPLETE": "code_review",
},
```

Also update `max_iterations` for the build stage. Currently 10 (for 10 tasks). With phase owner, each iteration covers one full phase. Set to 3 as default (most builds have 1-3 phases), configurable via the existing parameter.

### 4. Build Artifact Enhancement

The `PromiseCompletion(extract_artifacts=True)` already extracts the JSON block alongside promise tags. We add two new fields to the artifact JSON emitted by the phase owner:

- `phase_task_descriptions`: Full text of all tasks completed in this phase (for code review)
- `files_touched`: List of files changed by all subagents (supplementary to git diff)

These flow through `context.update(result.artifacts)` in `executor.py:275` — no changes to executor needed.

### 5. Hooks Adjustments (`hooks.py`)

Minimal changes. The existing `after_stage_hook("build")` still works:
- `snapshot_head()` captures HEAD before the phase owner starts
- Subagents commit during the phase
- `collect_diff()` captures all subagent commits
- `format_file_list()` and `format_commits()` inject into context

One small addition: after collecting the diff, also propagate `phase_task_descriptions` from build artifacts into the code review context (if not already handled by `context.update(result.artifacts)` in executor.py — verify during implementation).

### 6. Token Tracking (`stats.py`)

**Phase 1 (ship with phase owner)**: Accept that the phase owner session's `result` event captures the phase owner's own tokens but NOT subagent tokens. The dashboard will underreport. This is the current behavior and shipping the phase owner pattern is the priority.

**Phase 2 (follow-up)**: Parse JSONL transcripts post-build to extract subagent token usage. Claude CLI writes transcripts to `~/.claude/projects/{project-hash}/{session-id}.jsonl`. Add a `parse_session_tokens(jsonl_path)` utility that scans for `result` events in subagent sessions and aggregates.

### 7. Validate Prompt (No Changes Required)

The validate stage already:
- Reads full context once (max_iterations=1)
- Dispatches subagents per validation area
- Aggregates results and emits signals

The phase owner pattern doesn't change validate's behavior. The only improvement would be prompt-level: ensure the validate agent gives each subagent only the relevant slice of context. This is a prompt refinement, not infrastructure.

---

## Critical Files for Implementation

| File | Reason |
|------|--------|
| `build-loop/src/build_loop/prompts/build.md` | Full rewrite as phase owner prompt — the core of this feature |
| `build-loop/src/build_loop/prompts/code_review.md` | Remove full context reads, add phase_task_descriptions variable |
| `build-loop/src/build_loop/pipeline/loader.py:261-275` | Remove TASK_COMPLETE transition, adjust max_iterations |
| `build-loop/src/build_loop/hooks.py:38-79` | Verify artifact propagation, minor adjustments if needed |
| `/Users/joe/Dev/spectre/plugins/spectre/commands/execute.md` | Reference implementation — copy wave dispatch and completion report patterns |
| `build-loop/src/build_loop/prompts/validate.md` | Review for potential prompt-level optimization (low priority) |
