# Release Notes — R21

Release: `PneumoApp_v6_80_R176_WINDOWS_CLEAN_R21_2026-03-19`

## Fixed
- Desktop Animator no longer crashes on explicit trapezoid hardpoint solver-point kinds introduced by R20.
- `solver_points_contract.point_cols()` now accepts the optional kinds:
  - `lower_arm_frame_front/rear`
  - `lower_arm_hub_front/rear`
  - `upper_arm_frame_front/rear`
  - `upper_arm_hub_front/rear`
- `DataBundle.point_xyz()` now warns and degrades gracefully on unknown kinds instead of killing the whole animator frame update.

## Contract policy
- Baseline required solver-point contract is unchanged for older bundles.
- Optional trapezoid branch triplets are validated when present, but are not forced for legacy bundles.

## User-visible effect
- Opening an `anim_latest.npz` bundle produced by R20 should no longer die on first frame update with `ValueError: Unknown solver-point kind: 'lower_arm_frame_front'`.
