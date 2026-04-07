# Release build report — R31AC (2026-03-25)

## Release
`PneumoApp_v6_80_R176_R31AC_2026-03-25`

## Base
- built from: `PneumoApp_v6_80_R176_R31AB_2026-03-25.zip`
- patch type: bundle-driven hotfix

## Trigger
User-visible regression from latest Windows SEND bundle:
- Animator hangs
- road is not visible

Bundle inspection isolated the cause to a startup `TypeError` inside `Car3DWidget._corner_is_front` during `load_npz -> _update_frame(0)`.

## Changed files
- `pneumo_solver_ui/desktop_animator/app.py`
- `tests/test_r31ac_desktop_animator_corner_front_staticmethod.py`
- `docs/11_TODO.md`
- `docs/12_Wishlist.md`
- `docs/WISHLIST.json`
- `pneumo_solver_ui/release_info.py`
- `release_tag.json`
- `VERSION.txt`
- `BUILD_INFO_LATEST.txt`
- `BUILD_INFO_PneumoApp_v6_80_R176_R31AC_2026-03-25.txt`
- `RELEASE_NOTES_LATEST.txt`
- `RELEASE_NOTES_R31AC_2026-03-25.md`
- `BUNDLE_ANALYSIS_R31AB_ANIMATOR_CRASH_2026-03-25.md`
- `BUNDLE_ANALYSIS_R31AB_ANIMATOR_CRASH_2026-03-25.json`

## Verification
- `py_compile`: PASS
- `compileall`: PASS
- focused pytest slice: `22 passed`
- broader desktop-animator slice: `56 passed`

## Acceptance status
- container/static regression gate: PASS
- live Windows runtime acceptance: OPEN
