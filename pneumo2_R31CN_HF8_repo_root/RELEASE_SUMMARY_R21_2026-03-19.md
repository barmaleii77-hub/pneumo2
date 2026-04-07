# Release Summary — R21

Release: `PneumoApp_v6_80_R176_WINDOWS_CLEAN_R21_2026-03-19`

## Scope
Desktop Animator hotfix for the R20 arm/trapezoid geometry update.

## Root cause fixed
R20 desktop animator requested explicit trapezoid hardpoints (`lower_arm_frame_front`, `lower_arm_frame_rear`, `lower_arm_hub_front`, `lower_arm_hub_rear`, `upper_arm_frame_front`, `upper_arm_frame_rear`, `upper_arm_hub_front`, `upper_arm_hub_rear`), but `solver_points_contract.point_cols()` still rejected them as unknown kinds. This raised `ValueError` during `load_npz()` / first frame update, so wheels and arms never reached the 3D scene update.

## Fix
- added optional known solver-point kinds for trapezoid branch hardpoints;
- kept the baseline required contract unchanged for older bundles;
- hardened `DataBundle.point_xyz()` to warn and return `None` instead of crashing on unknown kinds.

## Expected visible result
The desktop animator should stop crashing on `anim_latest.npz` bundles that already contain the new R20 hardpoint triplets, and wheels/arms should render again in 3D.
