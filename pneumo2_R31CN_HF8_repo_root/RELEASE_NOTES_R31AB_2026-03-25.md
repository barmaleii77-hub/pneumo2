# Release notes — R31AB (2026-03-25)

## Release
`PneumoApp_v6_80_R176_R31AB_2026-03-25`

## What this patch targets
This patch deliberately stays on the **Web UI idle CPU / browser diagnostics** path.
It does **not** mix another round of cylinder / road / Qt changes into the same release.

## Context recheck
A full re-read of the current project context (`ABSOLUTE LAW`, TODO, Wishlist, R31AA release state) showed that the browser idle-CPU fix was still too narrow:
- R31AA hardened off-screen detection and single-flight scheduling for the heaviest trio only.
- Acceptance, however, still required **measured browser-side diagnostics**, not only feeling/Task Manager.
- Other follower widgets and inline HTML widgets still deserved the same wake-discipline and visibility policy so Web UI CPU could be checked end-to-end.

## What changed

### Browser-wide single-flight and off-screen policy
Applied the same `cancel -> reschedule -> wake` discipline to **all** Web UI follower components with their own loop path:
- `corner_heatmap_live`
- `minimap_live`
- `road_profile_live`
- `mech_anim_quad`
- `mech_anim`
- `mech_car3d`
- `pneumo_svg_flow`
- `playhead_ctrl`
- `playhead_ctrl/index_unified_v1`

Inline HTML widgets in `app.py` and `pneumo_ui_app.py` now follow the same policy.

### Browser perf registry / measurable diagnostics
Each follower component now writes a compact perf snapshot to localStorage under:
- `pneumo_perf_component::*`

Typical counters include:
- wakeups (`storage`, `focus`, `visibility`)
- duplicate-guard hits
- hidden / zero-size / CSS-hidden gating hits
- current loop kind (`raf` / `timeout`)
- idle polling interval
- render count / schedule counters

### Playhead perf overlay and JSON export
`playhead_ctrl` now has a user-facing browser perf overlay and a JSON export path.
This is the first concrete step toward bundle-grade numeric browser acceptance instead of guesswork.

## Validation
- `python -m py_compile`: PASS
- `python -m compileall -q .`: PASS
- JS syntax recheck for patched component script blocks: PASS
- targeted pytest: PASS (`23 passed`)

## TODO / Wishlist refresh
Updated:
- `docs/11_TODO.md`
- `docs/12_Wishlist.md`
- `docs/WISHLIST.json`

## Still open
- Fresh **Windows SEND bundle** is still required to prove that Web UI idle CPU is actually gone on the live browser/driver stack.
- If CPU tail still survives after R31AB, the next step is to inject the browser perf registry automatically into diagnostics/SEND bundle instead of relying only on manual JSON export.
