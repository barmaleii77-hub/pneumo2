# RELEASE BUILD REPORT — R31P (2026-03-24)

## Base
- Input archive: `PneumoApp_v6_80_R176_R31O_2026-03-23.zip`
- Evidence bundle: `SEND_20260324_005743_manual_bundle.zip` (duplicate payload also received as `f0a52e21-f3fc-4eb8-9e23-0ad2820bdec1.zip`)
- Output release tag: `PneumoApp_v6_80_R176_R31P_2026-03-24`

## Evidence extracted from the manual bundle
- Bundle validation: OK
- `anim_latest`: usable
- geometry acceptance: PASS
- Desktop Animator child process: repeated `OpenGL.error.GLError` during detached/floating 3D rendering and exit code `0xC0000409`
- strict loglint: false `non-monotonic seq` because UI and child animator reused the same session id but different pids

## Code fixes included
- `pneumo_solver_ui/desktop_animator/app.py`
  - keep the 3D GL dock attached during detached/tiled layout;
  - update startup warning text to match the new stability policy.
- `pneumo_solver_ui/tools/loglint.py`
  - strict seq validation is now keyed by `session_id + pid` when pid is available.
- `pneumo_solver_ui/release_info.py`
  - default release aligned with `VERSION.txt`.

## Documentation refreshed
- `RELEASE_NOTES_R31P_2026-03-24.md`
- `TODO_WISHLIST_R31P_ADDENDUM_2026-03-24.md`
- `docs/11_TODO.md`
- `docs/12_Wishlist.md`
- `docs/WISHLIST.json`

## Verification
- `PYCHECKS_R31P_2026-03-24.log`: PASS
- `PYTEST_TARGETED_R31P_2026-03-24.log`: PASS

## Known remaining open items
- repeat real Windows acceptance on the new R31P bundle to confirm detached side panels no longer crash Desktop Animator;
- canonical `road_width_m` in export/meta to eliminate SERVICE/DERIVED warning;
- measured Windows/browser performance acceptance;
- solver-points completeness / cylinder packaging contract.
