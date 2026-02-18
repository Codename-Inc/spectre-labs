# Build Progress

## Codebase Patterns
- Tool allow/deny lists are module-level constants in `agent.py` (global) and `loader.py` (per-pipeline)
- `CLAUDE_ALLOWED_TOOLS` feeds `--allowedTools` flag; `CLAUDE_DENIED_TOOLS` feeds `--disallowedTools` flag
- Pipeline-level deny lists (`PLAN_DENIED_TOOLS`, `PLAN_RESEARCH_DENIED_TOOLS`) are assigned to `StageConfig.denied_tools` in factory functions
- Existing test patterns: exact-set assertions for deny list contents, membership assertions for specific tools
- Full test suite: 280 tests, runs in ~0.4s via `pytest tests/ -v`
- `AgentRunner.run_iteration()` accepts `denied_tools: list[str] | None = None` — all subclasses must match
- `Stage.run_iteration()` passes `self.config.denied_tools` to runner — legacy callers omit param (defaults to None → global CLAUDE_DENIED_TOOLS)

---

## Iteration — [1.1] Remove Task from Global Deny Lists and Add to Allowed
**Status**: Complete
**What Was Done**: Removed `"Task"` from all three deny lists (`CLAUDE_DENIED_TOOLS`, `PLAN_DENIED_TOOLS`, `PLAN_RESEARCH_DENIED_TOOLS`) and added it to `CLAUDE_ALLOWED_TOOLS`. Created `test_tool_filtering.py` with 9 tests covering exact contents of all four lists. Updated existing `test_plan_pipeline.py` test that asserted Task was denied in research stage.
**Files Changed**:
- `build-loop/src/build_loop/agent.py` — removed Task from denied, added to allowed
- `build-loop/src/build_loop/pipeline/loader.py` — removed Task from PLAN_DENIED_TOOLS and PLAN_RESEARCH_DENIED_TOOLS
- `build-loop/tests/test_tool_filtering.py` — new, 9 tests for tool list contents
- `build-loop/tests/test_plan_pipeline.py` — updated research deny test, added Task-allowed test
- `docs/tasks/subagent-unblock/specs/tasks.md` — marked 1.1 sub-tasks complete
**Key Decisions**:
- Interactive tools (AskUserQuestion, EnterPlanMode, NotebookEdit) and web tools (WebFetch, WebSearch) remain blocked at global level — only Task was unblocked per user request
- Added exact-set assertions to catch any future drift in deny list contents
**Blockers/Risks**: None

## Iteration — [1.2] Wire Per-Stage Tool Filtering from StageConfig Through to Runner
**Status**: Complete
**What Was Done**: Extended `AgentRunner.run_iteration()` abstract signature with `denied_tools: list[str] | None = None`, updated `ClaudeRunner` to use per-stage list (falling back to `CLAUDE_DENIED_TOOLS` when None), updated `CodexRunner` to accept the param (ignored — Codex has no equivalent), and wired `Stage.run_iteration()` to pass `self.config.denied_tools` through to the runner. Created 7 new tests covering all paths.
**Files Changed**:
- `build-loop/src/build_loop/agent.py` — added `denied_tools` param to abstract method, `ClaudeRunner`, and `CodexRunner`
- `build-loop/src/build_loop/pipeline/stage.py` — pass `denied_tools=self.config.denied_tools` to runner
- `build-loop/tests/test_per_stage_tool_filtering.py` — new, 7 tests for per-stage denied_tools wiring
- `docs/tasks/subagent-unblock/specs/tasks.md` — marked 1.2 sub-tasks complete
**Key Decisions**:
- `ClaudeRunner` uses ternary: `denied_tools if denied_tools is not None else CLAUDE_DENIED_TOOLS` — empty list is valid (means deny nothing)
- Legacy callers (`loop.py`, `validate.py`) omit `denied_tools` → defaults to `None` → backward compatible
- `CodexRunner` accepts param silently — Codex CLI has no `--disallowedTools` equivalent
**Blockers/Risks**: None
