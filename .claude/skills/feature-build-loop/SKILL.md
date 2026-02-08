---
name: feature-build-loop
description: Use when modifying build loop code, debugging stats/token tracking, adding CLI features, changing iteration prompts, or understanding how spectre-build works end-to-end
user-invocable: false
---

# Build Loop (spectre-build)

**Trigger**: build loop, spectre-build, build iteration, validation cycle, promise tags, build stats
**Confidence**: high
**Created**: 2026-02-07
**Updated**: 2026-02-07
**Version**: 1

## What is Build Loop?

spectre-build is an automated task execution CLI that runs Claude Code (or Codex) in a loop, completing one parent task per iteration. The CLI handles the loop; the agent handles task tracking and progress writing. It supports recursive validation cycles that catch gaps and auto-remediate, multi-agent backends, manifest-driven configs, and a pipeline abstraction for multi-stage workflows.

## Why Use It?

| Problem | How Build Loop Solves It |
|---------|--------------------------|
| Manual re-prompting for multi-task builds | Runs autonomously, one task per iteration, until all tasks complete |
| No quality gate after build | Validation cycles detect gaps (dead code, missing connections) and auto-remediate |
| Session interruptions lose progress | Session persistence in `.spectre/build-session.json` enables `spectre-build resume` |
| Configuring builds is repetitive | Manifest mode: YAML frontmatter in `.md` files makes builds self-documenting |

## User Flows

### Flow 1: Flag-Based Build with Validation
```bash
spectre-build --tasks docs/tasks.md --context docs/scope.md --validate --max-iterations 15
```
1. Validates inputs (files exist, iterations > 0)
2. Saves session to `.spectre/build-session.json`
3. Runs build loop (1 task per iteration, up to max)
4. On BUILD_COMPLETE, runs validation pass
5. If gaps found → writes `validation_gaps.md` → runs another build cycle
6. Repeats until validation passes or 5 cycles hit
7. Prints aggregate stats dashboard

### Flow 2: Manifest-Driven Build
Create `build.md`:
```yaml
---
tasks: tasks.md
context:
  - scope.md
  - plan.md
max_iterations: 15
agent: claude
validate: true
---
# Feature Build
Description of what this build does...
```
Run: `spectre-build build.md`

### Flow 3: Resume Interrupted Session
```bash
spectre-build resume      # prompts for confirmation
spectre-build resume -y   # skip confirmation
```

## Technical Design

### Execution Flow
```
cli.main()
├─ parse_args() → determine mode (serve/resume/manifest/flag/interactive)
├─ validate_inputs()
├─ save_session()
└─ run_build_validate_cycle(tasks, context, max_iter, agent, validate)
    ├─ Creates ONE BuildStats for entire session
    ├─ while True:
    │   ├─ run_build_loop(tasks, context, max_iter, agent, stats)
    │   │   ├─ get_agent() → ClaudeRunner or CodexRunner
    │   │   ├─ for each iteration:
    │   │   │   ├─ build_prompt() from template + file paths
    │   │   │   ├─ runner.run_iteration(prompt, stats)
    │   │   │   │   ├─ spawn subprocess (claude -p --output-format stream-json)
    │   │   │   │   ├─ parse stream events in real-time
    │   │   │   │   │   ├─ "system" → capture model name
    │   │   │   │   │   ├─ "assistant" → display text + track tool calls
    │   │   │   │   │   └─ "result" → capture usage, cost, turns
    │   │   │   │   └─ return (exit_code, output, stderr)
    │   │   │   └─ detect_promise(output) → TASK_COMPLETE or BUILD_COMPLETE
    │   │   └─ return (exit_code, iterations_completed)
    │   ├─ [if validate] run_validation(tasks, context, agent, stats)
    │   │   ├─ build_validation_prompt()
    │   │   ├─ runner.run_iteration(prompt, stats) ← same shared stats
    │   │   ├─ parse_validation_json(output) → ValidationResult
    │   │   └─ return (exit_code, output, gaps_file)
    │   ├─ [if gaps_file] → set tasks = gaps_file, continue loop
    │   └─ [if no gaps] → break
    └─ stats.print_summary() ← ONE summary for entire session
```

### Promise-Based Flow Control
The agent signals completion via tags in its output text:
- `[[PROMISE:TASK_COMPLETE]]` → task done, loop continues
- `[[PROMISE:BUILD_COMPLETE]]` → all tasks done, exit loop

Detection: `re.search(r"\[\[PROMISE:(.*?)\]\]", output, re.DOTALL)`

Promise overrides exit code: if agent exits non-zero but emits a promise, the task is considered complete.

### Tool Filtering
**Allowed**: Bash, Read, Write, Edit, Glob, Grep, LS, TodoRead, TodoWrite, Skill
**Denied**: AskUserQuestion, WebFetch, WebSearch, Task, EnterPlanMode, NotebookEdit

Denied tools prevent: hanging on network calls, interactive prompts, or spawning unpredictable subagents.

### Stats Pipeline
Token usage and cost are tracked via a SINGLE `BuildStats` instance shared across all build and validation cycles:
- `stream.py` captures model from `system` events, usage/cost/turns from `result` events
- `stats.py` calculates cost from token breakdowns using model-specific pricing (opus/sonnet/haiku)
- Individual `assistant` events are NOT used for usage (only `result` events have authoritative totals)
- The summary dashboard prints once at the very end

### Validation Principle
> "Definition ≠ Connection ≠ Reachability"

Three levels verified:
1. **Defined**: Code exists in a file
2. **Connected**: Code is imported/called by other code
3. **Reachable**: A user action can trigger the code path

Validation dispatches parallel analyst subagents, consolidates findings, and writes `validation_gaps.md` as remediation tasks if gaps exist.

## Key Files

| File | Purpose | When to Modify |
|------|---------|----------------|
| `build-loop/src/build_loop/cli.py` | CLI orchestration, session management, build-validate cycle | Adding CLI flags, changing execution modes |
| `build-loop/src/build_loop/loop.py` | Core iteration loop, promise detection | Changing iteration behavior or exit conditions |
| `build-loop/src/build_loop/agent.py` | Agent runners (Claude/Codex), tool filtering | Adding new agent backends, changing tool allowlists |
| `build-loop/src/build_loop/stream.py` | Stream-JSON event parsing, model/usage capture | Fixing stats tracking, adding new event types |
| `build-loop/src/build_loop/stats.py` | BuildStats dataclass, cost calculation, dashboard | Adding new metrics, updating pricing |
| `build-loop/src/build_loop/validate.py` | Post-build validation, JSON result parsing | Changing validation flow or output format |
| `build-loop/src/build_loop/prompt.py` | Template loading + variable substitution | Changing prompt variables |
| `build-loop/src/build_loop/prompts/build.md` | 6-step iteration prompt template | Changing what the agent does per iteration |
| `build-loop/src/build_loop/prompts/validate.md` | Validation prompt with D!=C!=R principle | Changing validation criteria |
| `build-loop/src/build_loop/manifest.py` | YAML frontmatter parsing for manifest mode | Adding new manifest fields |

## Common Tasks

### Add a New CLI Flag
1. Add argument in `cli.py:parse_args()` (~line 110)
2. Wire it through to `run_build_validate_cycle()` or `run_build_loop()`
3. Add to `save_session()` for resume support
4. Add interactive prompt if needed (e.g. `prompt_for_X()`)

### Add a New Stat to the Dashboard
1. Add field to `BuildStats` dataclass in `stats.py`
2. Capture it in `stream.py:process_stream_event()` from the appropriate event type
3. Format and display in `stats.py:print_summary()`

### Change the Iteration Prompt
Edit `build-loop/src/build_loop/prompts/build.md`. Variables available:
- `{tasks_file_path}` — absolute path to tasks file
- `{progress_file_path}` — absolute path to progress file
- `{additional_context_paths_or_none}` — formatted context paths or "None"

### Add a New Agent Backend
1. Create a new `AgentRunner` subclass in `agent.py`
2. Implement `check_available()` and `run_iteration()`
3. Register in `_AGENTS` dict at bottom of `agent.py`
4. Add to `--agent` choices in `cli.py:parse_args()`

## Gotchas

- **Stats from `assistant` events are unreliable**: Only the `result` event has authoritative totals. Individual `assistant` events have partial per-turn fragments.
- **Promise overrides exit code**: A non-zero exit with a valid promise is NOT a failure. The loop warns but continues.
- **Validation cycle limit**: Max 5 cycles (`MAX_VALIDATION_CYCLES` in cli.py) prevents infinite remediation loops.
- **`owns_stats` flag**: When `run_build_loop()` receives an external `stats` param, it does NOT print the summary. The caller is responsible. This prevents duplicate dashboards.
- **Template variables must match exactly**: `{tasks_file_path}`, `{progress_file_path}`, `{additional_context_paths_or_none}` — typos silently break the prompt.
