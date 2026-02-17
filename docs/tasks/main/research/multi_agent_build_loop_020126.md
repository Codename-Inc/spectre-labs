---
date: "2026-02-01T12:00:00-08:00"
git_commit: 7491e5847964de788fb94881de9983539f9a37b8
branch: main
repository: spectre-labs
topic: "Multi-Agent Build Loop: Adding Codex CLI Support to spectre-build"
tags: [research, build-loop, codex, multi-agent, architecture]
status: complete
last_updated: "2026-02-01"
last_updated_by: Researcher
---

# Research: Multi-Agent Build Loop — Adding Codex CLI Support

**Date**: 2026-02-01
**Git Commit**: `7491e58`
**Branch**: `main`
**Repository**: spectre-labs

## Research Question

How to add agent selection (`--agent claude|codex`) to `spectre-build` so the build loop can run identically with either Claude Code or Codex CLI executing each iteration?

## Summary

The build loop currently hardcodes `claude -p` as the subprocess. Adding Codex support requires:

1. An **agent abstraction** — a strategy interface that encapsulates CLI invocation, tool filtering, and stream parsing per agent
2. A **CLI flag** (`--agent`) to select which agent runs
3. **Agent-specific stream parsers** — Claude emits `stream-json` events, Codex emits JSONL with different event shapes
4. **Adapted tool filtering** — Claude uses `--allowedTools`/`--disallowedTools`, Codex uses `--sandbox` modes and `--disable` feature flags

The existing `cli/cli/subagent/runner.py` already has a working Codex subprocess runner with JSONL parsing — substantial code can be reused.

## Detailed Findings

### 1. Current Build Loop Architecture

The build loop (`build-loop/src/build_loop/loop.py:46-125`) is tightly coupled to Claude Code:

- **Command construction** (line 73-79): Hardcoded `claude -p` with `--allowedTools`, `--disallowedTools`, `--output-format stream-json`
- **Stream parsing** (line 98-108): Expects Claude's stream-json event format via `process_stream_event()`
- **Promise detection** (line 128-144): Regex for `[[PROMISE:...]]` — this is agent-agnostic and works with any agent that outputs the tag
- **Stats tracking** (line 65-66): `BuildStats.add_usage()` expects Claude's `usage` dict shape (`input_tokens`, `output_tokens`, `cache_read_input_tokens`)

### 2. Existing Codex Runner (Reusable Code)

`cli/cli/subagent/runner.py` already implements Codex subprocess management:

- **`_run_codex_sync()`** (line 334-459): Runs `codex exec --sandbox workspace-write --json`, reads JSONL, extracts agent messages
- **`extract_agent_messages()`** (line 196-228): Parses Codex JSONL events, extracts `item.completed` with `type: agent_message`
- **`setup_codex_home()`** (line 148-178): Syncs `~/.codex` credentials to `.spectre/codex-subagent/` for sandboxed execution
- **Prompt injection** (line 402-404): Sends prompt via stdin, same pattern as Claude

### 3. Claude vs Codex CLI Comparison

| Aspect | Claude Code | Codex CLI |
|--------|------------|-----------|
| Non-interactive | `claude -p` | `codex exec` |
| Prompt input | stdin after `-p` flag | stdin to `codex exec` |
| JSON output | `--output-format stream-json` | `--json` |
| Tool allowlist | `--allowedTools Bash,Read,...` | Not supported; use `--sandbox` mode |
| Tool denylist | `--disallowedTools Task,WebSearch,...` | `--disable shell_tool`, feature flags |
| Sandbox | N/A (uses tool lists) | `--sandbox read-only\|workspace-write\|danger-full-access` |
| Token usage events | `usage` in `assistant` message | Different event structure |
| Event types | `assistant`, `tool_use`, `tool_result` | `item.completed`, `tool_call`, `tool_result`, etc. |

### 4. Tool Filtering Strategy

**Claude** (current): Explicit allow/deny lists per tool name:
```
--allowedTools Bash,Read,Write,Edit,Glob,Grep,LS,TodoRead,TodoWrite,Skill
--disallowedTools AskUserQuestion,WebFetch,WebSearch,Task,EnterPlanMode,NotebookEdit
```

**Codex**: Sandbox mode + feature flags:
```
--sandbox workspace-write     # Can edit workspace files, no network
--disable web_search          # No web search
```

Codex doesn't support granular tool allowlists. The `--sandbox workspace-write` mode already blocks network access (equivalent to denying WebFetch/WebSearch) and restricts file access to the workspace. The `--disable shell_tool` flag could disable Bash if needed, but for the build loop we want shell access.

**Recommended Codex flags for build loop**:
```
codex exec --sandbox workspace-write --json
```
This gives: file read/write/edit, shell execution, no network — closely matching the Claude allowlist.

### 5. Stream Parsing Differences

**Claude stream-json** (what `process_stream_event` handles):
```json
{"type": "assistant", "message": {"content": [{"type": "text", "text": "..."}, {"type": "tool_use", "name": "Read", "input": {...}}], "usage": {...}}}
```

**Codex JSONL** (what `extract_agent_messages` handles):
```json
{"type": "item.completed", "item": {"type": "agent_message", "text": "..."}}
{"type": "item.completed", "item": {"type": "tool_call", "name": "shell", "arguments": "..."}}
```

Key difference: Codex uses `item.completed` wrapper events. Tool names differ (`shell` vs `Bash`, `apply_patch` vs `Edit`).

### 6. Proposed Architecture

**Agent Strategy Pattern** — one module per agent backend:

```
build-loop/src/build_loop/
├── agents/
│   ├── __init__.py      # AgentBackend protocol + factory
│   ├── claude.py        # Claude Code backend
│   └── codex.py         # Codex CLI backend
├── loop.py              # Uses AgentBackend.run_iteration()
├── stream.py            # Claude-specific (move to agents/claude.py or keep as-is)
└── ...
```

**AgentBackend Protocol**:
```python
class AgentBackend(Protocol):
    name: str

    def build_command(self) -> list[str]:
        """Return the CLI command + flags."""
        ...

    def build_env(self) -> dict[str, str]:
        """Return environment variables for the subprocess."""
        ...

    def process_line(self, line: str, text_buffer: list[str], stats: BuildStats) -> None:
        """Process one line of streaming output."""
        ...
```

**Factory**:
```python
def get_agent(name: str) -> AgentBackend:
    if name == "claude":
        return ClaudeBackend()
    elif name == "codex":
        return CodexBackend()
    raise ValueError(f"Unknown agent: {name}")
```

**Loop change** — `run_claude_iteration` becomes `run_iteration(agent: AgentBackend, ...)`:
- `agent.build_command()` replaces hardcoded `cmd`
- `agent.process_line()` replaces `process_stream_event()`
- Promise detection stays in `loop.py` (agent-agnostic)

### 7. CLI Changes

Add `--agent` flag to `cli.py`:
```python
parser.add_argument(
    "--agent",
    type=str,
    choices=["claude", "codex"],
    default="claude",
    help="Coding agent to run (default: claude)",
)
```

Pass through to `run_build_loop()` and store in session JSON for resume.

### 8. Stats Tracking Differences

Claude provides token usage in `assistant` message events. Codex JSONL doesn't include equivalent token counts in the same format. Options:
- Skip token tracking for Codex (show N/A)
- Parse Codex-specific usage events if they exist
- Track tool calls only (both agents emit tool call events)

## Code References

| File | Line(s) | Purpose |
|------|---------|---------|
| `build-loop/src/build_loop/loop.py` | 18-43 | Tool allow/deny lists (Claude-specific) |
| `build-loop/src/build_loop/loop.py` | 46-125 | `run_claude_iteration()` — subprocess invocation |
| `build-loop/src/build_loop/loop.py` | 128-144 | `detect_promise()` — agent-agnostic |
| `build-loop/src/build_loop/loop.py` | 147-263 | `run_build_loop()` — main loop |
| `build-loop/src/build_loop/stream.py` | 46-87 | `process_stream_event()` — Claude stream parser |
| `build-loop/src/build_loop/cli.py` | 85-155 | `parse_args()` — add `--agent` here |
| `build-loop/src/build_loop/cli.py` | 27-44 | `save_session()` — add agent to session JSON |
| `build-loop/src/build_loop/stats.py` | 12-121 | `BuildStats` — token tracking is Claude-specific |
| `cli/cli/subagent/runner.py` | 148-178 | `setup_codex_home()` — credential sync (reuse) |
| `cli/cli/subagent/runner.py` | 196-228 | `extract_agent_messages()` — Codex JSONL parser (reuse) |
| `cli/cli/subagent/runner.py` | 334-459 | `_run_codex_sync()` — Codex subprocess pattern (reference) |

## Architecture Insights

1. **Promise detection is already agent-agnostic** — it's just regex on text output. Both Claude and Codex can be instructed to emit `[[PROMISE:TASK_COMPLETE]]` in their prompt template.

2. **The prompt template (`build.md`) is agent-agnostic** — it describes workflow steps, not tool names. The only Claude-specific part is the `@skill-spectre:spectre-tdd` reference in Step 3, which Codex doesn't support. This needs a conditional or separate template.

3. **Codex `--sandbox workspace-write`** provides equivalent safety to Claude's tool allow/deny lists for this use case — workspace file access + shell, no network.

4. **The subagent runner already solved the Codex subprocess pattern** — credential sync, JSONL parsing, stdin prompt injection. The build loop's Codex backend can reuse or adapt this code.

5. **Skill invocation (`Skill` tool)** is Claude-specific. The prompt template references `@skill-spectre:spectre-tdd`. For Codex, this instruction should be replaced with equivalent inline instructions or skipped.

## Open Questions

1. **Codex token usage**: Does Codex JSONL include token/usage events? If not, the stats dashboard will need a "N/A" path.
2. **Prompt template divergence**: Should there be one template with conditionals, or separate `build-claude.md` / `build-codex.md` templates? The Skill reference is the main divergence point.
3. **Codex tool names in stream display**: Codex uses `shell` instead of `Bash`, `apply_patch` instead of `Edit`. The `format_tool_call()` function needs mapping.
4. **Session resume**: When resuming, should the agent choice be locked to what was used initially, or allow switching mid-build?
5. **`setup_codex_home()` placement**: Should this be duplicated in build-loop or imported from the CLI package? The build-loop is a separate pip-installable package.
