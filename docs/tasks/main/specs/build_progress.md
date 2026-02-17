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

## Iteration — [2.2] Create assess stage prompt
**Status**: Complete
**What Was Done**: Replaced the placeholder `assess.md` prompt with a comprehensive autonomous complexity assessment template. The prompt guides the agent through 6 steps: read task context and scope docs, score complexity across 5 dimensions (files impacted, pattern match, components crossed, data model changes, integration points) using a Low/Medium/High scoring matrix, check hard-stop conditions (new service, auth/PII, public API, new data pipeline, cross-team dependency), determine tier (LIGHT/STANDARD/COMPREHENSIVE) from total score, write architecture design section into task_context.md for COMPREHENSIVE tier, and emit JSON with status/depth/tier fields. Added 12 unit tests covering template content, variable substitution, and structural requirements.
**Files Changed**:
- `build-loop/src/build_loop/prompts/planning/assess.md` (replaced placeholder with full prompt)
- `build-loop/tests/test_assess_prompt.py` (new, 12 tests)
- `docs/tasks/main/specs/tasks.md` (marked 2.2 complete)
**Key Decisions**:
- Used a scoring matrix (5 dimensions x 3 levels = 5-15 total) to make tier determination concrete and reproducible
- Hard-stops override the score entirely — any single hard-stop forces COMPREHENSIVE
- Architecture design for COMPREHENSIVE is appended to existing task_context.md (not a separate file) so create_plan stage gets it automatically
- Follows same style as research.md — numbered steps, explicit rules, "Do NOT" guardrails, JSON output at end
**Blockers/Risks**: None

## Iteration — [2.3] Create plan generation prompt
**Status**: Complete
**What Was Done**: Replaced the placeholder `create_plan.md` prompt with a comprehensive autonomous plan generation template. The prompt guides the agent through 4 steps: read task context and scope docs, determine section depth based on `{depth}` variable (standard vs comprehensive) using a detail-level table, write the implementation plan to `{output_dir}/specs/plan.md` with required sections (Overview, Out of Scope, Technical Approach, Critical Files, Risks), and emit `PLAN_COMPLETE` JSON with `plan_path` artifact. Added 12 unit tests covering template content, variable substitution, and structural requirements.
**Files Changed**:
- `build-loop/src/build_loop/prompts/planning/create_plan.md` (replaced placeholder with full prompt)
- `build-loop/tests/test_create_plan_prompt.py` (new, 12 tests)
- `docs/tasks/main/specs/tasks.md` (marked 2.3 complete)
**Key Decisions**:
- Depth-aware detail table maps standard/comprehensive to concrete section expectations (e.g., standard = 2-3 paragraphs overview, comprehensive = full system overview with diagrams)
- Plan structure includes Out of Scope section to prevent scope creep during task breakdown
- Writing rules require grounding claims in code references from task_context.md
- Follows same style as research.md and assess.md — numbered steps, explicit rules, "Do NOT" guardrails, JSON output at end
**Blockers/Risks**: None
