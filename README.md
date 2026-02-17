# SPECTRE Labs

Experimental and power-user features for the [SPECTRE](https://github.com/Codename-Inc/spectre) workflow framework.

## Build Loop

Automated task execution CLI that runs Claude Code (or Codex) in a loop, completing one parent task per iteration with built-in code review and validation.

### Install

```bash
cd build-loop
pipx install -e .
pipx inject spectre-build pyyaml pydantic
```

### Usage

```bash
# Interactive mode (prompts for inputs)
spectre-build

# Flag-based
spectre-build --tasks tasks.md --context scope.md --max-iterations 10

# With code review + validation (recommended)
spectre-build --tasks tasks.md --context scope.md --validate

# Using a pipeline YAML definition
spectre-build --pipeline .spectre/pipelines/full-feature.yaml --tasks tasks.md

# From a manifest file (YAML frontmatter)
spectre-build docs/tasks/feature-x/build.md

# Resume interrupted session
spectre-build resume

# Start the web GUI
spectre-build serve
```

### Features

- **Code review gate** — Automated review between build and validation catches issues early
- **Phase-aware builds** — Multi-phase task plans get reviewed and validated per phase boundary
- **Validation cycles** — Post-build gap analysis (D!=C!=R) with automatic remediation
- **Multi-agent** — Pluggable backends (Claude Code, Codex)
- **Pipeline mode** — Stage-based execution from YAML definitions with configurable signals
- **Manifest mode** — Self-documenting builds via YAML frontmatter in `.md` files
- **Session resume** — Pick up where you left off after interruptions
- **TDD integration** — Loads `spectre-tdd` skill for test-driven execution
- **Web GUI** — FastAPI server with real-time WebSocket streaming

### How It Works

With `--validate`, spectre-build runs a 3-stage pipeline:

```
Build → Code Review → Validate
  ^         |              |
  |    CHANGES_REQUESTED   |
  +--------<---------------+-- VALIDATED / GAPS_FOUND
                           |
                     ALL_VALIDATED → done
```

**Build stage** — Each iteration completes one parent task:
1. Context Gathering — Read progress, context files, task state, and any review fixes
2. Task Planning — Identify current phase, select one incomplete task
3. Task Execution — Implement with TDD
4. Verification — Lint and test
5. Progress Update — Commit and write progress
6. Signal — `TASK_COMPLETE` (more tasks), `PHASE_COMPLETE` (phase boundary), or `BUILD_COMPLETE` (all done)

**Code review stage** — Reviews the git diff from the build:
- Scoped to only changed files and commits
- Severity scale: CRITICAL / HIGH / MEDIUM / LOW
- Approves if zero CRITICAL and zero HIGH issues
- Writes remediation tasks if changes requested

**Validate stage** — Checks Definition != Connection != Reachability:
- `ALL_VALIDATED` — all tasks complete and verified, pipeline ends
- `VALIDATED` — current work verified, more phases remain
- `GAPS_FOUND` — writes remediation tasks, loops back to build

## Why Separate?

These features are:
- **Experimental** — APIs may change
- **Power-user oriented** — Require more setup
- **Not core to SPECTRE** — You can use SPECTRE workflow without them

The main [SPECTRE](https://github.com/Codename-Inc/spectre) repo contains the stable workflow framework.

## License

MIT
