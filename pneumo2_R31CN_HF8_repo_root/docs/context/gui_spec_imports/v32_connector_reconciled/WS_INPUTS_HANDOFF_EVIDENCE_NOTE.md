# WS-INPUTS Handoff Evidence Note

Date: 2026-04-17

Scope: `WS-INPUTS`, `WS-RING`, `WS-SUITE`, `WS-BASELINE`,
`HO-002`, `HO-003`, `HO-004`, `HO-005`.

Implemented proof:

- `WS-INPUTS` freezes canonical model inputs into
  `workspace/handoffs/WS-INPUTS/inputs_snapshot.json`.
- `inputs_snapshot.json` is validated as `desktop_inputs_snapshot_v1` with
  `frozen = true`, canonical `payload_hash`, `snapshot_hash`,
  `invented_keys = []`, section keys, and target handoffs `HO-002` and
  `HO-003`.
- `WS-RING` consumes `HO-002` through a read-only ref/hash resolver and does
  not receive or mutate live `inputs`.
- `WS-SUITE` consumes `HO-003` through the same frozen ref/hash contract,
  records the input hash in `validated_suite_snapshot.json`, and combines it
  with `WS-RING` `HO-004` lineage.
- `WS-BASELINE` consumes `HO-005` and sees the same
  `suite_snapshot_hash`, `inputs_snapshot_hash`, and `ring_source_hash`
  without rebinding upstream state.
- Ring and Suite desktop UIs surface visible missing/current/stale/invalid
  banners for the input handoff.

Repo evidence:

- `tests/test_desktop_input_editor_contract.py`
- `tests/test_desktop_ring_editor_contract.py`
- `tests/test_desktop_suite_snapshot.py`
- `tests/test_desktop_run_setup_center_contract.py`
- Evidence chain test:
  `test_full_handoff_chain_preserves_refs_and_hashes_without_solver_run`

Verified commands:

```powershell
python -m pytest tests/test_desktop_suite_snapshot.py -q
python -m pytest tests/test_desktop_input_editor_contract.py tests/test_desktop_ring_editor_contract.py tests/test_desktop_suite_snapshot.py tests/test_desktop_run_setup_center_contract.py tests/test_desktop_main_shell_qt_contract.py tests/test_test_center_results_center_contract.py tests/test_desktop_optimizer_center_contract.py -q
```

Latest observed result in this workstream: `114 passed`.

Non-claims:

- This note does not claim solver correctness, optimizer correctness, or
  runtime physics closure.
- This note does not close producer-side truth gaps, cylinder packaging,
  measured performance, viewport gating, Windows visual acceptance, or SEND
  bundle runtime closure.
- This note does not authorize downstream editing of inputs, ring geometry,
  scenarios, optimizer internals, or solver truth.
- Any future wire-shape change to `inputs_snapshot.json` still requires a
  separate contract update.
