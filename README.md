# SPECTRE Labs

Experimental and power-user features for the [SPECTRE](https://github.com/Codename-Inc/spectre) workflow framework.

## Build Loop

Automated task execution CLI that runs Claude Code (or Codex) in a loop, completing one parent task per iteration with built-in validation.

### Install

```bash
cd build-loop
pipx install -e .
```

### Usage

```bash
# Interactive mode (prompts for inputs)
spectre-build

# Flag-based
spectre-build --tasks tasks.md --context scope.md --max-iterations 10

# With post-build validation
spectre-build --tasks tasks.md --validate

# From a manifest file (YAML frontmatter)
spectre-build docs/tasks/feature-x/build.md

# Resume interrupted session
spectre-build resume

# Start the web GUI
spectre-build serve
```

### Features

- **Multi-agent** — Pluggable backends (Claude Code, Codex)
- **Validation cycles** — Post-build gap analysis with automatic remediation
- **Manifest mode** — Self-documenting builds via YAML frontmatter in `.md` files
- **Pipeline mode** — Stage-based execution from YAML definitions
- **Session resume** — Pick up where you left off after interruptions
- **TDD integration** — Loads `spectre-tdd` skill for test-driven execution
- **Web GUI** — FastAPI server with real-time WebSocket streaming

### How It Works

Each iteration follows a 6-step cycle:

1. **Context Gathering** — Read progress, context files, and task state
2. **Task Planning** — Select one incomplete parent task
3. **Task Execution** — Implement with TDD
4. **Verification** — Lint and test
5. **Progress Update** — Commit and write progress
6. **Promise** — Signal `TASK_COMPLETE` or `BUILD_COMPLETE`

The loop exits when all tasks are marked complete or max iterations is reached.

## Why Separate?

These features are:
- **Experimental** — APIs may change
- **Power-user oriented** — Require more setup
- **Not core to SPECTRE** — You can use SPECTRE workflow without them

The main [SPECTRE](https://github.com/Codename-Inc/spectre) repo contains the stable workflow framework.

## License

MIT
