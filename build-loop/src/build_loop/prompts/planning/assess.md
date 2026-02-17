# Assess Stage

Assess the complexity of the planned work to determine planning depth.

## Input

- **Task Context**: {task_context_path}
- **Scope Documents**: {context_files}

## Instructions

1. Read `{task_context_path}` for codebase research findings
2. Read scope documents for requirements
3. Score complexity across dimensions:
   - Files impacted
   - Pattern match (existing patterns vs new patterns)
   - Components crossed
   - Data model changes
   - Integration points
4. Check hard-stops (new service, auth/PII changes, public API changes)
5. For COMPREHENSIVE: include architecture design section in task_context.md

## Complexity Tiers

- **LIGHT**: Single component, follows existing patterns, <5 files
- **STANDARD**: Multiple components, some new patterns, 5-15 files
- **COMPREHENSIVE**: Cross-cutting, new architecture, >15 files or hard-stops triggered

## Output

```json
{
  "status": "LIGHT|STANDARD|COMPREHENSIVE",
  "depth": "light|standard|comprehensive",
  "tier": "LIGHT|STANDARD|COMPREHENSIVE"
}
```
