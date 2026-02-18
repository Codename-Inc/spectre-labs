# Validation Gaps — Ship Loop (`--ship`)
*Generated: 2026-02-18*

## Summary
- **Overall Status**: Complete
- **Requirements**: 30 of 30 delivered
- **Gaps Found**: 0 requiring remediation

All 30 requirements across 4 phases (12 parent tasks, 14 sub-tasks) have been validated as Delivered — Defined AND Connected AND Reachable from user action.

---

## Gap Remediation Tasks

No gaps found. All tasks are fully delivered, connected, and reachable.

---

## Validation Coverage

| Area | Task | Status | Definition | Usage |
|------|------|--------|------------|-------|
| CLI Flag & Routing | 1.1 | ✅ | cli.py:238-242 | cli.py:1294 (main), cli.py:1324 (interactive guard) |
| Ship Pipeline Orchestration | 1.2 | ✅ | cli.py:859-949 | cli.py:1304 (main), cli.py:1043 (resume), cli.py:1148 (manifest) |
| Interactive Mode | 1.3 | ✅ | cli.py:356-368, cli.py:1365-1408 | cli.py:1325 (mode dispatch) |
| Pipeline Factory | 2.1 | ✅ | loader.py:413-475 | cli.py:925 (run_ship_pipeline) |
| Ship Hooks | 2.2 | ✅ | hooks.py:186-251 | cli.py:937-938 (PipelineExecutor wiring) |
| Clean Prompt | 3.1 | ✅ | prompts/shipping/clean.md (7 tasks) | loader.py:430 (stage config) |
| Test Prompt | 3.2 | ✅ | prompts/shipping/test.md (4 tasks) | loader.py:444 (stage config) |
| Rebase Prompt | 3.3 | ✅ | prompts/shipping/rebase.md (single window) | loader.py:458 (stage config) |
| Session Persistence | 4.1 | ✅ | cli.py:42-43, cli.py:1032-1048, cli.py:97-101 | cli.py:1302 (save), cli.py:1032 (resume) |
| Manifest Support | 4.2 | ✅ | manifest.py:21, cli.py:1143-1165 | cli.py:1143 (routing check) |
| Stats Tracking | 4.3 | ✅ | stats.py:65, stats.py:245-262, stats.py:209-211 | cli.py:929 (handler), cli.py:935 (wiring) |
| Notification | 4.4 | ✅ | notify.py:188-221 | cli.py:1314, cli.py:1084, cli.py:1158 |
| No Core Engine Changes | REQ-030 | ✅ | N/A | executor.py, stage.py, completion.py, stream.py, agent.py untouched |

---

## Reachability Traces

### Trace 1: `spectre-build --ship`
```
User: spectre-build --ship
→ main() [cli.py:1222]
→ parse_args() → args.ship=True [cli.py:1226]
→ args.ship check [cli.py:1294]
→ context_files resolved (optional) [cli.py:1295-1296]
→ save_session(..., ship=True) [cli.py:1302]
→ run_ship_pipeline(context_files, max_iterations, agent) [cli.py:1304-1308]
  → _detect_parent_branch() [cli.py:901] → fail fast if None [cli.py:902-905]
  → working_set_scope = f"{parent_branch}..HEAD" [cli.py:908]
  → create_ship_pipeline() [cli.py:925] → PipelineConfig(name="ship", stages={clean,test,rebase})
  → create_ship_event_handler(stats) [cli.py:929]
  → PipelineExecutor(config, runner, on_event, context, ship_before_stage, ship_after_stage) [cli.py:932-939]
  → executor.run(stats) [cli.py:941]
    → Stage "clean" → 7 tasks via clean.md → CLEAN_TASK_COMPLETE/CLEAN_COMPLETE
    → ship_after_stage("clean") → context["clean_summary"] set
    → Stage "test" → 4 tasks via test.md → TEST_TASK_COMPLETE/TEST_COMPLETE
    → ship_after_stage("test") → context["test_summary"] set
    → Stage "rebase" → rebase.md → SHIP_COMPLETE → pipeline ends
→ notify_ship_complete() [cli.py:1314-1319]
→ sys.exit(exit_code) [cli.py:1321]
```

### Trace 2: `spectre-build` (interactive ship)
```
User: spectre-build (no flags)
→ main() → prompt_for_mode() [cli.py:1325]
→ User selects "ship" → mode == "ship" [cli.py:1365]
→ prompt_for_context_files() (optional) [cli.py:1366]
→ _detect_parent_branch() [cli.py:1373] → fail fast if None
→ Display parent branch, confirm [cli.py:1380-1385]
→ save_session(..., ship=True) [cli.py:1389]
→ run_ship_pipeline() [cli.py:1391-1395]
→ notify_ship_complete() [cli.py:1400-1406]
→ sys.exit(exit_code) [cli.py:1408]
```

### Trace 3: `spectre-build resume` (ship session)
```
User: spectre-build resume
→ run_resume(args) [cli.py:974]
→ load_session() → session.get("ship") == True [cli.py:1032]
→ save_session(..., ship=True, ship_context=...) [cli.py:1034-1041]
→ run_ship_pipeline(resume_context=session.get("ship_context")) [cli.py:1043-1048]
  → resume_context path → skips _detect_parent_branch() [cli.py:897-898]
→ notify_ship_complete() [cli.py:1084-1089]
→ sys.exit(exit_code) [cli.py:1105]
```

### Trace 4: `spectre-build ship.md` (manifest)
```
User: spectre-build ship.md
→ main() → positional.endswith(".md") → run_manifest() [cli.py:1242-1244]
→ load_manifest("ship.md") → manifest.ship=True [manifest.py:171]
→ manifest.ship check [cli.py:1143] → before validate check [cli.py:1175]
→ save_session(..., ship=True, manifest_path=...) [cli.py:1145-1146]
→ run_ship_pipeline() [cli.py:1148-1152]
→ notify_ship_complete() [cli.py:1158-1163]
→ sys.exit(exit_code) [cli.py:1165]
```

## Scope Creep

None detected. All changes are scoped to ship loop requirements. The only file outside the core ship implementation that was modified is `pipeline/__init__.py` (added `create_ship_pipeline` to the package's public exports), which is the expected pattern.

## Files Changed (12 implementation files + tests)

| File | Changes |
|------|---------|
| `cli.py` | `--ship` flag, `run_ship_pipeline()`, `_detect_parent_branch()`, ship routing in `main()`, `run_resume()`, `run_manifest()`, ship in `prompt_for_mode()`, ship fields in `save_session()`, ship display in `format_session_summary()` |
| `pipeline/loader.py` | `create_ship_pipeline()` factory with 3 stages |
| `pipeline/__init__.py` | Export `create_ship_pipeline` |
| `hooks.py` | `ship_before_stage()`, `ship_after_stage()`, `_collect_stage_summary()` |
| `stats.py` | `ship_loops` field, `create_ship_event_handler()`, `print_summary()` ship display |
| `notify.py` | `notify_ship_complete()` |
| `manifest.py` | `ship: bool = False` field in `BuildManifest`, parsed from frontmatter |
| `prompts/shipping/clean.md` | 7-task clean stage prompt |
| `prompts/shipping/test.md` | 4-task test stage prompt |
| `prompts/shipping/rebase.md` | Single-context-window rebase prompt with PR/merge landing |
