# Release notes — R31BS (2026-03-30)

## Focus
Next wishlist step on the truth-contract path: materialize exporter-owned hardpoints and cylinder packaging artifacts for anim_latest instead of relying on secondary summaries only.

## Changes
- Added `HARDPOINTS_SOURCE_OF_TRUTH.json` alongside `anim_latest.npz`.
- Added `CYLINDER_PACKAGING_PASSPORT.json` alongside `anim_latest.npz`.
- Kept existing `anim_latest.contract.sidecar.json` and validation artifacts.
- Exposed these truth-contract files in run-artifacts diagnostics, send-bundle diagnostics and triage markdown.

## Why
- Wishlist W0 / CAN-REQ-011 keeps pointing to explicit hardpoints and packaging truth as the next blocker-closing step.
- Consumers should see the exporter-owned SoT/passport directly, not infer them indirectly.

## Acceptance
- targeted pytest green
- py_compile PASS
- compileall PASS
