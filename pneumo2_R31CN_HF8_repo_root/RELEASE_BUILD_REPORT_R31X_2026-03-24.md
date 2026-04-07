# Release build report — R31X (2026-03-24)

## Source base
- Base tree: `PneumoApp_v6_80_R176_R31W_2026-03-24`
- New release: `PneumoApp_v6_80_R176_R31X_2026-03-24`

## Bundle-driven findings used for this patch
- Dense road surface `ds_long` on the received bundle varied from `0.067039 m` to `0.108870 m` with `686` distinct values across playback.
- `n_long` varied from `180` to `720` (`355` unique values) for the same bundle/view family.
- Cylinder packaging still violated the required visual semantics: old piston-position correlation versus `stroke_pos` had the wrong sign for this project, and the body was rendered all the way to the arm-side endpoint.

Detailed analysis artifacts:
- `BUNDLE_ANALYSIS_R31W_ROAD_SURFACE_AND_CYL_PACKAGING_2026-03-24.md`
- `BUNDLE_ANALYSIS_R31W_ROAD_SURFACE_AND_CYL_PACKAGING_2026-03-24.json`

## Checks executed

### Python checks
See `PYCHECKS_R31X_2026-03-24.log`
- `python -m py_compile ...` -> PASS
- `python -m compileall -q pneumo_solver_ui tests` -> PASS

### Targeted pytest slice
See `PYTEST_TARGETED_R31X_2026-03-24.log`
Executed:
- `tests/test_r24_contact_patch_and_cylinder_helpers.py`
- `tests/test_r26_road_view_density_helpers.py`
- `tests/test_r42_bundle_stable_road_grid_and_aux_cadence_metrics.py`
- `tests/test_r44_cylinder_packaging_contract_and_animator.py`
- `tests/test_r44_road_crossbars_exact_world_interp.py`
- `tests/test_r45_stable_surface_mesh_spacing_and_animator.py`
- `tests/test_active_generators_solver_points_canon.py`
- `tests/test_r22_solver_points_frame_plane_and_meta.py`
- `tests/test_geom3d_helpers_axes_contract.py`
- `tests/test_desktop_animator_gl_float_suppression.py`

Result:
- PASS (`34` checks in the selected slice)

## Packaging notes
- Version metadata updated to `R31X`.
- TODO / Wishlist / contract docs updated to reflect that road *surface* drift and cylinder body/rod semantics are now explicit acceptance gates.

## Acceptance status
This is a real code patch, not a workaround. However final acceptance is still **bundle-driven on live Windows runtime**.
