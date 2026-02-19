---
name: strategy-scaling-architecture
description: Use when planning product scaling, adding GUI/server layers, multi-model support, adversarial reviews, live steering, telemetry, scheduling/triggers, or node-based pipeline editors to spectre-build
user-invocable: false
---

# Scaling Architecture Review

**Trigger**: scale, GUI, multi-model, model abstraction, event bus, orchestrator, async, adversarial review, live steering, telemetry, industrial, node editor, pipeline editor, multi-tenant, server layer, product scaling, scheduler, cron, triggers, webhooks, pipeline chaining, command center, Prose, OpenProse, semantic completion
**Confidence**: high
**Created**: 2026-02-18
**Updated**: 2026-02-18
**Version**: 2

## Context

In Feb 2026, a full E2E architecture review was conducted across all three pipelines (plan, build, ship) to identify what blocks scaling spectre-build from a CLI tool to an industrial-grade product with GUIs, pluggable models, adversarial reviews, live steering, and telemetry.

Full review document: `docs/architecture-review-2026-02-18.md`

## What's Sound (Don't Rewrite)

The pipeline engine is the best part of the codebase:

- **CompletionStrategy ABC** (`completion.py:29-43`) — clean, extensible, zero coupling. Add new strategies (FunctionCallCompletion, ExitCodeCompletion) without touching existing code.
- **PipelineExecutor** (`executor.py`) — state machine with event system (5 event types) + lifecycle hooks (before/after stage). Already partially event-driven.
- **Stage** (`stage.py`) — model-agnostic. Calls runner via injected interface, evaluates output via injected CompletionStrategy.
- **YAML pipeline loading** (`loader.py:170-205`) — external pipelines with Pydantic validation. Cross-reference validation on transitions.
- **File-mediated stage communication** — artifacts on disk (task_context.md, plan.md, tasks.md, validation_gaps.md) survive crashes, enable debugging, support parallelism.

## What Blocks Scaling (The Three Walls)

### Wall 1: cli.py God Module (1,587 LOC)

Does 6 jobs: arg parsing, session mgmt, context assembly, orchestration, hook wiring, output formatting.

- Routing duplicated 3x (main, resume, manifest) — same `if plan → elif ship → elif validate →` branching
- `save_session()` called from 9 sites with 12 parameters
- Context dicts hardcoded in 4 separate functions (run_default_pipeline, run_plan_pipeline, run_ship_pipeline, run_build_validate_cycle)
- Cannot invoke pipelines from GUI/API — entangled with argparse, `print()`, `sys.exit()`
- God functions: `main()` (281 lines), `run_plan_pipeline()` (168 lines), `run_resume()` (133 lines)

### Wall 2: Print-Coupled Output

`print()` scattered across executor.py, stage.py, agent.py, stream.py, stats.py. No event bus for structured output. The event system (`on_event`) fires lifecycle events but NOT output events. GUI cannot subscribe to "what's happening" without parsing stdout.

### Wall 3: Synchronous Everything

`subprocess.Popen` blocks the entire process. No `async/await` anywhere. No cancellation mid-iteration (only between iterations via `executor.stop()`). No way to inject feedback into a running pipeline. GUI would freeze. Parallel pipelines require process-level parallelism.

## The Phased Path

### Phase 0: Foundation Extraction (2-3 weeks, unblocks everything)

**Extract Orchestrator** from cli.py:
```python
class PipelineOrchestrator:
    def __init__(self, event_bus: EventBus, session_store: SessionStore): ...
    def run_build(self, config: BuildConfig) -> PipelineResult: ...
    def run_plan(self, config: PlanConfig) -> PipelineResult: ...
    def run_ship(self, config: ShipConfig) -> PipelineResult: ...
```
- Config dataclasses in, result objects out (not argparse.Namespace → exit code)
- CLI becomes thin adapter: parse args → config → orchestrate → present

**Add EventBus** (replace print with structured events):
```python
class EventBus:
    def emit(self, event: Event) -> None: ...
    def subscribe(self, event_type: type, handler: Callable) -> None: ...
# Event types: OutputEvent, StageTransitionEvent, ToolCallEvent, TokenUsageEvent, ErrorEvent
```

**Type context dicts** with Pydantic models:
```python
class BuildContext(BaseModel):
    tasks_file_path: str
    progress_file_path: str
    changed_files: str = "No files changed (first run)"
    remediation_tasks_path: str = ""
    # ... all fields documented and validated
```

**Extract routing** into single `route_pipeline()` function (eliminates 3x duplication).

### Phase 1: Model Abstraction (1-2 weeks)

- Async `AgentRunner` protocol with `RunConfig` (timeout, denied_tools, model, temperature, max_tokens) and `IterationResult` (exit_code, output, stderr, usage, tool_calls)
- Stream parser extraction: `ClaudeStreamParser`, `OpenAIStreamParser` behind `StreamParser` protocol
- Model registry: `ModelRegistry.register("openai", OpenAIRunner)`
- Dynamic pricing: YAML config instead of hardcoded `_MODEL_PRICING` dict in stats.py

### Phase 2: Server Layer (2-3 weeks)

- REST + WebSocket API: `POST /api/pipelines/build`, `WS /ws/pipelines/:id`
- `PipelineStateStore` protocol: `FileStateStore` → `SQLiteStateStore` → `PostgresStateStore`
- Async pipeline execution: `asyncio.create_subprocess_exec`, propagate async through Stage → Executor
- `run_serve()` already stubbed in cli.py — this is the path

### Phase 3: Live Steering (1 week)

- Feedback injection: `executor.inject_feedback(text)` → populates `{user_feedback}` context var
- Stage controls: `skip_stage()`, `retry_stage()`, `override_signal()`
- Generalized pause/resume: any stage can emit PAUSED signal (plan pipeline already has this for clarifications)

### Phase 4: Adversarial Reviews (1 week)

- Second code reviewer with different persona/model/temperature
- `ConsensusCompletion` strategy: requires N of M reviewers to agree
- Red team stage between test_verify and test_commit
- Slots into existing pipeline via YAML config or factory extension

### Phase 5: Telemetry (2 weeks)

- Per-stage metrics: `StageMetrics(stage_name, iterations, wall_time, input_tokens, output_tokens, cost, tool_calls, errors)`
- Token efficiency: `tasks_completed / total_tokens * 1_000_000` (tracked per pipeline type, per stage, over time)
- Missing today: per-stage cost, per-task time, tool success/failure rates, cache trends, subagent metrics, error classification

### Phase 6: Node-Based Pipeline Editor (4-6 weeks)

- `StageRegistry` with `StageDefinition(name, description, input_schema, output_schema, completion, default_model, category)`
- Visual builder generates YAML → `load_pipeline()` → execute (no new engine code)
- Prompt template editor with variable preview and version control

## Key Decision: Extract, Don't Rewrite

The PipelineExecutor IS the workflow engine. CompletionStrategy IS the extensibility point. YAML loading IS the customization path. The work is extraction and layering, not replacement. Each phase ships independently. Each preserves backward CLI compat.

## The One Rule Going Forward

**Stop adding to cli.py.** New pipeline modes → factory in `loader.py` + config dataclass. Not another 100-line function in the god module.

## Priority Matrix

| Phase | Effort | Unblocks |
|-------|--------|----------|
| 0: Foundation | 2-3 weeks | Everything |
| 1: Model Abstraction | 1-2 weeks | Multi-model, cost optimization |
| 2: Server Layer | 2-3 weeks | GUI, remote execution |
| 3: Live Steering | 1 week | Human-in-the-loop |
| 4: Adversarial | 1 week | Quality at scale |
| 5: Telemetry | 2 weeks | Optimization, SLAs |
| 6: Node Editor | 4-6 weeks | User customization |

**Critical path** (GUI product): Phase 0 → Phase 2 → Phase 6
**Value path** (operational excellence): Phase 0 → Phase 5 → Phase 1

## Key Files

| File | LOC | Scaling Concern |
|------|-----|-----------------|
| `cli.py` | 1,587 | God module — extract Orchestrator |
| `pipeline/executor.py` | 295 | Sound — replace print with events |
| `pipeline/stage.py` | 252 | Sound — already model-agnostic |
| `pipeline/completion.py` | 223 | Excellent — zero changes needed |
| `pipeline/loader.py` | 705 | Hardcoded factories — expose via YAML |
| `agent.py` | 306 | Model-coupled — extract stream parsers |
| `stats.py` | 263 | Print-coupled — add to_dict(), per-stage metrics |
| `stream.py` | 109 | Claude-specific — extract to parser protocol |
| `hooks.py` | 253 | Stage-name coupled — register hooks declaratively |

## What NOT to Do

1. Don't rewrite in a different language (Python is fine — bottleneck is LLM latency)
2. Don't build a workflow engine from scratch (PipelineExecutor IS the engine)
3. Don't abstract prematurely (hardcoded factories are OK until Phase 6)
4. Don't break the CLI (it's the product today)
