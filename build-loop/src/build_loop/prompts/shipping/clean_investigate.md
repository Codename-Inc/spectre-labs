# Ship — Clean Investigate Stage

You are running the **clean_investigate** sub-stage of the ship pipeline. Your job is to deeply investigate SUSPECT findings from the discover stage and validate high-risk removal candidates — using parallel subagents for throughput — so the execute stage has a vetted action plan.

You will complete **one task per iteration**. After each task, STOP and output a completion signal. The outer loop will call you again for the next task.

---

## Context

- **Parent branch**: `{parent_branch}`
- **Working set scope**: `{working_set_scope}`
- **Context files**: {context_files}

---

## Tasks

### Task 1: Dispatch Investigation Subagents

Take all SUSPECT dead code findings and complex duplication patterns from the discover stage and investigate them in parallel using the Task tool.

**Step 1 — Group findings into investigation chunks**:
- Chunk SUSPECT findings by area (module, directory, or logical group)
- Aim for 2-5 groups; each group should have related files
- If fewer than 3 total findings, investigate sequentially without subagents (skip to Step 3)

**Step 2 — Dispatch parallel subagents via Task tool**:
- Dispatch up to 4 investigation subagents in a SINGLE message with multiple Task tool calls
- Each subagent receives the investigation prompt below, filled in with its chunk's details

**Investigation Subagent Prompt Template**:

```
You are investigating recent changes in {area_name} for dead code artifacts.

**Context**: These files were recently modified. Look for artifacts from failed implementation attempts, abandoned branches, or incomplete refactors.

**Files in scope**: {file_list}
**Initial patterns detected**: {patterns_for_area}

**Your task**:
1. Review all files in scope thoroughly
2. For EACH potential issue, verify:
   - Is this code actually unused? (check imports, calls, references across the whole project)
   - Is this a remnant from a failed approach? (check git history if needed)
   - Could this break something if removed? (check dependencies)
3. Categorize each finding:
   - CONFIRMED_SAFE: Confirmed dead code, no dependencies, safe to remove
   - NEEDS_VALIDATION: Likely dead but has dynamic references, reflection, or test-only usage that needs confirmation
   - KEEP: Actually used or unclear — do not remove
4. Document evidence for each finding

**Output**: Respond with a markdown report organized by category (CONFIRMED_SAFE, NEEDS_VALIDATION, KEEP) with evidence for each item.
**Critical**: Be conservative. When in doubt, classify as NEEDS_VALIDATION.
```

**Step 3 — Collect and merge results**:
- Wait for all investigation subagents to complete
- Merge results into a unified findings list grouped by classification

For each duplication finding from the discover stage:
- Verify both copies have identical behavior (not just similar-looking code)
- Check if extracting a helper would create cross-module dependencies
- Mark as ACTIONABLE (safe to consolidate) or SKIP (consolidation too risky)

**Do NOT** modify any files — only investigate and reclassify findings.

**When done, STOP and output:**
```json
{"status": "CLEAN_INVESTIGATE_TASK_COMPLETE", "summary": "Investigation complete: N items CONFIRMED_SAFE, M items NEEDS_VALIDATION, K items KEEP"}
```

---

### Task 2: Validate High-Risk Findings

Review all CONFIRMED_SAFE items that involve high-risk removals and NEEDS_VALIDATION items. Optionally dispatch a second wave of validation subagents for thoroughness.

**Step 1 — Identify high-risk items**:
- Extract CONFIRMED_SAFE items that involve:
  - Function or class deletions
  - File deletions
  - Export removals (public API surface)
- Gather all NEEDS_VALIDATION items

**Step 2 — Dispatch validation subagents** (optional, for larger sets):
- If there are 3+ high-risk items, dispatch parallel validation subagents via Task tool
- Each validation subagent receives one or more related findings to cross-check:

```
You are validating a finding from dead code analysis.

**Original finding**:
{finding_description}
{file_path}:{line_numbers}
{reasoning_from_investigation}

**Your task**:
1. Search the codebase for ANY usage (dynamic imports, string refs, reflection, __getattr__)
2. Check test files for usage
3. Verify the code is actually dead, not just indirectly used
4. Determine: CONFIRMED_SAFE, UNSAFE, or UNCERTAIN

**Output**: Respond with verdict, evidence, and reasoning for each finding.
```

**Step 3 — Consolidate and create action plan**:
- Reconcile investigation and validation results:
  - CONFIRMED_SAFE → approved for removal
  - UNSAFE → document why, exclude from removal
  - UNCERTAIN → mark as KEEP (conservative)
- Create a final action plan listing exactly what will be changed, in what order
- Include ACTIONABLE duplication consolidations in the action plan

**Do NOT** modify any files — only validate and plan.

This is the **final task** in the clean_investigate sub-stage.

**When done, STOP and output:**
```json
{"status": "CLEAN_INVESTIGATE_COMPLETE", "summary": "Validated: N removals and M consolidations approved, K items excluded"}
```

---

## Rules

- Work ONLY on files in the working set (`{working_set_scope}`) — do not investigate code outside the branch's changes
- **Do NOT modify any files** — this is an investigation-only stage; only reclassify findings and create an action plan
- Use the Task tool for parallel subagent dispatch when there are enough findings to warrant it (3+ SUSPECT items)
- Be conservative — when in doubt, classify as NEEDS_VALIDATION or KEEP rather than CONFIRMED_SAFE
- Complete exactly one task per iteration, then STOP — do not combine multiple tasks

**Do NOT:**
- Modify files outside the working set
- Remove or edit any code — execution happens in the next stage
- Skip investigation for SUSPECT findings — each must be verified
- Dispatch more than 4 parallel subagents at once (keep context manageable)
- Combine multiple tasks into one iteration
