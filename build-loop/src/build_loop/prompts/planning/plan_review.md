# Plan Review Stage

Review the plan and tasks for over-engineering and unnecessary complexity.

## Input

- **Plan**: {plan_path}
- **Tasks**: {tasks_path}

## Instructions

1. Read `{plan_path}` and `{tasks_path}`
2. Identify over-engineering: unnecessary abstractions, premature optimization, YAGNI violations
3. Apply simplifications by editing files in-place
4. Remove complexity, not requirements

## Output

Edit files in-place, then emit:

```json
{
  "status": "REVIEW_COMPLETE",
  "changes_summary": "Brief description of simplifications made"
}
```
