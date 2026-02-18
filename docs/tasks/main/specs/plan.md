# Implementation Plan: `--dry-run` Flag

*Light depth | Generated 2026-02-17*

## Overview

Add a `--dry-run` flag to `spectre-build` that prints what pipeline stages and transitions would execute, then exits without invoking any agent. This is a CLI-only change — no prompt templates, completion strategies, hooks, or executor changes needed.

## Desired End State

```bash
# Show what --validate would do without running anything
spectre-build --dry-run --validate --tasks tasks.md

# Show what --plan would do
spectre-build --dry-run --plan --context scope.md

# Show what a manifest would do
spectre-build --dry-run build.md

# Show what resume would do
spectre-build --dry-run resume
```

Each prints a human-readable summary of pipeline stages, transitions, and end signals, then exits with code 0. No agents are invoked.

## Out of Scope

- Changes to pipeline executor, stage behavior, or prompt templates
- Changes to completion strategies, hooks, or agent runners
- Verbose/debug output modes for dry-run
- Machine-readable (JSON) dry-run output

## Technical Approach

### 1. Flag + Formatting Utility

Add `--dry-run` to `parse_args()` in `cli.py` as `action="store_true"` (same pattern as `--plan`). Create a `format_pipeline_plan(config: PipelineConfig) -> str` function that walks from `start_stage` through transitions, printing stage names, transition signals, and end signals.

### 2. Interception Points

Check `args.dry_run` in each execution path after the pipeline config is built but before execution begins:

| Path | Function | Config Source |
|------|----------|---------------|
| `--plan` | `main()` | `create_plan_pipeline()` |
| `--pipeline` | `main()` | `load_pipeline()` |
| `--validate` | `main()` | `create_default_pipeline()` |
| Legacy (no flags) | `main()` | No config — print simple build loop description |
| Resume | `run_resume()` | Rebuilt from session state |
| Manifest | `run_manifest()` | Rebuilt from manifest settings |

Each interception: build config → `format_pipeline_plan()` → `print()` → `sys.exit(0)`.

### Critical Files

| File | Reason |
|------|--------|
| `build-loop/src/build_loop/cli.py` | Add flag, formatting function, and all interception points |
| `build-loop/src/build_loop/pipeline/executor.py` | `PipelineConfig` dataclass (read-only reference) |
| `build-loop/src/build_loop/pipeline/stage.py` | `StageConfig` dataclass (read-only reference) |
| `build-loop/tests/` | New test file for dry-run |
