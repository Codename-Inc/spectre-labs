# Create Plan Stage

Generate an implementation plan from the research context and scope documents.

## Input

- **Task Context**: {task_context_path}
- **Scope Documents**: {context_files}
- **Depth**: {depth}
- **Output Directory**: {output_dir}

## Instructions

1. Read `{task_context_path}` for codebase research findings
2. Read scope documents for requirements
3. Write plan to `{output_dir}/specs/plan.md` with:
   - Overview and desired end state
   - Technical approach
   - Critical files for implementation
   - Section depth based on `{depth}` (standard vs comprehensive)

## Output

Write plan to `{output_dir}/specs/plan.md`, then emit:

```json
{
  "status": "PLAN_COMPLETE",
  "plan_path": "{output_dir}/specs/plan.md"
}
```
