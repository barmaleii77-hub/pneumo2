# RELEASE_NOTES_R31BN_2026-03-30

## What changed

### 1) Explicit anim export validation and sidecars
- `export_anim_latest_bundle()` now computes `anim_export_validation`.
- Export writes machine-checkable artifacts next to `anim_latest`:
  - `anim_latest.contract.sidecar.json`
  - `anim_latest.contract.validation.json`
  - `anim_latest.contract.validation.md`
- Pointer / trace diagnostics now expose validation level and truth readiness.

### 2) Desktop Animator honesty gate for cylinders
- Added `desktop_animator/cylinder_truth_gate.py`.
- Cylinder body/rod/piston meshes are enabled only when explicit per-cylinder packaging contract is complete.
- Otherwise Animator stays in axis-only honesty mode instead of drawing fabricated packaging geometry.
- Self-checks now surface per-cylinder truth-mode decisions.

### 3) SEND-bundle diagnostics visibility
- `make_send_bundle.py` now surfaces anim-export validation summary in diagnostics/triage context.
- Validation-level information is available to bundle inspection and health-report flows.

### 4) Optimization suite state normalization
- Stage bias normalization no longer pushes disabled/template rows below zero.
- Missing / NaN / duplicate suite row ids are repaired to stable UUIDs.
- Ring scenario editor now creates explicit ids for new suite rows.

## Validation executed
- `py_compile` on changed files: PASS
- `compileall` on `pneumo_solver_ui`, `pneumo_dist`, `tests`: PASS
- `pytest` targeted slice: 27 passed

## Notes
- This release is cumulative on top of the uploaded `R31BL` source tree.
- It folds in the uploaded R31BM anim-contract patch content, the Desktop Animator truth-gate files, and the suite-state patch draft after validation.
