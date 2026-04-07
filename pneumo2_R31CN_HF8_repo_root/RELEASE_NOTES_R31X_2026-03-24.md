# Release notes — R31X (2026-03-24)

## What this patch fixes

### 1) Dense road surface mesh drift in Desktop Animator
The earlier R31S/R31T/R31V fixes stabilized the visible wire-grid and cross-bars, but the **dense shaded road surface** still rebuilt its longitudinal rows from a fresh per-frame `linspace(s_min, s_max, n_long)`.

That left one more real drift path:
- the wire-grid could look better,
- but the shaded triangle rows of the road surface still changed spacing/phase with the playback window,
- so users could still see the *road mesh itself* drift over the same relief.

R31X fixes that by switching the dense surface rows to **world-anchored, bundle/view-stable longitudinal spacing** instead of per-frame local linspace sampling.

### 2) Cylinder / rod / piston visual inversion
The previous packaging layer still had two consumer-side mistakes:
- piston motion followed the wrong stroke direction;
- the visible cylinder body was drawn along the full `cyl*_top -> cyl*_bot` axis, which made the body appear anchored on the arm side too.

R31X restores the required semantics from project context and contract docs:
- **`cyl*_top` = frame / body side**
- **`cyl*_bot` = arm / rod side**
- **`stroke_pos` = rod extension**

Visual split is now rendered as:
- `body = top -> piston_plane`
- `rod = piston_plane -> bot`

The piston plane now moves toward the cap/frame side when rod extension grows, and piston markers are no longer kept permanently hidden when valid piston centers exist.

## Files changed
- `pneumo_solver_ui/desktop_animator/app.py`
- `pneumo_solver_ui/desktop_animator/geom3d_helpers.py`
- `tests/test_r44_cylinder_packaging_contract_and_animator.py`
- `tests/test_r45_stable_surface_mesh_spacing_and_animator.py`
- `01_PARAMETER_REGISTRY.md`
- `DATA_CONTRACT_UNIFIED_KEYS.md`
- `docs/11_TODO.md`
- `docs/12_Wishlist.md`
- `docs/WISHLIST.json`
- release metadata (`VERSION.txt`, `pneumo_solver_ui/release_info.py`, `release_tag.json`, `BUILD_INFO_LATEST.txt`, `RELEASE_NOTES_LATEST.txt`)

## Validation
- `py_compile`: PASS
- `compileall`: PASS
- targeted pytest slice: PASS

## Still open after R31X
- Live Windows acceptance on a fresh SEND bundle is still required to confirm:
  1. the *surface mesh* no longer drifts, not just the cross-bars;
  2. cylinders visually read as **body on frame / rod on arm** across all 4 corners and both channels.
