# Diagnostics Producer Gaps Handoff

Date: 2026-04-17

Scope: `WS-DIAGNOSTICS`, `PB-002`, `RGH-006`, `RGH-007`, `RGH-016`.

This note is a handoff for the remaining producer-owned evidence needed after
Diagnostics/SEND bundle hardening. It is not a domain calculation change and it
does not close `OG-001`, `OG-002`, `OG-003`, `OG-004`, `OG-005`, or `OG-006`.

Current proof snapshot:

- ZIP: `send_bundles/SEND_20260417_083330_bundle.zip`
- SHA256: `2dc744bf767e6bf073a66de91577ee47dd0875cd8fb920e6b51dd6b11c5156d9`
- Trigger / mode: `desktop_diagnostics_center` / `manual`
- PB-002 required evidence: `pb002_missing_required_count=0`
- Validation: `ok=True`, `errors=0`, `warnings=7`
- Health: `ok=False`, `notes=9`
- Latest sidecars: `latest_send_bundle.zip`, `latest_send_bundle_path.txt`,
  `latest_send_bundle.sha256`, `latest_evidence_manifest.json` and
  `latest_send_bundle_inspection.json` agree on the same ZIP bytes.

Producer-owned warnings still present:

| warning | owner lane | expected producer artifact | diagnostics behavior |
| --- | --- | --- | --- |
| `Analysis evidence / HO-009 context state is missing` | `V32-07` / Results Center | `latest_analysis_evidence_manifest.json` is present, but producer must populate current result context, selected run/test/NPZ refs and hashes | Warn only; do not block PB-002 bundle construction. |
| `Geometry reference producer artifact handoff is missing` | `V32-12` / Geometry Reference, `V32-14` / Animator export | `workspace/_pointers/anim_latest.json` or `workspace/exports/anim_latest.json`, `workspace/exports/anim_latest.npz`, `workspace/exports/CYLINDER_PACKAGING_PASSPORT.json`, `workspace/exports/geometry_acceptance_report.json` | Warn only; Diagnostics records `producer_artifact_status=missing` and the producer next action, but does not fabricate evidence. |
| `Geometry reference evidence reports missing item(s): artifact_context, geometry_acceptance` | `V32-12` / Geometry Reference | `latest_geometry_reference_evidence.json` with `artifact_context` and `geometry_acceptance` evidence | Warn only; keep explicit missing-evidence text in validation, health and inspect. |
| `Geometry reference artifact context is missing` | `V32-12` / Geometry Reference | Current selected artifact context, including latest/selected relation | Warn only. |
| `Geometry reference artifact freshness is missing` | `V32-12` / Geometry Reference | `artifact_freshness_status`, `artifact_freshness_relation`, `latest_artifact_status` | Warn only. |
| `Geometry reference packaging passport state is mismatch` | `V32-12` / `V32-14` | Packaging passport evidence with matching contract hash/state | Warn only. |
| `Geometry acceptance gate is MISSING` | `V32-12` / `V32-14` | `geometry_acceptance_gate=PASS` from producer-owned acceptance artifact | Warn only until producer supplies runtime evidence. |
| `browser perf evidence is not trace_bundle_ready: missing` | `V32-15` | Browser perf trace/evidence report marked `trace_bundle_ready` | Health note only. |
| `browser perf comparison status: no_reference` | `V32-15` | Current and previous browser perf reference snapshots | Health note only. |

Diagnostics next action after producer artifacts arrive:

1. Rebuild SEND from Desktop Diagnostics Center.
2. Verify `latest_send_bundle.zip`, pointer, SHA sidecar, evidence sidecar and
   inspection sidecar agree on the same bytes.
3. Run `validate_send_bundle --zip send_bundles\latest_send_bundle.zip`.
4. Run `inspect_send_bundle --zip send_bundles\latest_send_bundle.zip`.
5. Update `DIAGNOSTICS_RELEASE_EVIDENCE_NOTE.md` with the new ZIP/SHA and
   remaining warning count.

Current HO-009 state:

- `latest_analysis_evidence_manifest.json` exists and is embedded in the SEND
  bundle.
- `analysis_handoff.status=WARN`.
- `analysis_handoff.result_context_state=MISSING`.
- `analysis_handoff.artifact_count=15`.
- Diagnostics must keep this as a warning until Results Center exports a
  current context with selected run/test/NPZ refs and provenance hashes.

Boundary:

- Diagnostics remains an adapter/evidence layer.
- Missing producer evidence must stay visible as warnings until producer lanes
  create real runtime artifacts.
- Do not compute or reinterpret solver, optimizer, animator, geometry or
  performance domain values in this lane.
