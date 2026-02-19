# SPECTRE Labs Architecture Review

**Date**: 2026-02-18
**Reviewer**: Architecture Review (E2E)
**Scope**: Plan Loop, Build Loop, Ship Loop — full pipeline stack
**Goal**: Identify what works, what breaks at scale, and the refactoring path to a multi-user product with GUIs, pluggable models, live steering, adversarial reviews, scheduling/triggers, and industrial-grade telemetry
**North Star**: See `docs/northstar_architecture.md` for the full product vision

---

## Executive Summary

SPECTRE Build has a **surprisingly good core abstraction** — the PipelineExecutor/Stage/CompletionStrategy stack is clean, extensible, and mostly model-agnostic. The problems are in the **layers around it**: a 1,587-line CLI monolith that mixes orchestration with presentation, `print()` statements that make GUI integration impossible, synchronous subprocess execution that blocks everything, and hardcoded context dicts that live in the wrong layer.

The path to scale is not a rewrite — it's a **progressive extraction**. The pipeline engine is sound. The work is:
1. Extract an Orchestrator from the CLI
2. Replace `print()` with an event bus
3. Make the agent runner async and model-pluggable
4. Build a server layer (you already started with `run_serve`)
5. Add the telemetry/steering/adversarial layers on top

---

## What You've Got

### The Three Pipelines

| Pipeline | Stages | Signal Pattern | Subagent Use | Complexity |
|----------|--------|----------------|--------------|------------|
| **Plan** | 7 stages (research → req_validate) | JsonCompletion, 1 iter/stage | Optional (research) | Medium — linear, one branch (LIGHT skip) |
| **Build** | 3 stages (build → code_review → validate) | Promise + JSON, multi-iter build | Validate dispatches parallel agents | High — cyclic (review→build, validate→build) |
| **Ship** | 8 stages (clean_discover → rebase) | JsonCompletion, multi-iter | clean_investigate + test_execute dispatch parallel | High — linear but with parallel subagent waves |

### Codebase by the Numbers

| Module | LOC | Responsibility | Coupling Level |
|--------|-----|----------------|----------------|
| `cli.py` | 1,587 | Routing + orchestration + session + prompts + paths | **Critical** — god module |
| `pipeline/loader.py` | 705 | Pipeline factories + YAML loader + schemas | Medium — hardcoded factories |
| `agent.py` | 306 | Claude/Codex subprocess runners | Medium — model-specific |
| `pipeline/executor.py` | 295 | State machine orchestration | **Low** — clean abstractions |
| `stats.py` | 263 | Token/cost tracking + dashboard | Medium — print-coupled |
| `hooks.py` | 253 | Inter-stage context injection | Medium — stage-name coupled |
| `pipeline/stage.py` | 252 | Single stage iteration loop | **Low** — clean abstractions |
| `pipeline/completion.py` | 223 | Signal detection strategies | **Excellent** — pure, extensible |
| `stream.py` | 109 | Subprocess JSON event parsing | Medium — Claude-format specific |
| `prompt.py` | 107 | Template loading + substitution | **Low** — simple but limited |
| `manifest.py` | 155 | YAML frontmatter parsing | **Low** — self-contained |
| **18 prompt templates** | ~2,800 | Agent instructions per stage | Medium — tool/convention coupled |

---

## Architectural Strengths

### 1. The Pipeline Engine Is Real

The `PipelineExecutor → Stage → CompletionStrategy` stack is the best part of the codebase. Key properties:

- **CompletionStrategy is a clean ABC** (`completion.py:29-43`). You can add `FunctionCallCompletion`, `ToolUseCompletion`, `ExitCodeCompletion` — or anything else — without touching existing code. The Composite pattern means you can stack them.

- **Stage doesn't know about Claude**. It calls `runner.run_iteration(prompt, stats, denied_tools)` and evaluates output via injected strategy. Model-agnostic at this layer.

- **PipelineExecutor has an event system** (`executor.py:160-166`). Five event types already fire: `StageStartedEvent`, `StageCompletedEvent`, `IterationStartedEvent`, `IterationCompletedEvent`, `PipelineCompletedEvent`. This is the seed of a GUI event bus.

- **Lifecycle hooks are clean callbacks** (`before_stage`, `after_stage`). They catch exceptions and never crash the pipeline. They can mutate the shared context dict freely.

- **YAML pipeline loading works** (`loader.py:170-205`). External pipeline definitions with Pydantic validation. This is the path to user-configurable workflows.

### 2. File-Mediated Stage Communication

Stages communicate via **files on disk** (task_context.md, plan.md, tasks.md, validation_gaps.md) rather than just in-memory state. This is accidentally great for:
- **Debugging**: You can inspect intermediate artifacts
- **Resume**: Files survive process crashes
- **Parallelism**: Subagents can read shared files without locks
- **Auditability**: Every planning artifact is a committed file

### 3. Promise/JSON Dual Signal System

The build pipeline uses `[[PROMISE:SIGNAL]]` tags (regex-detected) while planning/ship use JSON blocks. The `CompositeCompletion` strategy handles both. This flexibility means you can evolve the signal format without breaking existing pipelines.

---

## Architectural Problems (Ranked by Scaling Impact)

### Problem 1: The CLI Monolith

**Impact**: Blocks GUI, blocks API, blocks multi-tenant

`cli.py` at 1,587 lines is doing **six jobs**:
1. Argument parsing (argparse)
2. Interactive prompts (prompt_for_*)
3. Session persistence (save/load/format)
4. Context dict construction (4 separate hardcoded builders)
5. Pipeline orchestration (executor instantiation, hook wiring, stats)
6. Output presentation (notifications, print statements)

**The killer problem**: You cannot invoke `run_default_pipeline()` from a web server because it:
- Calls `reset_progress_file()` (side effect)
- Hardcodes context dict keys inline
- Calls `get_agent()` which checks CLI binary availability
- Prints errors to stderr
- Returns `(exit_code, iterations)` not a result object

**Routing is duplicated 3x**: `main()`, `run_resume()`, and `run_manifest()` all implement the same `if plan → ... elif ship → ... elif validate → ...` branching.

`save_session()` is called **9 times** across the codebase with **12 parameters**. Every new mode or flag requires updating all 9 call sites.

### Problem 2: Print-Coupled Output

**Impact**: Blocks GUI, blocks structured logging, blocks remote execution

`print()` is called directly in:
- `executor.py` (stage transitions, pipeline status, emojis)
- `stage.py` (iteration headers, signal reports)
- `agent.py` (tool calls, text output during streaming)
- `stream.py` (assistant text, tool call formatting)
- `stats.py` (ASCII dashboard)

There is no output abstraction. A GUI cannot subscribe to "what's happening" without capturing stdout, which loses structure. The event system (`on_event`) exists but doesn't cover output — it only fires lifecycle events.

### Problem 3: Synchronous Subprocess Execution

**Impact**: Blocks GUI responsiveness, blocks parallel pipelines, blocks live steering

The entire execution model is:
```
CLI → PipelineExecutor.run() [blocks] → Stage.run() [blocks] → AgentRunner.run_iteration() [blocks] → subprocess.Popen [blocks]
```

No `async/await` anywhere. No cancellation support (except `executor.stop()` which only checks between iterations). No way to inject feedback mid-iteration.

For a GUI: the UI thread would freeze for the entire pipeline run. For parallel pipelines: you'd need process-level parallelism (wasteful). For live steering: impossible without async.

### Problem 4: Model Lock-In

**Impact**: Blocks model switching, blocks cost optimization, blocks multi-provider

Coupling points to Claude specifically:
- `ClaudeRunner` (`agent.py:87-139`): `claude -p --output-format stream-json --allowedTools --disallowedTools`
- `stream.py`: Parses Claude's stream-JSON event format (`assistant`, `system`, `result` event types)
- `stats.py`: Hardcoded pricing for opus/sonnet/haiku
- `prompt.py` templates: Reference Claude-specific tools (`Skill`, `Task`) and skill names (`@skill-spectre:spectre-tdd`)

`CodexRunner` exists but has its own completely different event parsing. No common abstraction for events between the two.

### Problem 5: No Per-Stage Telemetry

**Impact**: Blocks optimization, blocks cost attribution, blocks SLA guarantees

`BuildStats` tracks **aggregate** metrics only:
- Total tokens (not per-stage)
- Total cost (not per-stage)
- Total time (not per-stage)
- Loop counts by type (build/review/validate) but not per-iteration metrics

Missing entirely:
- Tokens per stage
- Cost per stage
- Time per stage
- Tokens per task
- Tool success/failure rates
- Cache hit rate over time
- Token efficiency (tokens per task completed)
- Subagent metrics (when parallel agents dispatch, their tokens aren't tracked)
- Error classification (why did iterations fail?)

### Problem 6: Context Dict Is Untyped and Fragile

**Impact**: Blocks reliable stage communication, blocks validation, blocks schema evolution

The context dict is `dict[str, Any]` — a bag of strings. Problems:
- No schema validation (missing variables → `KeyError` at runtime)
- No documentation of what each stage reads/writes
- Keys are hardcoded strings in hooks.py, cli.py, and loader.py
- No way to know at pipeline-load time if all required variables will be present
- Internal bookkeeping keys (prefixed `_`) mixed with prompt variables

### Problem 7: Hardcoded Pipeline Factories

**Impact**: Blocks user-configurable workflows, blocks node-based editors

`create_default_pipeline()`, `create_ship_pipeline()`, and `create_plan_pipeline()` bake in:
- Exact stage names and count
- Exact transitions
- Exact prompt template paths
- Exact iteration limits
- Exact tool filter lists

`create_plan_pipeline()` takes **zero parameters** — fully hardcoded. Users cannot add, remove, or reorder stages without modifying Python source.

The YAML loader (`load_pipeline()`) can load custom pipelines, but the built-in ones bypass it entirely.

---

## Scaling Roadmap

### Phase 0: Foundation Extraction (Unblocks Everything)

**Goal**: Separate orchestration from presentation so the pipeline engine can be driven by CLI, API, or GUI.

#### 0.1: Extract Orchestrator

Create `orchestrator.py` with a pure orchestration class:

```python
class PipelineOrchestrator:
    def __init__(self, event_bus: EventBus, session_store: SessionStore):
        ...

    def run_build(self, config: BuildConfig) -> PipelineResult:
        ...

    def run_plan(self, config: PlanConfig) -> PipelineResult:
        ...

    def run_ship(self, config: ShipConfig) -> PipelineResult:
        ...
```

Where:
- `BuildConfig`, `PlanConfig`, `ShipConfig` are typed dataclasses (not argparse.Namespace)
- `PipelineResult` carries exit code, stats, artifacts, stage history (not just int)
- `EventBus` replaces `print()` (CLI subscribes and prints, GUI subscribes and renders)
- `SessionStore` is an interface (FileSessionStore for CLI, DBSessionStore for multi-tenant)

CLI becomes a thin adapter: parse args → build config → call orchestrator → format output.

**What this unblocks**: API server, GUI, test harness, multi-tenant

#### 0.2: Event Bus

Replace all `print()` calls with structured events:

```python
class EventBus:
    def emit(self, event: Event) -> None: ...
    def subscribe(self, event_type: type, handler: Callable) -> None: ...

# Event types
OutputEvent(text: str, source: str)          # replaces print()
StageTransitionEvent(from_stage, to_stage, signal)
ToolCallEvent(name, input, output)
TokenUsageEvent(input, output, cache_read, cache_write)
ErrorEvent(stage, iteration, error)
```

The CLI subscriber prints to terminal. The GUI subscriber pushes to WebSocket. The telemetry subscriber writes to a time-series store.

**What this unblocks**: Real-time GUI, structured logging, metrics pipeline

#### 0.3: Typed Context

Replace `dict[str, Any]` with typed Pydantic models per pipeline:

```python
class BuildContext(BaseModel):
    tasks_file_path: str
    progress_file_path: str
    changed_files: str = "No files changed (first run)"
    remediation_tasks_path: str = ""
    # ... all fields documented and validated

class PlanContext(BaseModel):
    context_files: str
    output_dir: str
    depth: Literal["light", "standard", "comprehensive"] = "standard"
    # ...
```

Prompt variable substitution validates against the model at load time, not runtime.

**What this unblocks**: IDE autocomplete on context fields, load-time validation, schema documentation

---

### Phase 1: Model Abstraction (Unblocks Multi-Model)

**Goal**: Run any LLM backend without changing pipeline code.

#### 1.1: Agent Runner Protocol

Formalize the runner interface:

```python
class AgentRunner(Protocol):
    async def run_iteration(
        self,
        prompt: str,
        config: RunConfig,
        on_event: Callable[[StreamEvent], None] | None = None,
    ) -> IterationResult: ...

@dataclass
class RunConfig:
    timeout: int = 300
    denied_tools: list[str] = field(default_factory=list)
    model: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None

@dataclass
class IterationResult:
    exit_code: int
    output: str
    stderr: str
    usage: TokenUsage
    tool_calls: list[ToolCall]
```

Key changes:
- `async def` (enables non-blocking GUI)
- `on_event` callback for streaming (replaces print-during-parse)
- `IterationResult` carries structured data (not just raw strings)
- `RunConfig` is model-agnostic (temperature, max_tokens are universal)

#### 1.2: Stream Parser Abstraction

Extract Claude-specific parsing from `stream.py`:

```python
class StreamParser(Protocol):
    def parse_line(self, line: str) -> StreamEvent | None: ...

class ClaudeStreamParser(StreamParser): ...   # current stream.py logic
class OpenAIStreamParser(StreamParser): ...   # SSE → StreamEvent
class AnthropicAPIParser(StreamParser): ...   # Messages API streaming
```

#### 1.3: Model Registry

```python
class ModelRegistry:
    def register(self, name: str, factory: Callable[..., AgentRunner]): ...
    def get(self, name: str) -> AgentRunner: ...

registry = ModelRegistry()
registry.register("claude-cli", lambda: ClaudeCLIRunner())
registry.register("claude-api", lambda: ClaudeAPIRunner())
registry.register("openai", lambda: OpenAIRunner())
registry.register("local-ollama", lambda: OllamaRunner())
```

#### 1.4: Dynamic Pricing

Move `_MODEL_PRICING` from hardcoded dict to external config:

```yaml
# pricing.yaml
models:
  claude-opus-4-6:
    input: 15.0
    output: 75.0
    cache_read: 1.50
    cache_write: 18.75
  gpt-4o:
    input: 2.50
    output: 10.0
```

**What this unblocks**: GPT-4, Gemini, local models, cost optimization by routing cheap stages to cheaper models

---

### Phase 2: Server Layer + Scheduler (Unblocks GUI + Automation)

**Goal**: HTTP/WebSocket server that drives the orchestrator, streams events to clients. Scheduler for automated, recurring, and trigger-based execution.

#### 2.1: REST + WebSocket API

```
POST /api/pipelines/build    → Start build pipeline
POST /api/pipelines/plan     → Start plan pipeline
POST /api/pipelines/ship     → Start ship pipeline
GET  /api/pipelines/:id      → Get pipeline status
POST /api/pipelines/:id/stop → Stop pipeline
WS   /ws/pipelines/:id       → Stream real-time events
POST /api/sessions/:id/resume → Resume session
POST /api/schedules           → Create scheduled/triggered pipeline
GET  /api/schedules           → List active schedules
DELETE /api/schedules/:id     → Cancel schedule
```

You already have `run_serve()` stubbed in cli.py. This is the path.

#### 2.2: Scheduler

Pipelines don't just run on-demand. They run on schedules, triggers, and conditions:

```python
class Scheduler:
    async def schedule(self, config: ScheduleConfig) -> str: ...
    async def cancel_schedule(self, schedule_id: str) -> None: ...

# Trigger types
CronTrigger(cron="0 2 * * *")                    # Daily at 2am
IntervalTrigger(every_minutes=30)                  # Every 30 minutes
GitTrigger(event="push", branch="main")            # On git push to main
WebhookTrigger(path="/hooks/deploy")               # On webhook receipt
PipelineCompleteTrigger(pipeline_id="build-*")     # When another pipeline finishes
CompositeTrigger(all_of=[...])                     # Multiple conditions
```

With a run queue: concurrency limits, priority ordering (manual > triggered > scheduled), deduplication, and rate limiting. See `docs/northstar_architecture.md` for full scheduler design.

#### 2.3: Pipeline State Store

Replace `.spectre/build-session.json` with a proper state store:

```python
class PipelineStateStore(Protocol):
    def save(self, pipeline_id: str, state: PipelineState) -> None: ...
    def load(self, pipeline_id: str) -> PipelineState | None: ...
    def list(self, filters: dict) -> list[PipelineSummary]: ...

class FileStateStore(PipelineStateStore): ...     # Current behavior
class SQLiteStateStore(PipelineStateStore): ...   # Local GUI
class PostgresStateStore(PipelineStateStore): ... # Multi-tenant SaaS
```

#### 2.4: Async Pipeline Execution

Convert the hot path to async:

```
CLI/API → Orchestrator.run_build() [async] → PipelineExecutor.run() [async] → Stage.run() [async] → AgentRunner.run_iteration() [async]
```

This requires:
- `asyncio.create_subprocess_exec` instead of `subprocess.Popen` in runners
- `async for line in process.stdout` for streaming
- `await` at every level of the call stack
- Task cancellation via `asyncio.Task.cancel()`

**What this unblocks**: Non-blocking GUI, concurrent pipeline execution, live steering, automated scheduling

---

### Phase 3: Live Steering (Unblocks Human-in-the-Loop)

**Goal**: Humans can observe and intervene in running pipelines.

#### 3.1: Feedback Injection

Add a feedback channel to the executor:

```python
class PipelineExecutor:
    async def inject_feedback(self, feedback: str) -> None:
        """Inject user feedback into next iteration's context."""
        self._pending_feedback.append(feedback)

    async def _run_stage_iteration(self, stage, context):
        if self._pending_feedback:
            context["user_feedback"] = "\n".join(self._pending_feedback)
            self._pending_feedback.clear()
        await stage.run_iteration(context, self.stats)
```

Prompts include a `{user_feedback}` variable that's empty by default but populated when humans intervene.

#### 3.2: Stage Skip / Retry / Override

```python
class PipelineExecutor:
    async def skip_stage(self, stage_name: str) -> None: ...
    async def retry_stage(self, stage_name: str) -> None: ...
    async def override_signal(self, signal: str) -> None: ...
```

GUI sends: "Skip code review, I already reviewed it" → executor transitions directly to validate.

#### 3.3: Pause/Resume at Stage Boundaries

The plan pipeline already has pause/resume for clarifications. Generalize this:

```python
class PipelineExecutor:
    async def pause(self) -> PipelineSnapshot: ...
    async def resume(self, snapshot: PipelineSnapshot) -> None: ...
```

Any stage can emit a `PAUSED` signal. The executor serializes state, waits for human input, then resumes.

**What this unblocks**: Human oversight of autonomous pipelines, correction without restart, guided exploration

---

### Phase 4: Adversarial Reviews (Unblocks Quality at Scale)

**Goal**: Independent reviewers that challenge, not just validate.

#### 4.1: Adversarial Code Review Stage

Add a second code review with a different persona:

```yaml
stages:
  adversarial_review:
    prompt: prompts/adversarial_review.md
    completion:
      type: json
      statuses: [APPROVED, REJECTED]
    transitions:
      APPROVED: validate
      REJECTED: build
    model: claude-opus-4-6  # Use strongest model for adversarial
```

The adversarial reviewer is specifically prompted to:
- Find edge cases the builder missed
- Challenge architectural decisions
- Look for security vulnerabilities
- Evaluate test coverage gaps
- Flag performance concerns

Different model, different temperature, different persona.

#### 4.2: Multi-Reviewer Consensus

```python
class ConsensusCompletion(CompletionStrategy):
    """Requires N of M reviewers to agree before proceeding."""
    def __init__(self, strategies: list[CompletionStrategy], threshold: int):
        ...
```

Run 3 parallel reviewers. Require 2/3 APPROVED to proceed. Flag disagreements for human review.

#### 4.3: Red Team Stage

A dedicated stage that tries to break the build:
- Generates adversarial inputs
- Fuzzes API endpoints
- Tests error handling paths
- Verifies security boundaries

This slots into the ship pipeline between test_verify and test_commit.

**What this unblocks**: Confidence at scale, security hardening, catch issues that single-reviewer misses

---

### Phase 5: Telemetry & Observability (Unblocks Industrial Operation)

**Goal**: Know exactly where time and money go, optimize continuously.

#### 5.1: Per-Stage Metrics

```python
@dataclass
class StageMetrics:
    stage_name: str
    iterations: int
    wall_time_seconds: float
    input_tokens: int
    output_tokens: int
    cache_tokens: int
    cost_usd: float
    tool_calls: dict[str, int]
    subagent_count: int
    subagent_tokens: int
    errors: list[str]
```

Collected automatically by wrapping `Stage.run()`. Stored per pipeline run.

#### 5.2: Token Efficiency Score

```
efficiency = tasks_completed / total_tokens * 1_000_000
```

Track this per pipeline type, per stage, over time. Identify which stages burn tokens disproportionately. This is the metric that tells you if your prompt engineering is working.

#### 5.3: Pipeline Analytics Dashboard

Time-series data for:
- Average pipeline duration (plan, build, ship)
- Cost per pipeline run
- Token burn rate by stage
- Cache hit rate trends
- Failure rate by stage (which stages retry most?)
- Subagent utilization (parallel efficiency)
- Human intervention rate (how often does steering happen?)

#### 5.4: Throughput Tracking

For industrial operation:
- Pipelines per hour/day
- Concurrent pipeline capacity
- Queue depth and wait times
- Resource utilization (CPU, memory, API rate limits)

**What this unblocks**: Cost optimization, SLA guarantees, capacity planning, pricing models

---

### Phase 6: Node-Based Pipeline Editor (Unblocks User Customization)

**Goal**: Users drag-and-drop stages to build custom pipelines.

#### 6.1: Stage Registry

```python
class StageRegistry:
    def register(self, name: str, config: StageDefinition): ...
    def list(self) -> list[StageDefinition]: ...
    def get(self, name: str) -> StageDefinition: ...

@dataclass
class StageDefinition:
    name: str
    description: str
    prompt_template: str
    input_schema: type[BaseModel]   # What context this stage reads
    output_schema: type[BaseModel]  # What context this stage writes
    completion: CompletionStrategy
    default_model: str
    category: str  # "build", "review", "test", "deploy", "custom"
```

The registry enables:
- Discovery (GUI shows available stages)
- Validation (check input/output compatibility when connecting stages)
- Documentation (auto-generated from schemas)

#### 6.2: Visual Pipeline Builder

The YAML loader already validates pipelines via Pydantic. A GUI that generates valid YAML → `load_pipeline()` → execute. No new engine code needed.

Stages are nodes. Transitions are edges. Signals are labeled ports. The user connects them visually and the system serializes to YAML.

#### 6.3: Prompt Template Editor

Allow users to:
- Fork built-in prompts
- Edit variables and instructions
- Preview variable substitution with sample data
- Version control prompt changes

This builds on the existing `{variable}` template system.

**What this unblocks**: Customizable workflows, domain-specific pipelines, customer self-service

---

### Phase 7: Pipeline Definition Language (Explore)

**Goal**: Evaluate higher-level pipeline definition formats beyond YAML.

[OpenProse](https://github.com/openprose/prose) is a programming language for AI agent orchestration where "a long-running AI session is a Turing-complete computer." Key concepts that map to SPECTRE:

- Prose `agent` definitions → SPECTRE per-stage model assignment
- Prose `session` calls → SPECTRE `Stage.run_iteration()`
- Prose `loop until **semantic condition**` → SPECTRE `CompletionStrategy.evaluate()`
- Prose parallel blocks → SPECTRE subagent dispatch
- Prose state backends (fs/sqlite/postgres) → SPECTRE `StateStore` protocol

**Near-term action**: Prototype a `SemanticCompletion` strategy inspired by Prose's `**...**` pattern — use an LLM to judge whether a stage's output meets a natural-language condition, rather than matching signals with regex.

**Medium-term**: Add `.prose` as an alternative pipeline definition format that compiles to `PipelineConfig`.

See `docs/northstar_architecture.md` for full Prose integration analysis.

---

## Priority Matrix

| Phase | Effort | Impact | Unblocks |
|-------|--------|--------|----------|
| **0: Foundation** | Medium (2-3 weeks) | Critical | Everything else |
| **1: Model Abstraction** | Medium (1-2 weeks) | High | Multi-model, cost optimization |
| **2: Server + Scheduler** | Medium (3-4 weeks) | High | GUI, automation, remote execution |
| **3: Live Steering** | Low (1 week) | Medium | Human-in-the-loop |
| **4: Adversarial Reviews** | Low (1 week) | Medium | Quality at scale |
| **5: Telemetry** | Medium (2 weeks) | High | Optimization, SLAs |
| **6: Node Editor** | High (4-6 weeks) | High | User customization |
| **7: Prose / DSL** | Low-Medium (explore) | Medium | Semantic completion, richer definitions |

**Critical path**: Phase 0 → Phase 2 → Phase 6 (gets you to a GUI product)
**Value path**: Phase 0 → Phase 5 → Phase 1 (gets you operational excellence first)

---

## Specific Refactoring Recommendations

### Immediate (Do Now)

1. **Stop adding to cli.py**. Every new feature makes extraction harder. If you need a new pipeline mode, add it as a factory in loader.py and a config dataclass, not another 100-line function in cli.py.

2. **Add `to_dict()` to BuildStats** (`stats.py`). One method that returns all stats as a JSON-serializable dict. This is a 10-line change that unblocks structured output immediately.

3. **Type the context dicts**. Create Pydantic models for BuildContext, PlanContext, ShipContext. Use them for validation even if you don't change the execution path yet.

4. **Extract routing into a router function**. The `if plan → elif ship → elif validate →` pattern appears 3 times. Factor it into `route_pipeline(session_or_args) -> PipelineConfig`.

### Near-Term (Next Sprint)

5. **Create EventBus**. Start with a simple `emit(event)` / `subscribe(type, handler)` pattern. Replace `print()` in executor.py and stage.py first (highest value). Leave agent.py for later.

6. **Extract Orchestrator**. Move context dict construction, executor instantiation, and hook wiring out of cli.py into `orchestrator.py`. CLI becomes: parse → config → orchestrate → present.

7. **Abstract session storage**. `SessionStore` protocol with `FileSessionStore` implementation. Same behavior, cleaner interface.

### Medium-Term (Next Month)

8. **Async agent runner**. This is the biggest structural change. Start with `ClaudeRunner` only. Use `asyncio.create_subprocess_exec`. Propagate async up through Stage and Executor.

9. **Stream parser extraction**. Pull Claude-specific JSON parsing into `parsers/claude.py`. Define `StreamParser` protocol. This cleans the path for adding OpenAI/Gemini runners.

10. **Per-stage metrics**. Wrap `Stage.run()` to capture tokens, time, and cost per stage. Store in `PipelineResult.stage_metrics`.

---

## Architecture Target State

```
                    ┌──────────────────────────────────────────┐
                    │              Clients                      │
                    │  CLI  │  Command Center  │  CI/CD  │ VS  │
                    │       │  (GUI)           │ Hooks   │Code │
                    └───┬───┴────────┬─────────┴────┬────┴──┬──┘
                        │            │              │       │
                    ┌───▼────────────▼──────────────▼───────▼──┐
                    │          Event Bus / WebSocket            │
                    │    (structured events, streaming)         │
                    └───┬────────────────────────────────────┬──┘
                        │                                    │
                    ┌───▼──────────────────────────────┐     │
                    │         Control Plane             │     │
                    │                                   │     │
                    │  Orchestrator ─── Scheduler        │     │
                    │  (config→run)    (cron/trigger/    │     │
                    │                   chain/webhook)   │     │
                    │                                   │     │
                    │  Steering Engine ◄────────────────│─────┘
                    │  (feedback/skip/retry/pause)      │  feedback
                    │                                   │
                    └───┬──────────────────────────────┘
                        │
                    ┌───▼──────────────────────────────┐
                    │    PipelineExecutor               │
                    │  (async, cancellable)             │
                    │  stages → transitions → hooks     │
                    └───┬──────────────────────────────┘
                        │
                    ┌───▼──────────────────────────────┐
                    │    Model Registry + Stage Registry│
                    │  ┌─────────┐ ┌──────────┐        │
                    │  │ Claude  │ │ OpenAI   │        │
                    │  └─────────┘ └──────────┘        │
                    │  ┌─────────┐ ┌──────────┐        │
                    │  │ Claude  │ │ Ollama   │        │
                    │  │ API     │ │ Local    │        │
                    │  └─────────┘ └──────────┘        │
                    └──────────────────────────────────┘

              ┌────────────────────────────────────────────┐
              │              Data Layer                     │
              │  State Store  │  Telemetry  │  Artifacts   │
              │  sessions     │  per-stage  │  plans       │
              │  schedules    │  tokens     │  tasks       │
              │  run queue    │  cost/time  │  reviews     │
              │  snapshots    │  efficiency │  diffs       │
              │  (File/SQLite/Postgres)                    │
              └────────────────────────────────────────────┘
```

---

## Risk Assessment

### What Could Go Wrong

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Async conversion breaks existing CLI | Medium | High | Feature flag: `--async` enables new path, sync stays default until stable |
| Multi-model prompts work differently | High | Medium | Prompt validation test suite: run each prompt through each model, verify signal format |
| GUI adds complexity without value | Low | Medium | Ship CLI improvements first, GUI second. CLI users are power users. |
| Over-engineering the abstraction layers | Medium | Medium | Each phase should ship independently. Don't build Phase 6 abstractions in Phase 0. |
| Subagent token tracking remains a gap | High | Medium | Accept the gap short-term. Track at the orchestrator level (total subprocess tokens) not individual subagent level. |
| Scheduler complexity exceeds initial value | Medium | Medium | Start with cron + pipeline-chaining only. Add git triggers and webhooks when server layer is stable. |
| Prose adoption too early | Low | Low | Don't adopt Prose as runtime. Prototype SemanticCompletion strategy only. Keep YAML as primary format. |

### What NOT to Do

1. **Don't rewrite in a different language**. Python is fine. The bottleneck is LLM latency, not Python performance. asyncio solves the concurrency problem.

2. **Don't build a workflow engine from scratch**. The PipelineExecutor IS your workflow engine. Extend it, don't replace it.

3. **Don't abstract prematurely**. The three pipeline factories are hardcoded, and that's OK for now. Extract to YAML when users actually need to customize (Phase 6), not before.

4. **Don't break the CLI**. The CLI is the product today. Every refactoring must keep `spectre-build --tasks foo.md --validate` working exactly as it does now.

---

## Summary

You've built a legitimate pipeline execution engine that happens to be trapped inside a CLI monolith. The core abstractions (Executor, Stage, CompletionStrategy, hooks) are sound and extensible. The work to scale is extraction and layering, not replacement.

The critical path is:
1. **Extract the Orchestrator** (separate what-to-do from how-to-present-it)
2. **Add the Event Bus** (separate execution from output)
3. **Go async** (separate execution from blocking)
4. **Build the server** (separate execution from the terminal)
5. **Layer on telemetry, steering, adversarial reviews, and the node editor**

Each phase ships independently. Each phase preserves backward compatibility. And each phase makes the next one easier.

This is a Code Factory. The foundation is solid. Now we need to industrialize it.

---

## Appendix: North Star Reference

The full product architecture vision — including the Agent Command Center GUI, scheduling/trigger system, Prose language exploration, adversarial quality patterns, and pipeline definition language evolution — is documented in `docs/northstar_architecture.md`.

Key additions beyond this review:
- **Scheduler**: Cron, interval, git-triggered, webhook, pipeline-chained, and condition-gated execution
- **Run Queue**: Concurrency limits, priority ordering, deduplication, rate limiting
- **Agent Command Center**: Active runs view, run detail with live output, analytics dashboard, schedule manager
- **Prose Integration**: Semantic completion conditions (`**...**` pattern), potential alternative pipeline definition language
- **Beyond Software**: Platform supports any agent-driven workflow (docs, security, data pipelines)
