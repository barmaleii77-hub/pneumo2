# Mnemo Truth Graphics Evidence Note

Date: 2026-04-17

Scope: `WS-TOOLS`, `Desktop Mnemo`, `V32-10`, `RGH-003`.

Status: V32-10 Desktop Mnemo truth-graphics contracts accepted for lane
integration. This is a dataset/provenance acceptance note, not a runtime gap
closure claim.

Accepted proof shape:

- Desktop Mnemo prepares a semantic dataset from NPZ runtime tables with
  `desktop_mnemo_dataset_contract_v1` and explicit provenance.
- Source files and runtime tables expose availability, SHA/provenance and source
  markers for flow, pressure, state, scheme mapping and cylinder snapshot
  surfaces.
- Pneumatic scheme fidelity is checked against canonical nodes/routes and the
  native underlay reference instead of inventing alternate topology.
- Flow, pressure and state overlays keep explicit unavailable/degraded states;
  missing pressure/state/cylinder data remains visible to the operator.
- Cylinder snapshot rendering uses geometry and stroke channels only when
  available, and keeps pressure-only mode without silent volume fallback when
  geometry is absent.
- Launchers, settings bridge, snapshot dock, native canvas diagnostics, window
  layout contract and inline overlay contracts remain discoverable from tests.

Targeted test command:

```powershell
python -m pytest tests/test_desktop_mnemo_dataset_contract.py tests/test_desktop_mnemo_inline_overlay_contract.py tests/test_desktop_mnemo_launcher_contract.py tests/test_desktop_mnemo_main_contract.py tests/test_desktop_mnemo_page_contract.py tests/test_desktop_mnemo_settings_bridge_contract.py tests/test_desktop_mnemo_snapshot_contract.py tests/test_desktop_mnemo_window_contract.py tests/test_pneumo_scheme_mnemo_cache_resource_contract.py -q
```

Result: `22 passed`, with expected Qt deprecation warnings from
`QTableWidgetItem.setTextAlignment`.

Non-claims:

- This note does not change solver physics, Animator geometry, Compare Viewer
  behavior, input ownership or diagnostics SEND-bundle closure.
- This note does not close `OG-001`, `OG-002`, `OG-003`, `OG-004`, `OG-005` or
  `OG-006`.
- Desktop Mnemo remains a specialized window; other workspaces may launch it or
  pass frozen context, but should not duplicate its scheme surface.
