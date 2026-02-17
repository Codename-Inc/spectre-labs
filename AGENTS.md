# AGENTS.md — Build Agent Notes

## Testing

- **pytest**: Available via `pipx inject spectre-build pytest`. Run tests from `build-loop/` directory:
  ```bash
  /Users/joe/.local/pipx/venvs/spectre-build/bin/python -m pytest tests/test_plan_pipeline.py -v
  ```
- **Linting**: Use `py_compile` for syntax checking:
  ```bash
  /Users/joe/.local/pipx/venvs/spectre-build/bin/python -m py_compile path/to/file.py
  ```
- **Import testing**: Use the pipx venv python for full import tests (system python lacks pyyaml/pydantic):
  ```bash
  /Users/joe/.local/pipx/venvs/spectre-build/bin/python -c "from build_loop.pipeline import ..."
  ```

## Gotchas

- System python lacks `yaml` and `pydantic` — always use pipx venv at `/Users/joe/.local/pipx/venvs/spectre-build/bin/python`
- Test files go in `build-loop/tests/` directory
- `pyproject.toml` package-data must include new prompt subdirectories (e.g., `prompts/planning/*.md`)
- When mocking functions used via lazy imports (e.g., `from .agent import get_agent` inside a function), mock at the source module (`build_loop.agent.get_agent`), not at the consumer module (`build_loop.cli.get_agent`)
- When testing `main()` that calls `sys.exit()`, use `pytest.raises(SystemExit)` — patching `sys.exit` lets execution continue past the exit point, causing downstream failures
