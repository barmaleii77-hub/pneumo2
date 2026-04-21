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
- `baseline_run` has hosted run setup, readiness check and review/adopt/restore surfaces. The old `desktop_run_setup_center` remains available as an explicit advanced fallback command.
- `ring_editor` and `test_matrix` are hosted workspace surfaces with legacy fallback commands for detailed tools.
- `optimization` now has a hosted primary setup/readiness surface. The old `desktop_optimizer_center` remains available as an explicit advanced fallback command.
- `results_analysis` is still mostly a `legacy_bridge` surface.
- `animation` is route-visible, but its main actions still launch external Animator and Mnemo windows.
- `tools` is a support workspace and keeps legacy/tooling entrypoints available for fallback.

## V21 Findings Applied In This Step

V21 says the main conflict is at shell/route level: the home surface must stop acting like a catalog of nearly equal launchpoints. The first implementation change from this audit is therefore intentionally small and low-risk:

- `overview.quick_action_ids` now contains only direct workspace-open commands.
- `overview.quick_action_ids` no longer contains `results.center.open`, `animation.animator.open` or `diagnostics.collect_bundle`.
- The `Последние результаты` overview card now opens `workspace.results_analysis.open`.
- The `Последний архив проекта` overview card now opens `workspace.diagnostics.open`.

This keeps direct actions available through their owning workspaces and command search, but removes legacy/external actions from the first overview decision row.

## Follow-Up Applied: Hosted WS-RING

The second implementation change starts the route-critical migration after the overview cleanup:

- `ring_editor.launch_surface` is now `workspace`, so the canonical shell treats WS-RING as a hosted route surface.
- `DesktopGuiSpecMainWindow` creates `RingWorkspacePage` for `ring_editor` instead of falling through to the generic bridge/control hub.
- The new WS-RING page reads state through `desktop_ring_editor_model` and `desktop_ring_editor_runtime`, then shows source-of-truth, segment/event counts, ring length/time, seam/closure status, validation status and the next route.
- `ring.editor.open` remains a legacy fallback command for detailed editing; it is no longer the only visible implementation of the workspace.
- The ring workspace quick actions are now the fallback editor plus the route-forward handoff to `workspace.test_matrix.open`.

## Follow-Up Applied: Hosted WS-SUITE

The third implementation change promotes the suite lane into the active route after WS-RING:

- `test_matrix.launch_surface` is now `workspace`, matching the existing native `SuiteWorkspacePage`.
- `SuiteWorkspacePage` exposes a stable `WS-SUITE-HOSTED-PAGE` object name for smoke/contract tests.
- The page remains the active HO-005 surface: it shows test rows, checks upstream WS-INPUTS/WS-RING links and can save the validated suite snapshot for baseline run setup.
- `workspace.baseline_run.open` is visible as the route-forward handoff after suite validation.
- `test.center.open` remains a legacy fallback/advanced command instead of the only implementation of the workspace.

## Follow-Up Applied: Hosted WS-BASELINE Setup

The fourth implementation change starts closing the baseline side-launcher gap:

- `baseline.run_setup.open` is now a hosted action routed through `BaselineWorkspacePage`, not a direct module launch.
- `BaselineWorkspacePage` now exposes `WS-BASELINE-HOSTED-PAGE` plus a native `BL-RUN-SETUP-PANEL` for profile, cache policy, runtime policy, suite readiness and launch preparation.
- `baseline.run_setup.verify`, `baseline.run_setup.prepare_checked` and `baseline.run_setup.prepare` are command-search-visible hosted actions for readiness and launch preparation.
- `baseline.legacy_run_setup.open` keeps the old Tk run setup center available as an explicit advanced fallback.
- The active route now reads as `WS-SUITE -> WS-BASELINE` without forcing the user into an external setup window before seeing baseline state.

## Follow-Up Applied: Hosted WS-OPTIMIZATION Setup

The fifth implementation change moves optimization setup onto the active route:

- `optimization.center.open` is now a hosted action routed through `OptimizationWorkspacePage`, not a direct module launch.
- `OptimizationWorkspacePage` now exposes `WS-OPTIMIZATION-HOSTED-PAGE` plus `OP-STAGERUNNER-BLOCK` for the primary optimization setup surface.
- The hosted surface shows objective stack, hard gate, baseline provenance, suite/search-space readiness, active job and latest run state through `desktop_optimizer_runtime`.
- `optimization.readiness.check` and `optimization.primary_launch.prepare` are command-search-visible hosted actions for readiness and preparation.
- `optimization.legacy_center.open` keeps the old optimizer center available as an explicit advanced fallback.
- The active route now reads as `WS-BASELINE -> WS-OPTIMIZATION -> WS-ANALYSIS` without forcing the user into the optimizer center before seeing launch readiness.

## Remaining Gaps Against Master V1

| Gap | Master V1 source | Current state | Next action |
| --- | --- | --- | --- |
| Ring editor must dominate as step 2 | V21 `CUR-RING-NOT-DOMINANT`, V20/V19 ring graphs, V13 ring migration | hosted summary/control surface; legacy editor fallback remains | expand WS-RING from control surface to native editor once source mutation rules are ready |
| Suite must read as consumer after ring | V21 `CUR-WIN-SUITE`, V20 `WS-SUITE` graph | hosted table/check/snapshot surface; legacy test center fallback remains | expand native suite editing beyond enable/check/save once mutation rules are ready |
| Baseline setup must not be a side launcher | V20 `WS-BASELINE`, route cost scenarios | setup/readiness hosted; actual heavy run execution still delegated to advanced center | wire native execution once subprocess contract is isolated from Tk editor state |
| Optimization needs one primary route | V21 `CUR-SHELL-OPT-PAGE`, V17 path-cost data | setup/readiness hosted; heavy execution remains in advanced optimizer center | wire native execution once launch subprocess state is separated from the detailed optimizer center |
| Analysis compare must be primary inside analysis | V21 `CUR-WIN-COMPARE` | results workspace exists, results center and compare viewer are launchers | host latest result/compare summary first, keep viewer advanced |
| Animation is route-visible but still external | V20 `WS-ANIMATOR` | workspace exists, Animator/Mnemo external | host route-aware animation hub before native re-host |

## Next Implementation Order

1. Finish route-first overview hardening and keep tests that prevent legacy/external launchpoints from returning to the overview quick-action row.
2. Implement hosted `WS-RING` as the next route-critical workspace. Done as hosted summary/control surface.
3. Implement hosted `WS-SUITE` as consumer of the ring/source snapshot. Done as hosted table/check/snapshot surface.
4. Move baseline run setup into hosted `WS-BASELINE`. Done as hosted setup/readiness surface; native execution wiring remains next.
5. Move StageRunner-first optimization controls into hosted `WS-OPTIMIZATION`. Done as hosted setup/readiness surface; native execution wiring remains next.
6. Move latest results and primary compare summary into hosted `WS-ANALYSIS`.
7. Convert `WS-ANIMATOR` from external-window hub to hosted control hub, then re-host Animator/Mnemo surfaces when runtime evidence is ready.

## Validation Added

- `tests/test_desktop_gui_spec_shell_contract.py` now asserts that overview quick actions are workspace-only.
- The same test asserts that overview result and diagnostics cards open workspaces, not legacy/action commands.
- Existing diagnostics hosted tests remain responsible for proving that `diagnostics.collect_bundle` still works from the diagnostics lane and global command routing.
- `tests/test_desktop_gui_spec_shell_contract.py` now asserts that WS-RING is a hosted workspace while `ring.editor.open` remains a legacy fallback.
- `tests/test_desktop_gui_spec_shell_runtime_contract.py` now opens `ring_editor` offscreen and verifies that the shell hosts `RingWorkspacePage`.
- `tests/test_desktop_gui_spec_shell_contract.py` now asserts that WS-SUITE is a hosted workspace while `test.center.open` remains a legacy fallback.
- `tests/test_desktop_gui_spec_shell_runtime_contract.py` and `tests/test_desktop_gui_spec_workspace_pages_contract.py` now verify the hosted suite page, route-forward baseline action and advanced fallback action.
- `tests/test_desktop_gui_spec_shell_contract.py` now asserts that baseline setup is hosted while `baseline.legacy_run_setup.open` remains the advanced fallback.
- `tests/test_desktop_gui_spec_shell_runtime_contract.py` and `tests/test_desktop_gui_spec_workspace_pages_contract.py` now verify the hosted baseline setup panel and command routing.
- `tests/test_desktop_gui_spec_shell_contract.py` now asserts that optimization setup is hosted while `optimization.legacy_center.open` remains the advanced fallback.
- `tests/test_desktop_gui_spec_shell_runtime_contract.py` and `tests/test_desktop_gui_spec_workspace_pages_contract.py` now verify the hosted optimization setup panel and command routing.
