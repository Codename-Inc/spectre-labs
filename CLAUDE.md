# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

SPECTRE Labs contains experimental features for the [SPECTRE](https://github.com/Codename-Inc/spectre) workflow framework:

1. **Build Loop** (`build-loop/`) - Automated task execution CLI that runs Claude Code iteratively, completing one task per iteration
2. **Sparks** (`sparks/`) - Knowledge capture plugin for Claude Code that enables learning reuse across sessions

## Tech Stack

- Python 3.10+
- setuptools for packaging (src layout)
- argparse for CLI
- subprocess with stream-JSON parsing for Claude process management
- macOS native notifications via osascript (cross-platform fallback)

## Commands

### Build Loop Installation & Usage

```bash
# Install as CLI tool
cd build-loop
pipx install -e .

# Run with task file
spectre-build --tasks tasks.md --max-iterations 10

# With additional context
spectre-build --tasks tasks.md --context scope.md plan.md --max-iterations 15

# Resume interrupted session
spectre-build resume

# Help
spectre-build --help
```

### Sparks Plugin Installation

```bash
/plugin marketplace add Codename-Inc/spectre-labs
/plugin install sparks@spectre-labs
```

### Development

```bash
# Run directly without installing
python -m build_loop.cli --help

# Install in editable mode
pip install -e build-loop/
```

### Release

```bash
# Interactive release script - bumps versions, commits, tags, pushes
node scripts/release.js
```

Updates versions in:
- `sparks/.claude-plugin/plugin.json`
- `.claude-plugin/marketplace.json`
- `build-loop/pyproject.toml`

## Architecture

### Build Loop Package Structure

```
build-loop/
├── pyproject.toml
└── src/build_loop/
    ├── __init__.py      # Package entry point (main function)
    ├── cli.py           # CLI arg parsing, routing, run_default_pipeline
    ├── loop.py          # Core iteration loop (legacy build-only path)
    ├── hooks.py         # Stage lifecycle hooks (git scope injection)
    ├── git_scope.py     # Git diff utilities for inter-stage context
    ├── prompt.py        # Template loading
    ├── stats.py         # BuildStats dataclass (with loop counters)
    ├── stream.py        # Stream-JSON parsing
    ├── notify.py        # macOS notifications
    ├── pipeline/        # Stage-based pipeline executor
    │   ├── executor.py  # PipelineExecutor with before/after hooks
    │   ├── stage.py     # Stage iteration + completion detection
    │   ├── completion.py # Promise/JSON/Composite strategies
    │   └── loader.py    # YAML loading + create_default_pipeline()
    └── prompts/
        ├── build.md         # Build iteration (phase-aware)
        ├── code_review.md   # Code review with scope injection
        ├── validate.md      # Validation with D!=C!=R
        └── shipping/        # Ship pipeline prompts (8 sub-stages)
            ├── clean_discover.md     # Scope + dead code + duplication analysis
            ├── clean_investigate.md  # Parallel subagent investigation
            ├── clean_execute.md      # Apply changes + lint compliance
            ├── test_plan.md          # Risk assessment + batching strategy
            ├── test_execute.md       # Parallel subagent test writing
            ├── test_verify.md        # Run suite, fix failures, re-verify
            ├── test_commit.md        # Stage and commit test files
            └── rebase.md             # Rebase, conflicts, land via PR/merge
```

### Build Loop Module Dependencies

```
cli.py → loop.py, notify.py, hooks.py, pipeline/
hooks.py → git_scope.py, pipeline/completion.py
loop.py → prompt.py, stats.py, stream.py
pipeline/executor.py → pipeline/stage.py, stats.py
pipeline/loader.py → pipeline/completion.py, pipeline/executor.py, pipeline/stage.py
prompt.py → prompts/build.md (template file)
stream.py → stats.py (updates BuildStats during event processing)
```

### Core Execution Flow

**With --validate (default pipeline):**
1. `cli.py:run_default_pipeline()` creates 3-stage pipeline (build/code_review/validate)
2. `PipelineExecutor` runs stages with lifecycle hooks:
   - `before_stage_hook`: Snapshots HEAD before build
   - Build stage iterates tasks, emits TASK_COMPLETE/PHASE_COMPLETE/BUILD_COMPLETE
   - `after_stage_hook`: Collects git diff, injects into context
   - Code review reads changed files, emits APPROVED/CHANGES_REQUESTED
   - Validate checks D!=C!=R, emits ALL_VALIDATED/VALIDATED/GAPS_FOUND
3. Pipeline ends on ALL_VALIDATED signal

**Without --validate (legacy):**
1. `run_build_validate_cycle()` with validate=False
2. Simple build loop via `loop.py`, one task per iteration
3. Promise tags control flow

### Tool Filtering

Two layers of tool filtering:

**Global (agent.py — legacy loop.py path):**
- **Allowed**: Bash, Read, Write, Edit, Glob, Grep, LS, TodoRead, TodoWrite, Skill, Task
- **Denied**: AskUserQuestion, WebFetch, WebSearch, EnterPlanMode, NotebookEdit

**Per-Stage (loader.py — pipeline path):**
- `StageConfig.denied_tools` is wired through `Stage.run_iteration()` → `AgentRunner.run_iteration()`, overriding the global deny list when set
- `PLAN_DENIED_TOOLS`: AskUserQuestion, WebFetch, WebSearch, EnterPlanMode, NotebookEdit (used by most pipeline stages)
- `PLAN_RESEARCH_DENIED_TOOLS`: AskUserQuestion, EnterPlanMode, NotebookEdit (research stages get web access)

Denied tools are blocked to prevent the loop from hanging (network calls, interactive prompts). Task and Skill are allowed so stages can dispatch subagents for parallel work.

### Promise-Based Flow Control

Claude signals completion via promise tags in output:
- `[[PROMISE:TASK_COMPLETE]]` - Task done, more tasks in current phase
- `[[PROMISE:PHASE_COMPLETE]]` - Phase done, more phases remain
- `[[PROMISE:BUILD_COMPLETE]]` - All tasks done

Detected by regex: `\[\[PROMISE:(.*?)\]\]`

### Session Management

Sessions stored in `.spectre/build-session.json`:
```json
{
  "tasks_file": "/absolute/path/to/tasks.md",
  "context_files": ["/path/to/context.md"],
  "max_iterations": 10,
  "started_at": "ISO-8601",
  "cwd": "/working/directory"
}
```

### Sparks Plugin Structure

```
sparks/
├── .claude-plugin/
│   ├── plugin.json         # Plugin manifest
│   └── marketplace.json    # Marketplace catalog
├── commands/               # User-invocable commands
│   ├── learn.md           # /learn entry point
│   └── find.md            # /find entry point
├── hooks/hooks.json       # SessionStart hooks
└── skills/
    ├── sparks-learn/      # Knowledge capture skill
    ├── sparks-apply/      # Auto-loaded at session start
    └── sparks-find/       # Registry generation
```

Knowledge stored in `{{project_root}}/.claude/skills/` with registry at `sparks-find/references/registry.toon` (format: `skill-name|category|triggers|description`).

## Key Files

| File | Purpose |
|------|---------|
| `build-loop/src/build_loop/cli.py` | CLI routing, run_default_pipeline, session I/O |
| `build-loop/src/build_loop/loop.py` | Core iteration loop (legacy build-only path) |
| `build-loop/src/build_loop/hooks.py` | Stage lifecycle hooks (git scope injection) |
| `build-loop/src/build_loop/git_scope.py` | Git diff utilities for inter-stage context |
| `build-loop/src/build_loop/prompt.py` | Template loading and variable substitution |
| `build-loop/src/build_loop/stats.py` | BuildStats dataclass, loop counters, dashboard |
| `build-loop/src/build_loop/stream.py` | Stream-JSON parsing, formatted output |
| `build-loop/src/build_loop/notify.py` | macOS/cross-platform notifications |
| `build-loop/src/build_loop/pipeline/executor.py` | PipelineExecutor with before/after hooks |
| `build-loop/src/build_loop/pipeline/loader.py` | YAML loading, create_default_pipeline(), create_ship_pipeline() |
| `build-loop/src/build_loop/prompts/build.md` | Phase-aware build iteration prompt |
| `build-loop/src/build_loop/prompts/code_review.md` | Code review with scope injection |
| `build-loop/src/build_loop/prompts/validate.md` | Validation with D!=C!=R principle |
| `build-loop/src/build_loop/prompts/shipping/clean_discover.md` | Ship: scope + dead code + duplication analysis |
| `build-loop/src/build_loop/prompts/shipping/clean_investigate.md` | Ship: parallel subagent investigation of suspects |
| `build-loop/src/build_loop/prompts/shipping/clean_execute.md` | Ship: apply approved changes + lint |
| `build-loop/src/build_loop/prompts/shipping/test_plan.md` | Ship: risk assessment + batching strategy |
| `build-loop/src/build_loop/prompts/shipping/test_execute.md` | Ship: parallel subagent test writing |
| `build-loop/src/build_loop/prompts/shipping/test_verify.md` | Ship: run suite, fix failures |
| `build-loop/src/build_loop/prompts/shipping/test_commit.md` | Ship: stage and commit test files |
| `build-loop/src/build_loop/prompts/shipping/rebase.md` | Ship: rebase, conflicts, land via PR/merge |

## Constraints

- **Prompt template variables**: `{tasks_file_path}`, `{progress_file_path}`, `{additional_context_paths_or_none}`, `{remediation_tasks_path}` - must match exactly
- **Code review variables**: `{changed_files}`, `{commit_messages}`, `{review_fixes_path}`, `{phase_completed}`, `{validated_phases}` - injected by hooks.py and build artifacts
- **Validate variables**: `{phase_completed}`, `{completed_phase_tasks}`, `{remaining_phases}`, `{validated_phases}`, `{arguments}` - from build artifacts and cli.py defaults
- **Promise tag format**: `[[PROMISE:TASK_COMPLETE]]`, `[[PROMISE:PHASE_COMPLETE]]`, or `[[PROMISE:BUILD_COMPLETE]]`
- **Phase metadata**: Build agent outputs JSON block with `phase_completed`, `completed_phase_tasks`, `remaining_phases` alongside PHASE_COMPLETE/BUILD_COMPLETE signals. Extracted by `PromiseCompletion(extract_artifacts=True)`
- **Validate signals**: `ALL_VALIDATED`, `VALIDATED`, `GAPS_FOUND` — in JSON status field
- **GAPS_FOUND flow**: Validate sets `remediation_tasks_path` in context → build prompt tells agent to work on remediation file instead of tasks file
- **Session JSON structure**: Must remain compatible with resume logic in cli.py
- **Sparks registry format**: `skill-name|category|triggers|description` (one per line)
