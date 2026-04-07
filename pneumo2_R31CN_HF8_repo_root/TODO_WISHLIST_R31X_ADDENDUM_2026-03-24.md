# TODO / Wishlist addendum — R31X (2026-03-24)

## Closed in R31X
- Dense road surface mesh no longer relies on per-frame local `linspace(s_min, s_max, n_long)`; longitudinal surface rows are now world-anchored and bundle/view-stable.
- Cylinder packaging no longer visually inverts the actuator semantics: body reads on frame-side, rod on arm-side, piston follows the project stroke convention.
- Contract docs now explicitly state the required visual law for `cyl*_top`, `cyl*_bot`, and `stroke_pos`.

## Still open
- Fresh Windows SEND bundle for R31X to confirm:
  - dense surface mesh drift is gone visually;
  - cylinders / rods / pistons are readable and stable on all corners;
  - no new GL/FPS regressions were introduced.
- After that: move forward into catalogue-aware Camozzi sizing / limits and static acceptance `поршень≈середина хода`.
