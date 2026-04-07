# Build report R31AS (2026-03-27)

## Scope
- Desktop Animator auxiliary pane playback cadence restore
- 3D solver-truth speed/acceleration arrows restore
- Regression tests sync with current display-rate playback architecture

## Verification
- py_compile: PASS
- targeted pytest slice: 25 passed

## Changed areas
- `pneumo_solver_ui/desktop_animator/app.py`
- `pneumo_solver_ui/release_info.py`
- `release_tag.json`
- `VERSION.txt`
- `BUILD_INFO_LATEST.txt`
- `RELEASE_NOTES_LATEST.txt`
- `RELEASE_NOTES_R31AS_2026-03-27.md`
- `RELEASE_BUILD_REPORT_R31AS_2026-03-27.md`
- `TODO_WISHLIST_R31AS_ADDENDUM_2026-03-27.md`
- tests updated/added around animator cadence and solver-truth vectors
