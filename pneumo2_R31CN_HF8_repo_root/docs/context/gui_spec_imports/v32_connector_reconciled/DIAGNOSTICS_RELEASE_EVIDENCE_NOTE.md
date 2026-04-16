# Diagnostics Release Evidence Note

Date: 2026-04-17

Scope: `WS-DIAGNOSTICS`, `PB-002`, `RGH-006`, `RGH-007`, `RGH-016`,
`OG-005`.

Status: V32-11 diagnostics evidence contract accepted for lane integration,
with a named runtime SEND bundle proof attached below. This is still not a
full `OG-005` closure claim because adjacent analysis, geometry and perf
runtime evidence warnings remain visible.

Implemented proof:

- SEND bundle finalization order is captured in `diagnostics/evidence_manifest.json`.
- Final triage is rewritten before health is built.
- `latest_send_bundle.zip`, `latest_send_bundle_path.txt`, and `latest_send_bundle.sha256` are refreshed after final health/validation/dashboard passes.
- `latest_evidence_manifest.json` records final latest ZIP SHA, pointer match, SHA sidecar match, trigger, collection mode, effective workspace, and helper Python provenance.
- Desktop Diagnostics Center state exposes machine-readable paths for latest ZIP, path pointer, SHA, health, triage, validation, evidence manifest, and clipboard status.
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

Result: `25 passed`.

Runtime proof captured:

- ZIP: `send_bundles/SEND_20260417_013757_bundle.zip`
- Final latest SHA256: `08d5db2098762a57f7d76d6621e2b42859bcc88ea87de40760b63a5ee3fb1044`
- Trigger / mode: `desktop_diagnostics_center` / `manual`
- Validation: `ok=True`, `errors=0`, `warnings=5`
- PB-002 required evidence: `pb002_missing_required_count=0`
- Latest pointer/SHA proof: `latest_zip_matches_original=True`, `latest_sha_sidecar_matches=True`, `latest_pointer_matches_original=True`
- Desktop center state refreshed: `latest_desktop_diagnostics_center_state.json` exposes latest ZIP, path pointer, SHA, health, triage, validation, evidence manifest and clipboard paths.

Runtime proof command:

```powershell
python -m pneumo_solver_ui.tools.make_send_bundle --trigger desktop_diagnostics_center --max_file_mb 80 --print_path
python -m pneumo_solver_ui.tools.validate_send_bundle --zip send_bundles\SEND_20260417_013757_bundle.zip --print_summary
python -m pneumo_solver_ui.tools.inspect_send_bundle --zip send_bundles\SEND_20260417_013757_bundle.zip --print_summary
```

Runtime validation result: `validation ok`, with warnings for missing HO-009
analysis evidence, geometry reference/acceptance evidence and browser perf
evidence. These warnings are expected non-claims for adjacent workstreams and
are preserved in health/inspect output.

Evidence artifacts exercised by tests:

- `diagnostics/evidence_manifest.json`
- `latest_evidence_manifest.json`
- `latest_send_bundle.zip`
- `latest_send_bundle_path.txt`
- `latest_send_bundle.sha256`
- `latest_health_report.md`
- `health/health_report.json`
- `triage/triage_report.json`
- `validation/validation_report.json`

Non-claims:

- `OG-005` can move toward release closure only when the final release bundle
  names its ZIP, SHA sidecar, latest pointer, shell runtime proof and validation
  report.
- This note does not close `OG-001`, `OG-002`, `OG-003`, `OG-004`, or `OG-006`.
- Missing conditional evidence from producer, animator, performance, geometry, or analysis workstreams remains surfaced as warnings until those workstreams produce runtime artifacts.
- Diagnostics evidence remains adapter/proof only and does not alter solver, optimizer, animator, geometry, or domain calculations.
