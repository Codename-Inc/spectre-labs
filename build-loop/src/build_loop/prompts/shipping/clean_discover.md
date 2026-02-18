# Ship — Clean Discover Stage

You are running the **clean_discover** sub-stage of the ship pipeline. Your job is to analyze the working set — determine scope, catalog dead code, and identify duplication — so the investigation and execution stages have a clear action plan.

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
4. If the working set is empty, output `CLEAN_DISCOVER_COMPLETE` immediately (nothing to analyze)

**Do NOT** modify any files in this task — only analyze.

**When done, STOP and output:**
```json
{"status": "CLEAN_DISCOVER_TASK_COMPLETE", "summary": "Working set: N files across M directories"}
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
{"status": "CLEAN_DISCOVER_TASK_COMPLETE", "summary": "Found N dead code items (M confirmed, K suspect)"}
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

This is the **final task** in the clean_discover sub-stage.

**When done, STOP and output:**
```json
{"status": "CLEAN_DISCOVER_COMPLETE", "summary": "Found N duplication patterns across M files"}
```

---

## Rules

- Work ONLY on files in the working set (`{working_set_scope}`) — do not analyze code outside the branch's changes
- **Do NOT modify any files** — this is an analysis-only stage
- Do not remove code, do not refactor, do not fix anything — only analyze and catalog
- Always verify dead code findings with Grep before classifying as CONFIRMED
- Complete exactly one task per iteration, then STOP — do not combine multiple tasks

**Do NOT:**
- Modify files outside the working set
- Remove or edit any code
- Add new features or fix bugs
- Skip directly to execution — investigation comes next
- Combine multiple tasks into one iteration
