---
name: feature-plan-pipeline
description: Use when modifying the planning pipeline, debugging plan stages, changing clarification flow, or understanding how spectre-build --plan works end-to-end
user-invocable: false
---

# Planning Pipeline (--plan)

**Trigger**: plan pipeline, --plan, planning loop, plan stages, clarifications, plan resume, scope to manifest
**Confidence**: high
**Created**: 2026-02-17
**Updated**: 2026-02-17
**Version**: 1

## What is the Planning Pipeline?

The `--plan` flag on `spectre-build` runs a multi-stage autonomous planning pipeline that transforms scope documents into a build-ready manifest. It decomposes the interactive `/spectre:plan` workflow into 7 independent stages — each reading and writing files — leveraging the existing pipeline executor with zero changes to the core engine.

**Key insight**: The plan loop does NOT use `--tasks` (tasks are *generated*, not provided). It takes `--context` scope docs as input and produces a `.md` manifest with YAML frontmatter as output.

## Why Use It?

| Problem | How Plan Pipeline Solves It |
|---------|---------------------------|
| 20-40 min manual planning orchestration before builds | Runs autonomously from scope docs to build manifest |
| Manual multi-step `/spectre:*` command sequencing | 7 stages execute in sequence, file-mediated |
| Complexity misjudgment (over/under-planning) | Assess stage scores complexity, routes LIGHT/STANDARD/COMPREHENSIVE |
| Plans that are over-engineered | Plan review stage catches unnecessary abstractions |
| Scope gaps discovered late | Req validate cross-references scope vs plan/tasks |
| Clarification needs block the entire pipeline | Pause/resume: saves session, user edits file, resumes |

## User Flows

### Flow 1: Normal Planning (scope → manifest)
```bash
spectre-build --plan --context scope.md design_notes.md --max-iterations 10
```
Pipeline runs 6 stages autonomously:
```
research → assess → [create_plan] → create_tasks → plan_review → req_validate
```
Output: `docs/tasks/{branch}/build.md` manifest, then run `spectre-build build.md`.

### Flow 2: LIGHT Complexity (skips plan generation)
```
research → assess(LIGHT) → create_tasks → plan_review → req_validate
```
Assess determines the task is simple enough to skip `create_plan` entirely.

### Flow 3: Clarification Pause + Resume
```bash
# Pipeline pauses:
spectre-build --plan --context scope.md
# → req_validate finds gaps
# → writes scope_clarifications.md
# → saves session, exits with code 0
# → prints: "Edit: .../scope_clarifications.md"

# User edits clarifications file, then:
spectre-build resume
# → detects plan=True in session
# → runs update_docs stage only
# → incorporates answers, writes manifest
```

## Technical Design

### CLI Routing (cli.py:main())
```
parse_args()
├─ --plan → run_plan_pipeline()              ← checked FIRST, before --validate
├─ --pipeline → run_pipeline()
├─ --validate (no --pipeline) → run_default_pipeline()
└─ no flags → run_build_validate_cycle()
```

`--plan` requires `--context` (errors without it). Does NOT require `--tasks`.

### Pipeline Structure (7 stages)

```
                                Normal flow
                                ══════════
research → assess ─── LIGHT ──────────────────→ create_tasks → plan_review → req_validate
                  ├── STANDARD ───────→ create_plan ─→ create_tasks → plan_review → req_validate
                  └── COMPREHENSIVE ──→ create_plan ─→ create_tasks → plan_review → req_validate

                                Resume flow (separate pipeline config)
                                ════════════════════════════════════
                                update_docs → PLAN_READY (end)
```

### Stage Definitions

| Stage | Completion | Signals | Max Iter | Transitions |
|-------|-----------|---------|----------|-------------|
| research | JSON | `RESEARCH_COMPLETE` | 1 | → assess |
| assess | JSON | `LIGHT`, `STANDARD`, `COMPREHENSIVE` | 1 | LIGHT→create_tasks, STANDARD/COMPREHENSIVE→create_plan |
| create_plan | JSON | `PLAN_COMPLETE` | 1 | → create_tasks |
| create_tasks | JSON | `TASKS_COMPLETE` | 1 | → plan_review |
| plan_review | JSON | `REVIEW_COMPLETE` | 1 | → req_validate |
| req_validate | JSON | `PLAN_VALIDATED`, `CLARIFICATIONS_NEEDED` | 1 | end pipeline |
| update_docs | JSON | `PLAN_READY` | 1 | end pipeline (resume only) |

All stages use `JsonCompletion` with `signal_field="status"`. End signals: `["PLAN_VALIDATED", "PLAN_READY"]`.

### run_plan_pipeline() Function (cli.py:653-796)

```python
def run_plan_pipeline(
    context_files: list[str],
    max_iterations: int,
    agent: str = "claude",
    output_dir: str | None = None,       # Default: docs/tasks/{branch}
    resume_stage: str | None = None,      # Set to "update_docs" for resume
    resume_context: dict | None = None,   # Preserved context from session
) -> tuple[int, int]:
```

Key behaviors:
1. **Output dir**: Auto-creates `docs/tasks/{branch}/`, `specs/`, `clarifications/` subdirs
2. **Pipeline selection**: `resume_stage` → `create_plan_resume_pipeline()`, else → `create_plan_pipeline()`
3. **Context dict**: Built fresh or restored from `resume_context`
4. **CLARIFICATIONS_NEEDED handling**: Saves session, prints instructions, returns exit 0
5. **PLAN_VALIDATED/PLAN_READY**: Prints manifest path and `spectre-build` command

### Context Variables (shared across stages)

```python
context = {
    "context_files": "- `scope.md`\n- `notes.md`",   # Input scope docs
    "output_dir": "/abs/path/docs/tasks/main",         # Artifact root
    "task_context_path": ".../task_context.md",         # Written by research
    "plan_path": ".../specs/plan.md",                   # Written by create_plan
    "tasks_path": ".../specs/tasks.md",                 # Written by create_tasks
    "clarifications_path": "",                          # Set by req_validate if gaps
    "clarification_answers": "",                        # Injected by hook for update_docs
    "manifest_path": "",                                # Set by req_validate/update_docs
    "depth": "standard",                                # Set by assess artifacts
    "tier": "STANDARD",                                 # Set by assess artifacts
}
```

### Planning Hooks (hooks.py)

**`plan_before_stage()`** (hooks.py:118):
- `create_plan`: Defaults `depth` to `"standard"` if missing
- `update_docs`: Reads clarifications file, injects content as `clarification_answers`

**`plan_after_stage()`** (hooks.py:147):
- `assess`: Ensures `depth` and `tier` from artifacts flow into context
- `req_validate` + CLARIFICATIONS_NEEDED: Stores `clarifications_path` in context

### Stats (stats.py)

- `plan_loops: int = 0` field on `BuildStats` (stats.py:64)
- `create_plan_event_handler(stats)` (stats.py:220) — factory returning callback that increments `plan_loops` on every `StageCompletedEvent`
- Dashboard shows `PLAN LOOPS: N` when `plan_loops > 0` (stats.py:205-206)

### Session Persistence (cli.py:30-67)

Planning adds 4 fields to session JSON:
```python
save_session(
    tasks_file="",                              # Empty for --plan
    plan=True,                                  # Planning mode flag
    plan_output_dir=output_dir,                 # Artifact directory
    plan_context=context,                       # Full context dict for resume
    plan_clarifications_path=clarif_path,       # Path to clarifications file
    ...
)
```

`format_session_summary()` shows "Mode: Planning", output dir, and clarifications path.

### Resume Flow (cli.py:836-856)

```
spectre-build resume
→ load_session()
→ session.get("plan") == True
→ save_session() (timestamp update)
→ run_plan_pipeline(
    resume_stage="update_docs",
    resume_context=session.get("plan_context"),
    output_dir=session.get("plan_output_dir"),
  )
→ create_plan_resume_pipeline() (single update_docs stage)
→ executor.run()
→ notification
```

### Tool Filtering

- **Research stage**: `PLAN_RESEARCH_DENIED_TOOLS` — allows `WebSearch`/`WebFetch` (for external API docs)
- **All other stages**: `PLAN_DENIED_TOOLS` — same as build loop restrictions

Defined in `loader.py:395-410`.

### Pipeline Factories (loader.py)

- `create_plan_pipeline()` (loader.py:413) — 7-stage config, `start_stage="research"`, `end_signals=["PLAN_VALIDATED", "PLAN_READY"]`
- `create_plan_resume_pipeline()` (loader.py:523) — single `update_docs` stage, `start_stage="update_docs"`, `end_signals=["PLAN_READY"]`

Resume uses a **separate pipeline config** (not a start-stage offset) to avoid modifying the executor.

## Key Files

| File | Purpose | When to Modify |
|------|---------|----------------|
| `build-loop/src/build_loop/cli.py` | `--plan` flag, `run_plan_pipeline()`, session save/load/resume | Adding plan CLI options, changing plan routing |
| `build-loop/src/build_loop/pipeline/loader.py` | `create_plan_pipeline()`, `create_plan_resume_pipeline()`, denied tools lists | Adding/removing plan stages, changing transitions |
| `build-loop/src/build_loop/hooks.py` | `plan_before_stage()`, `plan_after_stage()` | Changing what context flows between plan stages |
| `build-loop/src/build_loop/stats.py` | `plan_loops` field, `create_plan_event_handler()` | Adding plan-specific metrics |
| `build-loop/src/build_loop/prompts/planning/*.md` | 7 prompt templates (research, assess, create_plan, create_tasks, plan_review, req_validate, update_docs) | Changing agent instructions per stage |

## Common Tasks

### Change Planning Stage Behavior
1. Edit the prompt in `prompts/planning/{stage}.md`
2. If changing signals, update `complete_statuses` in `create_plan_pipeline()` (loader.py)
3. If changing transitions, update the `transitions` dict for that stage

### Add a New Planning Stage
1. Create prompt template in `prompts/planning/`
2. Add `StageConfig` to `create_plan_pipeline()` in loader.py
3. Wire transitions from/to adjacent stages
4. Add hook logic in `hooks.py` if inter-stage context injection needed

### Debug Clarification Flow
Trace: `req_validate` emits `CLARIFICATIONS_NEEDED` → `plan_after_stage()` stores path → pipeline ends → `run_plan_pipeline()` detects signal at cli.py:756 → `save_session()` → user edits file → `resume` → `plan_before_stage("update_docs")` reads file at hooks.py:136

## Gotchas

- **`--plan` without `--context` exits immediately**: Error at cli.py:1024-1026. No interactive fallback.
- **Resume uses a separate pipeline config**: `create_plan_resume_pipeline()`, not a start-stage param on the main pipeline. The executor always starts at `start_stage`.
- **Context dict is serialized to session JSON**: Must be JSON-serializable (no Path objects). All paths are strings.
- **CLARIFICATIONS_NEEDED is NOT in `end_signals`**: The pipeline ends because there's no transition for it (empty transitions dict on req_validate). The CLI detects it by checking `state.stage_history[-1][1]`.
- **Research stage tool filtering differs**: Only stage that allows WebSearch/WebFetch. Defined by `PLAN_RESEARCH_DENIED_TOOLS` vs `PLAN_DENIED_TOOLS`.
- **All stages max_iterations=1**: Each planning stage runs once. No looping within stages.
- **Artifacts flow via executor**: `context.update(result.artifacts)` happens automatically in executor after each stage. Hooks handle edge cases (defaults, file reading).
