# Ship — Test Stage

You are running the **test** stage of the ship pipeline. Your job is to ensure the working set has thorough, risk-appropriate test coverage so the branch can be landed with confidence.

You will complete **one task per iteration**. After each task, STOP and output a completion signal. The outer loop will call you again for the next task.

---

## Context

- **Working set scope**: `{working_set_scope}`
- **Context files**: {context_files}

---

## Tasks

### Task 1: Discover Working Set and Plan

Identify every file changed on this branch and build a test plan.

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
{"status": "TEST_TASK_COMPLETE", "summary": "Working set: N source files, M already tested, K gaps identified"}
```

---

### Task 2: Risk Assessment and Test Plan

Prioritize test gaps using a risk-tiered approach.

1. Classify each test gap from Task 1 into a priority tier:
   - **P0 — Critical**: Core business logic, data integrity, security boundaries, error handling for external inputs
   - **P1 — High**: Public API surfaces, integration points between modules, state management
   - **P2 — Medium**: Internal helpers with non-trivial logic, edge cases in algorithms, configuration parsing
   - **P3 — Low**: Simple getters/setters, pass-through functions, formatting utilities, code that is already well-covered by integration tests
2. For each gap, define:
   - What to test (function/class name, specific behavior)
   - Test type (unit, integration, or end-to-end)
   - Expected assertions (what the test should verify)
   - Any mocks or fixtures required
3. Order the test plan: P0 first, then P1, P2, P3
4. If context files are available, cross-reference against scope requirements to ensure acceptance criteria have corresponding tests

**Do NOT** write any tests in this task — only prioritize and plan.

**When done, STOP and output:**
```json
{"status": "TEST_TASK_COMPLETE", "summary": "Test plan: N tests planned (P0: A, P1: B, P2: C, P3: D)"}
```

---

### Task 3: Write Tests and Verify

Implement the test plan from Task 2, starting with P0 and working down.

1. For each planned test (in priority order):
   - Create the test file if it does not exist, or add to the existing test file
   - Write the test following the project's existing test patterns and conventions
   - Use descriptive test names that explain the expected behavior
   - Include both happy path and primary failure mode for each test opportunity
2. After writing each batch of tests (per source file):
   - Run the new tests to verify they pass
   - Run lint on the test file to ensure compliance
   - If a test fails, fix the test or investigate whether the production code has a bug
     - If production code has a bug, fix it and note the fix
3. After all tests are written:
   - Run the full test suite for the working set (not the entire repo) to verify no regressions
   - Fix any failures before proceeding

**Do NOT** modify production code unless you discover a genuine bug during testing. Do NOT refactor or clean up code — that was the clean stage's job.

**When done, STOP and output:**
```json
{"status": "TEST_TASK_COMPLETE", "summary": "Tests written: N new tests (P0: A, P1: B, P2: C, P3: D), all passing"}
```

---

### Task 4: Commit

Commit all test changes and summarize the test stage work.

1. Stage all new and modified test files
2. Stage any production code bug fixes discovered during testing (if any)
3. Commit with a descriptive message summarizing what was tested
4. Verify the commit is clean — no unstaged changes remain for files you touched

This is the **final task** in the test stage.

**When done, STOP and output:**
```json
{"status": "TEST_COMPLETE", "summary": "Committed: N test files, M new tests, K bug fixes"}
```

---

## Rules

- Work ONLY on files in the working set (`{working_set_scope}`) — do not write tests for code outside the branch's changes
- Follow the project's existing test patterns — match naming conventions, directory structure, and assertion style
- Use mocks and stubs only when necessary (external services, filesystem, network) — prefer testing real behavior
- Every new public function or class in the working set should have at least one test
- P0 and P1 tests are mandatory — P2 and P3 are best-effort within iteration limits

**Do NOT:**
- Write tests for code outside the working set
- Refactor or clean up production code — that was the clean stage's job
- Add test infrastructure (new frameworks, plugins, fixtures) unless absolutely required
- Skip the risk assessment (Task 2) — prioritization prevents wasting iterations on low-value tests
- Combine multiple tasks into one iteration — complete exactly one task, then STOP
