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
    ├── cli.py           # CLI arg parsing, interactive prompts
    ├── loop.py          # Core iteration loop
    ├── prompt.py        # Template loading
    ├── stats.py         # BuildStats dataclass
    ├── stream.py        # Stream-JSON parsing
    ├── notify.py        # macOS notifications
    └── prompts/build.md # Iteration template
```

### Build Loop Module Dependencies

```
cli.py → loop.py, notify.py
loop.py → prompt.py, stats.py, stream.py
prompt.py → prompts/build.md (template file)
stream.py → stats.py (updates BuildStats during event processing)
```

### Core Execution Flow (loop.py)

1. Display configuration (tasks file, context, max iterations)
2. For each iteration:
   - Build prompt from template + current task state
   - Run `claude` CLI subprocess with tool allowlist/denylist
   - Parse stream-JSON output in real time
   - Detect promise tags (`[[PROMISE:TASK_COMPLETE]]` or `[[PROMISE:BUILD_COMPLETE]]`)
   - Continue or exit based on promise
3. Print summary statistics

### Tool Filtering (loop.py lines 18-42)

**Allowed**: Bash, Read, Write, Edit, Glob, Grep, LS, TodoRead, TodoWrite

**Denied**: AskUserQuestion, WebFetch, WebSearch, Task, Skill, EnterPlanMode, NotebookEdit

Denied tools are blocked to prevent the loop from hanging (network calls, interactive prompts) or spawning unpredictable subagents.

### Promise-Based Flow Control

Claude signals completion via promise tags in output:
- `[[PROMISE:TASK_COMPLETE]]` - Task done, more tasks remain
- `[[PROMISE:BUILD_COMPLETE]]` - All tasks done, exit loop

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
| `build-loop/src/build_loop/cli.py` | CLI arg parsing, interactive prompts, session I/O |
| `build-loop/src/build_loop/loop.py` | Core iteration loop, subprocess management, promise detection |
| `build-loop/src/build_loop/prompt.py` | Template loading and variable substitution |
| `build-loop/src/build_loop/stats.py` | BuildStats dataclass, summary dashboard |
| `build-loop/src/build_loop/stream.py` | Stream-JSON parsing, formatted output |
| `build-loop/src/build_loop/notify.py` | macOS/cross-platform notifications |
| `build-loop/src/build_loop/prompts/build.md` | 6-step iteration prompt template |

## Constraints

- **Prompt template variables**: `{tasks_file_path}`, `{progress_file_path}`, `{additional_context_paths_or_none}` - must match exactly
- **Promise tag format**: Must be exactly `[[PROMISE:TASK_COMPLETE]]` or `[[PROMISE:BUILD_COMPLETE]]`
- **Session JSON structure**: Must remain compatible with resume logic in cli.py
- **Sparks registry format**: `skill-name|category|triggers|description` (one per line)
