# Requirements Validation Stage

Cross-reference scope documents against plan and tasks for coverage gaps.

## Input

- **Scope Documents**: {context_files}
- **Plan**: {plan_path}
- **Tasks**: {tasks_path}
- **Output Directory**: {output_dir}

## Instructions

1. Read all scope documents
2. Read `{plan_path}` and `{tasks_path}`
3. For each requirement in scope: verify it has corresponding task coverage
4. If all requirements covered:
   - Write manifest to `{output_dir}/build.md` with YAML frontmatter
   - Emit PLAN_VALIDATED
5. If gaps found:
   - Write clarification questions to `{output_dir}/clarifications/scope_clarifications.md`
   - Emit CLARIFICATIONS_NEEDED

## Output (validated)

```json
{
  "status": "PLAN_VALIDATED",
  "manifest_path": "{output_dir}/build.md"
}
```

## Output (gaps found)

```json
{
  "status": "CLARIFICATIONS_NEEDED",
  "clarifications_path": "{output_dir}/clarifications/scope_clarifications.md"
}
```
