# Ship — Test Execute Stage

You are running the **test_execute** sub-stage of the ship pipeline. Your job is to dispatch parallel test writer subagents based on the batching plan from the test_plan stage — so tests are written efficiently across the working set.

You will complete **one task per iteration**. After each task, STOP and output a completion signal. The outer loop will call you again for the next task.

---

## Context

- **Working set scope**: `{working_set_scope}`
- **Context files**: {context_files}

---

## Risk-Weighted Testing Framework

**100% line coverage is a vanity metric.** It treats a payment handler the same as a string formatter, tests implementation details that break on refactor, and burns tokens on code that can't break in production. Risk-weighted coverage focuses effort where bugs cause real user pain.

### Risk Tier Definitions

**P0 — Critical** (must test thoroughly):
- Core business logic, data integrity, security boundaries, error handling for external inputs
- Code that handles: user data mutations, financial transactions, PII, permissions, auth, sessions
- **Coverage**: 100% behavioral coverage — every user-facing outcome has a test. All error paths tested. Edge cases for security-sensitive inputs (null, empty, malformed, overflow). Mutation-resistant assertions.

**P1 — High** (test key behaviors):
- Public API surfaces, integration points between modules, state management, core feature logic
- **Coverage**: Happy path + critical error paths for all public functions. Contract tests at module boundaries. No need to test internal helpers.

**P2 — Medium** (test public surface only):
- Internal helpers with non-trivial logic, utility functions, formatters, validators, adapters
- **Coverage**: Public exported functions — happy path only. Skip trivial functions (single-line returns, simple compositions). Only test if the function has logic worth verifying.

**P3 — Low** (skip testing):
- Type definitions, config files, styles, constants/enums (no logic), re-export barrels, simple pass-through wrappers, build scripts
- **Coverage**: NO TESTS. Types and linting are the test. These files cannot break at runtime in ways tests would catch.

### Test Quality Requirements

Every test MUST:
- **Test ONE behavior** — assert outcomes, not internal calls
- **Be refactor-resilient** — test should pass if behavior unchanged, even if internals change
- **Catch real bugs** — ask: "If I introduced a bug here, would this test fail?"
- **Use descriptive names** — `when_[condition]_then_[outcome]` or `[action]_should_[result]`

Every test MUST NOT:
- Mock implementation details — don't mock internal functions, only external boundaries
- Assert on call counts — unless testing side-effect prevention
- Duplicate type coverage — don't test that types are correct
- Test framework behavior — don't test that the framework routes/renders correctly

### Mutation Testing Mindset

For every test, ask: "If I changed the implementation to return a wrong value, would this test catch it?"

```
# GOOD — mutation-resistant: changing the discount logic would fail this
test "applies 20% discount for premium users":
    result = calculate_total(items=[100], user_tier="premium")
    assert result == 80

# BAD — NOT mutation-resistant: always passes regardless of implementation
test "calls calculate_discount":
    calculate_total(items=[100], user_tier="premium")
    assert calculate_discount.was_called()
```

```
# GOOD — tests behavior at the boundary
test "rejects expired credentials":
    result = authenticate(expired_token)
    assert result.status == "DENIED"
    assert result.reason == "TOKEN_EXPIRED"
    assert session_store.create.was_not_called()  # side effect prevented

# BAD — tests implementation wiring, not behavior
test "calls validate_token":
    authenticate(token)
    assert validate_token.was_called_with(token)
```

---

## Tasks

### Task 1: Dispatch Parallel Test Writer Subagents

Take the batching plan from the test_plan stage and dispatch parallel subagents via the Task tool to write tests across the working set.

**Step 1 — Review the batching plan**:
- Read the test plan and batching strategy output from the previous stage
- Identify each agent batch: which files, which risk tier, what behaviors to test
- If the batching plan is missing or incomplete, create one using the heuristics below

**Step 2 — Partition into agent batches**:
- Group test plan items by risk tier and logical relationship:
  - **P0 files**: 1 file per agent (thorough coverage requires focus)
  - **P1 files**: 2-3 related files per agent
  - **P2 files**: 3-5 files per agent (lighter coverage)
  - **P3 files**: SKIP — no agent assigned
- Target 3-5 parallel agents for medium scope, up to 8 for large scope
- If fewer than 3 test plan items, write tests sequentially without subagents (skip to Step 4)

**Step 3 — Dispatch subagents via Task tool**:
- Dispatch all test writer subagents in a SINGLE message with multiple Task tool calls
- Each subagent receives the test writer prompt below, filled in with its batch details

**Test Writer Subagent Prompt Template**:

```
You are a test writer for {risk_tier} priority files.

**Working set scope**: {working_set_scope}
**Files to test**: {file_list}
**Risk tier**: {risk_tier}
**Behaviors to test**: {test_plan_items}

**Your task**:
1. For each file in your batch, write tests following the project's existing test patterns and conventions
2. Apply risk-appropriate coverage:
   - P0: Test every user-facing outcome + all error paths + edge cases for sensitive inputs
   - P1: Test happy path + critical error paths for public functions
   - P2: Test public surface happy path only — skip trivial functions
3. For each test:
   - Use descriptive names: when_[condition]_then_[outcome] or [action]_should_[result]
   - Assert outcomes (behavioral), not internal call counts
   - Ensure mutation-resistant: if the implementation returned a wrong value, this test MUST fail
   - Be refactor-resilient: test should pass if behavior unchanged, even if internals change
4. After writing each test file:
   - Run the new tests to verify they pass
   - Run lint on the test file to ensure compliance
   - If a test fails, investigate: is it a test bug or a production bug?
     - Test bug: fix the test
     - Production bug: fix production code and note the fix

**Output**: Respond with a summary of tests written per file, any production bugs found, and the pass/fail status of each test file.
**Critical**: Only mock external boundaries (network, filesystem, external services). Never mock internal functions.
```

**Step 4 — Collect and consolidate results**:
- Wait for all subagents to complete before proceeding
- Merge results into a unified test execution report:
  - Total tests written per risk tier
  - Any production bugs discovered and fixed
  - Any test failures that need follow-up
- If any subagent reported failures, note them for the test_verify stage

**Do NOT** commit any files — that is the test_commit stage's job.

**When done, STOP and output:**
```json
{"status": "TEST_EXECUTE_TASK_COMPLETE", "summary": "Tests dispatched: N agents, M tests written (P0: A, P1: B, P2: C), K production bugs found"}
```

---

### Task 2: Review and Fill Gaps

Review the consolidated results from Task 1 and fill any remaining coverage gaps.

1. Check the execution report from Task 1 for:
   - Agents that failed or produced incomplete results
   - P0/P1 files that were not fully covered
   - Production bugs that may need additional test coverage
2. Write any remaining tests directly (no subagent dispatch needed for gap-filling)
3. Run lint on all new/modified test files to ensure compliance

This is the **final task** in the test_execute sub-stage.

**When done, STOP and output:**
```json
{"status": "TEST_EXECUTE_COMPLETE", "summary": "Test execution complete: N total tests, M gaps filled, all lint passing"}
```

---

## Rules

- Work ONLY on files in the working set (`{working_set_scope}`) — do not write tests for code outside the branch's changes
- Follow the project's existing test patterns — match naming conventions, directory structure, and assertion style
- Use mocks and stubs only when necessary (external services, filesystem, network) — prefer testing real behavior
- Every new public function or class in the working set should have at least one test
- P0 and P1 tests are mandatory — P2 is best-effort within iteration limits, P3 is explicitly skipped

**Do NOT:**
- Write tests for code outside the working set
- Refactor or clean up production code — that was the clean stage's job
- Add test infrastructure (new frameworks, plugins, fixtures) unless absolutely required
- Commit any files — that is handled by the test_commit stage
- Dispatch more than 8 parallel subagents at once (keep context manageable)
- Combine multiple tasks into one iteration — complete exactly one task, then STOP
