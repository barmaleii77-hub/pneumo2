# Branch Cleanup And Next Work Plan 2026-04-18

Purpose: record the branch cleanup decision and define the next safe
parallel-work shape after consolidating the temporary Codex branches into
`codex/work`.

## Branch Cleanup Result

Current integration branch:

- `codex/work` at `4879c21`
- `origin/codex/work` at `4879c21`

Remaining branches after cleanup:

- local: `codex/work`, `main`
- remote: `origin/codex/work`, `origin/main`

Integrated into `codex/work`:

- `codex/save-mnemo-dataset-contract-c6a4`
- `codex/save-autoselfcheck-disk-cache-b637`

Deleted after integration or triage:

- `codex/runtime-evidence-gates`: already included in `codex/work`
- `codex/ws-ring-ho004-suite-handoff`: already included in `codex/work`
- `codex/save-mnemo-dataset-contract-c6a4`: merged into `codex/work`
- `codex/save-autoselfcheck-disk-cache-b637`: merged into `codex/work`
- `codex/save-autoselfcheck-disk-cache-1b07`: rejected as an older conflicting
  duplicate of the autoselfcheck disk-cache work

Local auxiliary worktrees for those branches and stale detached `initial`
worktrees were removed. The primary repository worktree is clean.

## Validation Snapshot

Focused validation after merging:

```powershell
python -m pytest tests/test_desktop_mnemo_dataset_contract.py tests/test_desktop_mnemo_runtime_proof.py tests/test_autoselfcheck_disk_cache.py tests/test_gui_spec_docs_contract.py tests/test_knowledge_base_sync_contract.py tests/test_ui_text_no_mojibake_contract.py -q
```

Result:

- `48 passed`

## Parallel Work Policy

Parallel chats remain useful, but only with explicit ownership boundaries.
New work must start from `codex/work`, not from `main`.

Rules:

- keep `codex/work` as the only integration trunk until `main` is deliberately
  fast-forwarded or merged by a separate release decision;
- limit active implementation chats to 3-5 independent lanes;
- never let two chats edit the same module family at the same time;
- do not expand WEB; use WEB only as legacy reference while migrating operator
  flows to classic Windows GUI;
- keep `Desktop Animator`, `Compare Viewer` and `Desktop Mnemo` as specialized
  domains without duplicating their internals in other windows;
- every new user requirement or generated plan must be captured in the
  knowledge-base logs.

## Recommended Next Lanes

1. `V32-10 Desktop Mnemo Windows Acceptance`

Owned files:

- `pneumo_solver_ui/desktop_mnemo/*`
- `tests/test_desktop_mnemo_*`
- release evidence notes under `docs/context/release_readiness/`

Goal:

- close the immediate real-Windows no-hang/visual checklist gap without
  inventing graphics data or hiding unavailable states.

Exit evidence:

- visible startup proof regenerated after the latest merge;
- manual Windows checklist for open, resize, Snap, restore, close, dock overlap
  and visible scheme readability;
- no final acceptance claim until durable evidence exists.

2. `V32-01 Main Shell And Launch Surface`

Owned files:

- `pneumo_solver_ui/desktop_qt_shell/*`
- `pneumo_solver_ui/tools/desktop_main_shell_qt.py`
- `START_DESKTOP_MAIN_SHELL.py`
- `START_PNEUMO_APP.py`
- shell-focused tests

Goal:

- stabilize the classic Windows main shell, top menu, module launch commands,
  docks and startup behavior.

Exit evidence:

- all GUI module launch commands visible from one shell surface;
- focused shell tests pass;
- manual Snap/DPI/second-monitor checklist remains explicit until proven.

3. `V32-02 Input Data GUI`

Owned files:

- `pneumo_solver_ui/desktop_input_model.py`
- `pneumo_solver_ui/desktop_input_graphics.py`
- `pneumo_solver_ui/tools/desktop_input_editor.py`
- `tests/test_desktop_input_editor_contract.py`

Goal:

- make the operator input window understandable: sections, sliders, units,
  source markers, dirty/current states and frozen snapshot handoff.

Exit evidence:

- geometry, pneumatics, mechanics and calculation-settings clusters visible;
- no edits to Mnemo, Animator or Compare Viewer internals.

4. `V32-03/V32-04 Ring And Run Setup Handoff`

Owned files:

- `pneumo_solver_ui/scenario_ring.py`
- `pneumo_solver_ui/scenario_generator.py`
- `pneumo_solver_ui/tools/desktop_ring_scenario_editor.py`
- `pneumo_solver_ui/tools/desktop_run_setup_center.py`
- related ring/suite tests

Goal:

- make ring scenario editing and calculation setup a clear desktop workflow
  with explicit stale/current handoff to suite/baseline.

Exit evidence:

- canonical ring export and suite snapshot tests pass;
- no hidden ring-seam closure.

5. `V32-06/V32-07 Optimizer And Results Center`

Owned files:

- `pneumo_solver_ui/desktop_optimizer_*`
- `pneumo_solver_ui/desktop_results_*`
- `pneumo_solver_ui/tools/desktop_optimizer_center.py`
- `pneumo_solver_ui/tools/desktop_results_center.py`
- optimizer/results tests

Goal:

- preserve objective contract, baseline policy, resume/run identity and result
  provenance in desktop GUI.

Exit evidence:

- stale baseline states visible;
- selected run/result center handoff works without silent objective drift.

6. `V32-11 Diagnostics And SEND Bundle`

Owned files:

- `pneumo_solver_ui/desktop_diagnostics_*`
- `pneumo_solver_ui/send_bundle.py`
- `pneumo_solver_ui/tools/make_send_bundle.py`
- `pneumo_solver_ui/tools/validate_send_bundle.py`
- `pneumo_solver_ui/tools/send_bundle_evidence.py`
- diagnostics/SEND tests

Goal:

- keep evidence manifests honest and make missing producer artifacts visible as
  warnings, not fake release closure.

Exit evidence:

- latest bundle pointer and evidence manifest checks pass;
- producer-owned gaps remain explicit.

7. `V32-12/V32-14 Geometry And Producer Truth`

Owned files:

- `pneumo_solver_ui/anim_export_contract.py`
- `pneumo_solver_ui/desktop_geometry_reference_*`
- `pneumo_solver_ui/desktop_animator/data_bundle.py`
- producer truth and geometry acceptance tests

Goal:

- close truth-data gaps at the producer/export layer before expecting Animator,
  Mnemo or Compare Viewer to display reliable geometry.

Exit evidence:

- solver-points/hardpoints/packaging/road-width evidence is named and durable;
- no viewer-layer fabrication.

## Immediate Next Step

Start with `V32-10 Desktop Mnemo Windows Acceptance` and `V32-01 Main Shell And
Launch Surface` as the next two highest-impact lanes. They directly address the
recent user-visible pain: slow or hanging windows, unreliable Mnemo launch and
unclear desktop entrypoints.
