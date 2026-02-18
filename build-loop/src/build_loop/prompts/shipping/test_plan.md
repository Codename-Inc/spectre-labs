# Ship — Test Plan Stage

You are running the **test_plan** sub-stage of the ship pipeline. Your job is to discover the working set, assess risk, and produce a prioritized test plan with batching strategy — so the test_execute stage knows exactly what to dispatch.

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

### Task 1: Discover Working Set and Plan

Identify every file changed on this branch and build a structured inventory.

1. Run `git diff --name-only {working_set_scope}` to get the full list of changed files
2. Categorize each file:
   - **Source files**: production code that needs test coverage
   - **Test files**: existing tests that may need updating
   - **Config/docs/generated**: no test coverage needed
3. For each source file, identify:
   - What functions/classes were added or modified
   - What existing tests (if any) already cover this code
   - What test gaps remain (new code with no tests, modified code with stale tests)
4. Record the discovery as a structured list — you will reference this in every subsequent task

**Do NOT** write any tests in this task — only analyze and plan.

**When done, STOP and output:**
```json
{"status": "TEST_PLAN_TASK_COMPLETE", "summary": "Working set: N source files, M already tested, K gaps identified"}
```

---

### Task 2: Risk Assessment, Test Plan, and Batching Strategy

Prioritize test gaps using the risk-weighted framework above. The goal is surgical coverage that maximizes confidence while minimizing token cost — not brute-force line coverage. Then produce a batching strategy for parallel test execution.

#### Risk Assessment

1. Classify each test gap from Task 1 into a priority tier using the tier definitions above:
   - **P0 — Critical**: Auth, payments, security, data mutations, PII, permissions — thorough behavioral coverage
   - **P1 — High**: Public APIs, module boundaries, state management, core features — happy path + critical errors
   - **P2 — Medium**: Utilities, helpers, validators with real logic — public surface happy path only
   - **P3 — Low**: Types, configs, constants, simple wrappers, re-export barrels — **NO TESTS** (explicitly skip)
2. For each P0-P2 gap, define:
   - What to test (function/class name, specific **behavior** — not implementation detail)
   - Expected assertions (what the test verifies — must be mutation-resistant)
   - Any mocks required (external boundaries only — never mock internal functions)
3. Order the test plan: P0 first, then P1, P2. List P3 files explicitly as "SKIP — {reason}"
4. If context files are available, cross-reference against scope requirements to ensure acceptance criteria have corresponding tests

#### Batching Strategy for Parallel Execution

5. Group the test plan into independent batches for parallel agent dispatch:
   - **P0 files**: 1 file per agent (thorough coverage requires focus)
   - **P1 files**: 2-3 related files per agent
   - **P2 files**: 3-5 files per agent (lighter coverage)
   - **P3 files**: SKIP — no agent assigned
6. Target 3-5 parallel agents for medium scope, up to 8 for large scope
7. Output the batching plan as a numbered list of agent assignments:
   ```
   Agent 1 (P0): auth_handler.py — all behaviors + error paths
   Agent 2 (P1): api_router.py, middleware.py — happy path + critical errors
   Agent 3 (P2): utils.py, formatters.py, helpers.py — public surface only
   ```

**Do NOT** write any tests or implement anything in this task — only plan and organize.

This is the **final task** in the test_plan sub-stage.

**When done, STOP and output:**
```json
{"status": "TEST_PLAN_COMPLETE", "summary": "Test plan: N tests planned (P0: A, P1: B, P2: C, P3: D skipped), K agents batched"}
```

---

## Rules

- Work ONLY on files in the working set (`{working_set_scope}`) — do not plan tests for code outside the branch's changes
- Follow the project's existing test patterns — match naming conventions, directory structure, and assertion style
- Use mocks and stubs only when necessary (external services, filesystem, network) — prefer testing real behavior
- Every new public function or class in the working set should have at least one test planned
- P0 and P1 tests are mandatory — P2 is best-effort, P3 is explicitly skipped

**Do NOT:**
- Write tests or implement anything — this is a planning-only stage
- Plan tests for code outside the working set
- Skip the risk assessment — prioritization prevents wasting iterations on low-value tests
- Combine multiple tasks into one iteration — complete exactly one task, then STOP
