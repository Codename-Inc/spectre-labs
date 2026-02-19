# SPECTRE North Star Architecture

**The Autonomous Software Development Platform**

*From CLI tool to Code Factory to Agent Command Center*

---

## Vision

SPECTRE is a platform for **autonomous software development at industrial scale**. It orchestrates teams of AI agents through composable pipelines — planning features, building code, reviewing quality, testing rigorously, and shipping to production — while humans observe, steer, and intervene from a command center.

Plan, Build, and Ship are just the first three loops. The architecture supports any workflow that can be decomposed into agent-driven stages with completion contracts: compliance audits, data pipeline generation, documentation maintenance, security reviews, infrastructure provisioning. Whatever the domain, the pattern is the same: **define stages, assign agents, observe execution, measure outcomes**.

---

## What SPECTRE Is

A **pipeline execution platform** where:

- A **pipeline** is a directed graph of stages with typed inputs, outputs, and transitions
- A **stage** is a bounded unit of agent work with a completion contract (signals, artifacts)
- A **run** is an observable, steerable, measurable execution of a pipeline
- A **workspace** is a project + its pipelines + its run history + its telemetry
- A **schedule** is a trigger condition that starts a run automatically

The three pipelines today (plan, build, ship) are the first **recipes** — pre-built graphs that ship with the platform. Power users compose their own.

---

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────────────┐
│                         CLIENT LAYER                                 │
│                                                                      │
│   CLI              Agent Command        VS Code         CI/CD        │
│   (spectre-build)  Center (GUI)         Extension       Webhooks     │
│                                                                      │
│   All clients speak the same protocol:                               │
│   REST for commands, WebSocket for streaming, Events for state       │
└────────────────────────────────┬─────────────────────────────────────┘
                                 │
┌────────────────────────────────▼─────────────────────────────────────┐
│                      CONTROL PLANE                                   │
│                                                                      │
│   ┌──────────────┐  ┌──────────────┐  ┌────────────┐  ┌──────────┐ │
│   │ Orchestrator  │  │ Scheduler    │  │ Steering   │  │ Event    │ │
│   │               │  │              │  │ Engine     │  │ Bus      │ │
│   │ config → run  │  │ cron/trigger │  │            │  │          │ │
│   │ result ← run  │  │ queue mgmt   │  │ feedback   │  │ pub/sub  │ │
│   │ no print()    │  │ concurrency  │  │ skip/retry │  │ typed    │ │
│   │ no sys.exit() │  │ rate limits  │  │ pause/stop │  │ filtered │ │
│   └──────┬────────┘  └──────┬───────┘  └─────┬──────┘  └────┬─────┘ │
│          │                  │                 │              │       │
│   ┌──────▼──────────────────▼─────────────────▼──────────────▼─────┐ │
│   │                  Pipeline Executor                              │ │
│   │   stages → transitions → hooks → completion strategies          │ │
│   │   (today's engine — async, event-emitting)                      │ │
│   └──────────────────────────┬──────────────────────────────────────┘ │
└──────────────────────────────┼───────────────────────────────────────┘
                               │
┌──────────────────────────────▼───────────────────────────────────────┐
│                        AGENT LAYER                                   │
│                                                                      │
│   ┌──────────────────────────────────────────────────────────────┐   │
│   │                    Model Registry                             │   │
│   │                                                               │   │
│   │   ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────────┐│   │
│   │   │ Claude   │  │ Claude   │  │ OpenAI   │  │ Local /     ││   │
│   │   │ CLI      │  │ API      │  │ API      │  │ Ollama      ││   │
│   │   │ (today)  │  │          │  │          │  │             ││   │
│   │   └──────────┘  └──────────┘  └──────────┘  └─────────────┘│   │
│   │                                                               │   │
│   │   Per model: Runner + StreamParser + CompletionStrategy       │   │
│   │              + CostProfile + ToolCapabilities                 │   │
│   └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
│   ┌──────────────────────────────────────────────────────────────┐   │
│   │                    Stage Registry                             │   │
│   │                                                               │   │
│   │   Built-in: research, assess, plan, build, code_review,      │   │
│   │             validate, clean_*, test_*, rebase, adversarial    │   │
│   │                                                               │   │
│   │   Custom: user-defined stages with input/output schemas       │   │
│   │                                                               │   │
│   │   Per stage: PromptTemplate + InputSchema + OutputSchema      │   │
│   │              + CompletionStrategy + DefaultModel + Category    │   │
│   └──────────────────────────────────────────────────────────────┘   │
└──────────────────────────────┬───────────────────────────────────────┘
                               │
┌──────────────────────────────▼───────────────────────────────────────┐
│                         DATA LAYER                                   │
│                                                                      │
│   ┌────────────────┐  ┌─────────────────┐  ┌──────────────────────┐ │
│   │ State Store    │  │ Telemetry Store  │  │ Artifact Store       │ │
│   │                │  │                  │  │                      │ │
│   │ sessions       │  │ per-stage        │  │ plans, tasks,        │ │
│   │ run history    │  │ tokens, cost     │  │ reviews, gaps,       │ │
│   │ schedules      │  │ time, errors     │  │ test reports,        │ │
│   │ snapshots      │  │ efficiency       │  │ git diffs            │ │
│   │ queue state    │  │ throughput       │  │                      │ │
│   └────────────────┘  └─────────────────┘  └──────────────────────┘ │
│                                                                      │
│   Interface-based: File → SQLite → Postgres                          │
└──────────────────────────────────────────────────────────────────────┘
```

---

## The Four Layers

### 1. Client Layer — How Humans Connect

Every client is a **thin adapter** that submits configurations and subscribes to events. Zero business logic lives in the client.

| Client | Primary Use | Protocol |
|--------|------------|----------|
| **CLI** (`spectre-build`) | Power users, CI/CD, scripting | stdin/stdout (today), REST+WS (future) |
| **Agent Command Center** (GUI) | Observation, steering, analytics | REST + WebSocket |
| **VS Code Extension** | In-editor pipeline triggers | REST + language server protocol |
| **CI/CD Webhooks** | Automated triggers on git events | REST callbacks |
| **Scheduled Jobs** | Recurring / timer / cron pipelines | Internal (scheduler → orchestrator) |

The CLI remains a first-class client forever. Every feature accessible through the GUI is also accessible through the CLI.

### 2. Control Plane — The Brain

Four components that together manage the lifecycle of pipeline runs:

#### Orchestrator

The extracted core of what cli.py does today — minus the argparse, print statements, and sys.exit calls.

```python
class PipelineOrchestrator:
    def __init__(self, event_bus: EventBus, state_store: StateStore,
                 scheduler: Scheduler, model_registry: ModelRegistry): ...

    async def submit(self, config: PipelineConfig) -> RunHandle: ...
    async def resume(self, run_id: str) -> RunHandle: ...
    async def cancel(self, run_id: str) -> None: ...
    async def get_status(self, run_id: str) -> RunStatus: ...
```

- **Typed configs in, result objects out** — `BuildConfig`, `PlanConfig`, `ShipConfig`, or any `PipelineConfig`
- **No presentation logic** — emits events, doesn't print
- **No CLI coupling** — can be called from HTTP handler, test harness, scheduler, or CLI adapter

#### Scheduler

Pipelines don't just run on-demand. They run on **schedules, triggers, and conditions**.

```python
class Scheduler:
    async def schedule(self, schedule: ScheduleConfig) -> str: ...
    async def cancel_schedule(self, schedule_id: str) -> None: ...
    async def list_schedules(self) -> list[ScheduleSummary]: ...

@dataclass
class ScheduleConfig:
    pipeline: PipelineConfig          # What to run
    trigger: TriggerSpec              # When to run it

# Trigger types
CronTrigger(cron="0 2 * * *")                    # Daily at 2am
IntervalTrigger(every_minutes=30)                  # Every 30 minutes
GitTrigger(event="push", branch="main")            # On git push to main
WebhookTrigger(path="/hooks/deploy")               # On webhook receipt
PipelineCompleteTrigger(pipeline_id="build-*")     # When another pipeline finishes
ManualTrigger()                                    # Human clicks "Run"
CompositeTrigger(all_of=[...])                     # Multiple conditions
```

**Use cases:**

| Schedule | Example |
|----------|---------|
| **Nightly ship** | Every night at 2am, run ship pipeline on feature branches with >5 commits |
| **Post-merge build** | On push to main, run build + validate to verify integration |
| **Recurring cleanup** | Every Friday, run clean pipeline across all active branches |
| **Timer-based retry** | If build fails, retry in 15 minutes (max 3 attempts) |
| **Pipeline chaining** | When plan completes, automatically start build; when build completes, start ship |
| **Watchdog** | Every hour, check test coverage; if below threshold, run test pipeline |

The scheduler maintains a **run queue** with concurrency controls:
- Max concurrent pipelines (per project, per user, globally)
- Priority ordering (manual > triggered > scheduled)
- Rate limiting (max N pipeline starts per hour to control API costs)
- Deduplication (don't start a second build if one is already running on the same branch)

#### Steering Engine

The human-in-the-loop interface for running pipelines.

```python
class SteeringEngine:
    async def inject_feedback(self, run_id: str, text: str) -> None: ...
    async def skip_stage(self, run_id: str, stage: str) -> None: ...
    async def retry_stage(self, run_id: str, stage: str) -> None: ...
    async def override_signal(self, run_id: str, signal: str) -> None: ...
    async def pause(self, run_id: str) -> None: ...
    async def resume(self, run_id: str) -> None: ...
    async def adjust_config(self, run_id: str, changes: dict) -> None: ...
```

Feedback injection works by prepending human text to the next iteration's prompt context. The agent sees it and adjusts. This generalizes the plan pipeline's clarification pause to all pipelines.

`adjust_config` enables mid-run changes: switch the model for the next stage, increase max iterations, change the temperature. The factory floor supervisor adjusting the machinery while it runs.

#### Event Bus

The spine of the entire system. Every meaningful thing that happens becomes a structured, typed event.

```python
class EventBus:
    async def emit(self, event: Event) -> None: ...
    def subscribe(self, event_type: type, handler: Callable) -> Subscription: ...
    def subscribe_filter(self, run_id: str, handler: Callable) -> Subscription: ...

# Core event types
@dataclass
class StageTransitionEvent:
    run_id: str
    from_stage: str | None
    to_stage: str
    signal: str | None
    timestamp: float

@dataclass
class IterationEvent:
    run_id: str
    stage: str
    iteration: int
    max_iterations: int
    timestamp: float

@dataclass
class AgentOutputEvent:
    run_id: str
    stage: str
    text: str
    source: Literal["assistant", "tool_call", "tool_result"]

@dataclass
class TokenUsageEvent:
    run_id: str
    stage: str
    input_tokens: int
    output_tokens: int
    cache_read: int
    cache_write: int
    model: str

@dataclass
class ToolCallEvent:
    run_id: str
    stage: str
    tool_name: str
    tool_input: dict
    success: bool

@dataclass
class PipelineLifecycleEvent:
    run_id: str
    status: Literal["queued", "running", "paused", "completed", "failed", "cancelled"]
    timestamp: float

@dataclass
class ScheduleTriggeredEvent:
    schedule_id: str
    run_id: str
    trigger_type: str
    timestamp: float
```

Subscribers react to events:
- **CLI subscriber**: Prints formatted output to terminal (current behavior)
- **WebSocket subscriber**: Pushes events to connected GUI clients
- **Telemetry subscriber**: Writes metrics to the telemetry store
- **Scheduler subscriber**: Listens for `PipelineLifecycleEvent(completed)` to trigger chained pipelines
- **Alert subscriber**: Sends notifications on failure or threshold breach

### 3. Agent Layer — Who Does the Work

#### Model Registry

Every model is a bundle of capabilities, not just an API endpoint.

```python
@dataclass
class ModelProfile:
    name: str                          # "claude-opus-4-6"
    runner: AgentRunner                # How to invoke it
    parser: StreamParser               # How to read its output
    cost: CostProfile                  # Pricing per token
    capabilities: set[str]             # {"tool_use", "extended_thinking", "vision"}
    max_context: int                   # Token limit
    default_temperature: float         # Recommended temperature
```

**Per-stage model assignment** is the key unlock. Not every stage needs the same model:

| Stage | Recommended Model | Rationale |
|-------|------------------|-----------|
| research | Haiku / Sonnet | Fast, cheap, just reading files |
| assess | Sonnet | Judgment call, moderate complexity |
| create_plan | Opus | Architectural decisions, high stakes |
| build | Opus | Code generation, tool use heavy |
| code_review | Opus (different provider) | Independent perspective |
| adversarial_review | GPT-4o | Cross-provider adversarial check |
| validate | Opus | Correctness verification |
| clean_discover | Sonnet | Pattern scanning |
| test_execute | Sonnet | Test writing, parallelizable |
| rebase | Opus | Git operations, conflict resolution |

**Cost optimization** becomes a configuration decision, not a code change. Route cheap stages to cheap models. Route critical stages to the strongest model available. The pipeline YAML specifies which model each stage uses.

#### Stage Registry

Stages are the atoms of the pipeline. The registry makes them discoverable, composable, and validatable.

```python
@dataclass
class StageDefinition:
    name: str                              # "code_review"
    description: str                       # Human-readable purpose
    category: str                          # "review", "build", "test", "deploy", "custom"
    prompt_template: str                   # Path to .md template
    input_schema: type[BaseModel]          # What context this stage reads
    output_schema: type[BaseModel]         # What artifacts this stage produces
    signals: list[str]                     # Possible completion signals
    completion: CompletionStrategy         # How to detect completion
    default_model: str                     # Recommended model
    default_max_iterations: int            # Recommended iteration limit
    tool_requirements: list[str]           # ["Bash", "Read", "Write", "Task"]
    supports_subagents: bool               # Can dispatch parallel work
```

**Built-in stages** ship with the platform:
- Plan group: research, assess, create_plan, create_tasks, plan_review, req_validate, update_docs
- Build group: build, code_review, validate
- Ship group: clean_discover, clean_investigate, clean_execute, test_plan, test_execute, test_verify, test_commit, rebase
- Quality group: adversarial_review, red_team, security_audit

**Custom stages** follow the same contract. A user creates a prompt template, defines input/output schemas, picks a completion strategy, and registers it. The node editor (GUI) makes this visual.

### 4. Data Layer — What Gets Remembered

#### State Store

Pipeline run state, session persistence, schedule configuration.

```python
class StateStore(Protocol):
    # Run lifecycle
    async def create_run(self, config: PipelineConfig) -> str: ...       # Returns run_id
    async def update_run(self, run_id: str, state: RunState) -> None: ...
    async def get_run(self, run_id: str) -> RunState | None: ...
    async def list_runs(self, filters: RunFilters) -> list[RunSummary]: ...

    # Scheduling
    async def save_schedule(self, schedule: ScheduleConfig) -> str: ...
    async def list_schedules(self) -> list[ScheduleSummary]: ...

    # Snapshots (for pause/resume)
    async def save_snapshot(self, run_id: str, snapshot: PipelineSnapshot) -> None: ...
    async def load_snapshot(self, run_id: str) -> PipelineSnapshot | None: ...
```

Implementations: `FileStateStore` (CLI, single user), `SQLiteStateStore` (local GUI), `PostgresStateStore` (multi-tenant SaaS).

#### Telemetry Store

Per-stage, per-run, per-pipeline metrics. This is what powers the analytics dashboard and cost optimization.

```python
@dataclass
class StageMetrics:
    run_id: str
    stage_name: str
    model: str
    iterations: int
    wall_time_seconds: float
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_write_tokens: int
    cost_usd: float
    tool_calls: dict[str, int]          # tool_name → count
    tool_errors: dict[str, int]         # tool_name → error_count
    subagent_count: int
    subagent_total_tokens: int
    completion_signal: str
    error: str | None

@dataclass
class RunMetrics:
    run_id: str
    pipeline_name: str
    trigger_type: str                   # "manual", "scheduled", "triggered"
    total_stages: int
    completed_stages: int
    total_wall_time: float
    total_tokens: int
    total_cost: float
    token_efficiency: float             # tasks_completed / total_tokens * 1M
    human_interventions: int            # feedback injections + steering actions
    outcome: str                        # "success", "failure", "cancelled", "paused"
    stage_metrics: list[StageMetrics]
```

#### Artifact Store

Plans, tasks, reviews, validation gaps, test reports, git diffs. Today these are files on disk — and that's actually correct for single-user operation. The interface abstracts the storage backend for multi-tenant.

```python
class ArtifactStore(Protocol):
    async def save(self, run_id: str, stage: str, name: str, content: str) -> str: ...
    async def load(self, artifact_id: str) -> str: ...
    async def list_for_run(self, run_id: str) -> list[ArtifactSummary]: ...
```

---

## The Agent Command Center

The GUI is not a dashboard. It's a **command center** for observing and steering a team of agents.

### Main View: Active Runs

```
┌─────────────────────────────────────────────────────────────────────┐
│  SPECTRE Command Center                              joe@codename  │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Active Runs                                                        │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │
│                                                                     │
│  ● auth-feature (build)         ▶ build [iter 3/10]    $0.34  4m   │
│    "Implementing JWT refresh token rotation..."                     │
│    [Feedback] [Skip Stage] [Pause] [Stop]                           │
│                                                                     │
│  ● payments-api (ship)          ▶ test_execute [2/5]   $1.12  18m  │
│    3 subagents writing tests in parallel                            │
│    [Feedback] [Pause] [Stop]                                        │
│                                                                     │
│  ● docs-refresh (plan)          ● paused (clarifications)          │
│    Waiting for scope clarifications → edit file                     │
│    [Resume] [Cancel]                                                │
│                                                                     │
│  Queued                                                             │
│  ┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄ │
│  ○ nightly-clean (scheduled)    starts in 2h 14m                    │
│  ○ api-v2-plan (triggered)      waiting: auth-feature to complete   │
│                                                                     │
│  Recent                                                             │
│  ┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄ │
│  ✓ user-profiles (ship)         completed    $2.18  42m   2h ago   │
│  ✗ search-index (build)         failed       $0.89  12m   5h ago   │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### Run Detail View

Click into a run to see the pipeline graph, live agent output, and stage-level telemetry:

```
┌─────────────────────────────────────────────────────────────────────┐
│  auth-feature / build pipeline                          ▶ Running   │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Pipeline Graph                                                     │
│  ┄┄┄┄┄┄┄┄┄┄┄┄┄┄                                                   │
│  [research ✓] → [assess ✓] → [plan ✓] → [tasks ✓]                 │
│       → [build ▶ iter 3] → [code_review ○] → [validate ○]         │
│                                                                     │
│  ┌─ Live Output ──────────────────────────┬─ Stage Metrics ──────┐ │
│  │                                        │                      │ │
│  │ 💬 Reading auth/jwt_service.py...      │  build (running)     │ │
│  │ 📄 Read: auth/jwt_service.py           │  Iteration: 3/10     │ │
│  │ ✏️  Edit: auth/jwt_service.py:42       │  Tokens: 84K         │ │
│  │ 💬 Adding refresh token rotation       │  Cost: $0.28         │ │
│  │    with configurable TTL...            │  Time: 3m 42s        │ │
│  │ 🔨 Bash: pytest tests/auth/ -x        │  Tools: 12 calls     │ │
│  │ 💬 All tests passing. Committing...    │  Cache: 67%          │ │
│  │ 🔨 Bash: git commit -m "feat..."      │                      │ │
│  │                                        │  Previous:           │ │
│  │                                        │  research: $0.02 12s │ │
│  │                                        │  assess:   $0.01  8s │ │
│  │                                        │  plan:     $0.03 45s │ │
│  │                                        │  tasks:    $0.02 22s │ │
│  └────────────────────────────────────────┴──────────────────────┘ │
│                                                                     │
│  ┌─ Feedback ──────────────────────────────────────────────────┐   │
│  │ > Use refresh tokens with rotation, not sliding expiry.  ⏎  │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  [Skip Stage] [Retry Stage] [Pause] [Stop] [View Artifacts]        │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### Analytics View

```
┌─────────────────────────────────────────────────────────────────────┐
│  Analytics — Last 30 Days                                           │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Pipeline Performance                                               │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │
│                                                                     │
│                Plan        Build       Ship        Total            │
│  Runs          47          89          34          170              │
│  Avg Duration  12m         42m         28m         82m              │
│  Avg Cost      $0.18       $1.24       $0.87       $2.29            │
│  Avg Tokens    89K         412K        287K        788K             │
│  Success Rate  94%         87%         91%         90%              │
│                                                                     │
│  Token Burn by Stage (build pipeline)                               │
│  ┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄                              │
│  build         ████████████████████████████░░░░  68%  280K         │
│  code_review   ████████░░░░░░░░░░░░░░░░░░░░░░░  18%   74K         │
│  validate      █████░░░░░░░░░░░░░░░░░░░░░░░░░░  14%   58K         │
│                                                                     │
│  Efficiency Trend                                                   │
│  ┄┄┄┄┄┄┄┄┄┄┄┄┄┄                                                   │
│  tokens/task:  18,200 → 14,800 → 12,100  (improving ↓)            │
│  cache rate:   42% → 58% → 67%           (improving ↑)            │
│  human steer:  34% → 18% → 8%            (improving ↓)            │
│                                                                     │
│  Cost Attribution                                                   │
│  ┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄                                                  │
│  Opus stages:    $142.80  (78%)                                     │
│  Sonnet stages:   $31.20  (17%)                                     │
│  Haiku stages:     $9.40   (5%)                                     │
│                                                                     │
│  Hotspot: test_execute burns 31% of ship tokens                     │
│  Recommendation: batch P2 tests more aggressively                   │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### Schedule Manager

```
┌─────────────────────────────────────────────────────────────────────┐
│  Schedules                                                          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Active                                                             │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │
│                                                                     │
│  🕐 nightly-clean                                                   │
│     Pipeline: ship (clean stages only)                              │
│     Trigger: cron 0 2 * * * (daily 2am)                            │
│     Scope: all branches with >3 days since last clean               │
│     Last run: 6h ago (success, $0.42)                               │
│     [Edit] [Pause] [Delete]                                         │
│                                                                     │
│  🔗 post-merge-validate                                             │
│     Pipeline: build + validate                                      │
│     Trigger: git push to main                                       │
│     Last run: 2h ago (success, $0.89)                               │
│     [Edit] [Pause] [Delete]                                         │
│                                                                     │
│  ⛓️  plan-then-build                                                │
│     Pipeline: plan → build (chained)                                │
│     Trigger: when plan completes successfully                       │
│     Condition: only if plan produces manifest                       │
│     [Edit] [Pause] [Delete]                                         │
│                                                                     │
│  ⏱️ coverage-watchdog                                               │
│     Pipeline: test (on changed files)                               │
│     Trigger: every 60 minutes                                       │
│     Condition: only if coverage < 80%                               │
│     Rate limit: max 3 runs/day                                      │
│     [Edit] [Pause] [Delete]                                         │
│                                                                     │
│  [+ New Schedule]                                                   │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Pipeline Definition Language

### YAML (Today)

The existing YAML pipeline format continues to work. It's the serialization target for all pipeline definitions.

```yaml
name: build-with-adversarial
start_stage: build
end_signals: [ALL_VALIDATED]

stages:
  build:
    prompt: prompts/build.md
    model: claude-opus-4-6
    max_iterations: 10
    completion:
      type: promise
      signals: [TASK_COMPLETE, PHASE_COMPLETE, BUILD_COMPLETE]
    transitions:
      TASK_COMPLETE: build
      PHASE_COMPLETE: code_review
      BUILD_COMPLETE: code_review

  code_review:
    prompt: prompts/code_review.md
    model: claude-opus-4-6
    completion:
      type: json
      statuses: [APPROVED, CHANGES_REQUESTED]
    transitions:
      APPROVED: adversarial_review
      CHANGES_REQUESTED: build

  adversarial_review:
    prompt: prompts/adversarial_review.md
    model: gpt-4o                      # Different provider for independence
    temperature: 0.7                    # Higher temp for creative attack vectors
    completion:
      type: json
      statuses: [APPROVED, REJECTED]
    transitions:
      APPROVED: validate
      REJECTED: build

  validate:
    prompt: prompts/validate.md
    model: claude-opus-4-6
    completion:
      type: json
      statuses: [ALL_VALIDATED, VALIDATED, GAPS_FOUND]
    transitions:
      VALIDATED: build
      GAPS_FOUND: build
```

### Prose (Future Exploration)

[OpenProse](https://github.com/openprose/prose) is a programming language for AI agent orchestration that runs *inside* an AI session. Its core thesis — "a long-running AI session is a Turing-complete computer" — aligns directly with SPECTRE's architecture.

**Where Prose fits in the SPECTRE stack:**

Prose is not a replacement for the pipeline executor. It's a **higher-level abstraction** that could serve as an alternative pipeline definition language — one that supports semantic completion conditions, natural language control flow, and dynamic agent coordination that YAML cannot express.

**Key Prose concepts that map to SPECTRE:**

| Prose Concept | SPECTRE Equivalent | Gap |
|---------------|-------------------|-----|
| `agent researcher: model: sonnet` | `StageConfig(model="sonnet")` | SPECTRE assigns models per stage, not named agents |
| `session "analyze the codebase"` | `Stage.run_iteration(prompt)` | Prose sessions are SPECTRE iterations |
| `loop until **draft meets standards**` | `CompletionStrategy.evaluate()` | Prose uses semantic evaluation; SPECTRE uses signal detection |
| `parallel { ... }` | Subagent dispatch via Task tool | SPECTRE's parallelism is prompt-driven, not language-level |
| `let results = session "..."` | `context.update(result.artifacts)` | Both flow data between stages |
| State backends (fs, sqlite, postgres) | `StateStore` protocol | Nearly identical progression |

**What Prose could unlock for SPECTRE:**

1. **Semantic completion conditions**: Instead of hardcoded signals (`ALL_VALIDATED`), write `loop until **all tasks pass validation and no critical issues remain**`. The AI evaluates whether the condition is met, not a regex.

2. **Dynamic stage generation**: A Prose program could inspect the codebase and *decide* which stages to run, rather than following a static graph. "If the diff touches API routes, add an API contract test stage."

3. **Natural language pipelines**: Users who aren't comfortable with YAML could define workflows in a more readable format that still compiles to executable pipelines.

4. **Cross-session agent persistence**: Prose supports persistent agents that maintain context across sessions — useful for reviewers who should "remember" past review feedback.

**Integration approach:**

Rather than adopting Prose wholesale, the recommended path is:

1. **Near-term**: Study Prose's semantic evaluation (`**...**`) pattern and prototype a `SemanticCompletion` strategy that uses an LLM to judge whether a stage's output meets a natural-language condition. This slots into the existing CompletionStrategy ABC.

2. **Medium-term**: Add Prose as an alternative pipeline definition format alongside YAML. A `.prose` file compiles to a `PipelineConfig` that the executor runs unchanged.

3. **Long-term**: Evaluate whether Prose's "AI as VM" model can handle complex coordination patterns (adversarial reviews, consensus, dynamic routing) more naturally than the current state machine.

Prose is beta today. The SPECTRE pipeline executor is production-tested. The right move is to take inspiration from Prose's design while keeping the battle-tested executor as the runtime.

---

## Adversarial Quality System

Quality at scale requires **independent perspectives**, not just more iterations of the same reviewer.

### Pattern 1: Cross-Provider Review

```
build (Claude Opus) → code_review (Claude Opus) → adversarial_review (GPT-4o) → validate
```

The adversarial reviewer uses a different model from a different provider. It can't share the builder's blind spots because it has different training data, different biases, different failure modes. It's prompted specifically to challenge:

- "Find edge cases the builder didn't test"
- "Identify assumptions that aren't validated"
- "Look for security vulnerabilities"
- "Challenge architectural decisions — is this the simplest solution?"
- "What happens when this code runs at 10x the expected load?"

### Pattern 2: Parallel Consensus

```
              ┌─ reviewer_1 (Claude Opus) ──┐
build ────────┤                              ├──── consensus → validate
              ├─ reviewer_2 (GPT-4o) ───────┤
              └─ reviewer_3 (Gemini Pro) ────┘
```

Three reviewers run in parallel. A `ConsensusCompletion` strategy requires 2/3 APPROVED. Disagreements generate a structured diff of opinions that gets sent to the human for adjudication via the steering engine.

### Pattern 3: Red Team Stage

A dedicated stage in the ship pipeline that actively tries to break the build:

```
test_verify → red_team → test_commit → rebase
```

The red team agent:
- Generates adversarial inputs for API endpoints
- Tests error handling with unexpected data types
- Verifies that auth boundaries hold under manipulation
- Checks for race conditions in concurrent code
- Validates that error messages don't leak internal details

Red team findings become remediation tasks that loop back to build.

---

## Scheduling & Automation

### Execution Modes

| Mode | Trigger | Example |
|------|---------|---------|
| **On-demand** | Human clicks "Run" or types CLI command | `spectre-build --ship` |
| **Scheduled** | Cron expression | "Run clean every night at 2am" |
| **Interval** | Timer | "Run test coverage check every 30 minutes" |
| **Git-triggered** | Repository event | "Run build on push to feature branches" |
| **Webhook-triggered** | External HTTP call | "Run deploy pipeline when staging passes" |
| **Pipeline-chained** | Another pipeline completes | "Run ship when build succeeds" |
| **Condition-gated** | Periodic check of a condition | "Run test if coverage drops below 80%" |

### Pipeline Chaining

Pipelines can be composed into larger workflows:

```
plan ──(success)──→ build ──(success)──→ ship
                       │
                       └──(failure)──→ notify + retry(15m, max=3)
```

The scheduler treats pipeline completion events as triggers. Combined with condition gates, this enables sophisticated automation:

```python
ScheduleConfig(
    pipeline=ShipConfig(branch="*", context=[]),
    trigger=CompositeTrigger(all_of=[
        PipelineCompleteTrigger(pipeline_name="build", status="success"),
        ConditionTrigger(check="git log --oneline main..HEAD | wc -l > 3"),
    ]),
    rate_limit=RateLimit(max_per_day=2),
)
```

"When a build completes successfully AND the branch has more than 3 commits, start ship — but no more than twice per day."

### Concurrency & Queue Management

```python
@dataclass
class QueueConfig:
    max_concurrent_runs: int = 3           # Global limit
    max_per_project: int = 2               # Per-project limit
    max_per_branch: int = 1                # Per-branch limit (prevent duplicate runs)
    priority_order: list[str] = field(
        default_factory=lambda: ["manual", "triggered", "scheduled"]
    )
    dedup_strategy: str = "cancel_older"   # or "skip_newer" or "queue"
```

When the queue is full:
- Manual runs get priority (human is waiting)
- Triggered runs queue behind manual
- Scheduled runs queue behind triggered
- If a duplicate run is detected (same pipeline, same branch), the older one is cancelled

---

## Beyond Software Development

Plan, Build, and Ship are the first three recipes. The platform supports any workflow that decomposes into agent-driven stages.

### Example: Documentation Pipeline

```yaml
name: docs-refresh
stages:
  scan:
    prompt: "Find all public functions without docstrings"
    model: haiku
    transitions: { SCAN_COMPLETE: generate }
  generate:
    prompt: "Generate docstrings for undocumented functions"
    model: sonnet
    transitions: { GENERATE_COMPLETE: review }
  review:
    prompt: "Review generated docs for accuracy and completeness"
    model: opus
    transitions: { APPROVED: commit, CHANGES_REQUESTED: generate }
  commit:
    prompt: "Commit documentation changes"
    max_iterations: 1
```

### Example: Security Audit Pipeline

```yaml
name: security-audit
stages:
  dependency_scan:
    prompt: "Audit all dependencies for known CVEs"
    model: sonnet
  code_scan:
    prompt: "Scan codebase for OWASP Top 10 vulnerabilities"
    model: opus
  report:
    prompt: "Generate security audit report with severity ratings"
    model: opus
```

### Example: Data Pipeline Generation

```yaml
name: data-pipeline
stages:
  schema_analyze:
    prompt: "Analyze source and target schemas, identify transformations"
    model: sonnet
  generate_transforms:
    prompt: "Generate data transformation code"
    model: opus
  generate_tests:
    prompt: "Generate test cases with edge cases and null handling"
    model: sonnet
  validate:
    prompt: "Validate transforms against sample data"
    model: opus
```

The pipeline executor doesn't know or care that these aren't software development workflows. Stages have prompts, models, completion contracts, and transitions. The engine runs them.

---

## Implementation Sequence

### What Exists Today (Foundation)

- PipelineExecutor with state machine, hooks, events (5 types)
- CompletionStrategy ABC with Promise, JSON, Composite implementations
- YAML pipeline loader with Pydantic validation
- Claude and Codex runners (subprocess-based)
- 18 prompt templates across 3 pipeline types
- Session persistence with resume capability
- File-mediated artifact passing between stages
- `run_serve()` stubbed in cli.py

### Phase 0: Extraction (Weeks 1-3)

Extract the Orchestrator, EventBus, and typed contexts from cli.py. This is the critical path — everything else depends on it.

- Orchestrator: config in, result out, no print/no argparse
- EventBus: structured events replace all print() calls
- Typed contexts: Pydantic models for Build/Plan/Ship/Custom
- Router: single function replaces 3x duplicated routing
- SessionStore protocol with FileSessionStore

### Phase 1: Async + Models (Weeks 4-6)

Make the agent runner async and model-pluggable. This unblocks the GUI and multi-model.

- Async AgentRunner protocol
- Stream parser extraction (Claude parser, extensible)
- Model registry with per-stage assignment
- Dynamic pricing config

### Phase 2: Server + Scheduler (Weeks 7-10)

HTTP/WebSocket server driving the orchestrator. Scheduler for automated execution.

- REST API for pipeline CRUD
- WebSocket streaming for real-time events
- Scheduler with cron, interval, git, webhook, chained triggers
- Run queue with concurrency controls
- State store upgrade (SQLite for local)

### Phase 3: Command Center GUI (Weeks 11-14)

The Agent Command Center — observation, steering, analytics.

- Active runs view with live streaming
- Run detail view with pipeline graph + agent output
- Steering controls (feedback, skip, retry, pause)
- Schedule manager UI
- Analytics dashboard

### Phase 4: Quality + Intelligence (Weeks 15-18)

Adversarial reviews, semantic completion, Prose exploration.

- Adversarial review stage (cross-provider)
- ConsensusCompletion strategy
- Red team stage
- SemanticCompletion prototype (Prose-inspired `**...**` evaluation)
- Per-stage telemetry + efficiency scoring

### Phase 5: Platform (Weeks 19-24)

Stage registry, node editor, custom pipelines, multi-tenant.

- Stage registry with input/output schemas
- Visual pipeline builder (generates YAML)
- Prompt template editor with version control
- Custom stage creation workflow
- Multi-tenant state store (Postgres)

---

## Design Principles

1. **The engine is the product.** PipelineExecutor, Stage, CompletionStrategy — this stack is sound. Extend it, don't replace it.

2. **Events are the interface.** Every client (CLI, GUI, CI/CD) consumes the same event stream. No special cases.

3. **Prompts are configuration.** Agent behavior changes by editing markdown templates, not Python code. Users can fork and customize.

4. **Models are interchangeable.** Any stage can run on any model. Cost optimization is a config change, not a code change.

5. **Stages are atoms.** A pipeline is a graph of stages. New capabilities come from new stages and new compositions, not new engines.

6. **Humans steer, agents execute.** The factory floor metaphor: humans are shift supervisors, not assembly line workers. They observe, intervene when needed, and let the system run autonomously otherwise.

7. **Everything is measurable.** If you can't measure it, you can't optimize it. Per-stage telemetry from day one.

8. **CLI is forever.** Every GUI feature has a CLI equivalent. Power users never have to leave the terminal.
