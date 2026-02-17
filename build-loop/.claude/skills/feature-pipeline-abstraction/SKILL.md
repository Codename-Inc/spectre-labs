---
name: feature-pipeline-abstraction
description: Use when working with pipeline stages, completion strategies, build loop orchestration, or the web GUI for spectre-build
user-invocable: false
---

# Pipeline Abstraction System

**Trigger**: pipeline, stages, completion strategy, build loop, web gui, spectre-build serve
**Confidence**: high
**Created**: 2025-02-03
**Updated**: 2026-02-08
**Version**: 2

## What is Pipeline Abstraction?

A generic stage-based pipeline system that replaces the hardcoded build→validate cycle. Pipelines are defined in YAML files with configurable stages, completion strategies, and signal-based transitions. Includes a web GUI for visual pipeline editing and live execution monitoring.

## Why Use It?

| Scenario | Solution |
|----------|----------|
| Need more than build→validate (e.g., code review stage) | Define custom pipeline YAML with additional stages |
| Want visual feedback on pipeline execution | Use `spectre-build serve` for web GUI |
| Need different completion detection per stage | Use Promise (tag-based) or JSON (structured) completion strategies |
| Want loops/retries in pipeline (gaps found → rebuild) | Define transition signals that loop back to earlier stages |

## Architecture

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│ YAML Config │───▶│   Loader    │───▶│ PipelineConfig │
└─────────────┘    │ (Pydantic)  │    └───────┬─────┘
                   └─────────────┘            │
                                              ▼
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   Agent     │◀───│   Stage     │◀───│  Executor   │
│  (Claude)   │    │ (iteration) │    │ (orchestrate)│
└─────────────┘    └─────────────┘    └─────────────┘
                          │
                          ▼
                   ┌─────────────┐
                   │ Completion  │  Promise: [[PROMISE:SIGNAL]]
                   │  Strategy   │  JSON: ```json {"status": "..."}```
                   └─────────────┘
```

## Key Files

| File | Purpose |
|------|---------|
| `src/build_loop/pipeline/completion.py` | CompletionStrategy ABC + PromiseCompletion, JsonCompletion, CompositeCompletion |
| `src/build_loop/pipeline/stage.py` | Stage class - runs iterations, handles transitions |
| `src/build_loop/pipeline/executor.py` | PipelineExecutor - graph traversal, event emission, before/after stage hooks |
| `src/build_loop/pipeline/loader.py` | YAML parsing, Pydantic validation, create_default_pipeline() factory |
| `src/build_loop/server/app.py` | FastAPI app for web GUI |
| `src/build_loop/server/routes/pipelines.py` | Pipeline CRUD REST API + demo pipeline creation |
| `src/build_loop/server/routes/execution.py` | Execution control (start/stop/status) |
| `src/build_loop/server/routes/ws.py` | WebSocket for live event streaming |
| `src/build_loop/server/static/pipeline-builder.js` | Canvas-based visual editor |
| `.spectre/pipelines/*.yaml` | Pipeline definitions (created per-project) |

## CLI Usage

```bash
# Legacy mode (still works)
spectre-build --tasks docs/tasks.md --validate

# Pipeline mode
spectre-build --pipeline .spectre/pipelines/full-feature.yaml --tasks docs/tasks.md

# Web GUI
spectre-build serve
spectre-build serve --port 9000 --host 0.0.0.0
```

## Pipeline YAML Format

```yaml
name: full-feature
description: "Build → Code Review → Validate cycle"
start_stage: build
end_signals: [COMPLETE]

stages:
  - name: build
    prompt: prompts/build.md
    completion:
      type: promise
      signals: [TASK_COMPLETE, BUILD_COMPLETE]
    max_iterations: 10
    transitions:
      BUILD_COMPLETE: code_review
      TASK_COMPLETE: build  # loop for more tasks

  - name: code_review
    prompt: prompts/code_review.md
    completion:
      type: json
      statuses: [APPROVED, CHANGES_REQUESTED]
    max_iterations: 1
    transitions:
      APPROVED: validate
      CHANGES_REQUESTED: build  # loop back

  - name: validate
    prompt: prompts/validate.md
    completion:
      type: json
      statuses: [COMPLETE, GAPS_FOUND]
    max_iterations: 1
    transitions:
      GAPS_FOUND: build  # loop back
```

## Completion Strategies

| Type | Detection | Use When |
|------|-----------|----------|
| `promise` | `[[PROMISE:SIGNAL]]` tags in output | Simple signal-based completion |
| `json` | ` ```json {"status": "..."}``` ` blocks | Need structured artifacts/metadata |
| `composite` | Tries multiple strategies | Backward compat (JSON with promise fallback) |

## Common Tasks

### Add a New Stage

1. Edit pipeline YAML - add stage to `stages` list
2. Create prompt template in `prompts/` directory
3. Define completion strategy (promise or json)
4. Add transitions from/to the new stage
5. Test with `spectre-build --pipeline your-pipeline.yaml --tasks test.md`

### Create Custom Completion Strategy

```python
# In pipeline/completion.py
class MyCompletion(CompletionStrategy):
    def evaluate(self, output: str, exit_code: int) -> CompletionResult:
        # Parse output, return CompletionResult
        return CompletionResult(
            is_complete=True,
            signal="MY_SIGNAL",
            artifacts={"key": "value"}
        )
```

## Dependencies

```toml
# pyproject.toml
dependencies = [
    "fastapi>=0.109.0",
    "uvicorn[standard]>=0.27.0",
    "pyyaml>=6.0",
    "pydantic>=2.0",
    "websockets>=12.0",
]
```

After `pipx install`, inject dependencies:
```bash
pipx inject spectre-build 'uvicorn[standard]' fastapi pyyaml pydantic websockets
```

## Gotchas

1. **Pipelines are CWD-relative** - Server looks for `.spectre/pipelines/` in current working directory, not package directory
2. **Demo pipelines auto-create** - If no pipelines exist, server creates `demo-build-validate.yaml` and `demo-full-feature.yaml`
3. **Regex in JS** - Avoid character classes with Unicode arrows (e.g., `[→->]` is invalid). Use `(?:→|->|=>)` instead
4. **Dependencies after reinstall** - `pipx install -e . --force` clears injected deps, must re-inject
