# Ship — Test Verify Stage

You are running the **test_verify** sub-stage of the ship pipeline. Your job is to run the full test suite scoped to the working set, diagnose any failures, fix them, and re-run to confirm everything passes — so the branch is ready for a clean commit.

This stage should be quick — aim for 3 iterations or fewer. If tests are passing, you are done in a single iteration.

You will complete **one task per iteration**. After each task, STOP and output a completion signal. The outer loop will call you again for the next task.

---

## Context

- **Working set scope**: `{working_set_scope}`
- **Context files**: {context_files}

---

## Tasks

### Task 1: Run Full Test Suite and Diagnose Failures

Run the full test suite scoped to the working set and diagnose any failures.

1. Run all tests related to the working set files:
   - Use scoped test execution (e.g., `pytest tests/ -k <relevant>` or `--testPathPattern`) — do NOT run the entire repository's test suite
   - Include both new tests (from test_execute) and existing tests that cover modified production code
2. If all tests pass:
   - Verify no warnings or flaky behavior
   - You are done — proceed to completion
3. If any tests fail, diagnose each failure:
   - **Test bug**: The test itself is wrong (bad assertion, stale mock, incorrect expectation)
     - Fix the test to match the correct behavior
   - **Production bug**: The production code has a genuine bug revealed by the test
     - Fix the production code and note the fix
   - **Integration issue**: Tests conflict with each other (shared state, ordering dependency)
     - Isolate the tests — add setup/teardown or use fresh fixtures
4. After fixing, re-run the failing tests to confirm they now pass
5. If fixes introduced new failures, diagnose and fix those too (iterate until clean)

**Do NOT** commit any files — that is the test_commit stage's job.

**When all tests pass, STOP and output:**
```json
{"status": "TEST_VERIFY_COMPLETE", "summary": "All tests passing: N tests run, M fixes applied (K test bugs, J production bugs)"}
```

**If fixes are still needed after this iteration, STOP and output:**
```json
{"status": "TEST_VERIFY_TASK_COMPLETE", "summary": "Partial fix: N tests passing, M still failing — continuing next iteration"}
```

---

## Rules

- Work ONLY on files in the working set (`{working_set_scope}`) — do not fix tests or code outside the branch's changes
- Follow the project's existing test patterns — match naming conventions, directory structure, and assertion style
- Prefer fixing tests over changing production code — only fix production code for genuine bugs
- Keep iterations minimal — verification should be quick, not exploratory

**Do NOT:**
- Write new tests — that was the test_execute stage's job
- Commit any files — that is handled by the test_commit stage
- Refactor or clean up production code — that was the clean stage's job
- Run the entire repository's test suite — scope to working set only
- Combine multiple tasks into one iteration — complete exactly one task, then STOP
