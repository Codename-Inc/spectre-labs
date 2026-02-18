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

# Plan mode — scope docs to build-ready manifest
spectre-build --plan --context scope.md design_notes.md

# Plan then auto-start build
spectre-build --plan --context scope.md --build

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

- **Planning pipeline** — Autonomous scope-to-manifest planning with complexity assessment and human-in-the-loop clarifications
- **Code review gate** — Automated review between build and validation catches issues early
- **Phase-aware builds** — Multi-phase task plans get reviewed and validated per phase boundary
- **Validation cycles** — Post-build gap analysis (D!=C!=R) with automatic remediation
- **Multi-agent** — Pluggable backends (Claude Code, Codex)
- **Pipeline mode** — Stage-based execution from YAML definitions with configurable signals
- **Manifest mode** — Self-documenting builds via YAML frontmatter in `.md` files
- **Session resume** — Pick up where you left off after interruptions
- **TDD integration** — Loads `spectre-tdd` skill for test-driven execution
- **Web GUI** — FastAPI server with real-time WebSocket streaming

### Planning Pipeline

`--plan` transforms scope documents into a build-ready manifest. Instead of writing tasks by hand, provide scope/design docs and the pipeline produces a structured task breakdown you can feed directly into the build loop.

```
spectre-build --plan --context scope.md
```

The pipeline runs 6 stages autonomously:

```
Research → Assess → [Create Plan] → Create Tasks → Plan Review → Req Validate
                                                                       |
                                                          PLAN_VALIDATED → build.md
                                                    CLARIFICATIONS_NEEDED → pause
```

**Research** — Explores the codebase, identifies key files, architecture patterns, and dependencies. Writes `task_context.md`.

**Assess** — Scores complexity and routes to the right depth:
- `LIGHT` — Simple tasks skip plan generation, go straight to task breakdown
- `STANDARD` — Normal planning depth
- `COMPREHENSIVE` — Deep analysis with architecture diagrams and risk matrices

**Create Plan** — Writes an implementation plan with technical approach, critical files, and change boundaries. Skipped for LIGHT tasks.

**Create Tasks** — Breaks the plan into phased, ordered tasks with YAML frontmatter for the build manifest.

**Plan Review** — Catches over-engineering, unnecessary abstractions, and scope creep.

**Req Validate** — Cross-references the scope docs against the plan and tasks. Two outcomes:
- `PLAN_VALIDATED` — Everything covered. Writes `build.md` manifest. Pipeline ends.
- `CLARIFICATIONS_NEEDED` — Gaps found. Writes a clarifications file, saves session, and pauses for human input.

#### Human-in-the-Loop Clarifications

When the pipeline needs input, it pauses and notifies you:

```
📋 CLARIFICATIONS NEEDED
   Edit: docs/tasks/main/clarifications/scope_clarifications.md
   Then: spectre-build resume
```

Edit the file to answer the questions, then resume. The `update_docs` stage incorporates your answers and produces the final manifest.

#### Plan to Build

After planning completes, start the build:

```bash
# Manual — review artifacts first, then run the manifest
spectre-build docs/tasks/main/build.md

# Automatic — chain directly with --build flag
spectre-build --plan --context scope.md --build

# Interactive — plan mode prompts "Start build now?" on completion
spectre-build
# → Mode [build/plan]: plan
```

Output artifacts land in `docs/tasks/{branch}/`:

```
docs/tasks/main/
├── build.md                          # Build manifest (YAML frontmatter)
├── task_context.md                   # Research findings
├── specs/
│   ├── plan.md                       # Implementation plan
│   └── tasks.md                      # Task breakdown
└── clarifications/
    └── scope_clarifications.md       # (if needed)
```

### Build Pipeline

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
