# Validation Gaps — Phase 4: CLI Integration
*Generated: 2026-02-17*

## Summary
- **Overall Status**: Complete
- **Requirements**: 8 of 8 delivered
- **Gaps Found**: 0 requiring remediation

---

## Gap Remediation Tasks

No gaps found. All Phase 4 tasks are fully delivered, connected, and reachable.

---

## Validation Coverage

| Area | Task | Status | Definition | Usage |
|------|------|--------|------------|-------|
| [4.1] `--plan` flag | 4.1.1 Add `--plan` argument | ✅ | cli.py:217-221 | cli.py:1023 |
| [4.1] run_plan_pipeline() | 4.1.2 Implement function | ✅ | cli.py:653-796 | cli.py:1037, cli.py:849 |
| [4.1] main() routing | 4.1.3 Wire `--plan` in main() | ✅ | cli.py:1022-1054 | Entry point → main() |
| [4.2] Session save/load | 4.2.1 Planning session fields | ✅ | cli.py:30-67 | cli.py:769, cli.py:1035, cli.py:838 |
| [4.2] Session display | 4.2.2 format_session_summary() | ✅ | cli.py:87-125 | cli.py:814 |
| [4.3] Resume flow | 4.3.1 Planning resume routing | ✅ | cli.py:836-856 | cli.py:1005-1007 |

### Dependency Verification

| Import | Definition | Usage Site |
|--------|------------|------------|
| `create_plan_pipeline` | loader.py:413 | cli.py:685, cli.py:714 |
| `create_plan_resume_pipeline` | loader.py:523 | cli.py:685, cli.py:712 |
| `plan_before_stage` | hooks.py:118 | cli.py:683, cli.py:745 |
| `plan_after_stage` | hooks.py:147 | cli.py:683, cli.py:746 |
| `create_plan_event_handler` | stats.py:220 | cli.py:686, cli.py:737 |

---

## Reachability Traces

### Trace 1: `spectre-build --plan --context scope.md`
```
User action: spectre-build --plan --context scope.md
→ main() [cli.py:990]
→ parse_args() → args.plan=True [cli.py:994]
→ args.plan check [cli.py:1023]
→ validate --context present [cli.py:1024-1026]
→ save_session(..., plan=True) [cli.py:1035]
→ run_plan_pipeline(context_files, max_iterations, agent) [cli.py:1037-1041]
→ create_plan_pipeline() [cli.py:714]
→ PipelineExecutor(..., before_stage=plan_before_stage, after_stage=plan_after_stage) [cli.py:740-747]
→ executor.run(stats) [cli.py:749]
→ notification on completion [cli.py:1046-1053]
```

### Trace 2: `spectre-build resume` (planning session)
```
User action: spectre-build resume
→ main() [cli.py:990]
→ positional == "resume" [cli.py:1005]
→ run_resume(args) [cli.py:1006]
→ load_session() [cli.py:803]
→ format_session_summary(session) shows Mode/Output/Clarif [cli.py:813-815]
→ session.get("plan") == True [cli.py:836]
→ save_session(...) timestamp update [cli.py:838-847]
→ run_plan_pipeline(..., resume_stage="update_docs", resume_context=...) [cli.py:849-856]
→ create_plan_resume_pipeline() [cli.py:712]
→ PipelineExecutor with hooks [cli.py:740-747]
→ executor.run(stats) [cli.py:749]
→ notification on completion [cli.py:889-897]
```

### Trace 3: CLARIFICATIONS_NEEDED signal flow
```
Pipeline running → req_validate stage emits CLARIFICATIONS_NEEDED
→ plan_after_stage("req_validate", context, result) [hooks.py:172-177]
→ stores clarifications_path in context [hooks.py:176]
→ Pipeline ends (no transition for CLARIFICATIONS_NEEDED)
→ run_plan_pipeline() detects last_signal == "CLARIFICATIONS_NEEDED" [cli.py:756]
→ Prints instructions to user [cli.py:762-766]
→ save_session(..., plan_clarifications_path=clarif_path) [cli.py:769-778]
→ Returns exit code 0 [cli.py:780]
```

## Scope Creep
None detected. All changes are scoped to Phase 4 CLI integration requirements.

## Detailed Requirement Verification

### [4.1.1] --plan argument
- ✅ Added as `store_true` action (cli.py:218-221)
- ✅ Help text: "Run planning pipeline: scope docs → build-ready manifest"
- ✅ `--plan` makes `--tasks` optional — plan check at line 1023 precedes tasks check at line 1057

### [4.1.2] run_plan_pipeline() function
- ✅ Returns `tuple[int, int]` (exit_code, total_iterations) — cli.py:660
- ✅ Creates output directory `docs/tasks/{branch}` — cli.py:695-708
- ✅ Builds initial context dict — cli.py:722-733
- ✅ Routes to `create_plan_pipeline()` or `create_plan_resume_pipeline()` based on `resume_stage` — cli.py:711-714
- ✅ Wires `plan_before_stage`/`plan_after_stage` hooks — cli.py:745-746
- ✅ Wires `create_plan_event_handler(stats)` as on_event — cli.py:737
- ✅ Handles CLARIFICATIONS_NEEDED: saves session, prints message, returns exit 0 — cli.py:752-780
- ✅ On PLAN_VALIDATED/PLAN_READY: prints manifest path and spectre-build command — cli.py:783-789

### [4.1.3] --plan routing in main()
- ✅ `--plan` takes priority (checked before tasks/validate) — cli.py:1023
- ✅ `--plan` without `--context` errors — cli.py:1024-1026
- ✅ Notification on completion/error — cli.py:1046-1053

### [4.2.1] Session persistence
- ✅ `save_session()` accepts `plan`, `plan_output_dir`, `plan_context`, `plan_clarifications_path` — cli.py:38-41
- ✅ Session JSON includes all planning fields when plan=True — cli.py:59-62
- ✅ `load_session()` returns full dict (no changes needed) — cli.py:70-84

### [4.2.2] format_session_summary()
- ✅ Shows "Mode: Planning" when plan=True — cli.py:93-94
- ✅ Shows output dir — cli.py:116-117
- ✅ Shows clarifications path — cli.py:119-120

### [4.3.1] Planning resume flow
- ✅ Detects plan=True in session — cli.py:836
- ✅ Routes to run_plan_pipeline() with resume_stage="update_docs" — cli.py:849-856
- ✅ Passes preserved plan_context — cli.py:855
- ✅ Passes plan_output_dir — cli.py:853
- ✅ Updates session timestamp before resume — cli.py:838-847
- ✅ Notification on completion — cli.py:889-897
