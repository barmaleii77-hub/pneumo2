# RELEASE BUILD REPORT — R31O (2026-03-23)

## Base
- Input archive: `PneumoApp_v6_80_R176_R31N_DESKTOP_FPS_PLAYBACK_LITEMODE_2026-03-23.zip`
- Output release tag: `PneumoApp_v6_80_R176_R31O_2026-03-23`

## Code fixes included
- `pneumo_solver_ui/scenario_ring.py`
  - raw ring tracks preserved for preview/summary;
  - periodic closure moved to separate closed arrays used by spline/export;
  - higher-order seam slope estimate + no-op path for already closed phased periodic SINE.
- `pneumo_solver_ui/ui_scenario_ring.py`
  - removed last active `use_container_width=True` in ring UI.
- `pneumo_solver_ui/release_info.py`
  - default release aligned with `VERSION.txt`.

## Documentation refreshed
- `RELEASE_NOTES_R31O_2026-03-23.md`
- `TODO_WISHLIST_R31O_ADDENDUM_2026-03-23.md`
- `docs/11_TODO.md`
- `docs/12_Wishlist.md`
- `docs/WISHLIST.json`
- `CHANGELOG.md`

## Verification
- `PYCHECKS_R31O_2026-03-23.log`: PASS
- `PYTEST_TARGETED_R31O_2026-03-23.log`: PASS (`14 passed`)

## Known remaining open items
- measured Windows browser performance acceptance;
- solver-points completeness / cylinder packaging contract;
- real Windows Qt/OpenGL visual acceptance on a fresh bundle.
