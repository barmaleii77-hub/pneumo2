# RELEASE BUILD REPORT — R31T (2026-03-24)

## Source base
- Base release: `PneumoApp_v6_80_R176_R31S_2026-03-24`
- Output release: `PneumoApp_v6_80_R176_R31T_2026-03-24`
- Trigger: latest live Windows feedback and bundle check on `R31S` — 3D FPS acceptable, but detached auxiliary panes still subjectively looked near-frozen and road wire-grid still appeared to move with a different speed/spacing than the road.

## Root causes addressed
1. **Road grid spacing still followed the instantaneous playback window**
   - `R31S` fixed cross-bar phase anchoring, but the actual spacing still came from `ds_long * cross_stride` inside each visible road window.
   - On the checked bundle the effective spacing ranged from **0.180905 m** to **1.059108 m** with **612** distinct rounded values, which is exactly the “grid speed relative to road” symptom.
   - `R31T` caches a bundle/view-stable spacing from nominal visible length + viewport bucket.

2. **Auxiliary pane cadence floor was still too low for real Windows perception**
   - `R31S` already refreshed groups instead of single-pane round-robin, but its cadence floors (`18/9`, `10/5`) could still look semi-frozen with many detached windows.
   - `R31T` raises the floor to `24/12` and `18/10`, while keeping lighter overlays and not reverting to starvation.

3. **Acceptance lacked pane-level cadence evidence**
   - Previous SEND bundles did not carry per-pane redraw cadence metrics for detached panes.
   - `R31T` adds `AnimatorAuxCadence` event telemetry for future bundle-side verification.

## Bundle-grounded reference numbers
- Checked bundle: `7a572387-4a18-4608-a2f3-d8986c69e809.zip`
- Release inside bundle: `PneumoApp_v6_80_R176_R31S_2026-03-24`
- R31S observed spacing min/max: `0.180905 m` / `1.059108 m`
- Example stable spacing targets with current R31T formula (same bundle speed profile):
  - viewport 960 px → `1.25 m`
  - viewport 1280 px → `0.95 m`
  - viewport 1600 px → `0.75 m`

## Code changes
- `pneumo_solver_ui/desktop_animator/geom3d_helpers.py`
  - added `stable_road_grid_cross_spacing_from_view(...)`
- `pneumo_solver_ui/desktop_animator/app.py`
  - added bundle-context road grid cache: `set_bundle_context(...)`
  - added `_stable_road_grid_cross_spacing(...)`
  - road wire-grid now uses stable bundle/view spacing instead of instantaneous `ds_long * cross_stride`
  - raised playback cadence floors for auxiliary panes
  - added `AnimatorAuxCadence` telemetry window emission
- tests / docs / release metadata updated to `R31T`

## Tests executed
- `py_compile` on changed modules/tests: **PASS**
- `compileall -q pneumo_solver_ui tests`: **PASS**
- targeted pytest slice: **15 passed**
  - `tests/test_release_info_default_release_sync.py`
  - `tests/test_app_release_sync.py`
  - `tests/test_r39_desktop_animator_playback_perf_mode.py`
  - `tests/test_r40_road_window_clamp_and_3d_playback_perf.py`
  - `tests/test_r41_aux_playback_and_worldanchored_grid.py`
  - `tests/test_r42_bundle_stable_road_grid_and_aux_cadence_metrics.py`
  - `tests/test_loglint_seq_pid_split.py`
  - `tests/test_desktop_animator_external_panel_state.py`

Logs:
- `PYCHECKS_R31T_2026-03-24.log`
- `PYTEST_TARGETED_R31T_2026-03-24.log`

## Honest status
`R31T` is a **code-level root-cause patch release** for the remaining `R31S` Animator misses.
It is **not** final Windows acceptance proof by itself. A new live `SEND` bundle on `R31T` is still required to confirm:
- detached auxiliary panes stay visibly live at runtime;
- road grid spacing remains stable relative to the road across the full playback;
- raised pane cadence does not regress acceptable 3D FPS.
