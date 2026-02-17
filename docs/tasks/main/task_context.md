# Task Context: Planning Pipeline

## Technical Research

### Architecture Patterns

The build loop uses a stage-based pipeline architecture where:
- `PipelineExecutor` runs stages in a loop, following signal-based transitions
- Stages iterate internally (up to `max_iterations`) until a completion strategy detects a signal
- Context dict is the artifact bus — initialized with prompt variables, mutated by hooks, enriched with stage artifacts
- `before_stage` / `after_stage` hooks inject computed data between stages (e.g., git diffs)
- Completion strategies: `PromiseCompletion` (regex `[[PROMISE:SIGNAL]]`), `JsonCompletion` (parses ```json blocks), `CompositeCompletion` (fallback chain)
- Factory functions (e.g., `create_default_pipeline()`) construct `PipelineConfig` programmatically
- Session JSON at `.spectre/build-session.json` persists routing state for resume

### Key Integration Points

| Component | Role | File |
|-----------|------|------|
| `cli.py` | CLI routing, session save/load, `run_default_pipeline()` | `build-loop/src/build_loop/cli.py` |
| `loader.py` | Pipeline factory functions, YAML loading | `build-loop/src/build_loop/pipeline/loader.py` |
| `executor.py` | Stage orchestration, transitions, hooks | `build-loop/src/build_loop/pipeline/executor.py` |
| `stage.py` | Stage iteration loop, prompt building, completion eval | `build-loop/src/build_loop/pipeline/stage.py` |
| `completion.py` | Promise/JSON/Composite completion strategies | `build-loop/src/build_loop/pipeline/completion.py` |
| `hooks.py` | Inter-stage context injection (git scope) | `build-loop/src/build_loop/hooks.py` |
| `stats.py` | BuildStats dataclass, loop counters, dashboard | `build-loop/src/build_loop/stats.py` |
| `agent.py` | Agent runners (Claude/Codex), tool filtering | `build-loop/src/build_loop/agent.py` |
| `prompt.py` | Template loading + variable substitution | `build-loop/src/build_loop/prompt.py` |

### Existing Prompts to Adapt

The main Spectre repo has interactive planning prompts at `/Users/joe/Dev/spectre/plugins/spectre/commands/`:
- `plan.md` — Meta-router: researches codebase, assesses complexity (LIGHT/STANDARD/COMPREHENSIVE), routes to plan+tasks or tasks-only
- `create_plan.md` — Full plan generation: codebase research → clarifications → implementation plan
- `create_tasks.md` — Task breakdown: requirements extraction → hierarchical tasks → dependency analysis → execution strategies
- `plan_review.md` — Simplification review: finds over-engineering, removes unnecessary abstractions

These need adaptation for autonomous mode:
- Strip `AskUserQuestion` calls
- Remove "Reply 'Approved'" waits
- Replace interactive flow with file-based context reading
- Add JSON completion blocks for signal detection

### Implementation Approach

**New pipeline factory**: `create_plan_pipeline()` in `loader.py` — constructs 6-stage pipeline:

```
research → assess ─── LIGHT ──────────→ create_tasks → plan_review → req_validate
                  ├── STANDARD ───────→ create_plan → create_tasks → plan_review → req_validate
                  └── COMPREHENSIVE ──→ create_plan → create_tasks → plan_review → req_validate
```

**New CLI flag**: `--plan` in `cli.py`, routing to `run_plan_pipeline()`

**New prompts**: 6 templates in `build-loop/src/build_loop/prompts/planning/`:
- `research.md` — Codebase research, pattern analysis
- `assess.md` — Complexity scoring, architecture design (if COMPREHENSIVE)
- `create_plan.md` — Implementation plan generation (adapted from `/spectre:create_plan`)
- `create_tasks.md` — Task breakdown (adapted from `/spectre:create_tasks`)
- `plan_review.md` — Simplification pass (adapted from `/spectre:plan_review`)
- `req_validate.md` — Requirements cross-reference, clarifications or manifest output

**Session extension**: Add `plan: bool` and `plan_output_dir: str` to session JSON

**Completion strategy**: All stages use `JsonCompletion` with stage-specific signals

### Dependencies

- No new Python dependencies needed
- Reuses existing pipeline executor, stage, and completion machinery
- Prompt templates are self-contained markdown files

### Similar Features

The existing `create_default_pipeline()` factory is the direct pattern to follow. The planning pipeline is structurally identical — different stages, same executor.

### Impact Summary

| Area | Impact |
|------|--------|
| `cli.py` | Add `--plan` flag, `run_plan_pipeline()`, update session save/load/resume |
| `loader.py` | Add `create_plan_pipeline()` factory |
| `hooks.py` | Add planning-specific hooks (inject depth, output dir into context) |
| `prompts/planning/` | 6 new prompt templates (adapted from Spectre interactive prompts) |
| `stats.py` | Add `plan_loops` counter or reuse existing counters per stage name |
| `executor.py` | No changes |
| `stage.py` | No changes |
| `completion.py` | No changes |

## Scope Reference

Full scope document: `docs/tasks/main/concepts/planning-pipeline-scope.md`

## Decisions

- **Complexity-aware routing**: Assess stage emits LIGHT/STANDARD/COMPREHENSIVE signal; transitions skip create_plan for LIGHT
- **Single-pass plan review**: One simplification pass, then req_validate catches real gaps
- **File-mediated communication**: Each stage reads/writes files, no in-memory state beyond context dict
- **Pause/resume for clarifications**: Session persistence, user runs `spectre-build resume`
- **Manifest output**: Final artifact is a `.md` with YAML frontmatter for `spectre-build build.md`
