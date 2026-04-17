# Diagnostics Release Evidence Note

Date: 2026-04-17

Scope: `WS-DIAGNOSTICS`, `PB-002`, `BND-018`, `RGH-006`, `RGH-007`,
`RGH-016`, `GAP-002`, `GAP-006`, `GAP-008`, `OG-005`.

Status: V32-11 diagnostics evidence contract accepted for lane integration,
with a named runtime SEND bundle proof attached below. This is still not a
full `OG-005` closure claim because adjacent analysis, geometry and perf
runtime evidence warnings remain visible. The Geometry Reference Center now
contributes a read-only `BND-018` handoff path, but this is partial evidence
surface coverage and not a producer-side geometry closure claim.

Implemented proof:

- SEND bundle finalization order is captured in `diagnostics/evidence_manifest.json`.
- Final triage is rewritten before health is built.
- `latest_send_bundle.zip`, `latest_send_bundle_path.txt`, and `latest_send_bundle.sha256` are refreshed after final health/validation/dashboard passes.
- `latest_evidence_manifest.json` records final latest ZIP SHA, pointer match, SHA sidecar match, trigger, collection mode, effective workspace, and helper Python provenance.
- `latest_send_bundle_inspection.json` and `latest_send_bundle_inspection.md` are refreshed by bundle finalization against `latest_send_bundle.zip`.
- Desktop Diagnostics Center state exposes machine-readable paths for latest ZIP, path pointer, SHA, health, triage, validation, evidence manifest, and clipboard status.
- `geometry/geometry_reference_evidence.json`,
  `workspace/exports/geometry_reference_evidence.json`, and
  `latest_geometry_reference_evidence.json` are recognized as `BND-018`
  Geometry Reference evidence.
- The Geometry Reference handoff payload carries `artifact_status`,
  `artifact_freshness_status`, `artifact_freshness_relation`,
  `geometry_acceptance_gate`, `road_width_status`, `road_width_source`,
  `packaging_status`, `packaging_mismatch_status`,
  `packaging_contract_hash`, `producer_artifact_status`,
  `producer_readiness_reasons`, component passport counts, and
  missing-evidence explanations for Diagnostics/Send Bundle consumption.
- Desktop Diagnostics Center surfaces the Geometry Reference handoff in its
  evidence handoff status and can open `latest_geometry_reference_evidence.json`
  directly from the Evidence tab.
- Geometry Reference Center remains `reader_and_evidence_surface` and
  `producer_owned=false`; it records `does_not_render_animator_meshes=true`.
- `diagnostics/evidence_manifest.json` tracks mandatory PB-002 evidence rows
  `BND-001`...`BND-006`, conditional evidence rows, HO-009 analysis handoff,
  runtime provenance and release-blocking missing-evidence warnings.
- Exit, crash and watchdog collection modes preserve trigger provenance.
- Health, validation and inspection surfaces carry missing evidence warnings
  instead of silently treating partial bundles as closed.

Targeted test command:

```powershell
python -m pytest tests/test_v32_diagnostics_send_bundle_evidence.py tests/test_health_report_inspect_send_bundle_anim_diagnostics.py tests/test_desktop_diagnostics_center_contract.py -q
```

Result: `33 passed`. Focused Geometry/Diagnostics producer-handoff
regression set: `45 passed`.

Focused Geometry/Diagnostics regression result: `87 passed`.

Runtime proof captured:

- ZIP: `send_bundles/SEND_20260417_083946_bundle.zip`
- Final latest SHA256: `67694d0c3e01ef7f30c4b1780729e4e74baf8d80b74419dddcd139fc0ec7c72a`
- Trigger / mode: `desktop_diagnostics_center` / `manual`
- Validation: `ok=True`, `errors=0`, `warnings=7`
- Health after final triage: `ok=False`, `notes=9`, preserving adjacent-workstream warnings.
- PB-002 required evidence: `pb002_missing_required_count=0`
- Latest pointer/SHA proof: `latest_zip_matches_original=True`, `latest_sha_sidecar_matches=True`, `latest_pointer_matches_original=True`
- Post-regression latest proof: after the `87 passed` focused Diagnostics run,
  `latest_send_bundle.zip`, `latest_send_bundle_path.txt`,
  `latest_send_bundle.sha256`, `latest_evidence_manifest.json` and
  `latest_send_bundle_inspection.json` still point to the same final manual ZIP
  and SHA256 above.
- Embedded evidence stage: `final_after_validation_dashboard`; latest sidecar proof stage: `latest_zip_sha_inspection_proof`.
- Latest inspection sidecars: `latest_send_bundle_inspection.json` points at `latest_send_bundle.zip`, carries matching `zip_sha256`, and reports health, validation, triage and evidence manifest present.
- HO-009 analysis sidecar proof: `latest_analysis_evidence_manifest.json` is
  present and embedded; current state is `analysis_handoff.status=WARN` with
  `result_context_state=MISSING`, so this is evidence presence, not analysis
  closure.
- BND-018 sidecar proof: `latest_geometry_reference_evidence.json` is embedded as
  `geometry/geometry_reference_evidence.json`; it carries
  `producer_artifact_status=missing`, `producer_evidence_owner=producer_export`,
  the required producer artifact list for `anim_latest`, packaging passport and
  geometry acceptance, `producer_next_action` for re-exporting producer evidence,
  producer readiness reasons such as `packaging_mismatch_not_match`,
  `consumer_may_fabricate_geometry=false`,
  `artifact_freshness_status=missing`, `artifact_freshness_relation=latest`,
  `road_width_status=derived_from_track_and_wheel_width`,
  `packaging_mismatch_status=mismatch`, and
  `geometry_acceptance_gate=MISSING`.
- Desktop center state refreshed: `latest_desktop_diagnostics_center_state.json` exposes latest ZIP, path pointer, SHA, health, triage, validation, evidence manifest and clipboard paths.

Geometry Reference / GAP evidence state:

- `GAP-002` packaging passport evidence is surfaced from
  `CYLINDER_PACKAGING_PASSPORT.json` and `meta.packaging` when producer
  artifacts provide them. Complete, axis-only and missing advanced-field
  counts stay visible; partial passports remain warnings and do not authorize
  consumer fabrication.
- `GAP-006` geometry acceptance evidence reads runtime NPZ/dataframe columns
  and solver-point triplets from the selected artifact. PASS/FAIL/MISSING rows,
  source path, timestamp/hash and scalar-vs-XYZ disagreement reasons stay in
  the handoff instead of being inferred silently.
- `GAP-008` road width evidence prefers explicit
  `meta.geometry.road_width_m`; derived base/reference values are shown as a
  declared fallback, and missing explicit/derived evidence keeps `GAP-008`
  open.
- Artifact freshness is explicit: current, historical, stale, missing and
  differs-from-latest relations are preserved through
  `artifact_freshness_status` and `artifact_freshness_relation`.
- Geometry Reference Center does not close `GAP-002`, `GAP-006`, or
  `GAP-008` by itself; it reports producer evidence, mismatches and gaps for
  Diagnostics to bundle.

Runtime proof command:

```powershell
python -m pneumo_solver_ui.tools.make_send_bundle --trigger desktop_geometry_reference_center --max_file_mb 80 --print_path
python -m pytest tests/test_v32_diagnostics_send_bundle_evidence.py tests/test_r53_send_bundle_final_health_after_triage.py tests/test_send_bundle_effective_workspace_projection.py tests/test_ui_autosave_bundle_contract.py tests/test_anim_latest_bundle_usability_diagnostics.py tests/test_health_report_inspect_send_bundle_anim_diagnostics.py tests/test_r31ci_send_bundle_helper_runtime_contract.py tests/test_desktop_diagnostics_center_contract.py tests/test_diagnostics_text_encoding_contract.py tests/test_diagnostics_entrypoint_summary_contract.py tests/test_send_bundle_gui_wrappers_contract.py tests/test_send_bundle_zip_page_contract.py tests/test_run_registry_send_bundle_anim_diagnostics.py tests/test_dashboard_validation_anim_latest_diagnostics.py tests/test_env_diagnostics_send_bundle_summary_source.py tests/test_triage_readme_anim_latest_diagnostics.py tests/test_r32_triage_and_anim_sidecars.py tests/test_legacy_send_bundle_page_wrappers.py tests/test_run_full_diagnostics_tool.py tests/test_clipboard_send_gui_contract.py tests/test_page_runner_auto_bundle_clipboard.py tests/test_page_runner_autobundle_summary.py tests/test_send_bundle_utcaware_source.py tests/test_gui_spec_docs_contract.py -q
python -m pneumo_solver_ui.tools.validate_send_bundle --zip send_bundles\latest_send_bundle.zip --print_summary
python -m pneumo_solver_ui.tools.inspect_send_bundle --zip send_bundles\latest_send_bundle.zip --print_summary
```

Runtime validation result: `validation ok`, with warnings for any missing
HO-009 analysis evidence, non-ready Geometry Reference sub-evidence such as
stale freshness, missing acceptance, missing `road_width_m` or partial
packaging, and browser perf evidence. These warnings are expected non-claims
for adjacent workstreams and are preserved in health/inspect output.

Final standalone audit result: `validate_send_bundle` reports
`OK errors=0 warnings=9 zip_entries=310 manifest_checked=286` for
`send_bundles/latest_send_bundle.zip`. `inspect_send_bundle` reports
`OK=False` because optional/adjacent evidence remains warning-only:
HO-009 context state, Geometry Reference producer artifacts, geometry
acceptance and browser perf evidence are still not closed by WS-DIAGNOSTICS.
The embedded/final validation sidecar remains `ok=True`, `errors=0`,
`warnings=7`; the two additional standalone warnings are audit-surface
warnings, not missing PB-002 required bundle artifacts.

Evidence artifacts exercised by tests:

- `diagnostics/evidence_manifest.json`
- `latest_evidence_manifest.json`
- `latest_send_bundle.zip`
- `latest_send_bundle_path.txt`
- `latest_send_bundle.sha256`
- `latest_send_bundle_inspection.json`
- `latest_send_bundle_inspection.md`
- `latest_health_report.md`
- `health/health_report.json`
- `triage/triage_report.json`
- `validation/validation_report.json`

Non-claims:

- `OG-005` can move toward release closure only when the final release bundle
  names its ZIP, SHA sidecar, latest pointer, shell runtime proof and validation
  report.
- This note does not close `OG-001`, `OG-002`, `OG-003`, `OG-004`, or `OG-006`.
- Diagnostics/Reference Center handoff does not close `GAP-002`, `GAP-006`, or
  `GAP-008`; those stay producer/runtime evidence gates.
- Missing conditional evidence from producer, animator, performance, geometry, or analysis workstreams remains surfaced as warnings until those workstreams produce runtime artifacts.
- Diagnostics evidence remains adapter/proof only and does not alter solver, optimizer, animator, geometry, or domain calculations.
