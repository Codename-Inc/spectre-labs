# Post-Build Validation

You are running as a post-build validation step after a build loop completed. Validate the implementation against the requirements.

## Context Documents

{arguments}

## Core Validation Principle

> **"Definition ≠ Connection ≠ Reachability"**

Three levels of implementation completeness:
1. **Defined**: Code exists in a file
2. **Connected**: Code is imported/called by other code
3. **Reachable**: A user action can trigger the code path

Validation must verify all three levels. A feature with Level 1 but not Level 2 or 3 is NOT complete—it's dead code that happens to match the requirement description.

When verifying any implementation:
- Don't stop at "function X exists in file Y"
- Continue to "function X is called by Z at file:line"
- Continue to "Z is triggered when user does W"

## Step (1/4) - Gather Validation Inputs

- **Action** — ReadScopeDocs: Read provided documents completely (no limits).

  - Extract all requirements, acceptance criteria, deliverables
  - Document scope boundaries (in-scope / out-of-scope)
  - Note constraints and success metrics

- **Action** — ChunkIntoValidationAreas: Break scope into discrete validation areas.

  - **From tasks.md**: Each parent task (e.g., \[1.1\], \[1.2\]) = one validation area
  - **From scope.md**: Each "In Scope" item = one validation area
  - Aim for 3-8 validation areas (merge small items, split large ones)

- **Action** — CreateValidationManifest: Document chunks before dispatch.

  ```plaintext
  Validation Areas:
  1. {Area Name} — {What to validate}
     - Source: {requirement text from scope doc}
     - Expected: {what should exist}
  2. ...
  ```

## Step (2/4) - Dispatch Parallel Validation Agents

**CRITICAL**: Dispatch ALL validation agents in parallel in a SINGLE message with multiple Task tool calls. Do NOT dispatch sequentially.

- **Action** — DispatchValidators: Launch one analyst subagent per validation area IN PARALLEL.

  **Subagent Prompt Template**:

  ```plaintext
  You are validating scope delivery for ONE specific area.

  ## Context Documents
  - Tasks: {tasks_file_path}
  - Branch: {branch_name}

  ## Your Validation Area
  **Area**: {area_name}
  **Source Requirement**: {exact text from scope/tasks doc}
  **Expected Deliverables**: {what should exist}

  ## Your Task
  1. Investigate YOUR SPECIFIC AREA only
  2. For each requirement, determine:
     - **Status**: ✅ Delivered | ⚠️ Partial | 🔌 Dead Code | ❌ Missing
       - ✅ **Delivered**: Defined AND connected AND reachable from user action
       - ⚠️ **Partial**: Code exists but has broken/missing connections
       - 🔌 **Dead Code**: Code exists but has zero usage sites
       - ❌ **Missing**: Code does not exist
     - **Evidence**: Must include BOTH:
       1. Definition site: `file:line` where code is defined
       2. Usage site: `file:line` where code is called/rendered
       - If you can only cite definition without usage → status is ⚠️ or 🔌
     - **Gap**: What's missing (if any)

  3. **CRITICAL - Reachability Verification**:
     - Trace the COMPLETE chain from user action to implementation:
       - Entry point: What user action triggers this? (click, route, event)
       - Call chain: How does execution flow to the implementation?
       - Terminal point: What side effect/UI change occurs?
     - A broken link at ANY point = ⚠️ NOT FULLY DELIVERED
     - For every function/component, grep for USAGE not just DEFINITION:
       - Functions: Search for `functionName(` to find invocations
       - Components: Search for `<ComponentName` to find render sites
       - Hooks: Search for `useHookName(` to find consumers
       - Props: Search for `propName={` to find where passed
     - Zero usage sites = 🔌 Dead Code

  4. Check for scope creep: anything beyond the requirement

  ## Output Format

  AREA: {area_name}
  STATUS: {overall: Delivered | Partial | Dead Code | Missing}

  REQUIREMENTS:
  - [REQ-1] {requirement}
    Status: {✅|⚠️|🔌|❌}
    Definition: {file:line where defined}
    Usage: {file:line where called/rendered, or "NONE FOUND"}
    Gap: {what's missing}
    Remediation: {specific fix}

  SCOPE CREEP: {any features beyond scope}
  SUMMARY: {1-2 sentences}
  ```

- **Wait** — All validation agents complete

## Step (3/4) - Consolidate & Create Gap Remediation Tasks

- **Action** — ConsolidateFindings: Merge all subagent outputs.

  - Aggregate status across all areas
  - Compile gaps by priority (Critical/Medium/Low)
  - Note any scope creep findings

- **Action** — DetermineOutputDir:

  - `branch_name=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo unknown)`
  - `OUT_DIR=docs/tasks/{branch_name}`
  - `mkdir -p "${OUT_DIR}/validation"`

- **Action** — CreateValidationGapsDoc: Generate `{OUT_DIR}/validation/validation_gaps.md`.

  **Document Structure**:

  ```markdown
  # Validation Gaps
  *Generated: {timestamp}*

  ## Summary
  - **Overall Status**: {Complete | Needs Work | Significant Gaps}
  - **Requirements**: {X of Y} delivered
  - **Gaps Found**: {count} requiring remediation

  ---

  ## Gap Remediation Tasks

  ### 📦 Phase 1: Critical Gaps

  #### 📋 [1.1] {Gap Title}
  **Requirement**: {original requirement text}
  **Current State**: {what exists now}
  **Gap**: {what's missing}

  - [ ] **1.1.1** {Specific action}
    - [ ] {Verifiable outcome 1}
    - [ ] {Verifiable outcome 2}

  ### 📦 Phase 2: Medium Priority Gaps
  ...

  ---

  ## Validation Coverage
  | Area | Status | Definition | Usage |
  |------|--------|------------|-------|
  | {area 1} | ✅ | {file:line} | {file:line} |
  | {area 2} | ⚠️ | {file:line} | NONE |
  ```

## Step (4/4) - Present Results & Signal Completion

- **Action** — PresentResults: Show validation summary.

  > ## Validation Complete
  > **Status**: {Complete | Needs Work | Significant Gaps}
  >
  > - {X of Y} requirements delivered
  > - {N} gaps requiring remediation
  >
  > **Gap Remediation Doc**: `{OUT_DIR}/validation/validation_gaps.md`
  >
  > {1-2 sentence summary of key findings}

- **Action** — OutputSignal: **CRITICAL** - Output exactly ONE of these signals at the end of your response:

  **If ALL requirements are verified (no gaps):**
  ```
  [[VALIDATION:COMPLETE]]
  ```

  **If gaps were found requiring remediation:**
  ```
  [[VALIDATION:GAPS_FOUND]]
  ```

  The outer build loop uses this signal to determine next steps:
  - `COMPLETE` → Feature is done, build loop ends
  - `GAPS_FOUND` → Another build cycle will run using `validation_gaps.md` as the new tasks file
