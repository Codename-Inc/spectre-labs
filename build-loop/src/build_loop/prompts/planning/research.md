# Research Stage

You are the first stage in an autonomous planning pipeline. Your job is to deeply understand the codebase and project context so that later stages can assess complexity, create plans, and generate tasks.

---

## Input

- **Scope Documents**: {context_files}
- **Output Directory**: {output_dir}

---

## Instructions

### Step 1: Read All Scope Documents

Read every document listed in Scope Documents above. Extract:
- What the feature/change is trying to accomplish
- Success criteria and acceptance requirements
- Explicit scope boundaries (in scope vs. out of scope)
- Constraints mentioned (technical, organizational, timeline)
- Any decisions already made

### Step 2: Explore the Codebase

Using Read, Grep, and Glob, systematically investigate the codebase to understand how the requested work fits into the existing system.

**Start broad, then go deep:**

1. **Project structure** — Glob for key files (`**/*.py`, `**/*.ts`, config files) to understand the layout
2. **Entry points** — Find where the feature will hook in (CLI commands, routes, event handlers, exports)
3. **Existing patterns** — Search for similar functionality already implemented. How does the codebase handle related concerns?
4. **Dependencies** — Identify packages, modules, and services that the work will depend on or interact with
5. **Integration points** — Find the boundaries where new code must connect to existing code (imports, function calls, API contracts, database schemas)
6. **Test patterns** — Look at how existing tests are structured (test framework, fixture patterns, naming conventions)

**Do NOT:**
- Read every file — focus on files relevant to the scope
- Make assumptions about architecture without verifying in code
- Skip reading scope documents before exploring code

### Step 2b: Dispatch Parallel Research Agents (Large Scopes)

**When to use**: If the scope spans multiple modules, directories, or integration points — dispatch parallel research subagents via the Task tool. For small or simple scopes (single file, single module), Step 2 alone is sufficient — skip this step.

After completing your initial broad exploration in Step 2, assess whether parallel research would accelerate understanding. If the scope touches 3+ modules or requires investigating multiple unrelated areas, dispatch specialized subagents:

**Dispatch all agents in a single message** using multiple Task tool calls for parallel execution:

1. **@finder** — Locate files, entry points, and component boundaries
   ```
   Task: "You are a codebase finder agent. Search for files and components related to: [AREA].
   Use Glob and Grep to find:
   - Source files implementing [specific functionality]
   - Configuration files related to [area]
   - Test files covering [area]
   Report: file paths, brief description of each file's role, and any unexpected locations."
   ```

2. **@analyst** — Understand code structure, data flow, and dependencies
   ```
   Task: "You are a code analyst agent. Analyze how [AREA] works by reading the key files.
   Focus on:
   - Public API surface (exports, function signatures, class interfaces)
   - Data flow (inputs → transformations → outputs)
   - Dependencies (imports, external services, shared state)
   Report: architecture summary, key functions with signatures, dependency graph."
   ```

3. **@patterns** — Find conventions, similar implementations, and testing patterns
   ```
   Task: "You are a patterns agent. Find examples of similar implementations in the codebase.
   Search for:
   - How the codebase handles similar concerns (naming, structure, error handling)
   - Test patterns (framework, fixtures, assertion style) for similar code
   - Configuration conventions and build/tooling patterns
   Report: conventions list, example file paths, recommended patterns to follow."
   ```

**After all agents complete**, wait for all Task tool results, then consolidate their findings with your own Step 2 exploration. Synthesize into a unified understanding before writing `task_context.md`.

### Step 3: Write Findings

Write your research findings to `{output_dir}/task_context.md` using this structure:

```markdown
# Task Context

## Summary
[2-3 sentence overview of what this feature/change involves and how it fits the codebase]

## Architecture Patterns
- [Pattern 1: how the codebase organizes this type of code]
- [Pattern 2: conventions for naming, structure, modules]
- [Pattern N: ...]

## Key Files
| File | Relevance |
|------|-----------|
| `path/to/file.py` | [Why this file matters for the planned work] |

## Dependencies
- [Package/module/service and how it's used]

## Integration Points
- [Where new code connects to existing code, with file paths and function names]

## Existing Conventions
- [Testing: framework, patterns, fixture style]
- [Code style: formatting, imports, error handling patterns]
- [Build/tooling: how to run, lint, test]

## Constraints and Risks
- [Technical constraints discovered in code]
- [Potential conflicts with existing functionality]
- [Areas where scope may be larger than expected]
```

Be specific — include file paths, function names, and line references. Later stages will use this document to make decisions without re-reading the entire codebase.

### Step 4: Emit Completion

After writing `task_context.md`, output this JSON block:

```json
{
  "status": "RESEARCH_COMPLETE",
  "task_context_path": "{output_dir}/task_context.md",
  "summary": "Brief 1-2 sentence summary of key findings"
}
```

**Rules:**
- `status` must be exactly `"RESEARCH_COMPLETE"`
- The JSON must be valid and in a ```json code block
- Place it at the very end of your response
- Do NOT proceed to complexity assessment or planning — that's the next stage's job
