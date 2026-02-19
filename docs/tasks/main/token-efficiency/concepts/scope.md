# Scope: Token-Efficient Build Loop (Phase Owner Pattern)

**Date**: 2026-02-18
**Status**: Draft
**Complexity**: L

---

## The Problem

The current build loop creates a fresh context window for every individual task. Each iteration re-reads the full scope documents, plan, tasks file, and context files before doing any work. For a typical build with 3 phases and 8 tasks each, that's 24 full context loads when only 3 are necessary.

**Impact**: Token costs scale linearly with task count rather than phase count. A 24-task build burns ~21x more input tokens on context reads than necessary (24 reads vs 3 phase-level reads). This makes larger builds increasingly expensive without any quality benefit — the 24th read of the scope doc provides zero new information.

**Current state**: The build pipeline works correctly and produces quality output. This is purely an efficiency optimization on a working system.

---

## Target Users

**Primary**: Build loop operators (Joe + future SPECTRE users) running multi-phase builds where token cost and execution time matter.

**Need**: Reduce input token burn without degrading code quality, while gaining speed through parallelization.

---

## Success Criteria

- Input tokens consumed per build reduced by 60-80% (measured via JSONL/transcript analysis)
- Code quality remains equal or better (validated by existing code review + validate stages)
- Build execution time decreases due to wave-based parallel task dispatch
- Existing pipeline mechanics (promise tags, phase metadata, git hooks) continue to work
- Token tracking accuracy improves (currently suspected to be inaccurate)

---

## User Experience

### Current Flow (per task)
```
Outer loop starts iteration
  → Agent reads ALL context files (scope, plan, tasks, progress, etc.)
  → Agent selects ONE task
  → Agent executes task
  → Agent commits + writes progress
  → Agent emits promise tag
Outer loop repeats
```

### New Flow (per phase)
```
Outer loop starts phase iteration
  → Phase Owner reads ALL context files ONCE
  → Phase Owner identifies tasks in current phase
  → Phase Owner groups tasks into waves (from task doc structure)
  → For each wave:
      → Phase Owner dispatches parallel subagents via Task tool
      → Each subagent receives:
          - Task-specific context (injected by phase owner)
          - Build progress doc path
          - Dynamic instructions (modeled after spectre:execute pattern)
      → Subagents execute tasks, commit independently, append to progress doc
      → Subagents return completion reports
      → Phase Owner aggregates results, adapts remaining tasks if needed
  → Phase Owner updates build progress, marks tasks done
  → Phase Owner emits promise tag (PHASE_COMPLETE / BUILD_COMPLETE)
Outer loop continues to code review / validate
```

### Code Review Flow (unchanged mechanics, reduced context)
```
Code review stage receives:
  - Explicit task descriptions (full text) from phase owner
  - Files touched (from phase owner, not git hooks)
  - NO scope docs, NO build progress, NO full task list
Reviews code quality independently
```

### Validate Flow (phase owner + subagent dispatch)
```
Validate phase owner reads full context ONCE
  → Breaks scope into distinct validation areas
  → Dispatches parallel subagents per area (already the pattern)
  → Each subagent gets only the slice relevant to their validation area
  → Phase owner aggregates, emits validation signals
```

---

## Scope Boundaries

### IN

- **Build stage phase owner pattern**: One persistent agent session per phase in the tasks document (e.g., Phase 1 tasks 1.1-1.4 = one phase owner)
- **Wave-based parallel subagent dispatch**: Phase owner dispatches parallel subagents per wave via the Task tool, all in a single message
- **Surgical context injection**: Phase owner provides each subagent exactly the context it needs — subagents do NOT read scope/plan/tasks docs
- **Subagent dynamic prompts**: Modeled after the spectre:execute pattern — dynamic prompt construction with embedded instructions (not a formal template file)
- **Completion reports**: Subagents return structured reports (implementation insights, files changed, scope signals) — same pattern as spectre:execute's @dev agents
- **Adaptive wave planning**: Phase owner reviews completion reports between waves, adapts remaining tasks if scope signals indicate issues
- **Independent subagent commits**: Each subagent commits its own work with conventional commit format. Parallelization planning ensures no conflicts
- **Subagent progress doc writes**: Subagents append their own iteration logs to the build progress doc
- **Code review context isolation**: Code review receives only explicit task descriptions + files touched from phase owner — no scope docs, no build progress
- **Validate subagent optimization**: Validate phase owner reads full context once, dispatches targeted subagents per validation area (pattern already exists, apply same optimization)
- **Token tracking improvements**: Extract token usage from JSONL/transcripts for accurate tracking including subagent usage
- **Phase owner prompt design**: New prompt or modified existing — to be determined during planning

### OUT

- Plan loop optimization (future consideration, focus on build loop)
- Output token optimization (agent verbosity, prompt size trimming)
- Changes to promise tag / completion signal mechanics
- Changes to the validate subagent dispatch pattern itself (already works correctly)
- Changes to pipeline stage abstractions (PipelineExecutor, Stage, CompletionStrategy)
- New CLI flags or manifest fields
- Changes to session management / resume logic

### MAYBE / FUTURE

- Plan loop subagent dispatch (similar pattern could apply to research and plan generation stages)
- Smarter context partitioning based on task dependency analysis
- Model selection per subagent (e.g., Haiku for simple tasks, Sonnet for complex)
- Subagent retry strategies with escalation

---

## Constraints

- **Backward compatibility**: Legacy build mode (`run_build_validate_cycle`) must continue to work
- **Promise tag contract**: Phase metadata JSON + promise tags must remain compatible with downstream stages
- **Git conflict avoidance**: Wave parallelization depends on task planning ensuring no file conflicts between concurrent subagents
- **Task tool interface**: Subagents are dispatched via Claude Code's Task tool — context injection is limited to the prompt string
- **Build progress doc**: Multiple writers (subagents) may append concurrently — must handle gracefully (append-only pattern minimizes conflicts)

---

## Integration Points

| Touches | Purpose |
|---------|---------|
| `build-loop/src/build_loop/prompts/build.md` | Phase owner prompt (new or modified) |
| `build-loop/src/build_loop/prompts/code_review.md` | Updated to receive explicit task + files instead of git diff |
| `build-loop/src/build_loop/hooks.py` | Code review hook changes — phase owner provides context instead of git diff hook |
| `build-loop/src/build_loop/pipeline/loader.py` | Pipeline factory may need adjustments for phase owner iteration model |
| `build-loop/src/build_loop/pipeline/stage.py` | Stage iteration logic changes (phase owner runs longer, one iteration per phase not per task) |
| `build-loop/src/build_loop/stats.py` | Token tracking improvements — JSONL/transcript parsing |
| `build-loop/src/build_loop/stream.py` | May need changes for subagent token aggregation |

| Avoids | Reason |
|--------|--------|
| `build-loop/src/build_loop/pipeline/executor.py` | Pipeline orchestration stays the same |
| `build-loop/src/build_loop/pipeline/completion.py` | Completion strategies unchanged |
| `build-loop/src/build_loop/cli.py` | No new CLI flags needed |
| `build-loop/src/build_loop/manifest.py` | No new manifest fields |

---

## Key Decisions

| Decision | Rationale |
|----------|-----------|
| Phase owner = one per phase in tasks doc | Phases are the natural grouping — reads context once, manages all tasks in that phase |
| Subagents commit independently | Simpler than coordinated commits; wave planning ensures no conflicts |
| Subagents write to progress doc directly | Minimal conflict risk with append-only pattern; avoids bottleneck at phase owner |
| Code review gets explicit context from phase owner | Intentional isolation — review should judge code quality independently, not be influenced by project scope |
| Dynamic subagent prompts (not template files) | Matches proven spectre:execute pattern; phase owner constructs context-specific prompts |
| Token tracking from JSONL/transcripts | Current stream-level tracking suspected inaccurate; JSONL is authoritative source |
| Model: spectre:execute as reference implementation | Proven wave dispatch, completion reports, adaptive planning — copy the pattern |

---

## Risks

| Risk | Mitigation |
|------|------------|
| Subagent quality drop from reduced context | Phase owner responsibility to inject sufficient context; completion reports surface gaps early |
| Git conflicts from parallel subagents | Task planning must ensure non-overlapping file scopes per wave; phase owner validates before dispatch |
| Token tracking complexity | Start with simple JSONL parsing; iterate on accuracy |
| Phase owner prompt complexity | Start with spectre:execute pattern (proven); iterate based on build results |
| Progress doc write conflicts | Append-only pattern; worst case is interleaved lines, not data loss |

---

## Next Steps

- **Recommended**: `/spectre:plan` — This is a large (L) scope requiring detailed technical planning before implementation. The plan should cover prompt design, pipeline stage changes, hook modifications, and token tracking approach.
- **Alternative**: `/spectre:create_tasks` — If the technical approach feels clear enough, go directly to task breakdown.
