# Diagnostics Producer Gaps Handoff

Date: 2026-04-17

Scope: `WS-DIAGNOSTICS`, `PB-002`, `RGH-006`, `RGH-007`, `RGH-016`.

This note is a handoff for the remaining producer-owned evidence needed after
Diagnostics/SEND bundle hardening. It is not a domain calculation change and it
does not close `OG-001`, `OG-002`, `OG-003`, `OG-004`, `OG-005`, or `OG-006`.

Current proof snapshot:

- ZIP: `send_bundles/SEND_20260417_082546_bundle.zip`
- SHA256: `8aa8b64347793c9023691de7d6edb5b987447a7bd516e074a774c03650112130`
- Trigger / mode: `desktop_diagnostics_center` / `manual`
- PB-002 required evidence: `pb002_missing_required_count=0`
- Validation: `ok=True`, `errors=0`, `warnings=6`
- Health: `ok=False`, `notes=8`
- Latest sidecars: `latest_send_bundle.zip`, `latest_send_bundle_path.txt`,
  `latest_send_bundle.sha256`, `latest_evidence_manifest.json` and
  `latest_send_bundle_inspection.json` agree on the same ZIP bytes.

Producer-owned warnings still present:

| warning | owner lane | expected producer artifact | diagnostics behavior |
| --- | --- | --- | --- |
| `Analysis evidence / HO-009 missing` | `V32-07` / Results Center | `latest_analysis_evidence_manifest.json` or `workspace/exports/analysis_evidence_manifest.json` | Warn only; do not block PB-002 bundle construction. |
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

Boundary:

- Diagnostics remains an adapter/evidence layer.
- Missing producer evidence must stay visible as warnings until producer lanes
  create real runtime artifacts.
- Do not compute or reinterpret solver, optimizer, animator, geometry or
  performance domain values in this lane.
