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
