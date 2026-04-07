# Release build report — R31AA (2026-03-25)

## Release
`PneumoApp_v6_80_R176_R31AA_2026-03-25`

## Scope
Patch release over `R31Z` focused on browser-side idle CPU after calculations / stop playback.

## Source basis
Base source tree: `PneumoApp_v6_80_R176_R31Z_2026-03-24`

## Main technical findings
- Coordinate-only iframe viewport checks were insufficient for Streamlit tabs because hidden/collapsed iframe slots can still report a rect that passes a naive position test.
- Some heavy browser widgets had multiple wake paths that could schedule a new RAF/timeout chain without first cancelling the previous pending one.

## Main code changes
1. Off-screen / hidden iframe detection hardened across browser follower components.
2. Idle polling intervals increased for paused browser followers and inline HTML widgets.
3. Single-flight loop scheduling added to the highest-cost browser widgets.
4. Release metadata and TODO/Wishlist updated for the new browser-perf focus.

## Validation
- `python -m py_compile`: PASS
- `python -m compileall -q pneumo_solver_ui`: PASS
- `pytest -q tests/test_r29_embedded_html_idle_guards.py tests/test_r31g_detail_autorun_fresh_and_cpu_idle.py tests/test_r31aa_web_idle_visibility_and_scheduler.py`: PASS (`11 passed`)

## Artifacts
- `PYCHECKS_R31AA_2026-03-25.log`
- `PYTEST_TARGETED_R31AA_2026-03-25.log`
- `CHANGED_FILES_R31AA_2026-03-25.txt`

## Acceptance status
This build is a **code-level fix** for the identified Web UI idle-loop paths.
It is **not yet final Windows acceptance**. A fresh SEND bundle is still required to confirm that live browser CPU stays quiet after calculations and that hidden tabs really sleep.
