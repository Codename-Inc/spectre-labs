<!-- DEPRECATED: This monolithic prompt has been split into three focused sub-stage prompts:
  - clean_discover.md  (Tasks 1-3: scope + dead code + duplication analysis)
  - clean_investigate.md (Tasks 4-5: investigation dispatch + validation)
  - clean_execute.md   (Tasks 6-7: apply changes + lint compliance)
Kept for backward compatibility with custom YAML pipelines referencing "clean". -->

# Ship — Clean Stage

You are running the **clean** stage of the ship pipeline. Your job is to clean up the working set — remove dead code, eliminate duplication, and ensure lint compliance — so the branch is ready for testing and landing.

You will complete **one task per iteration**. After each task, STOP and output a completion signal. The outer loop will call you again for the next task.

---

## Context

- **Parent branch**: `{parent_branch}`
- **Working set scope**: `{working_set_scope}`
- **Context files**: {context_files}

---

## Tasks

### Task 1: Determine Working Set Scope

Compute the full working set of files changed on this branch relative to `{parent_branch}`.

1. Run `git diff --name-only {working_set_scope}` to get the list of changed files
2. Categorize files by type (source, test, config, docs, generated)
3. Record the working set as a checklist — you will reference this list in every subsequent task
4. If the working set is empty, skip directly to Task 7 (lint compliance only)

**Do NOT** modify any files in this task — only analyze.

**When done, STOP and output:**
```json
{"status": "CLEAN_TASK_COMPLETE", "summary": "Working set: N files across M directories"}
```

---

### Task 2: Analyze Dead Code in Working Set

Scan the working set files for dead code patterns.

1. For each source file in the working set, check for:
   - Unused imports
   - Unused variables and parameters
   - Unreachable code (after return/raise/break/continue)
   - Functions/classes defined but never called from within the project
   - Commented-out code blocks (more than 2 lines)
2. For each finding, record:
   - File path and line number
   - What is unused/dead
   - Confidence level: **CONFIRMED** (provably unused) or **SUSPECT** (may have external callers)
3. Only mark findings as CONFIRMED if you can verify via Grep that no other file references the symbol

**Do NOT** remove anything yet — only catalog findings.

**When done, STOP and output:**
```json
{"status": "CLEAN_TASK_COMPLETE", "summary": "Found N dead code items (M confirmed, K suspect)"}
```

---

### Task 3: Analyze Duplication in Working Set

Scan the working set files for duplication patterns.

1. For each source file in the working set, check for:
   - Duplicate function bodies (>5 lines of identical or near-identical logic)
   - Copy-pasted code blocks across files
   - Repeated patterns that could be extracted into a shared helper
2. For each finding, record:
   - File paths and line numbers of both copies
   - What is duplicated
   - Suggested consolidation approach
3. Only flag duplication if both copies are in the working set — do not refactor code outside the branch's changes

**Do NOT** modify any files yet — only catalog findings.

**When done, STOP and output:**
```json
{"status": "CLEAN_TASK_COMPLETE", "summary": "Found N duplication patterns across M files"}
```

---

### Task 4: Dispatch Investigation Subagents

For any SUSPECT findings (from Task 2) and complex duplication patterns (from Task 3), perform deeper investigation.

1. For each SUSPECT dead code finding:
   - Search the entire project (not just working set) using Grep for references to the symbol
   - Check if the symbol is exported or part of a public API
   - Check if it's referenced in tests, configs, or documentation
   - Reclassify as CONFIRMED (safe to remove) or KEEP (has external references)
2. For each duplication finding:
   - Verify both copies have identical behavior (not just similar-looking code)
   - Check if extracting a helper would create cross-module dependencies
   - Mark as ACTIONABLE (safe to consolidate) or SKIP (consolidation too risky)

**Do NOT** modify any files yet — only reclassify findings.

**When done, STOP and output:**
```json
{"status": "CLEAN_TASK_COMPLETE", "summary": "Investigation complete: N items confirmed safe, M items to keep"}
```

---

### Task 5: Validate High-Risk Findings

Review all CONFIRMED removals and ACTIONABLE consolidations before executing.

1. For each CONFIRMED dead code removal:
   - Verify removing it will not break imports in other files
   - Verify no dynamic references (string-based imports, getattr, reflection)
   - If any doubt, reclassify as KEEP
2. For each ACTIONABLE duplication consolidation:
   - Verify the shared helper has a clear single responsibility
   - Verify the extraction does not change behavior
   - If the consolidation is more complex than the duplication, mark as SKIP
3. Create a final action plan listing exactly what will be changed, in what order

**Do NOT** modify any files yet — only validate and plan.

**When done, STOP and output:**
```json
{"status": "CLEAN_TASK_COMPLETE", "summary": "Validated: N removals and M consolidations approved"}
```

---

### Task 6: Execute Approved Changes

Execute all approved removals and consolidations from the validated action plan.

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
4. If any test fails after a change, **revert that specific change** and move on
5. Commit all successful changes with a descriptive message

**When done, STOP and output:**
```json
{"status": "CLEAN_TASK_COMPLETE", "summary": "Executed: N removals, M consolidations, K files modified"}
```

---

### Task 7: Lint Compliance

Run a final lint pass over all working set files to ensure full compliance.

1. Run the project's linter on all source files in the working set
2. Fix any lint errors or warnings introduced by this branch
3. Do NOT fix pre-existing lint issues in files outside the working set
4. If fixes require code changes, run related tests to verify no regressions
5. Commit any lint fixes

This is the **final task** in the clean stage.

**When done, STOP and output:**
```json
{"status": "CLEAN_COMPLETE", "summary": "Lint pass complete: N issues fixed, all clean"}
```

---

## Rules

- Work ONLY on files in the working set (`{working_set_scope}`) — do not clean code outside the branch's changes
- Never remove code that is referenced from outside the working set unless you are certain the reference is also dead
- Always verify removals with Grep before executing
- Always run tests after modifications — revert if tests fail
- Commit changes in Task 6 and Task 7 — do not leave uncommitted work between tasks

**Do NOT:**
- Modify files outside the working set
- Remove code you are not confident is dead — when in doubt, keep it
- Add new features or refactor working code that is not dead or duplicated
- Skip the investigation step (Task 4) for SUSPECT findings
- Combine multiple tasks into one iteration — complete exactly one task, then STOP
