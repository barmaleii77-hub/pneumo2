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

WS-SUITE / HO-005 update:

- `WS-SUITE` now has a runtime facade for
  `workspace/ui_state/desktop_suite_overrides.json` and
  `workspace/handoffs/WS-SUITE/validated_suite_snapshot.json`.
- Runtime overrides are limited to suite/runtime fields. Geometry and ring
  ownership fields such as `road_csv`, `axay_csv`, `scenario_json`,
  `segments`, and `geometry` are rejected instead of mutating upstream
  source-of-truth.
- `validated_suite_snapshot.json` records `inputs_snapshot.payload_hash`,
  `WS-RING` `HO-004` lineage/hash, `suite_snapshot_hash`, preview rows,
  validation state, and missing/stale/invalid/current banner reasons.
- Run Setup Center exposes `Набор испытаний / HO-005` with preview,
  validation, freeze, open snapshot, open handoff folder, and reset overrides
  commands.
- Test Center exposes a compact `HO-005` card with state,
  `suite_snapshot_hash`, enabled rows, missing refs, and snapshot path.
- Command search discovers the route by `validated_suite_snapshot`,
  `suite_snapshot_hash`, `HO-005`, and `заморозить HO-005`.
- Baseline launch uses a hard `HO-005` gate. `missing`, `invalid`, and
  `stale` block baseline launch even when `runtime_policy = force`; detail
  and full routes remain warning-only for missing `HO-005`.

Latest WS-SUITE validation:

```powershell
python -m py_compile pneumo_solver_ui\desktop_suite_snapshot.py pneumo_solver_ui\desktop_suite_runtime.py pneumo_solver_ui\tools\desktop_input_editor.py pneumo_solver_ui\tools\desktop_run_setup_center.py pneumo_solver_ui\tools\test_center_gui.py pneumo_solver_ui\optimization_baseline_source.py pneumo_solver_ui\optimization_baseline_source_ui.py
python -m pytest tests/test_desktop_suite_snapshot.py tests/test_desktop_run_setup_center_contract.py tests/test_test_center_results_center_contract.py tests/test_optimization_baseline_source_history.py tests/test_optimization_scoped_baseline_autoload.py -q
python -m pytest tests/test_desktop_gui_spec_shell_contract.py tests/test_desktop_shell_parity_contract.py tests/test_desktop_main_shell_contract.py tests/test_desktop_main_shell_qt_contract.py tests/test_suite_contract_migration.py tests/test_optimization_auto_ring_suite.py -q
python -m pytest tests/test_desktop_input_editor_contract.py -q
```

Observed results: `45 passed`, `52 passed`, `31 passed`.

Manual temp-workspace smoke:

- Frozen `inputs_snapshot.json` was written for `HO-003`.
- A ring-backed row consumed scenario `_lineage.ring_source_hash_sha256`
  without editing ring geometry.
- `validated_suite_snapshot.json` was written and validated.
- Baseline launch gate returned `state = current`,
  `baseline_launch_allowed = true`, and `runtime_policy_can_bypass = false`
  for `runtime_policy = force`.

Chunked full-suite scan:

```text
chunk 1: 309 passed, 2 failed
chunk 2: 216 passed, 1 failed
chunk 3: 180 passed
chunk 4: 200 passed, 1 skipped, 1 failed
chunk 5: 238 passed, 7 skipped, 9 failed
chunk 6: 157 passed, 13 failed
chunk 7: 250 passed, 1 skipped
chunk 8: 237 passed
```

No chunked full-suite failure was in `WS-SUITE`, `HO-005`,
`validated_suite_snapshot`, command discoverability, or baseline hard-gate
coverage. Observed failures were in active generator/worldroad numerical
checks, geometry-reference evidence, docs triage, animator visual/source
contracts, and static-trim pressure behavior.

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
