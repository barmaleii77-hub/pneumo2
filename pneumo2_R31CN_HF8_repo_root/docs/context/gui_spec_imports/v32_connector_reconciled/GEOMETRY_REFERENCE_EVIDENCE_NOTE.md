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
- Health and offline inspect surfaces now prefer producer-owned
  `geometry_acceptance_report.json` when it is present in SEND bundles, and
  preserve `inspection_status`, `truth_state_summary`, `missing_fields`,
  `warnings`, `producer_owned` and `no_synthetic_geometry`.
- Road-width evidence prefers explicit artifact metadata and keeps missing
  `road_width_m` visible as a gap warning instead of deriving it silently in
  Animator/viewer consumers.
- Cylinder packaging passport evidence compares base/reference state against
  export/runtime passport state and preserves the no-fabricated-geometry policy.
- Cylinder packaging passport evidence also compares
  `CYLINDER_PACKAGING_PASSPORT.json` against `meta.packaging` hash lineage;
  missing or stale passport hashes remain `mismatch` and keep producer
  readiness reasons open.
- Diagnostics handoff writes `geometry_reference_evidence.json` into workspace
  exports and `latest_geometry_reference_evidence.json` into send-bundle
  sidecar space, so future SEND bundles can name the geometry proof path.
- Diagnostics/send-bundle readiness now carries artifact freshness reasons
  (`artifact_freshness_missing`, `artifact_freshness_stale`) together with
  packaging and geometry acceptance reasons, so legacy partial sidecars cannot
  masquerade as complete evidence.

Targeted test command:

```powershell
python -m pytest tests/test_desktop_geometry_reference_center_contract.py tests/test_geometry_acceptance_release_gate.py tests/test_anim_latest_geometry_contract_gate.py tests/test_geometry_acceptance_web_and_bundle.py tests/test_visual_consumers_geometry_strict.py -q
```

Result: `40 passed`.

Stabilization addendum:

```powershell
python -m pytest tests/test_desktop_geometry_reference_center_contract.py tests/test_geometry_acceptance_release_gate.py tests/test_anim_latest_geometry_contract_gate.py tests/test_geometry_acceptance_web_and_bundle.py tests/test_visual_consumers_geometry_strict.py tests/test_geometry_reference_packaging_passport_drift.py tests/test_health_report_inspect_send_bundle_anim_diagnostics.py -q
```

Result: `50 passed`.

Additional accepted checks:

- `tests/test_geometry_reference_packaging_passport_drift.py` proves passport
  hash drift between runtime file and `meta.packaging` remains a mismatch.
- `tests/test_health_report_inspect_send_bundle_anim_diagnostics.py` proves
  health/inspect preserve `geometry_acceptance_report` `MISSING`, `WARN` and
  `FAIL` states without recomputing or flattening producer truth.

Merge-ready producer truth closure snapshot:

- Combined producer-side verification now keeps geometry reference, visual
  consumers, diagnostics SEND evidence, health reports and offline inspection
  aligned to producer-owned `anim_latest`, packaging passport and
  geometry-acceptance artifacts.
- Geometry consumers must preserve producer states such as `inspection_status`,
  `truth_state_summary`, `missing_fields`, `warnings`, `producer_owned` and
  `no_synthetic_geometry`; they must not flatten `MISSING`, `WARN` or `FAIL`
  into a fabricated PASS.
- Incomplete cylinder packaging remains acceptable only as explicit
  `axis_only_honesty_mode` WARN/degraded evidence; complete full-mesh geometry
  still requires a matching complete passport.

Combined verification command:

```powershell
python -m py_compile pneumo_solver_ui\anim_export_contract.py pneumo_solver_ui\npz_bundle.py pneumo_solver_ui\geometry_acceptance_contract.py pneumo_solver_ui\tools\validate_anim_export_contract.py pneumo_solver_ui\tools\health_report.py pneumo_solver_ui\tools\inspect_send_bundle.py pneumo_solver_ui\tools\send_bundle_evidence.py pneumo_solver_ui\tools\make_send_bundle.py
python -m pytest tests\test_anim_latest_solver_points_contract_gate.py tests\test_anim_export_contract_gate.py tests\test_r52_anim_export_contract_blocks.py tests\test_geometry_acceptance_release_gate.py tests\test_r31bn_cylinder_truth_gate.py tests\test_v32_desktop_animator_truth_contract.py tests\test_geometry_reference_packaging_passport_drift.py tests\test_desktop_geometry_reference_center_contract.py tests\test_anim_latest_geometry_contract_gate.py tests\test_geometry_acceptance_web_and_bundle.py tests\test_visual_consumers_geometry_strict.py tests\test_health_report_inspect_send_bundle_anim_diagnostics.py tests\test_v32_diagnostics_send_bundle_evidence.py tests\test_r31ci_send_bundle_helper_runtime_contract.py tests\test_r32_triage_and_anim_sidecars.py -q
```

Result: `111 passed`.

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
