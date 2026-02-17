# Todo CLI App — Scope

## Goal

Build a minimal command-line todo app in Python. Two phases: data layer first, then CLI on top.

## In Scope

- `Todo` dataclass with title, done flag, auto-incrementing id
- In-memory store with add, list, complete operations
- CLI with argparse subcommands: `add`, `list`, `done`
- Basic input validation (empty titles, invalid ids)

## Out of Scope

- Persistence (no file/database storage)
- Due dates, priorities, or categories
- Multi-user support
- Web interface

## Acceptance Criteria

1. `python cli.py add "Buy milk"` creates a new todo
2. `python cli.py list` shows all todos with checkboxes
3. `python cli.py done 1` marks todo #1 as complete
4. Invalid input produces clear error messages
