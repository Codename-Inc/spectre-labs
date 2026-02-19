---
name: feature-build-loop
description: Use when modifying build loop code, debugging stats/token tracking, adding CLI features, changing iteration prompts, or understanding how spectre-build works end-to-end
user-invocable: false
---

# Build Loop (spectre-build)

**Trigger**: build loop, spectre-build, build iteration, validation cycle, promise tags, build stats, code review, phase awareness
**Confidence**: high
**Created**: 2026-02-07
**Updated**: 2026-02-18
**Version**: 3

## What is Build Loop?

spectre-build is an automated task execution CLI that runs Claude Code (or Codex) in a loop, completing one parent task per iteration. The CLI handles the loop; the agent handles task tracking and progress writing. It supports recursive validation cycles that catch gaps and auto-remediate, multi-agent backends, manifest-driven configs, and a pipeline abstraction for multi-stage workflows.

## Why Use It?

| Problem | How Build Loop Solves It |
|---------|--------------------------|
| Manual re-prompting for multi-task builds | Runs autonomously, one task per iteration, until all tasks complete |
| No quality gate after build | Code review + validation stages catch issues before moving on |
| Session interruptions lose progress | Session persistence in `.spectre/build-session.json` enables `spectre-build resume` |
| Configuring builds is repetitive | Manifest mode: YAML frontmatter in `.md` files makes builds self-documenting |
| Multi-phase plans need per-phase validation | Phase-aware signals route through review/validate per phase boundary |

## User Flows

### Flow 1: Flag-Based Build with Code Review + Validation (Default Pipeline)
```bash
spectre-build --tasks docs/tasks.md --context docs/scope.md --validate --max-iterations 15
```
When `--validate` is used without `--pipeline`, the CLI routes through `run_default_pipeline()` which creates a 3-stage pipeline:
1. **Build** — Completes tasks, emits TASK_COMPLETE / PHASE_COMPLETE / BUILD_COMPLETE
2. **Code Review** — Reviews git diff from build, emits APPROVED / CHANGES_REQUESTED
3. **Validate** — Checks D!=C!=R for completed work, emits ALL_VALIDATED / VALIDATED / GAPS_FOUND

Stage lifecycle hooks (`hooks.py`) snapshot HEAD before build, then inject `changed_files` and `commit_messages` into context for the code review prompt.

### Flow 2: Build Without Validation (Legacy Mode)
```bash
spectre-build --tasks docs/tasks.md --context docs/scope.md
```
Without `--validate`, uses `run_build_validate_cycle()` with validate=False — simple build loop only, no pipeline.

### Flow 3: Explicit Pipeline YAML
```bash
spectre-build --pipeline .spectre/pipelines/full-feature.yaml --tasks docs/tasks.md
```
Uses `run_pipeline()` to load and execute a custom YAML pipeline definition.

### Flow 4: Manifest-Driven Build
```bash
spectre-build build.md
```
YAML frontmatter in .md file. If `validate: true`, routes to default pipeline.

### Flow 5: Resume Interrupted Session
```bash
spectre-build resume      # prompts for confirmation
spectre-build resume -y   # skip confirmation
```

## Technical Design

### Execution Routing (cli.py:main())
```
parse_args()
├─ --pipeline → run_pipeline() (load YAML, execute)
├─ --validate (no --pipeline) → run_default_pipeline() (3-stage build/review/validate)
└─ no --validate, no --pipeline → run_build_validate_cycle(validate=False) (legacy build-only)
```

Same routing logic applies in `run_resume()` and `run_manifest()`.

### Default Pipeline Flow
```
run_default_pipeline()
├─ create_default_pipeline() → PipelineConfig with 3 stages
├─ Build context dict (tasks_file_path, progress_file_path, etc.)
├─ Wire on_event callback for stats loop counting
├─ PipelineExecutor(config, runner, on_event, context, before_stage, after_stage)
└─ executor.run(stats)
    ├─ For each stage transition:
    │   ├─ before_stage_hook(stage_name, context)
    │   │   └─ For "build": snapshot HEAD into context["_phase_start_commit"]
    │   ├─ stage.run(context, stats)
    │   ├─ after_stage_hook(stage_name, context, result)
    │   │   ├─ For "build": collect git diff, inject changed_files/commit_messages/review_fixes_path
    │   │   └─ For "validate": track validated phases in context["_validated_phases"]
    │   ├─ context.update(result.artifacts) — propagates phase metadata from build
    │   └─ Transition based on signal → transitions map
    └─ End when signal in end_signals (ALL_VALIDATED)
```

### Promise-Based Flow Control (Build Stage)
The agent signals completion via tags in its output text:
- `[[PROMISE:TASK_COMPLETE]]` → task done, loop back to build
- `[[PROMISE:PHASE_COMPLETE]]` → phase done, transition to code_review
- `[[PROMISE:BUILD_COMPLETE]]` → all tasks done, transition to code_review

Phase rules: If the tasks file has no `## Phase N:` headers, never emit PHASE_COMPLETE.

### Phase-Scoped Context Flow
When the build agent emits `PHASE_COMPLETE` or `BUILD_COMPLETE`, it also outputs a JSON block with phase metadata:
```json
{"phase_completed": "Phase 1: ...", "completed_phase_tasks": "- [x] ...", "remaining_phases": "Phase 2: ..."}
```
`PromiseCompletion(extract_artifacts=True)` extracts this JSON into `result.artifacts`. The executor's `context.update(result.artifacts)` propagates these values to downstream stages. Code review and validate prompts use `{phase_completed}`, `{completed_phase_tasks}`, `{remaining_phases}`, and `{validated_phases}` to scope their work to the current phase.

Validated phases are tracked via `after_stage_hook("validate")` which appends completed phase names to `context["_validated_phases"]`.

### Code Review Stage
Prompt receives `{changed_files}` and `{commit_messages}` injected by `after_stage_hook`.
- Reads all changed files, reviews for correctness/security/quality
- Severity scale: CRITICAL/HIGH/MEDIUM/LOW
- Approval threshold: APPROVED if zero CRITICAL and zero HIGH
- If CHANGES_REQUESTED: writes remediation tasks to `{review_fixes_path}`, loops back to build
- Build prompt checks for `{review_fixes_path}` existence and addresses fixes first

### Validate Stage Signals
- `ALL_VALIDATED` → all parent tasks `[x]` and verified → pipeline ends
- `VALIDATED` → current work verified, but unchecked tasks remain → loop back to build
- `GAPS_FOUND` → gaps in completed work → `after_stage_hook` sets `context["remediation_tasks_path"]` to the gaps file path, loops back to build

### GAPS_FOUND → Remediation Flow
When validate returns GAPS_FOUND with a `gaps_file` artifact:
1. `after_stage_hook("validate")` injects `remediation_tasks_path` into context
2. Build prompt tells agent to read the remediation file and work on those tasks instead of the original tasks file
3. Agent completes remediation tasks, emits BUILD_COMPLETE
4. Pipeline cycles back through code_review → validate
5. If validate passes (VALIDATED/ALL_VALIDATED), `remediation_tasks_path` is cleared

### Executor Hooks
`PipelineExecutor` accepts optional `before_stage` and `after_stage` callbacks:
```python
before_stage: Callable[[str, dict[str, Any]], None] | None
after_stage: Callable[[str, dict[str, Any], CompletionResult], None] | None
```
Called in `run()` immediately before/after `stage.run()`. Errors caught and logged (don't crash pipeline).

### Stats Pipeline
- `BuildStats` has `build_loops`, `review_loops`, `validate_loops` fields
- Incremented via `on_event` callback listening for `StageCompletedEvent`
- Dashboard shows `LOOPS B:3 R:2 V:1` line between COMMITS and TOKENS
- Token/cost tracking from `result` events, model-specific pricing in `_MODEL_PRICING`
- **Stats persistence**: `to_dict()`/`from_dict()`/`merge()` methods on BuildStats
- Stats saved to `.spectre/build-stats.json` at each stage boundary via `save_stats()`
- On resume, previous stats loaded via `load_stats()` and merged into fresh stats
- Stats file cleared on successful pipeline completion via `clear_stats()`
- `[🪳 TEMP STATS]` debug logging in stream.py and stats.py for token count diagnosis

### Tool Filtering
**Allowed**: Bash, Read, Write, Edit, Glob, Grep, LS, TodoRead, TodoWrite, Skill, Task
**Denied**: AskUserQuestion, WebFetch, WebSearch, EnterPlanMode, NotebookEdit

### Validation Principle
> "Definition != Connection != Reachability"

Three levels: Defined → Connected → Reachable

## Key Files

| File | Purpose | When to Modify |
|------|---------|----------------|
| `build-loop/src/build_loop/cli.py` | CLI orchestration, routing, run_default_pipeline | Adding CLI flags, changing execution modes |
| `build-loop/src/build_loop/loop.py` | Core iteration loop, promise detection | Changing iteration behavior (legacy path) |
| `build-loop/src/build_loop/agent.py` | Agent runners (Claude/Codex), tool filtering | Adding agent backends, changing tool allowlists |
| `build-loop/src/build_loop/stream.py` | Stream-JSON event parsing, model/usage capture | Fixing stats tracking, adding event types |
| `build-loop/src/build_loop/stats.py` | BuildStats dataclass, cost calculation, dashboard | Adding metrics, updating pricing |
| `build-loop/src/build_loop/validate.py` | Legacy validation, JSON result parsing | Changing legacy validation flow |
| `build-loop/src/build_loop/hooks.py` | Stage lifecycle hooks (git scope injection) | Changing what context flows between stages |
| `build-loop/src/build_loop/git_scope.py` | Git diff utilities (snapshot_head, collect_diff) | Changing git scope capture |
| `build-loop/src/build_loop/prompt.py` | Template loading + variable substitution | Changing prompt variables |
| `build-loop/src/build_loop/prompts/build.md` | Build iteration prompt (phase-aware) | Changing agent instructions |
| `build-loop/src/build_loop/prompts/code_review.md` | Code review prompt with scope injection | Changing review criteria |
| `build-loop/src/build_loop/prompts/validate.md` | Validation prompt with D!=C!=R | Changing validation criteria |
| `build-loop/src/build_loop/pipeline/executor.py` | PipelineExecutor with before/after hooks | Changing orchestration logic |
| `build-loop/src/build_loop/pipeline/loader.py` | YAML loading + create_default_pipeline() | Adding pipeline factories |
| `build-loop/src/build_loop/pipeline/stage.py` | Stage iteration + completion detection | Changing stage behavior |
| `build-loop/src/build_loop/pipeline/completion.py` | Promise/JSON/Composite strategies | Adding completion strategies |
| `build-loop/src/build_loop/manifest.py` | YAML frontmatter parsing | Adding manifest fields |

## Common Tasks

### Add a New Pipeline Stage
1. Create prompt template in `prompts/` directory
2. Add stage config to `create_default_pipeline()` in `loader.py`
3. Define completion strategy and transitions
4. If the stage needs inter-stage context, add logic to `hooks.py`
5. Update YAML files in `.spectre/pipelines/`

### Change Review/Validate Behavior
- Review criteria: edit `prompts/code_review.md`
- Validation criteria: edit `prompts/validate.md`
- Git scope injection: edit `hooks.py` (after_stage_hook)
- Signal routing: edit transitions in `loader.py:create_default_pipeline()`

### Add a New Stat to the Dashboard
1. Add field to `BuildStats` dataclass in `stats.py`
2. Capture it in `stream.py:process_stream_event()` or via `on_event` callback
3. Format and display in `stats.py:print_summary()`

### Change the Build Prompt
Edit `build-loop/src/build_loop/prompts/build.md`. Variables available:
- `{tasks_file_path}` — absolute path to tasks file
- `{progress_file_path}` — absolute path to progress file
- `{additional_context_paths_or_none}` — formatted context paths or "None"
- `{review_fixes_path}` — path to review remediation file (if exists)

## Gotchas

- **Stats from `assistant` events are unreliable**: Only `result` events have authoritative totals.
- **Promise overrides exit code**: Non-zero exit with valid promise is NOT a failure.
- **`owns_stats` flag**: When `run_build_loop()` receives external `stats`, it does NOT print summary.
- **Template variables must match exactly**: Typos silently break the prompt.
- **Code review needs git commits**: If no commits between build start and end, review sees "No files changed."
- **Phase headers are optional**: If tasks file has no `## Phase N:` headers, PHASE_COMPLETE is never emitted.
- **Legacy path still exists**: `run_build_validate_cycle()` is used for non-validate builds. Don't break it.
- **Hooks are error-safe**: before/after stage hooks catch exceptions and log warnings, never crash the pipeline.
- **Model pricing is hardcoded in stats.py**: Updated 2026-02-18 for Opus 4.5+/Sonnet 4.5+/Haiku 4.5 pricing. Will need updating when Anthropic changes prices.
- **Subagent tokens are invisible**: Task tool dispatches (e.g., clean_investigate, test_execute) create nested Claude sessions whose tokens don't flow through the parent stream parser. Stats undercount when subagents are active.
- **Stats persist across resume**: Stats saved to `.spectre/build-stats.json` at stage boundaries. Merged on resume. Cleared on successful completion.
