# RELEASE NOTES — R31BE — 2026-03-28

## Fixed
- Optimization page no longer crashes with `NameError: sanitize_optimization_inputs`.
- `pneumo_solver_ui/pneumo_ui_app.py` now imports `sanitize_optimization_inputs` from `pneumo_solver_ui.optimization_input_contract`.

## Regression guard
- Added `tests/test_r31be_optimization_import_guard.py` to statically enforce that both UI optimization entrypoints import `sanitize_optimization_inputs` whenever they use it.

## Scope
- This is a narrow runtime blocker hotfix. Optimization defaults, stage semantics, suite sanitization, and aggregate-metric synthesis remain unchanged from R31BD.
