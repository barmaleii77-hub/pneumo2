# PneumoApp v6_73 — patch notes

## P0 fixes (stability / diagnostics)

- Fixed crash/exit diagnostics autosave: `pneumo_solver_ui/crash_guard.py` no longer references undefined `REPO_ROOT`.
  - This restores autosave bundle generation on normal exit (atexit) and on unhandled exceptions.

- Packaging cleanup: removed `__pycache__` folders and `*.pyc`/`*.pyo` from the release tree.
  - Less noise in archives and fewer chances of path/encoding issues.

## Verification performed (headless)

- `python -m compileall` over `pneumo_solver_ui`.
- `python -m pneumo_solver_ui.tools.mech_energy_smoke_check --t_end_max 0.05`.
- `python -m pneumo_solver_ui.tools.preflight_gate`.
- `python -m pneumo_solver_ui.tools.run_autotest --level quick`.

## Notes

- Source of truth for scheme remains: `pneumo_solver_ui/PNEUMO_SCHEME.json` (derived from "Пневмосхема исправленная2").
- No feature work / UI redesign performed in this patch; only bugfix + packaging hardening.
