# Build Loop Refactoring Task

The build loop was extracted from `Codename/spectre` and needs refactoring to work as a standalone package.

## Current State

The build loop files were copied from `spectre/cli/build/` to `spectre-labs/build-loop/` but retain their old import structure which assumes they're part of a larger `cli` package.

## Files

```
build-loop/
├── __init__.py
├── cli.py          # CLI argument parsing, interactive prompts
├── loop.py         # Core build loop logic
├── prompt.py       # Prompt template construction
├── prompts/
│   └── build.md    # Iteration prompt template
├── stats.py        # Token/timing metrics
├── stream.py       # Stream-json parsing + display
├── notify.py       # macOS notifications
└── pyproject.toml  # Package config (needs updates)
```

## Problems to Fix

### 1. Broken Imports

**cli.py** has:
```python
from .loop import run_build_loop
from ..notify import notify_build_complete, notify_build_error
```

The `..notify` import is broken because `notify.py` was moved into the same directory (not a parent).

**Fix**: Change to:
```python
from .loop import run_build_loop
from .notify import notify_build_complete, notify_build_error
```

### 2. Missing Entry Point

**pyproject.toml** has:
```toml
[project.scripts]
spectre-build = "cli:main"
```

But `cli.py` doesn't have a `main()` function — the build command was defined in the parent `spectre/cli/main.py` using Click decorators.

**Fix**: Create a proper Click-based entry point in `cli.py` or a new `main.py`:

```python
import click
from .loop import run_build_loop
from .cli import (
    prompt_for_tasks_file,
    prompt_for_context_files,
    prompt_for_max_iterations,
    validate_inputs,
    normalize_path,
    save_session,
    load_session,
    format_session_summary,
    get_session_path,
)

@click.group(invoke_without_command=True)
@click.option("--tasks", type=click.Path(exists=True), help="Path to tasks.md file")
@click.option("--context", multiple=True, type=click.Path(exists=True), help="Context files")
@click.option("--max-iterations", type=int, default=10, help="Maximum iterations")
@click.pass_context
def cli(ctx, tasks, context, max_iterations):
    """Run build loop, completing one task per iteration."""
    if ctx.invoked_subcommand is not None:
        return
    # ... run build logic

@cli.command()
def resume():
    """Resume the last build session."""
    # ... resume logic

def main():
    cli()

if __name__ == "__main__":
    main()
```

### 3. Update pyproject.toml Entry Point

After creating the entry point:
```toml
[project.scripts]
spectre-build = "build_loop.main:main"
```

Or if keeping in cli.py:
```toml
[project.scripts]
spectre-build = "build_loop.cli:main"
```

### 4. Rename Package Directory (Optional)

Consider renaming `build-loop/` to `build_loop/` (underscore) for valid Python package naming, or use a `src/` layout:

```
build-loop/
├── src/
│   └── build_loop/
│       ├── __init__.py
│       ├── main.py
│       ├── loop.py
│       └── ...
└── pyproject.toml
```

## Testing

After refactoring:

```bash
cd spectre-labs/build-loop
pip install -e .
spectre-build --help
spectre-build --tasks test-tasks.md --max-iterations 1
```

## Reference

The original working implementation is in the `pre-restructure-backup` branch of `Codename/spectre`:
- `cli/main.py` — The Click command definitions (lines 78-244)
- `cli/build/` — The build loop modules

## Acceptance Criteria

- [ ] `spectre-build --help` shows usage
- [ ] `spectre-build --tasks file.md` runs the build loop
- [ ] `spectre-build resume` resumes a previous session
- [ ] Package installs cleanly via `pip install -e .`
