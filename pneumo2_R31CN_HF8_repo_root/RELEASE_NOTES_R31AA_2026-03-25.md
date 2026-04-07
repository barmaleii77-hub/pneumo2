# Release notes — R31AA (2026-03-25)

## Release
`PneumoApp_v6_80_R176_R31AA_2026-03-25`

## What this patch targets
This patch deliberately focuses on the **idle CPU tail in the Web UI**.
It does **not** try to mix another round of cylinder / Qt / road-visual changes into the same release.

## Root cause recheck
A fresh code recheck found two browser-side problems that can keep CPU busy even after detail-run / stop playback:

1. **Hidden Streamlit tabs still looked “visible” to the old iframe guard.**
   The old `__frameInParentViewport()` logic checked only iframe position in the parent viewport.
   For collapsed / hidden tab slots this is not enough: a `0x0` iframe near the origin can still satisfy the old coordinate-only condition.
   Result: follower iframes in hidden tabs kept polling as if they were visible.

2. **Some heavy widgets could stack parallel wake loops.**
   `mech_anim`, `mech_car3d`, and `pneumo_svg_flow` had wake paths (`storage`, `focus`, `visibilitychange`) that could schedule a new RAF/timeout loop without cancelling an already pending one.
   Result: post-run browser CPU could stay elevated because more than one loop chain survived at the same time.

## What changed

### Browser iframe visibility / idle gating
Applied to follower components and inline HTML widgets:
- zero/tiny iframe rect now counts as off-screen;
- `clientWidth/clientHeight≈0` now counts as off-screen;
- CSS-hidden iframe (`display:none`, `visibility:hidden`, `opacity:0`) now counts as off-screen;
- paused visible idle polling is slower than before.

Updated files:
- `pneumo_solver_ui/components/corner_heatmap_live/index.html`
- `pneumo_solver_ui/components/mech_anim/index.html`
- `pneumo_solver_ui/components/mech_anim_quad/index.html`
- `pneumo_solver_ui/components/mech_car3d/index.html`
- `pneumo_solver_ui/components/minimap_live/index.html`
- `pneumo_solver_ui/components/playhead_ctrl/index.html`
- `pneumo_solver_ui/components/playhead_ctrl/index_unified_v1.html`
- `pneumo_solver_ui/components/pneumo_svg_flow/index.html`
- `pneumo_solver_ui/components/road_profile_live/index.html`
- `pneumo_solver_ui/app.py`
- `pneumo_solver_ui/pneumo_ui_app.py`

### Single-flight schedulers for high-cost browser loops
Added explicit cancel/re-schedule helpers so wakeups cannot create parallel loop chains:
- `mech_anim` → `__clearScheduledTick / __scheduleTick / __wakeTick`
- `mech_car3d` → `__clearScheduledRender / __scheduleRender / __wakeRender`
- `pneumo_svg_flow` → `__clearScheduledLoop / __scheduleLoop / __wakeLoop`

## Tests
- `py_compile`: PASS
- `compileall`: PASS
- targeted pytest: `11 passed`

## TODO / Wishlist refresh
Updated:
- `docs/11_TODO.md`
- `docs/12_Wishlist.md`
- `docs/WISHLIST.json`

## Still open
- Fresh **Windows SEND bundle** is still required to prove that Web UI idle CPU is actually gone on the live browser/driver stack.
- Browser-side wakeup counters / trace export are still desirable so future CPU regressions can be verified numerically.
