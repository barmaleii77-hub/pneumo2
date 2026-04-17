# Runtime Release Evidence Note

Date: 2026-04-17

Scope: `PB-005`, `PB-006`, `GAP-003`, `GAP-004`, `GAP-010`,
`RGH-011`, `RGH-012`, `RGH-019`, `OG-003`, `OG-004`, `OG-005`.

Status: V32-15 runtime evidence hard-gate contract accepted for lane
integration; runtime evidence and performance-gate contract accepted for the
full V32-15 targeted suite. This is not a release closure claim for `OG-003`,
`OG-004` or `OG-005`; closure still requires named measured runtime artifacts
from a real run/SEND bundle.

Accepted proof shape:

- `pneumo_solver_ui/runtime_evidence.py` validates measured runtime artifacts
  and hard-fails missing or failed evidence.
- `release_gate.py` exposes optional hard gates:
  `--require-browser-trace`, `--require-viewport-gating`,
  `--require-animator-frame-budget`, `--require-windows-runtime-proof`, and
  `--require-runtime-evidence`.
- Browser performance evidence is represented by `browser_perf_trace.json`,
  `browser_perf_registry_snapshot.json`, `browser_perf_contract.json`,
  `browser_perf_evidence_report.json`, and `browser_perf_comparison_report.json`.
- Viewport gating evidence is represented by `viewport_gating_report.json`
  with `release_gate=PASS`, zero hidden-surface updates and a trace reference.
- Animator frame-budget evidence is represented by
  `animator_frame_budget_evidence.json` with measured cadence and hidden-pane
  gating.
- Windows runtime proof is represented by `windows_runtime_proof.json`; it is
  tracked by the same validator but belongs to `OG-005` release closure.
- SEND bundle evidence hooks cover `BND-015`, `BND-016`, `BND-017` and
  `BND-019`; bundle manifest presence remains non-blocking by itself, while
  `release_gate.py` owns hard-fail enforcement through explicit requirement
  flags.
- Browser trace emission is explicit/export-driven. Runtime bridge support for
  `browser_perf_trace` is accepted, but normal snapshots do not continuously
  emit heavy trace payloads.

Compile smoke:

```powershell
python -m compileall pneumo_solver_ui\desktop_animator\app.py pneumo_solver_ui\runtime_evidence.py pneumo_solver_ui\browser_perf_artifacts.py pneumo_solver_ui\release_gate.py pneumo_solver_ui\tools\send_bundle_evidence.py pneumo_solver_ui\tools\make_send_bundle.py
```

Result: pass.

Historical narrow-slice command:

```powershell
python -m pytest tests/test_v32_runtime_evidence_gates.py tests/test_r31bu_browser_perf_artifacts.py tests/test_r78_animator_playback_speed_stability.py tests/test_r42_bundle_stable_road_grid_and_aux_cadence_metrics.py -q
```

Result: `47 passed`.

Targeted acceptance command:

```powershell
python -m pytest tests\test_r31bu_browser_perf_artifacts.py tests\test_v32_runtime_evidence_gates.py tests\test_v32_desktop_animator_truth_contract.py tests\test_v32_diagnostics_send_bundle_evidence.py tests\test_r42_bundle_stable_road_grid_and_aux_cadence_metrics.py tests\test_send_bundle_contract_helpers.py tests\test_r78_animator_playback_speed_stability.py tests\test_r37_desktop_animator_hidden_docks_skip_updates.py tests\test_r77_animator_user_regressions.py tests\test_r49_animator_layout_suspend_and_timer_budget.py tests\test_r51_animator_display_rate_and_idle_stop.py tests\test_r57_animator_timeline_interp_and_web_idle.py -q
```

Result: `95 passed`.

Latest `pytest --lf -q` status after the targeted acceptance sweep:
`26 failed, 1 passed`. The remaining failures are outside this lane: solver /
domain numerical assertions, animator visual/source-contract backlog, and
unrelated desktop contract work already present in the dirty worktree.

Current workspace probe:

```powershell
python -c "from pathlib import Path; from pneumo_solver_ui.runtime_evidence import validate_runtime_evidence_dir; print(validate_runtime_evidence_dir(Path('pneumo_solver_ui/workspace/exports'), require_browser_trace=True, require_viewport_gating=True, require_animator_frame_budget=True, require_windows_runtime=False)['hard_fail_count'])"
```

Result: `hard_fail_count=3` with hard failures for `browser_perf_trace`,
`viewport_gating`, and `animator_frame_budget`.

Non-claims:

- No measured `browser_perf_trace` is currently present in
  `pneumo_solver_ui/workspace/exports`.
- No current `viewport_gating_report.json` is present in
  `pneumo_solver_ui/workspace/exports`.
- No current `animator_frame_budget_evidence.json` is present in
  `pneumo_solver_ui/workspace/exports`.
- `OG-003` and `OG-004` stay open until a named SEND bundle contains measured
  trace and viewport-gating artifacts.
- This lane only accepts evidence adapters, hard gates and tests; it does not
  alter solver, optimizer, geometry or domain calculations.
