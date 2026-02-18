# Ship — Test Commit Stage

You are running the **test_commit** sub-stage of the ship pipeline. Your job is to commit all test changes and any production bug fixes discovered during testing — so the branch has a clean, atomic test commit ready for rebase.

This stage should complete in a single iteration. Stage files, commit, and verify clean state.

You will complete **one task per iteration**. After each task, STOP and output a completion signal. The outer loop will call you again for the next task.

---

## Context

- **Working set scope**: `{working_set_scope}`
- **Context files**: {context_files}

---

## Tasks

### Task 1: Stage, Commit, and Verify

Commit all test work from the test_execute and test_verify stages into a single, descriptive commit.

1. Stage all new and modified test files created during testing
2. Stage any production code bug fixes discovered during test_verify (if any)
3. Review the staged changes to ensure nothing unrelated is included
4. Commit with a descriptive message summarizing what was tested:
   - Include the number of new test files and tests added
   - Note any production bug fixes if applicable
   - Example: `test(ship): add 12 tests for auth module, fix token expiry bug`
5. Verify the commit is clean — no unstaged changes remain for files you touched
6. If unstaged changes remain, stage and amend the commit

This is the **final task** in the test_commit sub-stage.

**When done, STOP and output:**
```json
{"status": "TEST_COMMIT_COMPLETE", "summary": "Committed: N test files, M new tests, K production bug fixes"}
```

---

## Rules

- Work ONLY on files in the working set (`{working_set_scope}`) — do not commit changes outside the branch's scope
- Commit all test-related changes in a single atomic commit
- Include production bug fixes discovered during testing in the same commit
- Verify clean state after committing — no orphaned unstaged changes
- Complete exactly one task per iteration, then STOP

**Do NOT:**
- Write new tests — that was the test_execute stage's job
- Diagnose or fix test failures — that was the test_verify stage's job
- Modify production code unless staging previously-discovered bug fixes
- Split into multiple commits — keep it atomic
- Combine multiple tasks into one iteration
