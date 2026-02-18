# Task Context

## Summary
Add a `--dry-run` flag to `spectre-build` that prints the pipeline stages and their transitions without executing any agent invocations. The feature touches three areas: CLI argument parsing (adding the flag), pipeline config construction (already exists for all modes), and a new display function that walks the pipeline config and prints stage names, transitions, and end signals. The codebase has a clean separation between config construction and execution, making this straightforward.

## Architecture Patterns
- **CLI routing in `main()`**: Flags are parsed via `argparse` in `parse_args()`, then `main()` dispatches based on mode (`--plan`, `--pipeline`, `--validate`, manifest, etc.). Each mode constructs a `PipelineConfig` before passing it to a `PipelineExecutor` — dry-run intercepts after config construction, before execution.
- **Pipeline config as data**: `PipelineConfig` (dataclass) holds all stage definitions, transitions, start stage, and end signals. `StageConfig` holds per-stage details (name, prompt template path, completion strategy, max iterations, transitions). All the information needed for dry-run display is already in the config object.
- **Factory functions for pipeline configs**: `create_default_pipeline()`, `create_plan_pipeline()`, `create_plan_resume_pipeline()` in `loader.py` produce `PipelineConfig` instances programmatically. `load_pipeline()` parses YAML files into the same type. Dry-run can use any of these.
- **Legacy mode has no pipeline config**: `run_build_validate_cycle()` (no `--validate`, no `--pipeline`) runs a simple loop — no `PipelineConfig` exists. Dry-run must handle this case (either print a message or construct a minimal description).

## Key Files
| File | Relevance |
|------|-----------|
| `build-loop/src/build_loop/cli.py:128-249` | `parse_args()` — add `--dry-run` flag here |
| `build-loop/src/build_loop/cli.py:990-1143` | `main()` — routing logic where dry-run check goes (after config construction, before execution) |
| `build-loop/src/build_loop/cli.py:560-650` | `run_default_pipeline()` — creates config for `--validate` mode |
| `build-loop/src/build_loop/cli.py:653-796` | `run_plan_pipeline()` — creates config for `--plan` mode |
| `build-loop/src/build_loop/cli.py:494-557` | `run_pipeline()` — loads config for `--pipeline` mode |
| `build-loop/src/build_loop/cli.py:901-966` | `run_manifest()` — loads manifest, delegates to pipeline or legacy |
| `build-loop/src/build_loop/pipeline/executor.py:50-65` | `PipelineConfig` dataclass — the data structure to display |
| `build-loop/src/build_loop/pipeline/stage.py:22-40` | `StageConfig` dataclass — per-stage details |
| `build-loop/src/build_loop/pipeline/loader.py:231-315` | `create_default_pipeline()` — factory for build/review/validate |
| `build-loop/src/build_loop/pipeline/loader.py:413-520` | `create_plan_pipeline()` — factory for planning stages |
| `build-loop/src/build_loop/pipeline/loader.py:170-205` | `load_pipeline()` — YAML pipeline loading |

## Dependencies
- `argparse` — CLI parsing (stdlib, already imported in `cli.py`)
- `PipelineConfig` / `StageConfig` — dataclasses from `pipeline/executor.py` and `pipeline/stage.py`
- Pipeline factory functions from `pipeline/loader.py`
- `manifest.py:load_manifest()` — for manifest-driven dry-run

## Integration Points
- **`parse_args()` at `cli.py:128`**: Add `--dry-run` argument to the parser
- **`main()` at `cli.py:990`**: After determining mode (plan/pipeline/validate/legacy) and constructing the pipeline config, check `args.dry_run` and call a display function instead of executing
- **`run_manifest()` at `cli.py:901`**: Manifest mode also needs dry-run support — after loading manifest and determining validate mode, display config instead of running
- **New display function**: A function like `print_pipeline_dry_run(config: PipelineConfig)` that walks `config.stages`, prints name/transitions/completion for each, and shows the overall flow graph. Could live in `cli.py` or a new utility.

## Existing Conventions
- **Code style**: Standard Python, type hints, docstrings on all public functions. `from __future__ import annotations` not used.
- **Error handling**: `sys.exit(1)` for fatal errors, `print(..., file=sys.stderr)` for error messages
- **CLI output**: Uses emoji prefixes for visual hierarchy, `=`x60 separator lines, indented details
- **Testing**: pytest with `unittest.mock`. Test classes grouped by feature. Tests use `patch("sys.argv", [...])` for CLI testing.
- **Build/tooling**: `pyproject.toml` with setuptools, installed via `pipx install -e .` from `build-loop/`

## Constraints and Risks
- **Legacy mode (no pipeline config)**: When neither `--validate`, `--pipeline`, nor `--plan` is set, the CLI uses `run_build_validate_cycle()` which has no `PipelineConfig`. Dry-run must either: (a) print a simple "build loop (no pipeline)" message, or (b) construct a minimal config for display purposes.
- **Manifest mode routing**: `run_manifest()` calls `sys.exit()` directly, so dry-run must be intercepted before it enters that function, or the function must accept a dry-run parameter.
- **Resume mode**: `run_resume()` also calls `sys.exit()`. Dry-run for resume needs access to the saved session to determine what pipeline would run.
- **`--dry-run` + `--plan` interaction**: Plan pipeline constructs output directories (`docs/tasks/{branch}/`, `specs/`, `clarifications/`) before creating the config. Dry-run should skip directory creation or it creates side effects. The directory creation happens inside `run_plan_pipeline()` at line 706-708.
- **Scope is small**: Only 3 requirements — add flag, print stages/transitions, no agent invocations. No changes to the pipeline executor, stages, or completion strategies needed.
