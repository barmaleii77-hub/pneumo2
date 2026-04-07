# RELEASE BUILD REPORT — R31S (2026-03-24)

## Source base
- Base release: `PneumoApp_v6_80_R176_R31R_2026-03-24`
- Output release: `PneumoApp_v6_80_R176_R31S_2026-03-24`
- Trigger: live Windows feedback on `R31R` — 3D FPS acceptable, but auxiliary windows looked almost frozen and the visible road wire-grid appeared to drift relative to the road.

## Root causes addressed
1. **Auxiliary-pane playback starvation**
   - `CockpitWidget.update_frame()` used a low-cadence scheduler and, in many-docks mode, refreshed only one fast/slow pane per due cycle via round-robin.
   - With a large visible dock set this made the 3D pane look healthy while the rest of the windows appeared visually stalled.

2. **Viewport-anchored road wire-grid**
   - Visible road cross-bars were selected from local mesh rows starting at the first visible row of the current road window.
   - As the road window advanced, the grid phase drifted relative to the road.

## Code changes
- `pneumo_solver_ui/desktop_animator/app.py`
  - auxiliary playback scheduler switched from single-pane round-robin starvation to capped group refresh for visible panes;
  - many-docks mode still lowers cadence / enables lighter overlays, but no longer pseudo-freezes the other windows;
  - road grid generation now passes world-anchored row selection into the visible wire-grid builder.
- `pneumo_solver_ui/desktop_animator/geom3d_helpers.py`
  - added `road_grid_rows_from_s_nodes(...)` for world-anchored cross-bar selection;
  - `road_grid_line_segments(...)` now accepts explicit `row_indices`.
- Docs / backlog / release metadata updated to `R31S`.

## Tests executed
- `py_compile` on changed Desktop Animator modules: **PASS**
- `compileall -q pneumo_solver_ui tests`: **PASS**
- targeted pytest slice: **14 passed**
  - `tests/test_r26_road_view_density_helpers.py`
  - `tests/test_r37_desktop_animator_perf_gating.py`
  - `tests/test_r39_desktop_animator_playback_perf_mode.py`
  - `tests/test_r40_road_window_clamp_and_3d_playback_perf.py`
  - `tests/test_r41_aux_playback_and_worldanchored_grid.py`
  - `tests/test_release_info_default_release_sync.py`
  - `tests/test_app_release_sync.py`

Logs:
- `PYCHECKS_R31S_2026-03-24.log`
- `PYTEST_TARGETED_R31S_2026-03-24.log`

## Honest status
`R31S` is a **code-level root-cause patch release** for the newly reported Animator issues.
It is **not** the final Windows acceptance proof by itself. A new live `SEND` bundle on `R31S` is still required to confirm:
- auxiliary panes stay visually alive during playback on the actual driver/runtime stack;
- road wire-grid no longer drifts relative to the road;
- 3D FPS remains acceptable after the scheduler change.
