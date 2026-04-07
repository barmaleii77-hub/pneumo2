# Release notes — R31BT (2026-03-31)

## Focus
Next wishlist step on the explicit contract path: materialize separate road-parameter contract artifacts for Web UI and Desktop Animator, instead of treating road readiness as an implicit side effect.

## Changes
- Added `road_contract_web.json` alongside `anim_latest.npz`.
- Added `road_contract_desktop.json` alongside `anim_latest.npz`.
- `export_anim_latest_bundle()` now supplements nested `meta.geometry` with explicit service/derived `road_width_m` before writing `anim_latest`, so consumer-side road contracts can close without hidden runtime fallback.
- `meta.anim_export_contract_artifacts` now registers both road-contract files.
- Run-artifacts diagnostics, send-bundle diagnostics and triage markdown now surface both consumer-specific road-contract artifacts.

## Why
- Wishlist / CAN-REQ-010 requires road parameters to be validated separately for Web UI and Desktop Animator.
- The evidence expected for this gap is explicit `road_contract_web.json` and `road_contract_desktop.json` on the live build.
- This step keeps the contract honest: if road traces are missing, the failing consumer is named directly; if `road_width_m` is only derivable, that is surfaced explicitly.

## Acceptance
- targeted pytest green
- py_compile PASS
- compileall PASS
