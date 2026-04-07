# Release notes — R31BU

## Focus
- Browser perf registry snapshot exporter from `playhead_ctrl` into `workspace/exports`.
- Canonical browser perf sidecars in diagnostics / send-bundle / triage.

## Included changes
- new module `pneumo_solver_ui/browser_perf_artifacts.py`
- `playhead_ctrl` sends explicit `browser_perf_snapshot` payload to Python on JSON export
- Streamlit UI persists browser perf snapshot to `workspace/exports/browser_perf_registry_snapshot.json` and `browser_perf_contract.json`
- run-artifacts / send-bundle / triage now surface browser perf snapshot + optional external browser trace file

## Notes
- This step closes the exporter/plumbing side of wishlist `W-203` without pretending that full measured Windows perf acceptance is already closed.
- Heavy browser trace capture is still an acceptance artifact: if `browser_perf_trace.trace|json|cpuprofile` is present in `workspace/exports`, diagnostics now surface it explicitly.
