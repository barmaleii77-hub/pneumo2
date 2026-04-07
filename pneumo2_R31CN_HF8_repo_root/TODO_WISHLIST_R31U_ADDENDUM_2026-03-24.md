# TODO / Wishlist addendum — R31U (2026-03-24)

## Closed by R31U
- Startup degenerate placeholder meshes no longer poison `pyqtgraph.opengl.MeshData` normals with an `invalid value encountered in divide` warning before the first real frame.
- Exported animator bundle geometry now carries explicit `road_width_m` supplementation when absent, so healthy bundles stop normalizing a consumer-side fallback warning as routine behavior.
- Desktop Animator startup logs are cleaner on current Qt6/PySide builds: deprecated high-DPI attributes and deprecated integer alignment overloads are removed from the normal path.

## Still open after R31U
- Need a fresh live Windows SEND bundle from R31U to confirm the warning cleanup in practice.
- Need measured Windows/browser perf acceptance.
- Need solver-points completeness / cylinder packaging contract for fully faithful 3D mechanics.
