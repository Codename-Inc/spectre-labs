# Task Context

## Summary
The ship loop (`--ship`) is the third autonomous loop in the plan/build/ship trifecta. It adds a 3-stage pipeline (clean -> test -> rebase) to `spectre-build` that takes a feature branch from "works on branch" to "landed on main" autonomously. The implementation follows the exact same pipeline executor pattern already established by the build (`--validate`) and plan (`--plan`) pipelines, requiring no changes to the core pipeline engine — only new stage configs, prompt templates, hooks, and CLI routing.

## Architecture Patterns
- **Pipeline-as-stages**: Every autonomous loop (build/review/validate, plan, and now ship) is a set of `StageConfig` objects wired into a `PipelineConfig`, executed by the shared `PipelineExecutor`. Each stage has a prompt template, completion strategy, max iterations, and transition map.
- **Factory pattern for pipeline creation**: `loader.py` has factory functions (`create_default_pipeline()`, `create_plan_pipeline()`, `create_plan_resume_pipeline()`) that return `PipelineConfig` instances. Ship adds `create_ship_pipeline()`.
- **Hook pattern for inter-stage context**: `hooks.py` provides `before_stage` / `after_stage` callbacks per pipeline type. Build hooks snapshot HEAD and collect diffs. Plan hooks inject depth defaults and clarification answers. Ship hooks will inject `parent_branch`, `working_set_scope`, `clean_summary`, and `test_summary`.
- **JSON completion for single-pass stages**: Planning stages use `JsonCompletion(signal_field="status")` with `max_iterations=1`. Ship's rebase stage is similar (single context window, max 3 iterations).
- **JSON completion for iterative stages**: Ship's clean and test stages use `JsonCompletion` with iterate/complete signal pairs (`CLEAN_TASK_COMPLETE`/`CLEAN_COMPLETE`, `TEST_TASK_COMPLETE`/`TEST_COMPLETE`) and higher `max_iterations` (10 each), matching the scope's task decomposition model.
- **Session persistence**: All pipeline types save/restore state via `save_session()` / `load_session()` with JSON-serializable context dicts. Ship adds `ship: true` flag and `ship_context` to the session.
- **Notification pattern**: Each pipeline type has its own `notify_*_complete()` function in `notify.py` with the same signature pattern (iterations/time/success/project).
- **Manifest routing**: `manifest.py` loads YAML frontmatter from `.md` files. Currently supports `tasks`, `context`, `max_iterations`, `agent`, `validate` fields. Ship adds `ship: true`.
- **Stats tracking**: `BuildStats` has per-loop-type counters (`build_loops`, `review_loops`, `validate_loops`, `plan_loops`). Ship adds `ship_loops`. Dashboard displays non-zero loop counts.
- **Tool filtering per stage**: `agent.py` defines global `CLAUDE_ALLOWED_TOOLS`/`CLAUDE_DENIED_TOOLS`. `loader.py` adds pipeline-specific denied tool lists (`PLAN_DENIED_TOOLS`, `PLAN_RESEARCH_DENIED_TOOLS`). Ship uses the same standard denied tools for all 3 stages.

## Key Files

| File | Relevance |
|------|-----------|
| `build-loop/src/build_loop/cli.py` | **Primary integration point**. Add `--ship` flag to `parse_args()` (line 128). Add `run_ship_pipeline()` function (modeled on `run_plan_pipeline()` at line 686). Wire routing in `main()` (line 1043) — `--ship` must be checked after `--plan` but before `--validate`. Wire resume in `run_resume()` (line 844). Wire manifest in `run_manifest()` (line 954). Add `ship` fields to `save_session()` (line 30). Update `format_session_summary()` (line 87). |
| `build-loop/src/build_loop/pipeline/loader.py` | **Pipeline factory**. Add `create_ship_pipeline()` function (modeled on `create_plan_pipeline()` at line 413). Define 3 `StageConfig` objects for clean/test/rebase with `JsonCompletion` strategies and transitions. May add `SHIP_DENIED_TOOLS` list or reuse `PLAN_DENIED_TOOLS`. |
| `build-loop/src/build_loop/hooks.py` | **Inter-stage context injection**. Add `ship_before_stage()` and `ship_after_stage()` functions following the same signature as `plan_before_stage()`/`plan_after_stage()` (lines 118, 147). Before-clean: detect parent branch, compute working set scope. After-clean: capture `clean_summary`. After-test: capture `test_summary`. |
| `build-loop/src/build_loop/notify.py` | Add `notify_ship_complete()` function (modeled on `notify_plan_complete()` at line 152). Same pattern: branch detection, subtitle formatting, success/failure messaging. |
| `build-loop/src/build_loop/stats.py` | Add `ship_loops: int = 0` field to `BuildStats` (line 48). Add `create_ship_event_handler()` factory function (modeled on `create_plan_event_handler()` at line 220). Update dashboard in `print_summary()` to display ship loop count when > 0. |
| `build-loop/src/build_loop/manifest.py` | Add `ship: bool = False` field to `BuildManifest` dataclass (line 13). Update `load_manifest()` (line 117) to parse `ship` from frontmatter. |
| `build-loop/src/build_loop/prompts/shipping/clean.md` | **New file**. Clean stage prompt template. Task checklist (7 items from scope). Uses `{parent_branch}` and `{working_set_scope}` context variables. Emits JSON with `status: "CLEAN_TASK_COMPLETE"` or `"CLEAN_COMPLETE"`. |
| `build-loop/src/build_loop/prompts/shipping/test.md` | **New file**. Test stage prompt template. Task checklist (4 items from scope). Uses `{working_set_scope}` context variable. Emits JSON with `status: "TEST_TASK_COMPLETE"` or `"TEST_COMPLETE"`. |
| `build-loop/src/build_loop/prompts/shipping/rebase.md` | **New file**. Rebase stage prompt template. Single context window (not decomposed). Uses `{parent_branch}`, `{clean_summary}`, `{test_summary}` context variables. Handles PR creation (remote) or local merge (stash approval). Emits JSON with `status: "SHIP_COMPLETE"`. |
| `build-loop/src/build_loop/git_scope.py` | **Reused as-is**. `snapshot_head()` and `collect_diff()` used by ship hooks for working set scope detection. |
| `build-loop/src/build_loop/pipeline/executor.py` | **No changes needed**. Ship uses `PipelineExecutor` as-is with hooks. Understanding its `before_stage`/`after_stage` hook calling convention (lines 212-237) and artifact flow (`context.update(result.artifacts)` at line 275) is critical for hook design. |
| `build-loop/src/build_loop/pipeline/completion.py` | **No changes needed**. Ship reuses `JsonCompletion(signal_field="status")` for all 3 stages. |
| `build-loop/src/build_loop/pipeline/stage.py` | **No changes needed**. Stage's `build_prompt()` does `{variable}` substitution from context dict (line 122). Stage's `run()` iterates up to `max_iterations` (line 181). |
| `build-loop/src/build_loop/agent.py` | **No changes needed**. Default `CLAUDE_DENIED_TOOLS` blocks interactive/network tools. `gh` is invoked via Bash tool which is already allowed. |

## Dependencies
- **`PipelineExecutor`** (`pipeline/executor.py`): Core orchestration engine. Already supports hooks, events, artifact flow.
- **`StageConfig` / `Stage`** (`pipeline/stage.py`): Stage definition and execution. Handles template loading, prompt building, iteration loop.
- **`JsonCompletion`** (`pipeline/completion.py`): Completion strategy for all ship stages. Parses ```json blocks for status signal.
- **`BuildStats`** (`stats.py`): Token/cost tracking. Needs new `ship_loops` counter.
- **`save_session()` / `load_session()`** (`cli.py`): Session persistence for resume support.
- **`notify()`** (`notify.py`): Base notification function. Ship adds `notify_ship_complete()`.
- **`git_scope.py`**: Git diff utilities for working set detection and inter-stage context.
- **`BuildManifest`** (`manifest.py`): Manifest parsing for `ship: true` frontmatter.

## Integration Points
- **CLI arg parsing** (`cli.py:parse_args()` line 128): Add `--ship` as `store_true` argument, similar to `--plan` (line 218) and `--validate` (line 211).
- **Main routing** (`cli.py:main()` line 1043): `--ship` block inserted after `--plan` check (line 1076) but before `--validate` check. Pattern: check flag -> validate required args (context files optional for ship) -> resolve paths -> save_session -> call `run_ship_pipeline()` -> notify -> exit.
- **Resume routing** (`cli.py:run_resume()` line 844): Add `elif session.get("ship"):` block after `if session.get("plan"):` (line 881). Call `run_ship_pipeline()` with resume context.
- **Manifest routing** (`cli.py:run_manifest()` line 954): After loading manifest, check `manifest.ship` and route to `run_ship_pipeline()` instead of build pipeline.
- **Session schema** (`cli.py:save_session()` line 30): Add `ship: bool = False`, `ship_context: dict | None = None` parameters. All new params have defaults for backward compatibility.
- **Pipeline factory** (`loader.py`): `create_ship_pipeline()` returns `PipelineConfig` with name `"ship"`, 3 stages, `start_stage="clean"`, `end_signals=["SHIP_COMPLETE"]`.
- **Hooks** (`hooks.py`): `ship_before_stage()` and `ship_after_stage()` follow same signature as `plan_before_stage()`/`plan_after_stage()`.
- **Stats** (`stats.py`): `create_ship_event_handler()` follows `create_plan_event_handler()` pattern (line 220).
- **Prompt templates**: 3 new `.md` files in `prompts/shipping/` directory. Each uses `{variable}` placeholders substituted by `Stage.build_prompt()`.

## Existing Conventions
- **Testing**: No test suite found in the build-loop package. Testing is manual via CLI invocations.
- **Code style**: Python 3.10+ with type hints. Dataclasses for config/state objects. Pydantic for YAML validation (loader.py only). Logging via `logging.getLogger(__name__)`. F-string formatting. Imports grouped (stdlib, third-party, local).
- **Error handling**: Hooks catch exceptions and log warnings (never crash pipeline). File operations check existence before reading. CLI validates inputs before proceeding.
- **Build/tooling**: Install via `pipx install -e .` from `build-loop/`. Dependencies injected via `pipx inject spectre-build <pkg>`. Run directly with `python -m build_loop.cli --help`.
- **Prompt conventions**: Templates use `{variable}` placeholders. Instructions are structured as numbered steps with clear sections. JSON completion blocks at end of response. Iterative stages have clear STOP instructions. Prompts define task checklists for the agent to work through.
- **Pipeline naming**: Build pipeline is `"build-review-validate"`, plan pipeline is `"plan"`. Ship pipeline should be `"ship"`.

## Constraints and Risks
- **Session schema backward compatibility**: Adding new fields to `save_session()` must not break existing sessions. All new parameters should have defaults (e.g., `ship: bool = False`). `load_session()` uses `.get()` with defaults, so this is safe.
- **Token budget per stage**: Clean (max 10 iterations) and test (max 10 iterations) stages decompose work into task checklists. Rebase (max 3 iterations) runs as a single context window. If a stage exceeds its iteration budget, the pipeline reports it and moves on.
- **Prompt template variable mismatches**: Template variables must match exactly between the prompt `.md` files and the `context` dict built in `run_ship_pipeline()`. Typos silently break prompts — the `{variable}` placeholder stays in the prompt text as literal text.
- **Parent branch detection**: Must happen before the pipeline starts (in `run_ship_pipeline()` config step or in `ship_before_stage("clean")`). Needs to handle detached HEAD, branches without tracking, and repos with no remote. Can use `git merge-base --fork-point` or `git log --oneline main..HEAD` patterns.
- **gh CLI availability**: Rebase stage's PR creation depends on `gh` being installed and authenticated. The prompt should instruct the agent to check `gh auth status` before attempting PR creation and handle gracefully if not available.
- **Stash approval flow**: When doing local merge on a dirty target branch, the scope says "user approves, agent executes." But `AskUserQuestion` is in the denied tools list. The agent will need to print a clear message via Bash `echo` and pause (e.g., `read -p "Approve stash+merge? [y/N]"` via Bash). This works because Bash is an allowed tool and `read` is a shell builtin, not a Claude tool.
- **No existing tests**: There's no test suite to validate changes against. Testing will be manual via `spectre-build --ship` invocations.
- **`run_manifest()` currently calls `sys.exit()`**: Line 1019. When extending for ship mode, the `sys.exit()` call must be preserved — ship routing happens inside `run_manifest()` before it would normally exit.
- **Scope explicitly says "no changes to PipelineExecutor"**: All ship-specific behavior must live in hooks, prompts, and the `run_ship_pipeline()` orchestration function. This is achievable and consistent with plan pipeline precedent.
- **Interactive mode for `--ship`**: The scope mentions an interactive mode where the CLI prompts for context files and settings. This mirrors the interactive mode for `--plan` (line 1117 in `cli.py`). Need to add interactive prompts for ship-specific settings (confirm parent branch, etc.).
- **`--ship` does not require `--tasks`**: Like `--plan`, the ship loop generates its own work from the codebase state. It may optionally accept `--context` for scope documents to help the clean/test stages focus.
