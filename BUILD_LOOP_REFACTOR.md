# Build Loop Refactoring Task

The build loop was extracted from `Codename/spectre` and needs refactoring to work as a standalone package.

## Current State

**RESOLVED** - All issues fixed and tested. The package now uses a `src/` layout with proper imports.

## Final Structure

```
build-loop/
├── pyproject.toml
└── src/
    └── build_loop/
        ├── __init__.py      # Package entry point (main function)
        ├── cli.py           # CLI argument parsing, interactive prompts
        ├── loop.py          # Core build loop logic
        ├── prompt.py        # Prompt template construction
        ├── prompts/
        │   └── build.md     # Iteration prompt template
        ├── stats.py         # Token/timing metrics
        ├── stream.py        # Stream-json parsing + display
        └── notify.py        # macOS notifications
```

## Problems Fixed

### 1. Broken Imports ✅

**cli.py** had:
```python
from ..notify import notify_build_complete, notify_build_error
```

**Fixed** to:
```python
from .notify import notify_build_complete, notify_build_error
```

### 2. Package Structure ✅

Adopted `src/` layout with `build_loop` package directory. Entry point in `__init__.py`:

```python
def main() -> None:
    """Main entry point for Spectre Build CLI."""
    from .cli import main as cli_main
    cli_main()
```

### 3. pyproject.toml Entry Point ✅

Updated to:
```toml
[project.scripts]
spectre-build = "build_loop:main"

[tool.setuptools.packages.find]
where = ["src"]

[tool.setuptools.package-data]
build_loop = ["prompts/*.md"]
```

### 4. Removed Unused Dependency ✅

Removed `click>=8.0` from dependencies since the CLI uses `argparse`.

## Testing

```bash
cd spectre-labs/build-loop
python3 -m venv test-env
source test-env/bin/activate
pip install -e .
spectre-build --help
spectre-build --tasks test-tasks.md --max-iterations 1
spectre-build resume -y
```

## Acceptance Criteria

- [x] `spectre-build --help` shows usage
- [x] `spectre-build --tasks file.md` runs the build loop
- [x] `spectre-build resume` resumes a previous session
- [x] Package installs cleanly via `pip install -e .`
