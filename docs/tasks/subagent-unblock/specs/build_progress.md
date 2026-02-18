# Build Progress

## Codebase Patterns
- Tool allow/deny lists are module-level constants in `agent.py` (global) and `loader.py` (per-pipeline)
- `CLAUDE_ALLOWED_TOOLS` feeds `--allowedTools` flag; `CLAUDE_DENIED_TOOLS` feeds `--disallowedTools` flag
- Pipeline-level deny lists (`PLAN_DENIED_TOOLS`, `PLAN_RESEARCH_DENIED_TOOLS`) are assigned to `StageConfig.denied_tools` in factory functions
- Existing test patterns: exact-set assertions for deny list contents, membership assertions for specific tools
- Full test suite: 309 tests, runs in ~0.8s via `pytest tests/ -v`
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

## Iteration — [2.1] Create `clean_discover.md` Prompt Template
**Status**: Complete
**What Was Done**: Created `clean_discover.md` prompt template extracting Tasks 1-3 (working set scope, dead code analysis, duplication analysis) from monolithic `clean.md` into a focused discovery sub-stage with `CLEAN_DISCOVER_TASK_COMPLETE`/`CLEAN_DISCOVER_COMPLETE` signals and analysis-only guardrails. Created 12 TDD tests covering content, signals, variables, and negative assertions.
**Files Changed**:
- `build-loop/src/build_loop/prompts/shipping/clean_discover.md` — new, 3-task discovery prompt
- `build-loop/tests/test_clean_discover_prompt.py` — new, 12 tests for prompt content
- `docs/tasks/subagent-unblock/specs/tasks.md` — marked 2.1 sub-tasks complete
**Key Decisions**:
- Prompt structure mirrors `clean.md` style (numbered tasks, JSON completion blocks, Rules section) for consistency
- Analysis-only guardrails are explicit: "Do NOT modify any files" appears in both task instructions and Rules section
- Final task (Task 3) emits `CLEAN_DISCOVER_COMPLETE` (not `TASK_COMPLETE`) to trigger transition to `clean_investigate` stage
- Empty working set short-circuits at Task 1 with immediate `CLEAN_DISCOVER_COMPLETE`
**Blockers/Risks**: None

## Iteration — [2.2] Create `clean_investigate.md` Prompt Template with Subagent Dispatch
**Status**: Complete
**What Was Done**: Created `clean_investigate.md` prompt template extracting Tasks 4-5 (investigation dispatch, high-risk validation) from monolithic `clean.md`, enhanced with parallel subagent dispatch instructions modeled after original `/spectre:clean` Step 4. Task 1 chunks SUSPECT findings into 2-5 groups and dispatches up to 4 parallel investigation subagents via Task tool with CONFIRMED_SAFE/NEEDS_VALIDATION/KEEP classification. Task 2 dispatches optional second-wave validation subagents for high-risk items and consolidates into a final action plan. Created 17 TDD tests covering content, signals, variables, subagent dispatch instructions, and negative assertions.
**Files Changed**:
- `build-loop/src/build_loop/prompts/shipping/clean_investigate.md` — new, 2-task investigation prompt with subagent dispatch
- `build-loop/tests/test_clean_investigate_prompt.py` — new, 17 tests for prompt content
- `docs/tasks/subagent-unblock/specs/tasks.md` — marked 2.2 sub-tasks complete
**Key Decisions**:
- Investigation subagent prompt template embedded directly in the prompt (not a separate file) — keeps the stage self-contained
- Conditional subagent dispatch: fewer than 3 SUSPECT items → sequential investigation without subagents
- Conservative classification default: NEEDS_VALIDATION rather than CONFIRMED_SAFE when in doubt
- Max 4 parallel subagents per dispatch to keep context manageable
- Second-wave validation is optional (only for 3+ high-risk items)
**Blockers/Risks**: None
