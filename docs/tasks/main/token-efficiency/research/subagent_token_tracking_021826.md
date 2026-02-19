---
date: "2026-02-18T17:15:00-08:00"
git_commit: 38e53f55c820b2be352603777bd46bec6407588a
branch: main
repository: spectre-labs
topic: "Subagent Token Tracking in Plan/Build/Ship Loops"
tags: [research, tokens, subagents, stats, pipeline, cost-tracking]
status: complete
last_updated: "2026-02-18"
last_updated_by: "Researcher (Opus 4.6)"
---

# Research: Subagent Token Tracking in Plan/Build/Ship Loops

**Date**: 2026-02-18
**Git Commit**: `38e53f5`
**Branch**: `main`
**Repository**: spectre-labs

## Research Question

How can we include subagent (Task tool) token counts in our aggregate token tracking for plan, build, and ship pipeline loops? Currently documented as a known gap requiring architectural change.

## Summary

The `result` event from `claude -p --output-format stream-json` contains **three** cost-relevant fields, but we only parse two:

1. **`usage`** (parsed) -- Token breakdown for the **parent session only**. Does NOT include subagent tokens.
2. **`total_cost_usd`** (parsed) -- Authoritative aggregate cost **including all subagent usage**.
3. **`modelUsage`** (NOT parsed) -- Per-model token breakdown that **includes subagent tokens**, broken down by model family (e.g., Opus parent + Haiku subagents).

The simplest high-impact fix: parse `modelUsage` from the result event and aggregate its token counts. This requires ~30 lines of code and closes 80-90% of the tracking gap. For per-subagent attribution, post-session JSONL parsing is the only reliable path.

## Detailed Findings

### 1. Current Token Tracking Architecture

**Entry point**: `agent.py:95-139` -- `ClaudeRunner.run_iteration()` spawns `claude -p --output-format stream-json` as a subprocess.

**Stream parsing**: `stream.py:100-148` -- `process_stream_event()` processes events line-by-line:
- `system` event: captures `model` name (line 90-98)
- `assistant` event: tracks tool calls, accumulates text (line 63-88)
- `result` event: extracts `usage`, `total_cost_usd`, `num_turns` (line 100-148)

**Token accumulation**: `stats.py:142-147` -- `BuildStats.add_usage()` extracts four fields:
- `input_tokens` (includes cache reads)
- `output_tokens`
- `cache_read_input_tokens`
- `cache_creation_input_tokens`

**Cost calculation**: `stats.py:149-169` -- `calculate_cost()` uses model family pricing. Falls back to `total_cost_usd` from result event when calculated cost is zero.

### 2. What the `result` Event Contains

Based on code analysis and web research, the `result` event schema is:

```json
{
  "type": "result",
  "usage": {
    "input_tokens": 125000,
    "output_tokens": 8500,
    "cache_read_input_tokens": 110000,
    "cache_creation_input_tokens": 15000
  },
  "total_cost_usd": 0.0425,
  "num_turns": 12,
  "modelUsage": {
    "claude-opus-4-6-20261201": {
      "inputTokens": 100000,
      "outputTokens": 6000,
      "cacheReadInputTokens": 90000,
      "cacheCreationInputTokens": 12000,
      "costUSD": 0.035
    },
    "claude-haiku-4-5-20251001": {
      "inputTokens": 25000,
      "outputTokens": 2500,
      "cacheReadInputTokens": 20000,
      "cacheCreationInputTokens": 3000,
      "costUSD": 0.0075
    }
  }
}
```

**Critical distinction**:
- `usage` = parent session only (no subagent tokens)
- `total_cost_usd` = authoritative total including subagents
- `modelUsage` = per-model breakdown including subagent models

Our code reads `usage` and `total_cost_usd` but **ignores `modelUsage` entirely**.

### 3. Which Stages Dispatch Subagents

| Stage | Pipeline | Subagent Count | Subagent Work | Token Split |
|-------|----------|---------------|---------------|-------------|
| `validate` | default + ship | 3-8 per run | D!=C!=R reachability tracing, codebase grep | ~80% subagent |
| `clean_investigate` | ship | 2-8 (two waves) | Dead code investigation, git blame, dependency analysis | ~85% subagent |
| `test_execute` | ship | 3-8 per run | Test writing, test running, bug diagnosis | ~90% subagent |
| `build` | default | 0 | Direct task execution | 100% parent |
| `code_review` | default + ship | 0 | Direct file review | 100% parent |
| All other ship stages | ship | 0 | Direct execution | 100% parent |

**Token gap by pipeline mode**:
- **Default pipeline** (build/review/validate): ~10-20% invisible (validate subagents only)
- **Ship pipeline** (8 stages): ~30-40% invisible (validate + clean_investigate + test_execute)
- **Large-scope ship**: ~50-70% invisible (max subagent parallelism)

### 4. External Research: Claude Code Token Reporting

**GitHub issues (all closed as "Not Planned")**:
- [#10164](https://github.com/anthropics/claude-code/issues/10164) -- Show sub-agent token usage in `/context` and Task tool output
- [#13994](https://github.com/anthropics/claude-code/issues/13994) -- Expose per-sub-agent metrics in status line and hooks
- [#10388](https://github.com/anthropics/claude-code/issues/10388) -- Agent Token Usage API for real-time per-agent metrics

**Still open**:
- [#11008](https://github.com/anthropics/claude-code/issues/11008) -- Expose token usage and cost data in hook inputs (9 upvotes, stale)
- [#15677](https://github.com/anthropics/claude-code/issues/15677) -- Expose sub-agent context sizes in statusline API

**Key insight**: Anthropic has not prioritized per-subagent token visibility. The canonical issues were auto-closed. The only workaround documented is parsing `agent-{agentId}.jsonl` transcripts from `~/.claude/projects/`.

**Available mechanisms**:
- `modelUsage` field in result event (per-model, not per-subagent)
- `total_cost_usd` in result event (aggregate, authoritative)
- Post-session JSONL parsing from `~/.claude/projects/` (per-subagent, post-hoc)
- OpenTelemetry export via `CLAUDE_CODE_ENABLE_TELEMETRY=1` (real-time, no per-subagent)

## Architectural Approaches (Ranked)

### Approach A: Parse `modelUsage` from Result Event

**Effort**: Low (~30 lines)
**Impact**: High (closes 80-90% of gap)
**Risk**: Low (additive change, no existing behavior modified)

**Implementation**:
1. In `stream.py:process_stream_event()`, extract `modelUsage` from the result event
2. Add `model_usage: dict[str, dict]` field to `BuildStats`
3. Aggregate token counts from all models in `modelUsage` into existing total fields
4. Store per-model breakdown for dashboard display
5. Update `print_summary()` to show multi-model token split when subagents used different models

**Why it works**: When the parent runs Opus and dispatches Haiku subagents, `modelUsage` will have entries for both. Summing tokens across all models gives the true total.

**Verification needed**: Confirm `modelUsage` is present in `claude -p --output-format stream-json` output (vs only in Agent SDK). Add to existing `[TEMP STATS]` logging to capture it from a real run.

```python
# stream.py addition (sketch)
model_usage = event.get("modelUsage", {})
if stats and model_usage:
    for model_id, model_data in model_usage.items():
        stats.total_input_tokens += model_data.get("inputTokens", 0)
        stats.total_output_tokens += model_data.get("outputTokens", 0)
        stats.total_cache_read_tokens += model_data.get("cacheReadInputTokens", 0)
        stats.total_cache_write_tokens += model_data.get("cacheCreationInputTokens", 0)
```

**IMPORTANT**: If `modelUsage` is present, we should use it INSTEAD of `usage` (not in addition to), since `modelUsage` aggregates across all models including subagents while `usage` only covers the parent.

### Approach B: Prefer `total_cost_usd` Over Calculated Cost

**Effort**: Trivial (~5 lines)
**Impact**: Medium (accurate cost, but no token breakdown)
**Risk**: None

**Implementation**: In `stats.py:print_summary()`, always prefer `total_cost_usd` when available instead of `calculate_cost()`. The result event's cost is authoritative and includes subagent costs.

```python
# stats.py change (sketch)
cost = self.total_cost_usd if self.total_cost_usd > 0 else self.calculate_cost()
```

**Limitation**: Gives accurate cost but no token breakdown for subagent work. Users see correct dollar amount but can't see how many tokens subagents consumed.

### Approach C: Post-Session JSONL Parsing

**Effort**: Medium (~100-150 lines)
**Impact**: High (full per-subagent attribution)
**Risk**: Medium (file system coupling, path discovery)

**Implementation**:
1. After each `ClaudeRunner.run_iteration()` completes, scan `~/.claude/projects/` for new `agent-*.jsonl` files created during the iteration
2. Parse each JSONL for `result` events to extract per-subagent token usage
3. Aggregate into `BuildStats` with per-subagent breakdown
4. Track which JSONL files have been processed to avoid double-counting on resume

**Challenges**:
- JSONL file path discovery (need to match timestamps/session IDs)
- Claude Code may change transcript directory structure between versions
- File I/O overhead between iterations
- Race conditions if subagent JSONL isn't flushed when parent result arrives

**Best for**: Detailed reporting, post-mortem analysis, billing reconciliation

### Approach D: OpenTelemetry Integration

**Effort**: High (~200+ lines + infrastructure)
**Impact**: Medium (real-time monitoring, no per-subagent attribution)
**Risk**: High (external dependency, infrastructure overhead)

**Implementation**:
1. Set `CLAUDE_CODE_ENABLE_TELEMETRY=1` in the subprocess environment
2. Run an OTLP collector (e.g., local file exporter)
3. Parse exported metrics for `claude_code.token.usage` and `claude_code.cost.usage`
4. Integrate into `BuildStats`

**Best for**: Production monitoring, not build-time stats

## Recommended Implementation Path

### Phase 1: Quick Wins (1 session)

1. **Add `modelUsage` logging** to existing `[TEMP STATS]` in `stream.py` to verify the field is present in `claude -p` output
2. **Prefer `total_cost_usd`** over calculated cost in `print_summary()`
3. Run a real build with subagent-dispatching stages to capture actual data

### Phase 2: Parse `modelUsage` (1 session)

1. If `modelUsage` confirmed present, switch from `usage` to `modelUsage` for token extraction
2. Add `model_usage: dict` to `BuildStats` for per-model breakdown
3. Update `to_dict()`/`from_dict()`/`merge()` for persistence
4. Update dashboard to show multi-model split when applicable

### Phase 3: JSONL Post-Processing (future, optional)

1. Only if per-subagent attribution is needed (billing, optimization)
2. Implement post-iteration JSONL scan
3. Add subagent token breakdown to stats persistence

## Code References

| File | Line(s) | Purpose |
|------|---------|---------|
| `build-loop/src/build_loop/stream.py` | 100-148 | Result event parsing (add `modelUsage` here) |
| `build-loop/src/build_loop/stats.py` | 51-69 | BuildStats dataclass (add `model_usage` field) |
| `build-loop/src/build_loop/stats.py` | 142-147 | `add_usage()` (refactor for modelUsage) |
| `build-loop/src/build_loop/stats.py` | 230-308 | `print_summary()` (prefer `total_cost_usd`, show model split) |
| `build-loop/src/build_loop/stats.py` | 71-90 | `to_dict()` (add model_usage serialization) |
| `build-loop/src/build_loop/stats.py` | 93-115 | `from_dict()` (add model_usage deserialization) |
| `build-loop/src/build_loop/stats.py` | 117-140 | `merge()` (add model_usage merge logic) |
| `build-loop/src/build_loop/agent.py` | 63-75 | Tool allowlist (Task is allowed) |
| `build-loop/src/build_loop/agent.py` | 95-139 | `ClaudeRunner.run_iteration()` (subprocess spawn) |
| `build-loop/src/build_loop/prompts/validate.md` | 64-131 | Validate subagent dispatch instructions |
| `build-loop/src/build_loop/prompts/shipping/clean_investigate.md` | 19-73 | Clean investigate subagent dispatch |
| `build-loop/src/build_loop/prompts/shipping/test_execute.md` | 87-154 | Test execute subagent dispatch |

## Architecture Insights

1. **`modelUsage` is the key unlock** -- It's already in the result event, we just don't parse it. This is the lowest-effort, highest-impact change.

2. **Token counting vs cost counting are separate problems** -- `total_cost_usd` gives accurate cost today. `modelUsage` gives accurate token breakdown. `usage` gives neither when subagents are active.

3. **Per-subagent attribution is a luxury** -- For build stats, we need aggregate totals (which `modelUsage` provides). Per-subagent breakdown is only valuable for optimization work, and JSONL parsing handles that as a separate concern.

4. **The gap grows with scope** -- Ship pipeline on a large scope can have 70% invisible tokens. This makes the dashboard misleading for the most expensive runs.

5. **Anthropic won't fix this upstream** -- All related GitHub issues were closed. We need to solve it at the orchestrator level.

## Open Questions

1. **Is `modelUsage` actually present in `claude -p --output-format stream-json` output?** The Agent SDK docs confirm it, but CLI mode may differ. Need to verify via temp logging in a real run with subagent-dispatching stages.

2. **Does `modelUsage` double-count with `usage`?** If both are present, we need to use one OR the other, not both. Need to verify whether `usage` is a subset of or separate from `modelUsage` totals.

3. **What happens when subagents use the same model as the parent?** If all sessions use Opus, `modelUsage` will have one entry. The total will be correct, but we can't distinguish parent vs subagent tokens from `modelUsage` alone.

4. **JSONL file discovery**: How reliably can we find subagent JSONL files? Does Claude Code create them in a predictable location with predictable naming?
