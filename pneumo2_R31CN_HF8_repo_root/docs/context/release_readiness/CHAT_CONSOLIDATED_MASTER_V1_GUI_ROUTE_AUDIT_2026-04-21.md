# Chat Consolidated Master V1 GUI Route Audit - 2026-04-21

Source layer: `docs/context/gui_spec_imports/chat_consolidated_master_v1/`.

Status: actionable implementation audit after importing `pneumo_chat_consolidated_master_v1.zip`. This note is evidence-bound. It does not claim runtime-closure proof or visual acceptance.

## Source Files Read

- `04_GRAPH_ANALYSIS/00_MASTER_SUMMARY.md`
- `06_INDEX/MASTER_EXEC_SUMMARY.json`
- `06_INDEX/SUPERSEDED_AND_EXCLUDED.csv`
- `04_GRAPH_ANALYSIS/01_reconciliation_v21/GRAPH_ANALYSIS_REPORT_V21.md`
- `04_GRAPH_ANALYSIS/01_reconciliation_v21/CURRENT_TO_CANONICAL_RECONCILIATION_V21.csv`
- `04_GRAPH_ANALYSIS/01_reconciliation_v21/LAUNCHPOINT_ONLY_TRIAGE_V21.csv`
- `04_GRAPH_ANALYSIS/01_reconciliation_v21/ROUTE_COST_REBALANCING_V21.csv`
- `04_GRAPH_ANALYSIS/02_workspace_graphs_v20/GRAPH_ANALYSIS_REPORT_V20.md`
- `04_GRAPH_ANALYSIS/04_cost_entropy_v17/GRAPH_ANALYSIS_REPORT_V17.md`
- `05_HUMAN_REPORTS/00_MASTER_SUMMARY.md`

## Current Runtime Evidence

- `pneumo_solver_ui/desktop_spec_shell/registry.py` exposes 11 top-level workspaces in the canonical route order.
- `diagnostics` is already a hosted workspace. `diagnostics.collect_bundle`, `diagnostics.verify_bundle` and `diagnostics.send_results` are hosted actions, while `diagnostics.legacy_center.open` remains a fallback.
- `baseline_run` has hosted review/adopt/restore actions, but the actual run setup still launches `desktop_run_setup_center` as a legacy bridge.
- `ring_editor`, `test_matrix`, `optimization` and `results_analysis` are still mostly `legacy_bridge` surfaces.
- `animation` is route-visible, but its main actions still launch external Animator and Mnemo windows.
- `tools` is a support workspace and keeps legacy/tooling entrypoints available for fallback.

## V21 Findings Applied In This Step

V21 says the main conflict is at shell/route level: the home surface must stop acting like a catalog of nearly equal launchpoints. The first implementation change from this audit is therefore intentionally small and low-risk:

- `overview.quick_action_ids` now contains only direct workspace-open commands.
- `overview.quick_action_ids` no longer contains `results.center.open`, `animation.animator.open` or `diagnostics.collect_bundle`.
- The `Последние результаты` overview card now opens `workspace.results_analysis.open`.
- The `Последний архив проекта` overview card now opens `workspace.diagnostics.open`.

This keeps direct actions available through their owning workspaces and command search, but removes legacy/external actions from the first overview decision row.

## Remaining Gaps Against Master V1

| Gap | Master V1 source | Current state | Next action |
| --- | --- | --- | --- |
| Ring editor must dominate as step 2 | V21 `CUR-RING-NOT-DOMINANT`, V20/V19 ring graphs, V13 ring migration | route-visible, still legacy bridge | build hosted `WS-RING` control surface and keep legacy editor as fallback |
| Suite must read as consumer after ring | V21 `CUR-WIN-SUITE`, V20 `WS-SUITE` graph | route-visible, still legacy bridge | host suite summary/list/detail and validation snapshot |
| Baseline setup must not be a side launcher | V20 `WS-BASELINE`, route cost scenarios | baseline state hosted, setup still legacy bridge | host run setup and single-run handoff |
| Optimization needs one primary route | V21 `CUR-SHELL-OPT-PAGE`, V17 path-cost data | workspace exists, optimizer center still legacy bridge | host StageRunner/contract summary and keep distributed mode advanced |
| Analysis compare must be primary inside analysis | V21 `CUR-WIN-COMPARE` | results workspace exists, results center and compare viewer are launchers | host latest result/compare summary first, keep viewer advanced |
| Animation is route-visible but still external | V20 `WS-ANIMATOR` | workspace exists, Animator/Mnemo external | host route-aware animation hub before native re-host |

## Next Implementation Order

1. Finish route-first overview hardening and keep tests that prevent legacy/external launchpoints from returning to the overview quick-action row.
2. Implement hosted `WS-RING` as the next route-critical workspace.
3. Implement hosted `WS-SUITE` as consumer of the ring/source snapshot.
4. Move baseline run setup into hosted `WS-BASELINE`.
5. Move StageRunner-first optimization controls into hosted `WS-OPTIMIZATION`.
6. Move latest results and primary compare summary into hosted `WS-ANALYSIS`.
7. Convert `WS-ANIMATOR` from external-window hub to hosted control hub, then re-host Animator/Mnemo surfaces when runtime evidence is ready.

## Validation Added

- `tests/test_desktop_gui_spec_shell_contract.py` now asserts that overview quick actions are workspace-only.
- The same test asserts that overview result and diagnostics cards open workspaces, not legacy/action commands.
- Existing diagnostics hosted tests remain responsible for proving that `diagnostics.collect_bundle` still works from the diagnostics lane and global command routing.
