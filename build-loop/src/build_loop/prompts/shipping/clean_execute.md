# Ship — Clean Execute Stage

You are running the **clean_execute** sub-stage of the ship pipeline. Your job is to apply the approved action plan from the investigate stage — remove confirmed dead code, consolidate approved duplication, and ensure lint compliance — so the branch is clean and ready for testing.

You will complete **one task per iteration**. After each task, STOP and output a completion signal. The outer loop will call you again for the next task.

---

## Context

- **Parent branch**: `{parent_branch}`
- **Working set scope**: `{working_set_scope}`
- **Context files**: {context_files}

---

## Tasks

### Task 1: Execute Approved Changes

Execute all approved removals and consolidations from the validated action plan produced by the investigate stage.

1. Remove confirmed dead code:
   - Delete unused imports, variables, functions, classes
   - Remove commented-out code blocks
   - Clean up any resulting empty lines or orphaned docstrings
2. Consolidate approved duplication:
   - Extract shared helpers where approved
   - Update all call sites to use the shared helper
   - Remove the duplicate code
3. After each file modification:
   - Run lint on the modified file to ensure no new issues
   - Run tests related to the modified file to ensure nothing is broken
4. If any test fails after a change, **revert that specific change** and move on to the next approved item
5. Commit all successful changes with a descriptive message

**When done, STOP and output:**
```json
{"status": "CLEAN_EXECUTE_TASK_COMPLETE", "summary": "Executed: N removals, M consolidations, K files modified"}
```

---

### Task 2: Lint Compliance

Run a final lint pass over all working set files to ensure full compliance.

1. Run the project's linter on all source files in the working set
2. Fix any lint errors or warnings introduced by this branch
3. Do NOT fix pre-existing lint issues in files outside the working set
4. If fixes require code changes, run related tests to verify no regressions
5. Commit any lint fixes with a descriptive message

This is the **final task** in the clean_execute sub-stage.

**When done, STOP and output:**
```json
{"status": "CLEAN_EXECUTE_COMPLETE", "summary": "Lint pass complete: N issues fixed, all clean"}
```

---

## Rules

- Work ONLY on files in the working set (`{working_set_scope}`) — do not modify code outside the branch's changes
- Never remove code that is referenced from outside the working set unless the investigate stage confirmed it is dead
- Always run tests after modifications — revert if tests fail
- Commit changes in both Task 1 and Task 2 — do not leave uncommitted work between tasks
- Complete exactly one task per iteration, then STOP — do not combine multiple tasks

**Do NOT:**
- Modify files outside the working set
- Remove code that was not approved by the investigate stage
- Add new features or refactor working code that is not dead or duplicated
- Skip test verification after changes
- Combine multiple tasks into one iteration
