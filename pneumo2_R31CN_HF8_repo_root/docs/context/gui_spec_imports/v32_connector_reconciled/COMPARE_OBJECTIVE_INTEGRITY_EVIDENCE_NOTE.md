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
- Qt compare surfaces keep dock object names and animation diagnostics
  discoverable without claiming new domain runtime behavior.

Targeted test command:

```powershell
python -m pytest tests/test_qt_compare_viewer_compare_contract.py tests/test_qt_compare_viewer_session_autoload_source.py tests/test_qt_compare_offline_npz_anim_diagnostics.py tests/test_qt_compare_viewer_dock_object_names.py tests/test_optimization_objective_contract.py tests/test_r31cw_optimization_run_history_objective_contract.py tests/test_optimization_baseline_source_history.py tests/test_optimization_resume_run_dir.py tests/test_optimization_staged_resume_run_dir.py -q
```

Result: `41 passed`.

Non-claims:

- This note does not close `OG-003`, `OG-004`, `OG-005` or any visual/runtime
  acceptance gap.
- This note does not alter optimizer algorithms, solver physics, animator
  geometry or diagnostics SEND-bundle content.
- Release movement for `RGH-013`, `RGH-014` and `RGH-015` remains evidence-bound:
  a release candidate must name its objective contract artifacts, compare
  contract/session artifacts and stale/current provenance proof.
