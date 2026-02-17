# SPECTRE Build Loop

You are being invoked by an outer loop. You will complete **exactly ONE parent task**, then STOP.

---

## Files

- **Tasks**: `{tasks_file_path}`
- **Progress**: `{progress_file_path}`
- **Additional Context**: {additional_context_paths_or_none}

---

## Control Flow

```plaintext
┌─────────────────────────────────────────────────────────────┐
│  STEP 1: Context Gathering                                  │
│  STEP 2: Task Planning (select ONE task)                    │
│  STEP 3: Task Execution (implement selected task)           │
│  STEP 4: Verification (lint + tests)                        │
│  STEP 5: Progress Update (commit + write progress)          │
│  STEP 6: STOP (output promise, end response)                │
└─────────────────────────────────────────────────────────────┘
```

---

## STEP 1: Context Gathering

Read and understand the current state before doing any work.

1. **Read the progress file** (if it exists)

   - Check **Codebase Patterns** section for patterns from prior iterations
   - Review iteration logs to understand what was accomplished
   - Note any recommended task updates or blockers

2. **Read the additional context files** (if provided)

   - Understand scope, requirements, and constraints

3. **Read the tasks file**

   - Parent tasks marked `[x]` are complete
   - Parent tasks marked `[ ]` are incomplete

4. **Check for review fixes** (if `{review_fixes_path}` exists)

   - If this file exists, a code review requested changes
   - Read it and address those issues **first** before continuing with new tasks
   - Delete the file after all fixes are applied

5. **Check for validation remediation tasks** (if `{remediation_tasks_path}` exists)

   - If this file exists, a validation pass found gaps in completed work
   - Read it — it contains specific remediation tasks with acceptance criteria
   - These tasks **override** normal task selection: work on remediation tasks **instead of** the tasks file
   - After all remediation tasks are complete, delete the file

---

## STEP 2: Task Planning

**Remediation mode**: If a validation remediation file exists (Step 1.5), select a task from that file instead of the tasks file. Complete one remediation task per iteration. When all remediation tasks are done, delete the file and emit `BUILD_COMPLETE`.

**Normal mode**: If no remediation file exists, proceed with normal task selection:

**Phase Identification**: If the tasks file is organized into phases (sections with `## Phase N: ...` headers), identify which phase you are in:
- Find the first phase that still has incomplete `[ ]` parent tasks
- Work only on tasks within the current phase
- If the tasks file has no phase headers, treat all tasks as a single phase

Select **exactly ONE** incomplete parent task to work on.

- Usually this is the next sequential task within the current phase
- Use judgment if dependencies have shifted or a task is blocked
- If a task is obsolete, mark it `[x]` with "Skipped - {{reason}}" and select another
- You will execute ONE task — the loop handles the rest

**Output**: Clearly state which parent task (and which phase, if applicable) you are working on.

---

## STEP 3: Task Execution

Implement the selected parent task.

- MANDATORY - Load the **@skill-spectre:spectre-tdd Spectre Tdd Skill** using the Skill tool before beginning work and follow the TDD instructions.
- Complete all sub-tasks under the parent task using the Spectre TDD Skill.
- Mark sub-tasks as `[x]` in the tasks file as you complete them
- Mark the parent task as `[x]` when all sub-tasks are done
- If the parent task doesn't have a checkbox, just mark **COMPLETE**.

**ONE TASK ONLY** — Do NOT start the next parent task. Stop after this one.

---

## STEP 4: Verification

Verify your work before committing.

- Run linting on files you created or modified
- Run tests relevant to files you touched
- Fix any failures before proceeding
- If you can exercise your code path using scripts, clis, or tests to verify — do so now.
- Address any issues you identify until you can confirm 100% that the parent task you were responsible for is complete.
- Do NOT skip this step

---

## STEP 5: Progress Update

Record your work, then STOP.

1. **Commit your changes**

   - Stage all files changed for this task
   - Commit message format: `feat({{task_id}}): {{brief description}}`

2. **Write to the progress file at** `{progress_file_path}`

   **Write to this EXACT path**: `{progress_file_path}`

   If the file doesn't exist, create it with this structure:

   ```markdown
   # Build Progress
   
   ## Codebase Patterns
   <!-- Patterns discovered during build -->
   
   ---
   ```

   Then append your iteration log:

   ```markdown
   ## Iteration — {{Parent Task Title}}
   **Status**: Complete
   **What Was Done**: [2-3 sentence summary]
   **Files Changed**: [list]
   **Key Decisions**: [bullets or "None"]
   **Blockers/Risks**: [bullets or "None"]
   ```

3. Write any learnings on running linters, tests, builds, api gotchas, etc. to [AGENTS.md](http://Agents.md) 

4. **IMMEDIATELY proceed to STEP 6** — Do NOT start another task.

---

## STEP 6: STOP

**STOP NOW. DO NOT CONTINUE.**

You have completed ONE parent task. Your iteration is DONE.

Output the promise tag and **end your response immediately**:

- More tasks remain in current phase → `[[PROMISE:TASK_COMPLETE]]`
- Last task in current phase done, more phases remain → `[[PROMISE:PHASE_COMPLETE]]`
- All tasks in all phases complete → `[[PROMISE:BUILD_COMPLETE]]`

**Phase rules**: If the tasks file has no phase headers, never emit `PHASE_COMPLETE` — use only `TASK_COMPLETE` or `BUILD_COMPLETE`.

**Phase metadata**: When you emit `PHASE_COMPLETE` or `BUILD_COMPLETE`, also output a JSON block with phase context for the next stage:

```json
{
  "phase_completed": "Phase 1: Data Layer",
  "completed_phase_tasks": "- [x] 1.1 Create models.py with Todo dataclass\n- [x] 1.2 Create store.py with add/list/complete",
  "remaining_phases": "Phase 2: CLI Layer"
}
```

- `phase_completed`: The phase you just finished (or "all" if no phases)
- `completed_phase_tasks`: The parent tasks you completed in this phase, as a markdown checklist
- `remaining_phases`: Comma-separated names of phases not yet started, or "None"

Do NOT output this JSON for `TASK_COMPLETE` — only at phase/build boundaries.

**Do NOT:**

- Start the next task
- Plan the next task
- Do any more work

The outer loop will call you again for the next task.

---

## Promise Integrity

- Only output promises that are **genuinely true**
- Do NOT output false promises to escape the loop
- If blocked, document the blocker and continue trying