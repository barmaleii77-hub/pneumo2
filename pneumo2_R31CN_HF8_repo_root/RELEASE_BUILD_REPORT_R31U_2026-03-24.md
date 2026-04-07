# Release build report — R31U (2026-03-24)

## Input base
- Source release base: `PneumoApp_v6_80_R176_R31T_2026-03-24.zip`
- Checked live bundle: `3009ddbb-30a5-4a46-979e-dd2707a94a9c.zip`

## Bundle-driven findings that triggered R31U
- Bundle validation: OK
- Health report: OK
- Geometry acceptance: PASS
- Remaining warnings in bundle were limited to startup/runtime cleanliness issues:
  - Qt high-DPI deprecation warnings;
  - `QTableWidgetItem.setTextAlignment(int)` deprecation warning;
  - `MeshData invalid value encountered in divide` at Desktop Animator startup;
  - derived `road_width_m` fallback warning from Animator consumer side.

## Implemented fixes
- Replaced startup bootstrap road/contact meshes with empty meshdata.
- Removed deprecated Qt6 startup DPI attributes.
- Switched table alignment calls to `Qt.AlignmentFlag`.
- Added explicit exporter-side supplement of `meta.geometry.road_width_m` from canonical track/width when absent.

## Verification performed
- `python -m py_compile` on touched source files and new tests.
- `python -m compileall -q pneumo_solver_ui tests`
- targeted pytest slice covering:
  - release sync;
  - geometry contract/export source paths;
  - desktop animator startup/external panel contracts;
  - playback perf mode / road clamp / world-anchored grid / bundle cadence telemetry;
  - visual consumer strictness / anim_latest usability and geometry contract.

Result: **42 passed**.
