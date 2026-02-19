# Build Progress

## Codebase Patterns
- Tool allow/deny lists are module-level constants in `agent.py` (global) and `loader.py` (per-pipeline)
- `CLAUDE_ALLOWED_TOOLS` feeds `--allowedTools` flag; `CLAUDE_DENIED_TOOLS` feeds `--disallowedTools` flag
- Pipeline-level deny lists (`PLAN_DENIED_TOOLS`, `PLAN_RESEARCH_DENIED_TOOLS`) are assigned to `StageConfig.denied_tools` in factory functions
- Existing test patterns: exact-set assertions for deny list contents, membership assertions for specific tools
- Full test suite: 309 tests, runs in ~0.8s via `pytest tests/ -v`
- `AgentRunner.run_iteration()` accepts `denied_tools: list[str] | None = None` — all subclasses must match
- `Stage.run_iteration()` passes `self.config.denied_tools` to runner — legacy callers omit param (defaults to None → global CLAUDE_DENIED_TOOLS)

- Ship pipeline tests: 36 tests in `test_ship_pipeline.py` covering config, transitions, completions, iterations, prompt paths, denied tools
- Test classes: `TestCreateShipPipeline`, `TestShipStageTransitions`, `TestShipCompletionStatuses`, `TestShipStageIterations`, `TestShipPromptPaths`

---

## Iteration — [7.1] Update Pipeline Factory Tests
**Status**: Complete
**What Was Done**: Verified existing 8-stage test file (35 tests) was already correctly written for new architecture. Added explicit `test_task_tool_not_in_any_denied_tools` assertion (36th test). All 36 tests pass against `create_ship_pipeline()` implementation. Marked all sub-tasks complete.
**Files Changed**: `build-loop/tests/test_ship_pipeline.py`, `docs/tasks/subagent-unblock/specs/tasks.md`
**Key Decisions**: Added explicit "Task not in denied_tools" regression test rather than relying on implicit `PLAN_DENIED_TOOLS` equality check
**Blockers/Risks**: None

## Iteration — [7.2] Update Hook Tests
**Status**: Complete
**What Was Done**: Verified existing 24-test hook test file (`test_ship_hooks.py`) was already correctly written for the 8-stage architecture during the 4.2 hooks implementation. All 24 tests pass — covering `ship_before_stage` (HEAD snapshots at clean_discover/test_plan, no-ops for all 6 other sub-stages) and `ship_after_stage` (clean_summary capture at clean_execute, test_summary capture at test_commit, no-ops for all 6 other sub-stages). Happy + failure paths covered for all active hooks.
**Files Changed**: `docs/tasks/subagent-unblock/specs/tasks.md`
**Key Decisions**: Tests were already comprehensive from the 4.2 implementation — no changes needed, just verification
**Blockers/Risks**: None

## Iteration — [7.3] Update Integration and Prompt Tests
**Status**: Complete
**What Was Done**: Verified `test_run_ship_pipeline.py` integration tests (5 tests) already work with the 8-stage factory via mocked `create_ship_pipeline`. Verified all 7 new sub-stage prompt test files (128 tests) exist and pass — covering template variables, completion signals, subagent dispatch instructions (clean_investigate, test_execute), and negative assertions. Updated `test_ship_stats.py` to use new 8-stage names (`clean_discover`, `clean_investigate`, etc.) and new signals (`CLEAN_DISCOVER_COMPLETE`, etc.) instead of old 3-stage names (`clean`, `test`) and old signals (`CLEAN_COMPLETE`, `TEST_COMPLETE`). Full suite: 472 tests pass, 0 failures.
**Files Changed**: `build-loop/tests/test_ship_stats.py`, `docs/tasks/subagent-unblock/specs/tasks.md`
**Key Decisions**: Most test files were already correctly written during previous phase implementations; only `test_ship_stats.py` needed stage name updates
**Blockers/Risks**: None

## Iteration — [8.1] Update Project Documentation
**Status**: Complete
**What Was Done**: Updated `CLAUDE.md` with 8-stage ship pipeline architecture: rewrote Tool Filtering section to show two-layer filtering (global + per-stage), added shipping/ prompt directory tree with all 8 sub-stage files, added 8 new prompt files to Key Files table, updated `loader.py` description. Rewrote `feature-ship-pipeline/SKILL.md` from v1 (3-stage) to v2 (8-stage): updated all sections including stage configs with full signal/transition chain, inter-stage context flow with sub-stage hooks, new subagent dispatch section, expanded Key Files table with all 7 new prompts + 2 deprecated files, updated Common Tasks and Gotchas. Updated registry triggers to include sub-stage names.
**Files Changed**: `CLAUDE.md`, `.claude/skills/feature-ship-pipeline/SKILL.md`, `.claude/skills/spectre-recall/references/registry.toon`, `docs/tasks/subagent-unblock/specs/tasks.md`
**Key Decisions**: Added sub-stage names as registry triggers for precise matching; kept deprecated clean.md/test.md in Key Files table with DEPRECATED label
**Blockers/Risks**: None
