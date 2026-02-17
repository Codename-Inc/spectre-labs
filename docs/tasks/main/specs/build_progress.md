# Build Progress

## Codebase Patterns
- Pipeline factories follow `create_*_pipeline() -> PipelineConfig` pattern in `loader.py`
- All planning stages use `JsonCompletion` with `signal_field="status"` for consistency
- Tool filtering uses `PLAN_DENIED_TOOLS` and `PLAN_RESEARCH_DENIED_TOOLS` module-level constants
- Prompt paths resolved via `Path(__file__).parent.parent / "prompts" / "planning"` pattern
- Tests in `build-loop/tests/test_plan_pipeline.py` — run with `/Users/joe/.local/pipx/venvs/spectre-build/bin/python -m pytest tests/test_plan_pipeline.py -v`
- pytest available via `pipx inject spectre-build pytest`

---

## Iteration — [1.1] Create planning pipeline factory + [1.2] Create planning resume pipeline factory
**Status**: Complete
**What Was Done**: Implemented `create_plan_pipeline()` and `create_plan_resume_pipeline()` factory functions in `pipeline/loader.py`. The planning pipeline defines 7 stages (research, assess, create_plan, create_tasks, plan_review, req_validate, update_docs) with JsonCompletion on all stages, complexity-aware routing (LIGHT skips create_plan), and research stage expanded tool access (WebSearch/WebFetch allowed). Resume pipeline is a single update_docs stage. Created 7 placeholder prompt templates in `prompts/planning/`. Added 17 unit tests covering all requirements. Updated `__init__.py` exports and `pyproject.toml` package-data.
**Files Changed**:
- `build-loop/src/build_loop/pipeline/loader.py` (added `create_plan_pipeline`, `create_plan_resume_pipeline`, `PLAN_DENIED_TOOLS`, `PLAN_RESEARCH_DENIED_TOOLS`)
- `build-loop/src/build_loop/pipeline/__init__.py` (added exports)
- `build-loop/src/build_loop/prompts/planning/*.md` (7 new placeholder templates)
- `build-loop/pyproject.toml` (added `prompts/planning/*.md` to package-data)
- `build-loop/tests/test_plan_pipeline.py` (new, 17 tests)
- `docs/tasks/main/specs/tasks.md` (marked 1.1 and 1.2 complete)
**Key Decisions**:
- Combined tasks 1.1 and 1.2 into one iteration since they share the same file and test patterns
- Used module-level constants for denied tools lists (reusable by hooks and CLI in later phases)
- Placeholder prompts contain basic structure and variable references that Phase 2 will flesh out
**Blockers/Risks**: None

## Iteration — [2.1] Create research stage prompt
**Status**: Complete
**What Was Done**: Replaced the placeholder `research.md` prompt with a comprehensive autonomous research template. The prompt guides the agent through 4 steps: read scope documents, explore codebase using Read/Grep/Glob, write structured findings to `{output_dir}/task_context.md` (with sections for Architecture Patterns, Key Files, Dependencies, Integration Points, Existing Conventions, Constraints and Risks), and emit `RESEARCH_COMPLETE` JSON with `task_context_path` artifact. Added 10 unit tests covering template content, variable substitution, and structural requirements.
**Files Changed**:
- `build-loop/src/build_loop/prompts/planning/research.md` (replaced placeholder with full prompt)
- `build-loop/tests/test_research_prompt.py` (new, 10 tests)
- `docs/tasks/main/specs/tasks.md` (marked 2.1 complete)
**Key Decisions**:
- Prompt follows the same style as `code_review.md` — numbered steps, explicit rules, JSON output at end
- Template specifies a markdown structure for `task_context.md` output so downstream stages get consistent input
- Included "Do NOT" guardrails to prevent the agent from doing work that belongs to later stages
**Blockers/Risks**: None
