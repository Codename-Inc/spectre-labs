# Research Stage

Read the scope documents and explore the codebase to gather context for planning.

## Input

- **Scope Documents**: {context_files}
- **Output Directory**: {output_dir}

## Instructions

1. Read all scope documents listed above
2. Explore the codebase using Read, Grep, and Glob to understand architecture, patterns, and dependencies
3. Write findings to `{output_dir}/task_context.md` with:
   - Architecture patterns discovered
   - Key dependencies and integration points
   - Relevant existing code and modules
   - Constraints and risks identified

## Output

Write your findings to `{output_dir}/task_context.md`, then emit:

```json
{
  "status": "RESEARCH_COMPLETE",
  "task_context_path": "{output_dir}/task_context.md"
}
```
