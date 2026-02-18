# Ship Loop (`--ship`)

## The Problem

After `spectre-build` completes a feature build, there's a manual ceremony to get code from "works on branch" to "landed on main":

1. Run `/spectre:clean` to remove dead code and artifacts
2. Run `/spectre:test` to ensure coverage
3. Run `/spectre:rebase` to rebase and land

Each of these is a full context window of work. Today you invoke them manually, one at a time, waiting for each to finish. The ship loop automates this end-to-end — the third autonomous loop in the plan → build → ship trifecta.

**Current state**: Manual invocation of 3 separate commands with human babysitting between each.

**Desired state**: `spectre-build --ship` runs clean → test → rebase autonomously, landing the branch via PR or local merge when done.

## Target Users

- **Primary**: Developer who just finished a build loop and wants to ship the feature branch
- **Secondary**: Developer with a manually-built feature branch ready for landing

## Success Criteria

- Clean, test, and rebase stages complete autonomously without human intervention (happy path)
- Feature branch lands via PR (remote) or local merge (no remote) at the end
- Interrupted sessions can resume via `spectre-build resume`
- Each stage stays within a tight token budget by decomposing into per-context-window tasks
- User gets notification + audio when the ship loop completes

## User Experience

### Entry Points

**Flag mode** (fully autonomous):
```bash
spectre-build --ship --context scope.md --max-iterations 15
```

**Interactive mode** (prompted start):
```bash
spectre-build --ship
# Prompts for context files, confirms settings, then runs
```

**Manifest mode** (YAML frontmatter):
```bash
spectre-build ship.md
# ship.md has: ship: true in frontmatter
```

### Flow

```
spectre-build --ship
  1. Config: detect parent branch, validate clean working tree
  2. Clean stage: dead code removal, lint, fix failing tests for touched files
  3. Test stage: ensure complete coverage, write new tests
  4. Rebase stage: rebase onto parent, resolve conflicts, land branch
  5. Notify: sound + notification on completion
```

### Landing Logic (end of rebase stage, executed by the agent)

The rebase prompt instructs the agent to:

- **If remote exists** (`git remote -v` has entries):
  - Create PR via `gh pr create` using repo PR template if found, otherwise default structure
  - PR includes: title from branch/commits, summary of changes, test results
- **If no remote**:
  - Check target branch for uncommitted work
  - **If clean**: merge feature branch into parent locally
  - **If dirty**: prompt user with option to approve stash → merge → stash pop
  - **If user declines**: abort with message, leave branch as-is

## Scope Boundaries

### IN

- `spectre-build --ship` flag with interactive mode
- 3-stage pipeline: clean → test → rebase
- Each stage sends prompts to Claude agents (agents run all commands)
- Clean stage: decomposed into tasks from clean.md steps (7 steps → ~7 tasks)
  - Scope working set, analyze dead code, analyze duplication, dispatch investigation subagents, validate findings, execute removals + verify + commit, ESLint compliance
- Test stage: decomposed into tasks from test.md steps (4 steps → ~4 tasks)
  - Discover working set + plan, risk assessment + test plan, write tests + verify, commit
- Rebase stage: single context window (not decomposed)
  - Confirm target, prepare (safety ref, fetch), execute rebase, verify, summary + land
- Config/setup: identify parent branch before pipeline starts
- Resume support via `spectre-build resume` (same session persistence pattern)
- Notification + audio on completion (`notify_ship_complete()`)
- Task decomposition: steps within clean/test prompts become task checklists for the agent
- PR template detection: agent checks for `.github/PULL_REQUEST_TEMPLATE.md` or similar
- Default PR structure when no template found

### OUT

- Chaining from `--build` (manual human validation sits between build and ship)
- Stage skipping (`--skip-clean`, `--skip-test`) — always all 3 stages
- Running git/gh commands from Python code — agents handle all commands via prompts
- Standalone CLI command — stays as a flag on `spectre-build`
- New completion strategies — reuse existing `JsonCompletion` / `PromiseCompletion`
- Changes to `PipelineExecutor` — ship loop uses the existing executor as-is

### MAYBE / FUTURE

- `--build --ship` chaining (once human validation step is automated)
- Stage skipping flags for partial flows
- Custom ship pipeline YAML definitions
- Ship-specific code review stage (currently relies on build loop's review)

## Constraints

- **Token budget**: Each stage must decompose work into tasks that fit within a single context window. The pipeline iterates tasks, not the agent.
- **Agent tool filtering**: Same denied tools as build loop (no AskUserQuestion, WebFetch, WebSearch, Task, EnterPlanMode, NotebookEdit) — except rebase stage may need different filtering for `gh` CLI usage.
- **Session JSON compatibility**: Ship loop session must work with existing `save_session()` / `load_session()` / `resume` flow.
- **Platform**: macOS notifications via osascript, cross-platform fallback.
- **Python 3.10+**: Same as build loop.

## Integration

### Touches

| Component | How |
|-----------|-----|
| `cli.py` | New `--ship` flag, `run_ship_pipeline()`, session routing |
| `pipeline/loader.py` | `create_ship_pipeline()` factory, stage configs |
| `hooks.py` | `ship_before_stage()` / `ship_after_stage()` for inter-stage context |
| `stats.py` | `ship_loops` counter, dashboard display |
| `notify.py` | `notify_ship_complete()` function |
| `manifest.py` | Support `ship: true` frontmatter field |
| `prompts/shipping/` | New prompt templates: `clean.md`, `test.md`, `rebase.md` |

### Avoids

- No changes to `PipelineExecutor` — uses existing executor with hooks
- No changes to `loop.py` — ship loop is pipeline-only, no legacy path
- No changes to existing build/plan prompts
- No changes to `stream.py` or `agent.py`

### Dependencies

- Existing pipeline executor (`pipeline/executor.py`)
- Existing completion strategies (`pipeline/completion.py`)
- Existing session persistence (`cli.py:save_session/load_session`)
- Existing notification system (`notify.py`)

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Pipeline architecture | Reuse PipelineExecutor | Same pattern as build + plan loops, zero engine changes |
| Task decomposition | Steps in clean/test become tasks | Each step is ~1 context window of work, keeps token accumulation tight |
| Rebase as single context | Not decomposed | Rebase needs continuous state (conflict resolution mid-flow), can't split |
| Landing logic in prompt | Agent executes PR/merge | Consistent with architecture — Python orchestrates, agent acts |
| Parent branch detection | Config step before pipeline | Needed for rebase target, better to fail fast |
| PR template detection | Agent checks at runtime | Agent has filesystem access, can search for templates |
| Stash approval | User approves, agent executes | Safety: user decides on risky operations, agent does the work |

## Risks

| Risk | Mitigation |
|------|-----------|
| Clean stage removes production code | Clean prompt has conservative validation (CONFIRMED_SAFE only), subagent cross-validation |
| Test stage writes low-quality tests | Risk-tiered approach (P0-P3), quality spot-checks, mutation testing mindset |
| Rebase conflicts cause data loss | Safety ref branch created before rebase, backup restore documented |
| PR creation fails (no gh auth) | Agent should check `gh auth status` before attempting PR, report clearly |
| Token budget exceeded in a stage | Task decomposition + max_iterations cap per stage |
| Stash pop conflicts after local merge | Agent should warn user if stash pop has conflicts, leave stash intact |

## Stage Design

### Stage 1: Clean

**Prompt**: `prompts/shipping/clean.md`
**Completion**: `JsonCompletion(signal_field="status")`
**Signals**: `CLEAN_TASK_COMPLETE` (iterate), `CLEAN_COMPLETE` (transition to test)
**Max iterations**: 10
**Transitions**: `CLEAN_COMPLETE` → test

Task checklist (from clean.md steps):
- [ ] Determine working set scope (commit range from parent branch)
- [ ] Analyze working set for dead code patterns
- [ ] Analyze duplication in working set
- [ ] Dispatch investigation subagents for findings
- [ ] Validate high-risk findings
- [ ] Execute approved removals, verify lint + tests, commit
- [ ] ESLint compliance scan

### Stage 2: Test

**Prompt**: `prompts/shipping/test.md`
**Completion**: `JsonCompletion(signal_field="status")`
**Signals**: `TEST_TASK_COMPLETE` (iterate), `TEST_COMPLETE` (transition to rebase)
**Max iterations**: 10
**Transitions**: `TEST_COMPLETE` → rebase

Task checklist (from test.md steps):
- [ ] Discover full working set and plan
- [ ] Risk assessment and test plan (P0-P3 tiers)
- [ ] Write tests via parallel subagents + verify (lint + test pass)
- [ ] Commit (planning artifacts + code changes)

### Stage 3: Rebase

**Prompt**: `prompts/shipping/rebase.md`
**Completion**: `JsonCompletion(signal_field="status")`
**Signals**: `SHIP_COMPLETE` (end pipeline)
**Max iterations**: 3
**Transitions**: none (end)
**End signals**: `["SHIP_COMPLETE"]`

Task list (single context, not decomposed):
- Confirm parent branch target
- Prepare: commit uncommitted, fetch, create safety ref
- Execute rebase, resolve conflicts
- Verify: lint + tests pass
- Land: PR (remote) or merge (local, with stash approval if needed)
- Summary: rebase report + smoketest guide

### Inter-Stage Context Flow

```
Config (before pipeline)
  → context["parent_branch"] = detected parent
  → context["working_set_scope"] = commit range

Clean stage
  → after_stage_hook captures: files cleaned, commits made
  → context["clean_summary"] = what was removed

Test stage
  → after_stage_hook captures: test results, coverage data
  → context["test_summary"] = what was tested/added

Rebase stage
  → reads parent_branch from context
  → reads clean/test summaries for PR description
```

## Next Steps

Recommended path: `/spectre:plan` → `/spectre:execute` (this is a STANDARD complexity feature — multiple files, new prompts, pipeline wiring, but follows established patterns exactly).
