---
name: feature-sparks-plugin
description: Use when modifying sparks plugin, debugging hooks, adding knowledge categories, or understanding how knowledge capture works
user-invocable: false
---

# Sparks Plugin Architecture

**Trigger**: sparks, /learn, /find, knowledge, registry
**Confidence**: high
**Created**: 2025-01-18
**Updated**: 2025-01-18
**Version**: 2

## What is Sparks?

Sparks is a **knowledge capture and retrieval system** for Claude Code projects. It solves the problem of context loss between sessions - when you debug something hard, discover a gotcha, or establish a pattern, that knowledge usually dies with the conversation.

Sparks captures durable knowledge as **project-scoped skills** that Claude automatically discovers and loads when relevant. Think of it as building institutional memory for your codebase.

## Why Use It?

| Problem | How Sparks Helps |
|---------|------------------|
| Debugging the same issue twice | Gotchas captured, auto-loaded next time |
| "Why did we do it this way?" | Decisions + rationale preserved |
| New feature, no context | Feature dossiers explain architecture |
| Onboarding (human or AI) | Patterns and procedures documented |
| Knowledge siloed in conversations | Extracted into searchable, loadable skills |

## Use Cases

### 1. Capture Hard-Won Debugging Knowledge
After spending time debugging a tricky issue:
```
/learn the JWT refresh token was failing because...
```
Creates a gotcha that loads automatically when someone hits similar symptoms.

### 2. Document Feature Architecture
After implementing or understanding a feature:
```
/learn how the auth system works
```
Creates a feature dossier with flows, key files, and common tasks.

### 3. Record Architectural Decisions
After making a significant choice:
```
/learn we chose Redis over Postgres for sessions because...
```
Preserves the rationale so future you (or teammates) don't reverse it blindly.

### 4. Find Existing Knowledge
Before diving into unfamiliar code:
```
/find auth
```
Searches registry, loads relevant skills into context before you start.

## User Flows

### Capture Knowledge (`/learn`)
1. User invokes `/learn` with optional topic
2. Learn skill analyzes conversation for capture-worthy knowledge
3. Proposes learning with category, triggers, description
4. On approval: creates skill file + registers in registry + regenerates find skill
5. Confirmation shown to user

### Find Knowledge (`/find` or `sparks-find` skill)
1. User invokes `/find {query}` or Claude loads `sparks-find` skill
2. Registry embedded in skill - no extra file reads
3. Single match → auto-loads skill into context
4. Multiple matches → asks user which to load
5. Knowledge available for current task

### Auto-Apply (SessionStart Hook)
1. Session starts in project with sparks
2. Hook reads registry, counts entries
3. Injects compliance instructions + registry into context
4. Claude checks registry before searching codebase
5. Matching skills loaded via `Skill({skill-name})`

## Technical Design

### Storage Structure (Project-Level)
```
{{project}}/.claude/skills/
├── sparks-find/
│   ├── SKILL.md                      # Find skill (generated, embedded registry)
│   └── references/
│       └── registry.toon             # Registry source of truth
├── {category}-{slug}/                # Each learning = one skill
│   └── SKILL.md
└── ...
```

### Plugin Structure
```
plugins/sparks/
├── skills/
│   ├── learn/
│   │   ├── SKILL.md                  # Capture workflow
│   │   └── references/
│   │       └── find-template.md      # Template for project find skill
│   └── apply/
│       └── SKILL.md                  # Compliance (fallback for non-hook agents)
└── hooks/scripts/
    ├── load-knowledge.py             # SessionStart - injects registry
    └── register_spark.py             # Creates registry + find skill
```

### Registry Format
```
# registry.toon
{skill-name}|{category}|{triggers}|{description}
```

Example:
```
feature-auth-flows|feature|auth, login, JWT|Use when implementing or debugging authentication
gotchas-hook-timeout|gotchas|hook, timeout, silent|Use when hooks fail without error output
```

### Categories
| Category | When to Use |
|----------|-------------|
| feature | End-to-end feature knowledge (flows, architecture, key files) |
| gotchas | Hard-won debugging insights, non-obvious pitfalls |
| patterns | Repeatable solutions used across codebase |
| decisions | Architectural choices + rationale |
| procedures | Multi-step processes (deploy, release, migrate) |
| integration | Third-party APIs, vendor quirks |
| performance | Optimization learnings, benchmarks |
| testing | Test strategies, coverage decisions |
| ux | Design patterns, interaction conventions |
| strategy | Roadmap decisions, prioritization rationale |

### Key Architecture Decisions
1. **Project-scoped find skill** - generated per-project with embedded registry, not plugin-level
2. **Per-skill storage** - each learning is a separate skill file, not inline in registry
3. **`user-invocable: false`** - skills don't clutter /skill list but agent loads via Skill tool
4. **Apply skill retained** - fallback compliance for agents without SessionStart hooks
5. **Registry regenerates find skill** - `register_spark.py` keeps find skill in sync

## Key Files

| File | Purpose |
|------|---------|
| `plugins/sparks/skills/learn/SKILL.md` | Capture workflow - categorize, propose, write, register |
| `plugins/sparks/skills/learn/references/find-template.md` | Template for generating project find skill |
| `plugins/sparks/skills/apply/SKILL.md` | Compliance instructions for non-hook agents |
| `plugins/sparks/hooks/scripts/load-knowledge.py` | SessionStart hook - reads registry, injects context |
| `plugins/sparks/hooks/scripts/register_spark.py` | Creates/updates registry + regenerates find skill |

## Common Tasks

### Adding a New Category
1. Update category table in `plugins/sparks/skills/learn/SKILL.md`
2. Add to apply skill categories list
3. Document when to use it with clear examples

### Debugging Hook Issues
1. Verify registry exists at `.claude/skills/sparks-find/references/registry.toon`
2. Test hook output: `cd /project && python3 plugins/sparks/hooks/scripts/load-knowledge.py`
3. Check for valid JSON output with `systemMessage` and `additionalContext`

### Testing Learn Flow
1. Run `/learn` in project with a topic
2. Verify skill created at `.claude/skills/{category}-{slug}/SKILL.md`
3. Verify registry updated at `.claude/skills/sparks-find/references/registry.toon`
4. Verify find skill regenerated with new entry embedded
