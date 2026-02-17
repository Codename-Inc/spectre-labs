# Create Tasks Stage

Generate a hierarchical task breakdown from the plan and context.

## Input

- **Plan**: {plan_path}
- **Task Context**: {task_context_path}
- **Scope Documents**: {context_files}
- **Output Directory**: {output_dir}

## Instructions

1. Read `{plan_path}` (if it exists — may not exist for LIGHT tier)
2. Read `{task_context_path}` for codebase research findings
3. Read scope documents for requirements
4. Generate hierarchical task breakdown: Phase > Parent Task > Sub-task > Acceptance Criteria
5. Write to `{output_dir}/specs/tasks.md`

## Output

Write tasks to `{output_dir}/specs/tasks.md`, then emit:

```json
{
  "status": "TASKS_COMPLETE",
  "tasks_path": "{output_dir}/specs/tasks.md"
}
```
