# Planning Pipeline — Scope

## The Problem

Today, going from scope docs to a build-ready task file requires manually orchestrating multiple `/spectre:*` commands in sequence — research, assess complexity, create plan, create tasks — with human judgment at every step. This works interactively but can't run autonomously. The build loop already solves this for *execution*; we need the same autonomous loop for *planning*.

**Pain**: Manual multi-step planning is slow, breaks flow, and requires the user to be the orchestrator between steps that an agent could handle.

**Impact**: Every feature build starts with 20-40 minutes of manual planning orchestration before the build loop can even start.

**Current state**: `/spectre:plan` exists as an interactive meta-prompt that routes between plan+tasks or tasks-only based on complexity. But it runs in a single Claude session, requires user confirmation at multiple points, and can't leverage the loop's strength of independent iterations reading/writing files.

## Target Users

- **Primary**: Joe (and anyone using `spectre-build`) who wants to go from scope docs to a running build loop with minimal manual intervention.

## Success Criteria

- `spectre-build --plan --context scope.md` produces a build-ready manifest `.md` file autonomously
- Complexity assessment determines planning depth (LIGHT skips plan, goes straight to tasks)
- Plan review catches over-engineering in a single simplification pass
- Requirements validation cross-references scope against plan/tasks, pauses for human clarification if needed
- Resume flow picks up after human answers clarifications, updates docs, and outputs the manifest
- Final output is a manifest `.md` with YAML frontmatter that can be fed directly to `spectre-build build.md`

## User Experience

### Primary Flow

```
spectre-build --plan --context scope.md other_docs.md --max-iterations 10

  Stage 1: RESEARCH        → reads scope docs, explores codebase → writes task_context.md
  Stage 2: ASSESS          → reads task_context.md, scores complexity → signals LIGHT|STANDARD|COMPREHENSIVE
  Stage 3: CREATE_PLAN     → (skipped if LIGHT) reads context → writes plan.md
  Stage 4: CREATE_TASKS    → reads plan.md + context → writes tasks.md
  Stage 5: PLAN_REVIEW     → reads plan.md + tasks.md → simplifies, updates both
  Stage 6: REQ_VALIDATE    → reads scope + plan + tasks → outputs clarifications or manifest

  If clarifications needed:
    → writes scope_clarifications.md, saves session, exits
    → user edits clarifications
    → spectre-build resume
    → reads clarifications, updates docs, writes manifest

  Output: build.md (manifest with YAML frontmatter)
  Command: spectre-build build.md
```

### Resume Flow

```
spectre-build resume

  --- Resume Planning Session ---
    Context:    scope.md
    Stage:      req_validate (paused for clarifications)
    Clarifications: docs/tasks/main/clarifications/scope_clarifications_2026-02-09.md
  ---

  Resume this session? [Y/n]
```

## Scope Boundaries

### IN

- `--plan` flag on `spectre-build` CLI, routing to `run_plan_pipeline()`
- 6-stage planning pipeline: research → assess → create_plan → create_tasks → plan_review → req_validate
- Complexity-aware routing: LIGHT skips create_plan, STANDARD/COMPREHENSIVE include it
- Adapted prompts for each stage (autonomous, no user confirmation waits)
- Prompt templates in `build-loop/src/build_loop/prompts/planning/` directory
- Pipeline factory: `create_plan_pipeline()` in `loader.py`
- Session persistence for pause/resume on clarifications
- Manifest `.md` output with YAML frontmatter as final artifact
- Stats tracking (planning_loops, tokens, cost) using existing BuildStats
- Notifications on completion

### OUT

- Automatic continuation into build loop (future enhancement, wire later)
- Interactive/inline clarification mode (MVP uses file-based pause/resume only)
- Custom pipeline YAML for planning (hardcoded factory like `create_default_pipeline()`)
- Web GUI support for planning pipeline
- `/spectre:plan` command changes (we adapt prompts, don't modify the interactive commands)

### MAYBE / FUTURE

- `--plan --build` flag combo that chains planning → build pipeline
- Planning pipeline YAML for user customization
- Watch mode that detects clarification file changes and auto-resumes

## Constraints

- Prompts must work autonomously — no `AskUserQuestion`, no "Reply 'Approved'" waits
- Each stage reads files from previous stages, writes files for next stages (file-mediated communication)
- Tool filtering same as build loop (no WebFetch, WebSearch, Task, etc.)
- Assess stage must use JSON completion strategy to emit LIGHT/STANDARD/COMPREHENSIVE signal
- Pipeline executor and stage machinery are reused as-is — no changes to `executor.py` or `stage.py`
- Session JSON must capture planning-specific state (current planning stage, output directory, clarifications path)

## Integration

### Touches

| Component | How |
|-----------|-----|
| `cli.py` | New `--plan` flag, `run_plan_pipeline()` function, session save/load updates |
| `loader.py` | New `create_plan_pipeline()` factory function |
| `hooks.py` | May need planning-specific hooks (e.g., inject depth into create_plan context) |
| `prompts/planning/` | New directory with 6 prompt templates |
| `stats.py` | Add `plan_loops` counter (or reuse existing loop counters per stage) |

### Avoids

- `executor.py` — no changes needed, transitions handle conditional routing
- `stage.py` — no changes needed
- `completion.py` — existing JSON + Promise strategies sufficient
- `loop.py` — legacy path, untouched
- Main Spectre repo prompts — we adapt, not modify

### Dependencies

- Existing pipeline executor + stage machinery
- Existing session persistence (extended for planning state)
- Existing completion strategies (JSON for assess signals, Promise for stage completion)

## Decisions

| Decision | Rationale |
|----------|-----------|
| `--plan` flag (not subcommand) | Follows `--validate` pattern, consistent CLI UX |
| Adapt prompts into `prompts/planning/` | Decouples from main Spectre repo, allows autonomous-mode modifications |
| Assess + architecture combined in one stage | Architecture is only needed for COMPREHENSIVE; assess stage does both when needed |
| File-mediated inter-stage communication | Leverages loop's strength — each stage is independent, reads/writes files |
| JSON completion for assess | Clean signal extraction (LIGHT/STANDARD/COMPREHENSIVE) via existing strategy |
| Single-pass plan review | Requirements validation catches real gaps; review is for simplification only |
| Pause/resume for clarifications | MVP approach; interactive mode is a future enhancement |

## Risks

| Risk | Mitigation |
|------|------------|
| Adapted prompts may behave differently without human checkpoints | Test with diverse scope docs; the req_validate stage catches gaps |
| Assess stage may misjudge complexity | Err toward STANDARD; user can override with `--depth` flag later |
| File paths between stages may break | Use absolute paths in context dict, same pattern as build pipeline |
| Session resume may not restore planning state correctly | Extend session JSON with planning-specific fields, test resume flow |

## Architecture Context

### Pipeline Definition

```
create_plan_pipeline() → PipelineConfig:
  stages:
    research:
      prompt: prompts/planning/research.md
      completion: json (signal: RESEARCH_COMPLETE)
      transitions: { RESEARCH_COMPLETE: assess }

    assess:
      prompt: prompts/planning/assess.md
      completion: json (signal: LIGHT | STANDARD | COMPREHENSIVE)
      transitions:
        LIGHT: create_tasks
        STANDARD: create_plan
        COMPREHENSIVE: create_plan

    create_plan:
      prompt: prompts/planning/create_plan.md
      completion: json (signal: PLAN_COMPLETE)
      transitions: { PLAN_COMPLETE: create_tasks }

    create_tasks:
      prompt: prompts/planning/create_tasks.md
      completion: json (signal: TASKS_COMPLETE)
      transitions: { TASKS_COMPLETE: plan_review }

    plan_review:
      prompt: prompts/planning/plan_review.md
      completion: json (signal: REVIEW_COMPLETE)
      transitions: { REVIEW_COMPLETE: req_validate }

    req_validate:
      prompt: prompts/planning/req_validate.md
      completion: json (signal: PLAN_VALIDATED | CLARIFICATIONS_NEEDED)
      transitions:
        CLARIFICATIONS_NEEDED: (pause/exit)
      end_signals: [PLAN_VALIDATED]

  start_stage: research
  end_signals: [PLAN_VALIDATED]
```

### Context Flow Between Stages

```
research  → writes: {out_dir}/task_context.md
assess    → reads: task_context.md, scope docs
           → writes: updates task_context.md with complexity tier + architecture (if COMPREHENSIVE)
           → artifacts: { depth: "standard"|"comprehensive", tier: "LIGHT"|"STANDARD"|"COMPREHENSIVE" }
create_plan → reads: task_context.md, scope docs
             → context: { depth } from assess artifacts
             → writes: {out_dir}/specs/plan.md
create_tasks → reads: plan.md (if exists), task_context.md, scope docs
              → writes: {out_dir}/specs/tasks.md
plan_review → reads: plan.md, tasks.md
             → writes: updates plan.md and tasks.md in-place
req_validate → reads: scope docs, plan.md, tasks.md
              → writes: {out_dir}/clarifications/scope_clarifications_{ts}.md (if gaps)
              → writes: {out_dir}/build.md (manifest, if validated)
```

### CLI Routing

```python
# In cli.py:main()
if args.plan:
    exit_code, iterations = run_plan_pipeline(
        context_files=context_files,
        max_iterations=max_iterations,
        agent=agent,
    )
```

Note: `--plan` uses `--context` for input docs (no `--tasks` required since tasks are generated). The `--tasks` flag is ignored when `--plan` is set.

## Next Steps

1. `/spectre:plan` with this scope doc to generate implementation plan + tasks
2. Or: `/spectre:create_tasks` directly if this scope is clear enough for task breakdown
