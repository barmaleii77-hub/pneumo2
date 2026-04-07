# RELEASE BUILD REPORT — R31Q (2026-03-24)

## Base
- Input archive: `PneumoApp_v6_80_R176_R31P_2026-03-24.zip`
- Evidence bundle used for diagnosis: `SEND_20260324_005743_manual_bundle.zip`
- Output release tag: `PneumoApp_v6_80_R176_R31Q_2026-03-24`

## Why R31Q exists
- R31P localized the Windows crash-path correctly, but solved it by keeping live 3D docked.
- User requirement was stricter: the 3D panel must remain a separate detachable/movable/resizable window.
- Therefore R31P had to be reclassified as a workaround and replaced.

## Code changes included
- `pneumo_solver_ui/desktop_animator/app.py`
  - add `ExternalPanelWindow`;
  - host live GL 3D in a dedicated top-level window instead of floating `QDockWidget` mode;
  - keep menu toggle, move/resize and persistence for the external 3D window;
  - save/restore/close external panel windows together with main window state.
- `pneumo_solver_ui/tools/loglint.py`
  - keep pid-aware strict seq validation from R31P.
- `pneumo_solver_ui/release_info.py`
  - align default release with `VERSION.txt`.

## Documentation refreshed
- `RELEASE_NOTES_R31Q_2026-03-24.md`
- `TODO_WISHLIST_R31Q_ADDENDUM_2026-03-24.md`
- `docs/11_TODO.md`
- `docs/12_Wishlist.md`
- `docs/WISHLIST.json`

## Verification performed here
- `PYCHECKS_R31Q_2026-03-24.log`
- `PYTEST_TARGETED_R31Q_2026-03-24.log`

## Known remaining open items
- fresh Windows SEND-bundle on R31Q to verify the real runtime path;
- canonical `road_width_m` in export/meta;
- measured Windows/browser performance acceptance;
- solver-points completeness / cylinder packaging contract.
