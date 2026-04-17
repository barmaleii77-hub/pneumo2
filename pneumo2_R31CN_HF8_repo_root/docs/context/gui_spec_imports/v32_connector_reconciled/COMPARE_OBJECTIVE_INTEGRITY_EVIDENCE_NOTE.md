# Compare Objective Integrity Evidence Note

Date: 2026-04-17

Scope: `PB-007`, `PB-008`, `RGH-013`, `RGH-014`, `RGH-015`.

Status: V32-06/V32-08 compare and objective integrity contracts accepted for
lane integration. This is contract/provenance acceptance, not a runtime gap
closure claim.

Accepted proof shape:

- Optimization objective contracts persist selected objective stacks, hard
  gates, baseline policy and problem hashes into run directories.
- Resume/staged-resume paths reject or warn on objective-contract mismatch
  instead of silently rebinding to the current UI context.
- Run history surfaces current/historical/stale objective state with explicit
  contract hashes and mismatch reasons.
- Compare sessions carry explicit compare contracts, selected source hashes and
  mismatch banners.
- Compare viewer loading preserves inspect-only historical mode when the
  current workspace context does not match the selected bundle/session.
- Results Center may pass readonly `latest_compare_current_context.json` through
  `--current-context`; Compare Viewer consumes it only as
  `CompareSession.current_context_ref`, preserves `current_context_path`, shows
  `ready/missing/session` source status in `dock_compare_contract`, and exports
  that provenance in `compare_contract.json`.
- Qt compare surfaces keep dock object names and animation diagnostics
  discoverable without claiming new domain runtime behavior.

Targeted test command:

```powershell
python -m pytest tests/test_qt_compare_viewer_compare_contract.py tests/test_qt_compare_viewer_session_autoload_source.py tests/test_qt_compare_offline_npz_anim_diagnostics.py tests/test_qt_compare_viewer_dock_object_names.py tests/test_optimization_objective_contract.py tests/test_r31cw_optimization_run_history_objective_contract.py tests/test_optimization_baseline_source_history.py tests/test_optimization_resume_run_dir.py tests/test_optimization_staged_resume_run_dir.py -q
```

Result: `41 passed`.

Combined Compare/Results/Docs/Objective verification:

```powershell
python -m pytest tests/test_qt_compare_viewer_compare_contract.py tests/test_qt_compare_viewer_session_autoload_source.py tests/test_qt_compare_offline_npz_anim_diagnostics.py tests/test_qt_compare_viewer_dock_object_names.py tests/test_r64_qt_compare_viewer_workspace_layout_runtime.py tests/test_test_center_results_center_contract.py tests/test_gui_spec_docs_contract.py tests/test_optimization_objective_contract.py tests/test_r31cw_optimization_run_history_objective_contract.py tests/test_optimization_baseline_source_history.py tests/test_optimization_resume_run_dir.py tests/test_optimization_staged_resume_run_dir.py -q
```

Result: `72 passed`.

Non-claims:

- This note does not close `OG-003`, `OG-004`, `OG-005` or any visual/runtime
  acceptance gap.
- This note does not alter optimizer algorithms, solver physics, animator
  geometry or diagnostics SEND-bundle content.
- This note does not permit Compare Viewer to read or write optimizer runtime
  history, and it does not let compare contract data replace animator truth.
- Release movement for `RGH-013`, `RGH-014` and `RGH-015` remains evidence-bound:
  a release candidate must name its objective contract artifacts, compare
  contract/session artifacts and stale/current provenance proof.
