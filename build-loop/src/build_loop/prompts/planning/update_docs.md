# Update Docs Stage (Resume)

Incorporate clarification answers and produce the final build manifest.

## Input

- **Clarification Answers**: {clarification_answers}
- **Scope Documents**: {context_files}
- **Plan**: {plan_path}
- **Tasks**: {tasks_path}
- **Output Directory**: {output_dir}

## Instructions

1. Read the clarification answers provided above
2. Update scope documents, plan.md, and tasks.md based on answers
3. Write final manifest to `{output_dir}/build.md` with YAML frontmatter

## Output

Write manifest, then emit:

```json
{
  "status": "PLAN_READY",
  "manifest_path": "{output_dir}/build.md"
}
```
