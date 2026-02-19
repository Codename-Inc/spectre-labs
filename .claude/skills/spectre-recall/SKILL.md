---
name: spectre-recall
description: Use when user wants to search for existing knowledge, recall a specific learning, or discover what knowledge is available.
---

# Recall Knowledge

Search and load relevant knowledge from the project's spectre learnings into your context.

## Registry

```
# SPECTRE Knowledge Registry
# Format: skill-name|category|triggers|description

feature-build-loop|feature|build loop, spectre-build, build iteration, validation cycle, promise tags, build stats, build dashboard, token tracking, code review, phase awareness, git scope, hooks|Use when modifying build loop code, debugging stats/token tracking, adding CLI features, changing iteration prompts, or understanding how spectre-build works end-to-end
feature-plan-pipeline|feature|plan pipeline, --plan, --scope-name, planning loop, plan stages, clarifications, plan resume, scope to manifest, scope isolation, scope slug, run_plan_pipeline, create_plan_pipeline|Use when modifying the planning pipeline, debugging plan stages, changing clarification flow, scope isolation, or understanding how spectre-build --plan works end-to-end
feature-ship-pipeline|feature|ship pipeline, --ship, ship loop, clean stage, test stage, rebase stage, land branch, run_ship_pipeline, create_ship_pipeline, ship hooks, notify_ship_complete, clean_discover, clean_investigate, clean_execute, test_plan, test_execute, test_verify, test_commit, sub-stage, subagent dispatch|Use when modifying the ship pipeline, debugging ship stages, changing clean/test/rebase behavior, or understanding how spectre-build --ship works end-to-end
strategy-scaling-architecture|strategy|scale, GUI, multi-model, model abstraction, event bus, orchestrator, async, adversarial review, live steering, telemetry, industrial, node editor, pipeline editor, multi-tenant, server layer, product scaling|Use when planning product scaling, adding GUI/server layers, multi-model support, adversarial reviews, live steering, telemetry, or node-based pipeline editors to spectre-build
```

## How to Use

1. **Scan registry above** — match triggers/description against your current task
2. **Load matching skills**: `Skill({skill-name})`
3. **Apply knowledge** — use it to guide your approach

## Search Commands

- `/recall {query}` — search registry for matches
- `/recall` — show all available knowledge by category

## Workflow

**Single match** → Load automatically via `Skill({skill-name})`

**Multiple matches** → List options, ask user which to load

**No matches** → Suggest `/learn` to capture new knowledge
