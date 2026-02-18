# Tasks — Unblock Task Tool & Expand Ship Sub-Stages

*Generated 2026-02-18*

## Objective
Unblock the Task tool across all pipelines, wire per-stage tool filtering, expand ship pipeline from 3 stages to 8 sub-stages with subagent dispatch patterns aligned to the original spectre commands.

## Scope
- **In Scope**: Remove Task from deny lists, wire `StageConfig.denied_tools` through `Stage` to `AgentRunner`, split clean into 3 sub-stages (discover/investigate/execute), split test into 4 sub-stages (plan/execute/verify/commit), add subagent dispatch instructions to clean_investigate and test_execute prompts, add subagent dispatch to plan pipeline research.md, update hooks/stats for new sub-stage names, update all ship tests
- **Out of Scope**: Rebase stage changes, new completion strategies, PipelineExecutor changes, custom YAML pipeline support for sub-stages, build pipeline changes, new CLI flags

---

## Architecture Context

### Where This Fits
- Tool filtering lives in two layers: `agent.py` (global runner) and `loader.py` (per-stage config). `StageConfig.denied_tools` exists but is dead — `stage.py` never passes it to the runner.
- Ship pipeline stages are defined in `create_ship_pipeline()` in `loader.py` with prompt templates in `prompts/shipping/`.
- Original spectre commands at `/Users/joe/Dev/spectre/plugins/spectre/commands/` use parallel subagent dispatch via the Task tool — research.md, clean.md, and test.md all spawn specialized subagents.

### Technical Approach
- Remove Task from all deny lists (broad unblock per user request)
- Wire the existing `StageConfig.denied_tools` field through `Stage.run_iteration()` to `AgentRunner.run_iteration()` so per-stage filtering actually works
- Split monolithic clean/test prompts into focused sub-stage prompts, each with its own completion signals and transition rules
- Port subagent dispatch patterns from original spectre commands into the sub-stage prompts that need parallelism

### Key Decisions
- Task is unblocked globally — no per-stage gating (user explicitly requested broad unblock)
- Keep AskUserQuestion/EnterPlanMode/NotebookEdit denied (would hang the loop or cause unpredictable behavior)
- WebFetch/WebSearch remain in global deny (legacy loop.py safety), but per-stage override means research stage gets web access
- Rebase stays as a single stage (single context window by design, max 3 iterations)
- Old `clean.md`/`test.md` kept with deprecation headers for backward compat with custom YAML pipelines

---

## Tasks

### Phase 1: Unblock Task Tool (Foundation)

#### [1.1] Remove Task from Global Deny Lists and Add to Allowed
- [x] **1.1.1** Remove `"Task"` from `CLAUDE_DENIED_TOOLS` in `build-loop/src/build_loop/agent.py` (line 73-80)
  - **Produces**: Task tool no longer globally blocked for `claude -p` invocations
  - **Consumed by**: All pipeline stages, all prompts with subagent dispatch instructions
  - **Replaces**: Previous `CLAUDE_DENIED_TOOLS` list that included Task
  - [x] `CLAUDE_DENIED_TOOLS` contains exactly: `["AskUserQuestion", "WebFetch", "WebSearch", "EnterPlanMode", "NotebookEdit"]`
  - [x] `"Task"` does not appear in the list
- [x] **1.1.2** Add `"Task"` to `CLAUDE_ALLOWED_TOOLS` in `build-loop/src/build_loop/agent.py` (line 59-70)
  - **Produces**: Task tool explicitly allowed in `--allowedTools` flag
  - **Consumed by**: `ClaudeRunner.run_iteration()` command construction
  - **Replaces**: Previous `CLAUDE_ALLOWED_TOOLS` list without Task
  - [x] `"Task"` appears in `CLAUDE_ALLOWED_TOOLS`
- [x] **1.1.3** Remove `"Task"` from `PLAN_DENIED_TOOLS` in `build-loop/src/build_loop/pipeline/loader.py` (line 395-402)
  - **Produces**: Task no longer blocked at the pipeline stage config level
  - **Consumed by**: All stages that reference `PLAN_DENIED_TOOLS`
  - **Replaces**: Previous list that included Task
  - [x] `PLAN_DENIED_TOOLS` contains exactly: `["AskUserQuestion", "WebFetch", "WebSearch", "EnterPlanMode", "NotebookEdit"]`
- [x] **1.1.4** Remove `"Task"` from `PLAN_RESEARCH_DENIED_TOOLS` in `build-loop/src/build_loop/pipeline/loader.py` (line 405-410)
  - **Produces**: Task no longer blocked for research stages
  - **Consumed by**: Research stage config
  - **Replaces**: Previous list that included Task
  - [x] `PLAN_RESEARCH_DENIED_TOOLS` contains exactly: `["AskUserQuestion", "EnterPlanMode", "NotebookEdit"]`

#### [1.2] Wire Per-Stage Tool Filtering from StageConfig Through to Runner
- [x] **1.2.1** Extend `AgentRunner.run_iteration()` abstract signature in `build-loop/src/build_loop/agent.py` to accept `denied_tools: list[str] | None = None`
  - **Produces**: Abstract base class supports per-call tool overrides
  - **Consumed by**: `ClaudeRunner`, `CodexRunner`, `Stage.run_iteration()`
  - **Replaces**: Previous signature `(self, prompt, timeout=None, stats=None)`
  - [x] `AgentRunner.run_iteration()` has `denied_tools` parameter with default `None`
- [x] **1.2.2** Update `ClaudeRunner.run_iteration()` to use `denied_tools` parameter when provided, falling back to `CLAUDE_DENIED_TOOLS` when `None`
  - **Produces**: `claude -p --disallowedTools` uses per-stage list when available
  - **Consumed by**: All pipeline stages via `Stage.run_iteration()`
  - **Replaces**: Hardcoded `CLAUDE_DENIED_TOOLS` in command construction
  - [x] When `denied_tools` is `None`, uses `CLAUDE_DENIED_TOOLS` (backward compat)
  - [x] When `denied_tools` is a list, uses that list instead
- [x] **1.2.3** Update `CodexRunner.run_iteration()` to accept `denied_tools` parameter (ignore it — Codex has no equivalent)
  - **Produces**: Interface compatibility with updated abstract base
  - **Consumed by**: N/A (parameter accepted but unused)
  - **Replaces**: Previous signature without `denied_tools`
  - [x] `CodexRunner.run_iteration()` accepts `denied_tools` parameter without error
- [x] **1.2.4** Update `Stage.run_iteration()` in `build-loop/src/build_loop/pipeline/stage.py` (line 148) to pass `self.config.denied_tools` to `self.runner.run_iteration()`
  - **Produces**: Per-stage tool filtering is active — `StageConfig.denied_tools` actually takes effect
  - **Consumed by**: All pipeline stages
  - **Replaces**: Previous call that ignored `self.config.denied_tools`
  - [x] `self.runner.run_iteration()` receives `denied_tools=self.config.denied_tools`

---

### Phase 2: Expand Clean Stage → 3 Sub-Stages

#### [2.1] Create `clean_discover.md` Prompt Template
- [x] **2.1.1** Create `build-loop/src/build_loop/prompts/shipping/clean_discover.md` containing Tasks 1-3 from current `clean.md`
  - **Produces**: Prompt template for clean discovery sub-stage (scope + dead code + duplication analysis)
  - **Consumed by**: `create_ship_pipeline()` stage config, `Stage.build_prompt()` for template loading
  - **Replaces**: Tasks 1-3 section of monolithic `clean.md`
  - [x] Contains Task 1 (Determine Working Set Scope), Task 2 (Analyze Dead Code), Task 3 (Analyze Duplication)
  - [x] Uses `{parent_branch}`, `{working_set_scope}`, `{context_files}` template variables
  - [x] Completion signals: `CLEAN_DISCOVER_TASK_COMPLETE` (loop) and `CLEAN_DISCOVER_COMPLETE` (transition to clean_investigate)
  - [x] One-task-per-iteration instruction preserved
  - [x] Rules section scoped to analysis-only (no modifications)

#### [2.2] Create `clean_investigate.md` Prompt Template with Subagent Dispatch
- [x] **2.2.1** Create `build-loop/src/build_loop/prompts/shipping/clean_investigate.md` containing Tasks 4-5 from current `clean.md`, enhanced with parallel subagent dispatch instructions modeled after original `/spectre:clean` Step 4 (`/Users/joe/Dev/spectre/plugins/spectre/commands/clean.md` lines 159-228)
  - **Produces**: Prompt template for investigation sub-stage with parallel Task tool subagent dispatch
  - **Consumed by**: `create_ship_pipeline()` stage config, `Stage.build_prompt()`
  - **Replaces**: Tasks 4-5 section of monolithic `clean.md`
  - [x] Task 4 includes explicit subagent dispatch instructions: chunk SUSPECT findings into 2-5 groups, dispatch up to 4 parallel investigation subagents via Task tool in a single message
  - [x] Each subagent receives: area name, file list, detected patterns, investigation template with CONFIRMED_SAFE/NEEDS_VALIDATION/KEEP classification
  - [x] Task 5 includes optional second-wave validation subagents for high-risk SAFE_TO_REMOVE items (function/class/file deletions, export removals)
  - [x] Completion signals: `CLEAN_INVESTIGATE_TASK_COMPLETE` (loop) and `CLEAN_INVESTIGATE_COMPLETE` (transition to clean_execute)
  - [x] Uses `{parent_branch}`, `{working_set_scope}`, `{context_files}` template variables

#### [2.3] Create `clean_execute.md` Prompt Template
- [x] **2.3.1** Create `build-loop/src/build_loop/prompts/shipping/clean_execute.md` containing Tasks 6-7 from current `clean.md`
  - **Produces**: Prompt template for clean execution sub-stage (apply changes + lint)
  - **Consumed by**: `create_ship_pipeline()` stage config, `Stage.build_prompt()`
  - **Replaces**: Tasks 6-7 section of monolithic `clean.md`
  - [x] Contains Task 6 (Execute Approved Changes with test verification and revert on failure) and Task 7 (Lint Compliance)
  - [x] Completion signals: `CLEAN_EXECUTE_TASK_COMPLETE` (loop) and `CLEAN_EXECUTE_COMPLETE` (transition to test_plan)
  - [x] Uses `{parent_branch}`, `{working_set_scope}`, `{context_files}` template variables
  - [x] Commit instruction in both tasks (commit approved changes, commit lint fixes)

---

### Phase 3: Expand Test Stage → 4 Sub-Stages

#### [3.1] Create `test_plan.md` Prompt Template with Batching Strategy
- [x] **3.1.1** Create `build-loop/src/build_loop/prompts/shipping/test_plan.md` containing Tasks 1-2 from current `test.md`, enhanced with parallelization strategy output modeled after original `/spectre:test` Step 2 (`/Users/joe/Dev/spectre/plugins/spectre/commands/test.md` lines 243-273)
  - **Produces**: Prompt template for test planning sub-stage (discovery + risk assessment + batching plan)
  - **Consumed by**: `create_ship_pipeline()` stage config, `Stage.build_prompt()`
  - **Replaces**: Tasks 1-2 section of monolithic `test.md`
  - [x] Contains Task 1 (Discover Working Set and Plan) and Task 2 (Risk Assessment and Test Plan)
  - [x] Task 2 includes batching heuristics output: P0=1 file/agent, P1=2-3 files/agent, P2=3-5 files/agent, P3=SKIP
  - [x] Includes the full risk-weighted testing framework (P0-P3 definitions, test quality requirements, mutation testing mindset) from current `test.md`
  - [x] Completion signals: `TEST_PLAN_TASK_COMPLETE` (loop) and `TEST_PLAN_COMPLETE` (transition to test_execute)
  - [x] Uses `{working_set_scope}`, `{context_files}` template variables

#### [3.2] Create `test_execute.md` Prompt Template with Subagent Dispatch
- [ ] **3.2.1** Create `build-loop/src/build_loop/prompts/shipping/test_execute.md` with parallel @spectre:tester subagent dispatch modeled after original `/spectre:test` Step 3 (`/Users/joe/Dev/spectre/plugins/spectre/commands/test.md` lines 275-305)
  - **Produces**: Prompt template for test execution sub-stage with parallel Task tool subagent dispatch
  - **Consumed by**: `create_ship_pipeline()` stage config, `Stage.build_prompt()`
  - **Replaces**: Task 3 section of monolithic `test.md`
  - [ ] Includes explicit subagent dispatch instructions: partition test plan by risk tier, dispatch one @spectre:tester per batch in SINGLE message with multiple Task tool calls
  - [ ] Batching: P0 1 agent/file, P1 2-3 files/agent, P2 3-5 files/agent; aim for 3-5 agents medium scope, up to 8 large scope
  - [ ] Each subagent receives: file list, risk tier, test quality framework, project test conventions
  - [ ] Wait for all agents, consolidate results
  - [ ] Includes the full risk-weighted testing framework from current `test.md`
  - [ ] Completion signals: `TEST_EXECUTE_TASK_COMPLETE` (loop) and `TEST_EXECUTE_COMPLETE` (transition to test_verify)
  - [ ] Uses `{working_set_scope}`, `{context_files}` template variables

#### [3.3] Create `test_verify.md` Prompt Template
- [ ] **3.3.1** Create `build-loop/src/build_loop/prompts/shipping/test_verify.md` for post-execution verification
  - **Produces**: Prompt template for test verification sub-stage (run suite, fix failures, re-verify)
  - **Consumed by**: `create_ship_pipeline()` stage config, `Stage.build_prompt()`
  - **Replaces**: N/A (new sub-stage, partially extracted from Task 3's verification section)
  - [ ] Instructs: run full test suite scoped to working set, diagnose failures, fix (test bug vs production bug), re-run to confirm
  - [ ] Completion signal: `TEST_VERIFY_COMPLETE` (transition to test_commit)
  - [ ] Uses `{working_set_scope}`, `{context_files}` template variables
  - [ ] Max iterations hint: keep low (3), verification should be quick

#### [3.4] Create `test_commit.md` Prompt Template
- [ ] **3.4.1** Create `build-loop/src/build_loop/prompts/shipping/test_commit.md` containing Task 4 from current `test.md`
  - **Produces**: Prompt template for test commit sub-stage (logical grouping + commit)
  - **Consumed by**: `create_ship_pipeline()` stage config, `Stage.build_prompt()`
  - **Replaces**: Task 4 section of monolithic `test.md`
  - [ ] Stage all test files + production bug fixes, commit with descriptive message, verify clean state
  - [ ] Completion signal: `TEST_COMMIT_COMPLETE` (transition to rebase)
  - [ ] Uses `{working_set_scope}`, `{context_files}` template variables
  - [ ] Max iterations hint: 1 (single commit operation)

---

### Phase 4: Update Pipeline Config and Hooks

#### [4.1] Rewrite `create_ship_pipeline()` for 8 Sub-Stages
- [ ] **4.1.1** Replace the 3-stage definition in `create_ship_pipeline()` in `build-loop/src/build_loop/pipeline/loader.py` (lines 413-481) with 8 stages: `clean_discover`, `clean_investigate`, `clean_execute`, `test_plan`, `test_execute`, `test_verify`, `test_commit`, `rebase`
  - **Produces**: `PipelineConfig` with 8 stages, correct signals, transitions, and iteration limits
  - **Consumed by**: `run_ship_pipeline()` in `cli.py`, `PipelineExecutor`
  - **Replaces**: Previous 3-stage `create_ship_pipeline()` factory
  - [ ] `start_stage="clean_discover"`
  - [ ] `end_signals=["SHIP_COMPLETE"]`
  - [ ] Transition chain: clean_discover→clean_investigate→clean_execute→test_plan→test_execute→test_verify→test_commit→rebase→(end)
  - [ ] Iteration limits: clean_discover/clean_investigate/clean_execute/test_plan/test_execute use `max_iterations`; test_verify uses `min(max_iterations, 3)`; test_commit uses `1`; rebase uses `min(max_iterations, 3)`
  - [ ] All stages use `PLAN_DENIED_TOOLS` for denied_tools (Task no longer in that list)
  - [ ] Each stage references its corresponding new prompt template file

#### [4.2] Update Ship Hooks for New Sub-Stage Names
- [ ] **4.2.1** Update `ship_before_stage()` in `build-loop/src/build_loop/hooks.py` to snapshot HEAD at `clean_discover` and `test_plan` (start of each logical group), no-op for all other sub-stages
  - **Produces**: HEAD snapshots at correct points in sub-stage flow
  - **Consumed by**: `ship_after_stage()` for diff computation
  - **Replaces**: Previous `ship_before_stage()` that matched `"clean"` and `"test"`
  - [ ] `clean_discover` triggers HEAD snapshot
  - [ ] `test_plan` triggers HEAD snapshot
  - [ ] `clean_investigate`, `clean_execute`, `test_execute`, `test_verify`, `test_commit`, `rebase` are no-ops
- [ ] **4.2.2** Update `ship_after_stage()` in `build-loop/src/build_loop/hooks.py` to capture `clean_summary` after `clean_execute` and `test_summary` after `test_commit` (end of each logical group), no-op for all other sub-stages
  - **Produces**: `context["clean_summary"]` and `context["test_summary"]` populated at correct points
  - **Consumed by**: Rebase stage prompt via `{clean_summary}` and `{test_summary}` template variables
  - **Replaces**: Previous `ship_after_stage()` that matched `"clean"` and `"test"`
  - [ ] `clean_execute` captures `clean_summary` from git diff
  - [ ] `test_commit` captures `test_summary` from git diff
  - [ ] All other sub-stages are no-ops

---

### Phase 5: Add Subagent Dispatch to Plan Research

#### [5.1] Update Research Prompt with Parallel Subagent Dispatch
- [ ] **5.1.1** Add parallel subagent dispatch instructions to `build-loop/src/build_loop/prompts/planning/research.md` after Step 2, modeled after original `/spectre:research` Step 3 (`/Users/joe/Dev/spectre/plugins/spectre/commands/research.md` lines 42-55)
  - **Produces**: Research stage prompt that dispatches parallel @finder, @analyst, @patterns subagents via Task tool
  - **Consumed by**: Research stage agent during plan pipeline execution
  - **Replaces**: Previous sequential Read/Grep/Glob-only exploration instructions
  - [ ] Step 2b added: "Dispatch Parallel Research Agents" with Task tool dispatch for @finder, @analyst, @patterns
  - [ ] Conditional: only dispatch subagents for larger scopes (multiple modules)
  - [ ] Single-message parallel dispatch instruction included
  - [ ] Wait-for-all synchronization before consolidation into `task_context.md`
  - [ ] Existing Step 2 preserved as fallback for small scopes

#### [5.2] Light-Touch Updates to create_plan.md and create_tasks.md
- [ ] **5.2.1** Add optional subagent dispatch note to `build-loop/src/build_loop/prompts/planning/create_plan.md` for comprehensive-depth plans that need deep analysis of integration points
  - **Produces**: Plan stage can optionally dispatch @analyst subagents for complex features
  - **Consumed by**: Plan stage agent
  - **Replaces**: N/A (additive)
  - [ ] Optional subagent dispatch instruction added for comprehensive depth plans
- [ ] **5.2.2** Add optional subagent dispatch note to `build-loop/src/build_loop/prompts/planning/create_tasks.md` for task breakdown that needs codebase location research
  - **Produces**: Task stage can optionally dispatch @finder subagents to locate files for task granularity
  - **Consumed by**: Task stage agent
  - **Replaces**: N/A (additive)
  - [ ] Optional subagent dispatch instruction added for complex task breakdowns

---

### Phase 6: Deprecate Old Prompts

#### [6.1] Add Deprecation Headers to Old Prompt Files
- [ ] **6.1.1** Add deprecation comment to top of `build-loop/src/build_loop/prompts/shipping/clean.md` noting it has been split into `clean_discover.md`, `clean_investigate.md`, `clean_execute.md`
  - **Produces**: Backward compat for custom YAML pipelines referencing `clean.md`
  - **Consumed by**: N/A (informational)
  - **Replaces**: N/A
  - [ ] Deprecation header present at top of file
- [ ] **6.1.2** Add deprecation comment to top of `build-loop/src/build_loop/prompts/shipping/test.md` noting it has been split into `test_plan.md`, `test_execute.md`, `test_verify.md`, `test_commit.md`
  - **Produces**: Backward compat for custom YAML pipelines referencing `test.md`
  - **Consumed by**: N/A (informational)
  - **Replaces**: N/A
  - [ ] Deprecation header present at top of file

---

### Phase 7: Update Tests

#### [7.1] Update Pipeline Factory Tests
- [ ] **7.1.1** Rewrite `build-loop/tests/test_ship_pipeline.py` for 8-stage ship pipeline: update expected stage count, stage names (`clean_discover`, `clean_investigate`, `clean_execute`, `test_plan`, `test_execute`, `test_verify`, `test_commit`, `rebase`), `start_stage="clean_discover"`, new signal names, new transition maps, `denied_tools` no longer contains Task
  - **Produces**: Passing tests that validate the new 8-stage pipeline config
  - **Consumed by**: CI, `pytest tests/ -k ship`
  - **Replaces**: Previous 3-stage pipeline tests
  - [ ] `test_returns_pipeline_config` asserts 8 stages with correct names
  - [ ] `test_pipeline_name_and_start_stage` asserts `start_stage="clean_discover"`
  - [ ] Transition tests validate full chain: clean_discover→...→rebase→(end)
  - [ ] Completion status tests validate all new signal names
  - [ ] Denied tools test confirms Task is NOT in any stage's denied_tools

#### [7.2] Update Hook Tests
- [ ] **7.2.1** Update `build-loop/tests/test_ship_hooks.py` for new sub-stage names: `before_stage("clean_discover")` snapshots HEAD, `before_stage("clean_investigate")` is no-op, `after_stage("clean_execute")` captures `clean_summary`, `after_stage("test_commit")` captures `test_summary`
  - **Produces**: Passing hook tests for new sub-stage names
  - **Consumed by**: CI, `pytest tests/ -k ship_hooks`
  - **Replaces**: Previous hook tests that matched `"clean"` and `"test"`
  - [ ] Tests pass for all 8 sub-stage name permutations in before/after hooks

#### [7.3] Update Integration and Prompt Tests
- [ ] **7.3.1** Update `build-loop/tests/test_run_ship_pipeline.py` to work with the new 8-stage `create_ship_pipeline()` factory
  - **Produces**: Passing integration tests for `run_ship_pipeline()`
  - **Consumed by**: CI
  - **Replaces**: Previous integration tests with 3-stage factory mock
  - [ ] Happy path test passes with new factory
  - [ ] Resume test passes
  - [ ] Failure path tests pass
- [ ] **7.3.2** Update or create prompt content tests for the 7 new sub-stage prompt files: verify each contains correct template variables, completion signals, and (where applicable) subagent dispatch instructions
  - **Produces**: Passing prompt content tests
  - **Consumed by**: CI
  - **Replaces**: Previous `test_clean_prompt.py` and `test_test_prompt.py`
  - [ ] Each new prompt file has a test that validates template variables present
  - [ ] Each new prompt file has a test that validates completion signal names in output format
  - [ ] `clean_investigate.md` test verifies subagent dispatch instructions exist
  - [ ] `test_execute.md` test verifies subagent dispatch instructions exist
- [ ] **7.3.3** Update `build-loop/tests/test_ship_cli.py`, `test_ship_stats.py`, and any other ship tests that reference old stage names or tool lists
  - **Produces**: Full ship test suite passes
  - **Consumed by**: CI
  - **Replaces**: Tests referencing old 3-stage names
  - [ ] `pytest tests/ -k ship -v` — all tests pass

---

### Phase 8: Update Documentation and Knowledge

#### [8.1] Update Project Documentation
- [ ] **8.1.1** Update `CLAUDE.md` architecture section to reflect 8-stage ship pipeline, Task tool no longer denied, per-stage tool filtering active
  - **Produces**: Accurate project documentation
  - **Consumed by**: Future development sessions
  - **Replaces**: Previous 3-stage ship pipeline docs, previous tool filtering docs
  - [ ] Tool Filtering section updated: Task removed from denied lists
  - [ ] Ship pipeline section shows 8 stages with transition chain
  - [ ] New prompt files listed in Key Files table
- [ ] **8.1.2** Update `.claude/skills/feature-ship-pipeline/SKILL.md` with new 8-stage architecture, new signal names, new hook behavior, subagent dispatch patterns
  - **Produces**: Accurate feature knowledge for future sessions
  - **Consumed by**: spectre-recall skill loading
  - **Replaces**: Previous 3-stage ship pipeline knowledge
  - [ ] Stage config section shows 8 stages
  - [ ] Transition chain updated
  - [ ] Hook section updated for new sub-stage names
  - [ ] Key Files table includes all 7 new prompt files
  - [ ] Gotchas section updated

---

## Execution Strategies

### Sequential Execution
1. 1.1 - Remove Task from deny lists (no dependencies)
2. 1.2 - Wire per-stage tool filtering (depends on 1.1)
3. 2.1 - Create clean_discover.md (depends on 1.1)
4. 2.2 - Create clean_investigate.md (depends on 1.1)
5. 2.3 - Create clean_execute.md (depends on 1.1)
6. 3.1 - Create test_plan.md (depends on 1.1)
7. 3.2 - Create test_execute.md (depends on 1.1)
8. 3.3 - Create test_verify.md (depends on 1.1)
9. 3.4 - Create test_commit.md (depends on 1.1)
10. 4.1 - Rewrite create_ship_pipeline() (depends on 2.1-2.3, 3.1-3.4)
11. 4.2 - Update ship hooks (depends on 4.1)
12. 5.1 - Update research.md (depends on 1.1)
13. 5.2 - Update create_plan.md, create_tasks.md (depends on 1.1)
14. 6.1 - Deprecate old prompts (depends on 2.1-2.3, 3.1-3.4)
15. 7.1 - Update pipeline tests (depends on 4.1)
16. 7.2 - Update hook tests (depends on 4.2)
17. 7.3 - Update integration/prompt tests (depends on 4.1, 6.1)
18. 8.1 - Update docs and knowledge (depends on all above)

### Parallel Execution

**Wave 1 (concurrent)**: 1.1, 1.2
- Foundation: unblock Task + wire per-stage filtering

**Wave 2 (after Wave 1)**: 2.1, 2.2, 2.3, 3.1, 3.2, 3.3, 3.4, 5.1, 5.2
- All prompt creation/updates are independent of each other

**Wave 3 (after Wave 2)**: 4.1, 4.2, 6.1
- Pipeline config, hooks, and deprecation depend on prompts existing

**Wave 4 (after Wave 3)**: 7.1, 7.2, 7.3
- All test updates depend on implementation being complete

**Wave 5 (after Wave 4)**: 8.1
- Documentation depends on everything being done and verified

---

## Coverage Summary
- Phases: 8
- Parent Tasks: 14
- Sub-tasks: 25
