# Bundle / symptom analysis — R31R auxiliary panes + road grid (2026-03-24)

## What was observed
- User report on live Windows run: **3D FPS OK**, but the remaining Animator windows looked **almost frozen** during playback.
- User also reported that the visible **road grid looked out of sync with the road itself**.

## What the bundle could and could not prove
- The SEND bundle confirmed the run was on `R31R` and still showed the expected `road_width_m` derived warning.
- The bundle did **not** contain a direct cadence metric for every detached auxiliary pane, so the freeze root cause had to be confirmed from source inspection against the reported runtime behaviour.

## Root cause 1 — auxiliary pane starvation
In `pneumo_solver_ui/desktop_animator/app.py`, `CockpitWidget.update_frame()` used the following policy during playback:
- `many_visible_budget` triggered once enough auxiliary docks were visible;
- fast/slow groups were reduced to very low cadence;
- in many-docks mode only **one** panel from a group was updated per due cycle via round-robin.

With a large visible dock set this made 3D remain smooth while the rest of the windows looked visually stalled.

## Root cause 2 — viewport-anchored road wire-grid
The visible road cross-bars were generated from local mesh rows starting at the first visible row of the current road window.
As the window moved forward in longitudinal `s`, that local row-zero anchor moved too, which made the wire-grid phase drift relative to the road.

## Fix direction in R31S
- Refresh visible auxiliary panes as **visible groups** at capped FPS instead of single-panel round-robin starvation.
- Keep many-docks mode as a lighter-overlays / capped-cadence mode, not as a pseudo-freeze mode.
- Anchor visible road cross-bars to world longitudinal `s`, so the grid follows the road rather than the viewport edge.
