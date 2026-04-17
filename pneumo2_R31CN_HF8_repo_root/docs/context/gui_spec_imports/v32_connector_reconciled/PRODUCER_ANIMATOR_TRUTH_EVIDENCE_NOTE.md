# Producer Animator Truth Evidence Note

Date: 2026-04-17

Scope: `PB-001`, `RGH-001`, `RGH-002`, `RGH-003`, `RGH-018`, `OG-001`,
`OG-002`.

Status: V32-14/V32-09 producer and animator truth evidence contracts accepted
for lane integration. This is not a release closure claim for `OG-001` or
`OG-002`.

Accepted proof shape:

- `anim_latest` export requires the solver-points contract before writing the
  NPZ/pointer pair; broken triplets fail before consumer use.
- `anim_latest` metadata carries `solver_points`, `hardpoints` and `packaging`
  contract blocks with stable hashes.
- Export sidecars include validation, hardpoints source-of-truth,
  cylinder-packaging passport, geometry-acceptance report and capture/export
  manifest references.
- `anim_latest` metadata now exposes the complete
  `anim_export_contract_artifacts` surface: contract sidecar, validation
  JSON/MD, hardpoints source-of-truth, cylinder packaging passport, geometry
  acceptance JSON/MD, capture manifest and frame-budget evidence refs.
- `validate_anim_export_contract` accepts both `anim_latest` metadata and
  `anim_latest.contract.sidecar.json`; stale sidecar validation summaries and
  fake/fabricated geometry markers fail the same contract drift/no-fabrication
  gate as NPZ metadata.
- Geometry acceptance reports are producer-owned and explicitly mark
  `no_synthetic_geometry`.
- Partial cylinder packaging remains in `axis_only_honesty_mode`; full
  body/rod/piston meshes remain blocked until a complete packaging passport is
  present.
- Animator truth gates and truth badges consume the export contracts and keep
  incomplete cylinder packaging in warning/degraded mode instead of fabricating
  geometry.
- Analysis-to-animator context is loaded as a frozen `HO-008` source with hash
  checks and explicit blocking states on mismatch.

Targeted test command:

```powershell
python -m pytest tests/test_anim_latest_solver_points_contract_gate.py tests/test_anim_export_contract_gate.py tests/test_r52_anim_export_contract_blocks.py tests/test_geometry_acceptance_release_gate.py tests/test_r31bn_cylinder_truth_gate.py tests/test_v32_desktop_animator_truth_contract.py -q
```

Result: `36 passed`.

Stabilization addendum:

```powershell
python -m pytest tests/test_anim_latest_solver_points_contract_gate.py tests/test_anim_export_contract_gate.py tests/test_r52_anim_export_contract_blocks.py tests/test_geometry_acceptance_release_gate.py tests/test_r31bn_cylinder_truth_gate.py tests/test_v32_desktop_animator_truth_contract.py tests/test_geometry_reference_packaging_passport_drift.py -q
```

Result: `39 passed`.

Additional accepted checks:

- `tests/test_r52_anim_export_contract_blocks.py` covers sidecar CLI PASS,
  stale `validation` FAIL, and fake/fabricated geometry source FAIL.
- `tests/test_geometry_reference_packaging_passport_drift.py` keeps
  `CYLINDER_PACKAGING_PASSPORT.json` hash drift visible instead of treating a
  stale passport as current truth.

Merge-ready producer truth closure snapshot:

- Combined producer-side verification now covers `solver_points`, `hardpoints`,
  `packaging`, geometry acceptance, visual-consumer strictness,
  `anim_latest` sidecars, diagnostics/health/inspect evidence surfaces and
  R32 sidecar triage without GUI layout changes.
- GUI and diagnostics lanes remain consumers: they may read
  `anim_export_contract_artifacts`, validation summaries, packaging passports
  and geometry-acceptance reports, but must not fabricate missing solver,
  hardpoint or cylinder geometry truth.
- Axis-only honesty mode stays a reported WARN/degraded state for incomplete
  cylinder packaging; it is not permission to render full body/rod/piston mesh
  geometry without a complete passport.

Combined verification command:

```powershell
python -m py_compile pneumo_solver_ui\anim_export_contract.py pneumo_solver_ui\npz_bundle.py pneumo_solver_ui\geometry_acceptance_contract.py pneumo_solver_ui\tools\validate_anim_export_contract.py pneumo_solver_ui\tools\health_report.py pneumo_solver_ui\tools\inspect_send_bundle.py pneumo_solver_ui\tools\send_bundle_evidence.py pneumo_solver_ui\tools\make_send_bundle.py
python -m pytest tests\test_anim_latest_solver_points_contract_gate.py tests\test_anim_export_contract_gate.py tests\test_r52_anim_export_contract_blocks.py tests\test_geometry_acceptance_release_gate.py tests\test_r31bn_cylinder_truth_gate.py tests\test_v32_desktop_animator_truth_contract.py tests\test_geometry_reference_packaging_passport_drift.py tests\test_desktop_geometry_reference_center_contract.py tests\test_anim_latest_geometry_contract_gate.py tests\test_geometry_acceptance_web_and_bundle.py tests\test_visual_consumers_geometry_strict.py tests\test_health_report_inspect_send_bundle_anim_diagnostics.py tests\test_v32_diagnostics_send_bundle_evidence.py tests\test_r31ci_send_bundle_helper_runtime_contract.py tests\test_r32_triage_and_anim_sidecars.py -q
```

Result: `111 passed`.

Scoped PR / handoff inventory:

- Producer-truth merge scope covers runtime/export contracts:
  `pneumo_solver_ui/anim_export_contract.py`,
  `pneumo_solver_ui/npz_bundle.py` and
  `pneumo_solver_ui/geometry_acceptance_contract.py`.
- Validator and evidence surfaces in scope are
  `pneumo_solver_ui/tools/validate_anim_export_contract.py`,
  `pneumo_solver_ui/tools/health_report.py`,
  `pneumo_solver_ui/tools/inspect_send_bundle.py`,
  `pneumo_solver_ui/tools/send_bundle_evidence.py` and
  `pneumo_solver_ui/tools/make_send_bundle.py`.
- Contract tests in scope are the combined verification tests listed above,
  plus this documentation contract in `tests/test_gui_spec_docs_contract.py`.
- Evidence notes in scope are this note and
  `GEOMETRY_REFERENCE_EVIDENCE_NOTE.md`; Diagnostics remains an evidence
  consumer and warning surface unless a producer artifact is actually present.
- A neighboring GUI baseline workspace-page commit exists on `codex/work`, but
  it is outside producer truth closure and should be reviewed under GUI
  workspace-page scope, not as part of `solver_points` / `hardpoints` /
  packaging / geometry acceptance truth.

Non-claims:

- `OG-001` stays open until a named release bundle contains full
  hardpoints/solver-points truth artifacts, geometry acceptance and anim export
  validation for the release candidate.
- `OG-002` stays open until a complete cylinder packaging passport exists per
  cylinder and the truth gate permits full body/rod/piston meshes.
- Current accepted evidence includes contract tests and tmp-path generated
  artifacts, not a durable release SEND bundle.
- This lane does not alter optimizer objectives, solver physics, measured
  browser performance, viewport gating or diagnostics bundle closure.
