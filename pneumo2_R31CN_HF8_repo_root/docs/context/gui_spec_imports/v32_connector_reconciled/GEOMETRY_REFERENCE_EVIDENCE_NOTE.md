# Geometry Reference Evidence Note

Date: 2026-04-17

Scope: `PB-001`, `PB-008`, `RGH-018`, `OG-001`, `OG-002`, `OG-006`.

Status: V32-12 geometry reference evidence contracts accepted for lane
integration. This is documentation/provenance acceptance, not a runtime closure
claim for `OG-001`, `OG-002` or `OG-006`.

Accepted proof shape:

- Desktop Geometry Reference builds current suspension, cylinder, spring,
  component-fit and parameter-guide snapshots from repo canon/defaults.
- Selected `anim_latest` JSON/NPZ artifacts are loaded as explicit current or
  historical artifact contexts, with stale/missing states surfaced rather than
  rebound silently to latest workspace data.
- Geometry acceptance evidence is generated from solver-point artifacts and
  keeps `MISSING`, `PASS`, `WARN` and `FAIL` states explainable.
- Road-width evidence prefers explicit artifact metadata and keeps missing
  `road_width_m` visible as a gap warning instead of deriving it silently in
  Animator/viewer consumers.
- Cylinder packaging passport evidence compares base/reference state against
  export/runtime passport state and preserves the no-fabricated-geometry policy.
- Diagnostics handoff writes `geometry_reference_evidence.json` into workspace
  exports and `latest_geometry_reference_evidence.json` into send-bundle
  sidecar space, so future SEND bundles can name the geometry proof path.

Targeted test command:

```powershell
python -m pytest tests/test_desktop_geometry_reference_center_contract.py tests/test_geometry_acceptance_release_gate.py tests/test_anim_latest_geometry_contract_gate.py tests/test_geometry_acceptance_web_and_bundle.py tests/test_visual_consumers_geometry_strict.py -q
```

Result: `40 passed`.

Non-claims:

- `OG-001` remains open until a named release bundle carries full
  hardpoints/solver-points truth, geometry acceptance and anim export
  validation for the release candidate.
- `OG-002` remains open until cylinder packaging passports are complete enough
  to allow full body/rod/piston meshes.
- `OG-006` remains an imported-layer/runtime-proof open question until the
  release candidate names the live artifact path, SEND-bundle entry, source
  layer and test ID that prove the imported reference boundary.
- This note does not alter solver physics, Animator geometry, optimizer logic,
  measured performance traces or Windows runtime visual acceptance.
