# Release notes — R9 (2026-03-17)

Base:
- donor runtime: uploaded `PneumoApp_v6_80_R176_WINDOWS_RELEASE_2026-03-17_final.zip`
- incorporated useful fixes/behaviour from `R8` path-recovery branch

## Integrated useful pieces
- canonical package-context dynamic loading helper (`module_loading.py`) from the uploaded final release
- geometry acceptance / solver-point verification toolchain from the uploaded final release
- stale project path recovery from R8 (`project_path_resolution.py`)

## Removed harmful pieces
- removed runtime `.orig` backup sources:
  - `model_pneumo_v8_energy_audit_vacuum_patched_smooth_all.py.orig`
  - `model_pneumo_v9_mech_doublewishbone.py.orig`
  - `model_pneumo_v9_mech_doublewishbone_worldroad.py.orig`

## Fixed in R9
1. **Model/optimizer stale path recovery** in active UI loaders (`app.py`, `pneumo_ui_app.py`).
2. **Optimizer-side stale model path recovery** in `opt_worker_v3_margins_energy.py`.
3. **worldroad package import** now prefers canonical package-local `road_surface` import.
4. **Windows clipboard robustness**:
   - retry `OpenClipboard`
   - PowerShell fallback runs in `-STA`
   - send GUI gives a clearer message when only text-path fallback succeeded.

## Diagnostics verdict
- SEND bundle integrity: OK
- animator data completeness in the inspected manual bundle: insufficient (`anim_latest` missing)
- stale optimizer path: confirmed in diagnostics and addressed in R9

## Verification
- `compileall`: OK
- targeted pytest: **42 passed**
