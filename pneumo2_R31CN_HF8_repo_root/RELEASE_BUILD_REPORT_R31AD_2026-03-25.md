# Release build report — R31AD (2026-03-25)

`PneumoApp_v6_80_R176_R31AD_2026-03-25`

## Base

- input source tree: `PneumoApp_v6_80_R176_R31AC_2026-03-25.zip`
- evidence bundle analysed: `01798083-cb6d-412d-addc-fc7739be1301.zip`

## Root-cause summary

The analysed bundle contained valid road/export assets, but Desktop Animator failed on the first frame with:

- `TypeError`
- `TypeError("Car3DWidget._circle_line_vertices() missing 1 required positional argument: 'self'")`

This was a consumer-side crash in `Car3DWidget._circle_line_vertices`, not a missing-road export defect.

## Code changes

- fixed static helper signature in `pneumo_solver_ui/desktop_animator/app.py`;
- made piston-ring polyline rendering fail-soft instead of frame-fatal;
- synced ring-editor defaults in `pneumo_solver_ui/ui_scenario_ring.py` to the latest exported ring scenario;
- updated suite selection UX in `pneumo_solver_ui/pneumo_ui_app.py` and legacy `pneumo_solver_ui/app.py`;
- updated release metadata and TODO/Wishlist addenda.

## Validation executed

- `python -m py_compile` on modified Python files
- `python -m compileall -q pneumo_solver_ui`
- `pytest -q` on:
  - `tests/test_r31ac_desktop_animator_corner_front_staticmethod.py`
  - `tests/test_r31ad_desktop_animator_circle_line_vertices_staticmethod.py`
  - `tests/test_r31ad_ring_editor_user_defaults.py`
  - `tests/test_r31ad_suite_selection_can_be_empty.py`
  - `tests/test_r44_cylinder_packaging_contract_and_animator.py`
  - `tests/test_r46_cylinder_housing_shell_honesty.py`
  - `tests/test_r47_cylinder_visual_layers_readability.py`
  - `tests/test_r22_solver_points_frame_plane_and_meta.py`
  - `tests/test_r24_contact_patch_and_cylinder_helpers.py`
  - `tests/test_geom3d_helpers_axes_contract.py`

## Included release artifacts

- `BUILD_INFO_PneumoApp_v6_80_R176_R31AD_2026-03-25.txt`
- `RELEASE_NOTES_R31AD_2026-03-25.md`
- `RELEASE_BUILD_REPORT_R31AD_2026-03-25.md`
- `BUNDLE_ANALYSIS_R31AC_FIRST_FRAME_CRASH_AND_RING_DEFAULTS_2026-03-25.md`
- `BUNDLE_ANALYSIS_R31AC_FIRST_FRAME_CRASH_AND_RING_DEFAULTS_2026-03-25.json`
- `TODO_WISHLIST_R31AD_ADDENDUM_2026-03-25.md`
- `CHANGED_FILES_R31AD_2026-03-25.txt`
