# RELEASE BUILD REPORT — R31R (2026-03-24)

## Base
- Input source tree: `PneumoApp_v6_80_R176_R31Q_2026-03-24.zip`
- Diagnostic evidence: user bundle `4baf7ead-7cf9-47e7-9c54-50c85ef7c6ca.zip`
- Output release: `PneumoApp_v6_80_R176_R31R_2026-03-24`

## Root cause confirmed from bundle
- `anim_latest + road_csv`: usable / synced
- geometry acceptance: PASS
- real issue: 3D road rendering sampled outside available support at start/end of run
- consequence: repeated endpoint slices -> degenerate GL faces -> `MeshData invalid value encountered in divide` -> visual road corruption + avoidable playback cost

## Applied changes
1. Added `clamp_window_to_interpolation_support(...)` to `geom3d_helpers.py`.
2. Desktop Animator now clamps `s_min/s_max` to common support of `s_world`, `road_profile(center)`, `road_profile(left)`, `road_profile(right)`.
3. Added Car3D playback state + perf mode hooks.
4. Added lighter road mesh density tiers for `play` and `play_many`.
5. Updated release metadata and project TODO/Wishlist context.

## Verification
- `py_compile`: PASS
- targeted pytest: PASS (`17 passed`)
- offline bundle regression analysis: PASS

## Files
- `PYCHECKS_R31R_2026-03-24.log`
- `PYTEST_TARGETED_R31R_2026-03-24.log`
- `BUNDLE_ANALYSIS_R31Q_ROAD_SPEED_2026-03-24.md`
- `BUNDLE_ANALYSIS_R31Q_ROAD_SPEED_2026-03-24.json`
- `CHANGED_FILES_R31R_2026-03-24.txt`

## Acceptance not yet proven here
No live Windows runtime was available in this container, so final acceptance still depends on a fresh SEND bundle generated from `R31R` on the user machine.
