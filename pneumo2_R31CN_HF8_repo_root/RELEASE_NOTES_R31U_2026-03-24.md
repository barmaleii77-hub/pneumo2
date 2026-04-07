# Release notes — R31U (2026-03-24)

Product release: **PneumoApp_v6_80_R176_R31U_2026-03-24**

## Why R31U exists
R31U is a bundle-driven cleanup release after checking the first live R31T SEND bundle. The core road/FPS fixes from R31Q/R31R/R31S/R31T stayed in place, but the bundle still showed three remaining acceptance annoyances:

1. startup `RuntimeWarning: invalid value encountered in divide` in `pyqtgraph.opengl.MeshData`;
2. Animator-side `road_width_m` fallback warning because exporter left `meta.geometry` without explicit visual road width;
3. current Qt deprecation noise on Desktop Animator startup (`AA_EnableHighDpiScaling`, `AA_UseHighDpiPixmaps`, `QTableWidgetItem.setTextAlignment(int)`).

## What changed
- `pneumo_solver_ui/desktop_animator/app.py`
  - startup road/contact meshes now use truly empty meshdata instead of zero-area placeholder triangles;
  - deprecated high-DPI application attributes removed from Qt6 startup path;
  - table alignment calls switched to `Qt.AlignmentFlag` instead of deprecated integer overloads.
- `pneumo_solver_ui/data_contract.py`
  - added explicit exporter helper `supplement_animator_geometry_meta(...)`.
- `pneumo_solver_ui/pneumo_ui_app.py`
- `pneumo_solver_ui/app.py`
  - animator export meta now supplements `road_width_m` from canonical `track_m + wheel_width_m` when the bundle would otherwise force a runtime fallback.
- TODO / Wishlist / release metadata refreshed for R31U.

## Validation
- `py_compile`: PASS
- `compileall`: PASS
- targeted pytest slice: **42 passed**

## Remaining open items
- Need a fresh live Windows SEND bundle on R31U to verify that the startup warning trio and the derived-road-width warning are gone in practice.
- Measured Windows/browser perf acceptance and solver-points / cylinder packaging contract still remain open project work.
