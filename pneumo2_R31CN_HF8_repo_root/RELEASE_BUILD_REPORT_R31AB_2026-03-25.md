# Release build report — R31AB (2026-03-25)

## Release
`PneumoApp_v6_80_R176_R31AB_2026-03-25`

## Scope
Patch release over `R31AA` focused on **browser-side idle CPU hardening and measurable Web UI diagnostics**.

## Source basis
Base source tree: `PneumoApp_v6_80_R176_R31AA_2026-03-25`

## Main technical findings after recheck
- The original R31AA fix was correct but too narrow: the off-screen / single-flight policy should not live only in the heaviest trio of browser widgets.
- Measured acceptance was still missing. Without browser-side counters / export, future SEND bundles would again rely mostly on Task Manager or subjective user reports.
- Inline HTML widgets in `app.py` / `pneumo_ui_app.py` also needed the same wake-discipline so hidden/paused UI could not keep useless loops alive.

## Main code changes
1. Extended off-screen + single-flight scheduling to all follower components that own RAF/timeout loops.
2. Added browser perf registry snapshots (`pneumo_perf_component::*`) across those components.
3. Added playhead-side browser perf overlay and JSON export.
4. Updated TODO/Wishlist and release metadata for the measured-browser-acceptance path.

## Validation
- `python -m py_compile`: PASS
- `python -m compileall -q .`: PASS
- JS syntax recheck for patched HTML component script blocks: PASS
- `pytest -q tests/test_app_release_sync.py tests/test_pneumo_ui_app_no_bare_lock_expr.py tests/test_r26_streamlit_expander_stability.py tests/test_r29_embedded_html_idle_guards.py tests/test_r31g_detail_autorun_fresh_and_cpu_idle.py tests/test_r31aa_web_idle_visibility_and_scheduler.py tests/test_r31ab_web_ui_perf_registry_and_scheduler.py tests/test_root_app_manual_diag_download_flow_source.py tests/test_streamlit_use_container_width_compat_contract.py tests/test_streamlit_width_runtime_sources.py`: PASS (`23 passed`)

## Acceptance status
This build is a **code-level browser diagnostics/hardening step**.
It is **not yet final Windows acceptance**. A fresh SEND bundle with browser perf snapshot/export is still required to confirm that live Web UI CPU stays quiet after detail-run / stop playback.
