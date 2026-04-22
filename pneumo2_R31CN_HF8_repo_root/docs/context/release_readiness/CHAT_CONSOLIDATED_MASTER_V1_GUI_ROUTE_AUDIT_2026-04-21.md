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
- `input_data` now has a hosted editable parameter table. `input.editor.open` is routed through `InputWorkspacePage`, while `input.legacy_editor.open` remains an explicit fallback for the old detailed editor.
- `baseline_run` has hosted run setup, readiness check, native launch-request preparation and review/adopt/restore surfaces. The old `desktop_run_setup_center` remains available as an explicit advanced fallback command.
- `ring_editor` now has a hosted segment-editing surface. `ring.editor.open` is routed through `RingWorkspacePage`, while `ring.legacy_editor.open` remains an explicit fallback for the old detailed ring editor.
- `test_matrix` is a hosted workspace surface. `test.center.open` now routes through `SuiteWorkspacePage`, while `test.legacy_center.open` keeps the old test center available as a fallback command.
- `optimization` now has a hosted primary setup/readiness surface. The old `desktop_optimizer_center` remains available as an explicit advanced fallback command.
- `results_analysis` now has a hosted analysis/compare preparation surface with native compare and chart-series previews. The old `desktop_results_center` remains available as an explicit advanced fallback command.
- `animation` now has a hosted route-aware animation/mnemo readiness hub with native scene-data preview. The separate Animator and Mnemo windows remain available as explicit advanced fallback commands.
- `tools` is a support workspace and keeps legacy/tooling entrypoints available for fallback.

## V21 Findings Applied In This Step

V21 says the main conflict is at shell/route level: the home surface must stop acting like a catalog of nearly equal launchpoints. The first implementation change from this audit is therefore intentionally small and low-risk:

- `overview.quick_action_ids` now contains only direct workspace-open commands.
- `overview.quick_action_ids` no longer contains `results.center.open`, `animation.animator.open` or `diagnostics.collect_bundle`.
- The `Последние результаты` overview card now opens `workspace.results_analysis.open`.
- The `Последний архив проекта` overview card now opens `workspace.diagnostics.open`.

This keeps direct actions available through their owning workspaces and command search, but removes legacy/external actions from the first overview decision row.

## Follow-Up Applied: Hosted WS-INPUTS Editor

This implementation change removes the first route-critical legacy editor command from the active path:

- `input.editor.open` is now a hosted action routed through `InputWorkspacePage`, not a direct module launch.
- `InputWorkspacePage` exposes `WS-INPUTS-HOSTED-PAGE` plus `ID-PARAM-TABLE` for the primary editable input surface.
- The hosted surface reads sections and fields through `desktop_input_model`, shows section, parameter, value, unit and help text, and can save the working copy and the frozen route snapshot through the existing model functions.
- `input.legacy_editor.open` keeps the old detailed Tk editor available as an explicit advanced fallback command.
- The active route now reads as `WS-INPUTS -> WS-RING -> WS-SUITE` without forcing the user into a separate source-data editor before seeing or changing route-critical values.

## Follow-Up Applied: Hosted WS-RING

The second implementation change starts the route-critical migration after the overview cleanup:

- `ring_editor.launch_surface` is now `workspace`, so the canonical shell treats WS-RING as a hosted route surface.
- `DesktopGuiSpecMainWindow` creates `RingWorkspacePage` for `ring_editor` instead of falling through to the generic bridge/control hub.
- The new WS-RING page reads state through `desktop_ring_editor_model` and `desktop_ring_editor_runtime`, then shows source-of-truth, segment/event counts, ring length/time, seam/closure status, validation status and the next route.
- `ring.editor.open` is now the hosted active action: it opens the native segment table, supports segment add/duplicate/delete, editable duration/speed/turn/road columns, seam check and source save.
- `ring.legacy_editor.open` keeps the old detailed editor available as an explicit advanced fallback command.
- The ring workspace quick actions are now the hosted editor plus the route-forward handoff to `workspace.test_matrix.open`.

## Follow-Up Applied: Hosted WS-SUITE

The third implementation change promotes the suite lane into the active route after WS-RING:

- `test_matrix.launch_surface` is now `workspace`, matching the existing native `SuiteWorkspacePage`.
- `SuiteWorkspacePage` exposes a stable `WS-SUITE-HOSTED-PAGE` object name for smoke/contract tests.
- The page remains the active HO-005 surface: it shows test rows, checks upstream WS-INPUTS/WS-RING links and can save the validated suite snapshot for baseline run setup.
- `workspace.baseline_run.open` is visible as the route-forward handoff after suite validation.
- `test.center.open` is now the hosted active action for the suite lane; `test.legacy_center.open` keeps the old test center available as an explicit advanced fallback command.

## Follow-Up Applied: Hosted WS-BASELINE Setup

The fourth implementation change starts closing the baseline side-launcher gap:

- `baseline.run_setup.open` is now a hosted action routed through `BaselineWorkspacePage`, not a direct module launch.
- `BaselineWorkspacePage` now exposes `WS-BASELINE-HOSTED-PAGE` plus a native `BL-RUN-SETUP-PANEL` for profile, cache policy, runtime policy, suite readiness and launch preparation.
- `baseline.run_setup.verify`, `baseline.run_setup.prepare_checked` and `baseline.run_setup.prepare` are command-search-visible hosted actions for readiness and native launch-request preparation.
- `baseline.legacy_run_setup.open` keeps the old Tk run setup center available as an explicit advanced fallback.
- The active route now reads as `WS-SUITE -> WS-BASELINE` without forcing the user into an external setup window before seeing baseline state.

## Follow-Up Applied: Native WS-BASELINE Launch Request

The next implementation change isolates execution prerequisites from the old Tk run setup window:

- `pneumo_solver_ui/desktop_baseline_run_runtime.py` now owns the WS-BASELINE launch-request contract and writes `handoffs/WS-BASELINE/baseline_run_launch_request.json`.
- The request captures the frozen WS-SUITE snapshot, frozen WS-INPUTS snapshot, prepared input JSON, prepared suite JSON, selected test row, result folder, log path and `pneumo_solver_ui.tools.desktop_single_run` command plan.
- `BaselineWorkspacePage` calls the runtime from `baseline.run_setup.prepare_checked` and `baseline.run_setup.prepare`, so the hosted page now produces a reproducible launch request instead of only changing label text.

## Follow-Up Applied: Native WS-BASELINE Background Run

The next implementation change starts using the isolated request as the active execution path:

- `baseline.run.execute` is now a hosted command visible in the baseline workspace quick actions and command search.
- `BaselineWorkspacePage` starts the prepared `desktop_single_run` command through `QProcess`, keeps the main shell responsive and reports busy/done/error state through the bottom status bar.
- `desktop_baseline_run_runtime.py` records `running/done/failed` state, appends process output to the WS-BASELINE log and updates the launch request after completion.
- A successful native run writes a review-only baseline history candidate; explicit review/adopt is still required before the result becomes the active optimization baseline.

## Follow-Up Applied: WS-BASELINE Post-Run Controls

The next implementation change makes the hosted baseline run surface operable after launch:

- `baseline.run.cancel`, `baseline.run.open_log` and `baseline.run.open_result` are now hosted shell commands with stable automation ids.
- `BaselineWorkspacePage` exposes visible buttons for cancelling the current background run, opening the latest run log and opening the latest result folder.
- The cancel path terminates the active `QProcess`, records the launch request as failed/cancelled and keeps the review/adopt boundary intact.
- `desktop_baseline_run_runtime.py` exposes a read-only latest launch-request helper so the hosted page can restore artifact actions after refresh.

## Follow-Up Applied: WS-BASELINE Review Detail Card

The next implementation change hardens selected-result review before optimization handoff:

- `BaselineWorkspacePage` now exposes `BL-REVIEW-DETAILS` with a read-only review table for the selected history row.
- The card shows selected history id, source result file, run directory, baseline hash, suite/input/ring hashes, compare state, optimizer readiness and next safe step.
- `baseline.review` focuses the review card and remains read-only; `adopt` and `restore` still require explicit confirmation and never perform silent rebinding.
- The operator can now see what will be accepted or restored before changing the active baseline consumed by `WS-OPTIMIZATION`.

## Follow-Up Applied: Hosted WS-OPTIMIZATION Setup

The fifth implementation change moves optimization setup onto the active route:

- `optimization.center.open` is now a hosted action routed through `OptimizationWorkspacePage`, not a direct module launch.
- `OptimizationWorkspacePage` now exposes `WS-OPTIMIZATION-HOSTED-PAGE` plus `OP-STAGERUNNER-BLOCK` for the primary optimization setup surface.
- The hosted surface shows objective stack, hard gate, baseline provenance, suite/search-space readiness, active job and latest run state through `desktop_optimizer_runtime`.
- `optimization.readiness.check` and `optimization.primary_launch.prepare` are command-search-visible hosted actions for readiness and preparation.
- `optimization.legacy_center.open` keeps the old optimizer center available as an explicit advanced fallback.
- The active route now reads as `WS-BASELINE -> WS-OPTIMIZATION -> WS-ANALYSIS` without forcing the user into the optimizer center before seeing launch readiness.

## Follow-Up Applied: Hosted WS-ANALYSIS Setup

The sixth implementation change moves the first analysis surface onto the active route:

- `results.center.open` is now a hosted action routed through `ResultsWorkspacePage`, not a direct module launch.
- `ResultsWorkspacePage` now exposes `WS-ANALYSIS-HOSTED-PAGE` plus `RS-LEADERBOARD` for the primary analysis surface.
- The hosted surface shows validation/triage/result-context rows, recent analysis materials and compare readiness through `desktop_results_runtime`.
- `results.compare.prepare` and `results.evidence.prepare` are command-search-visible hosted actions for compare context and diagnostics evidence preparation.
- `results.legacy_center.open` keeps the old results center available as an explicit advanced fallback.
- The active route now reads as `WS-OPTIMIZATION -> WS-ANALYSIS -> WS-ANIMATOR/WS-DIAGNOSTICS` without forcing the user into the results center before seeing result readiness.

## Follow-Up Applied: Hosted WS-ANIMATOR Hub

The seventh implementation change makes animation a first-class route step instead of a direct external-window jump:

- `animation.animator.open` and `animation.mnemo.open` are now hosted actions routed through `AnimationWorkspacePage`.
- `AnimationWorkspacePage` exposes `WS-ANIMATOR-HOSTED-PAGE` plus `AM-VIEWPORT` for the primary animation/mnemo readiness surface.
- The hosted surface shows scene data readiness, playback data readiness, capture/truth state, mnemo event log state and the next recommended visual-check step through `desktop_results_runtime`.
- `animation.legacy_animator.open` and `animation.legacy_mnemo.open` keep the separate graphical windows available as explicit advanced fallback commands.
- The active route now reads as `WS-ANALYSIS -> WS-ANIMATOR -> WS-DIAGNOSTICS` without forcing the user into a separate window before seeing whether animation data exists.

## Follow-Up Applied: Native WS-OPTIMIZATION Execution Wiring

The eighth implementation change turns the optimization workspace from setup-only into a native execution surface:

- `optimization.primary_launch.execute` is now a hosted action routed through `OptimizationWorkspacePage`, not the legacy optimizer center.
- The hosted page keeps one active primary launch path: prepare/readiness, background execute, soft stop, hard stop, open log and open run directory.
- The page reuses `DesktopOptimizerRuntime` for `start_job`, soft-stop, hard-stop and artifact paths; shell code does not duplicate optimizer process logic.
- The bottom shell status is updated while optimization is running or stopping, so the active route stays responsive.
- `optimization.legacy_center.open` remains the explicit advanced fallback for detailed optimizer-center scenarios.

## Follow-Up Applied: Hosted WS-ANALYSIS Compare Handoff

The ninth implementation change moves the primary compare launch behind the analysis workspace instead of a direct module command:

- `results.compare.open` is now a hosted action routed through `ResultsWorkspacePage`.
- The hosted page opens comparison from the current analysis context and prepares the compare-current-context sidecar through `DesktopResultsRuntime`.
- `ResultsWorkspacePage` now exposes `RS-COMPARE-PREVIEW`, a native preview table showing the result file, compare context readiness, selected-run state and artifact preview lines before the detailed viewer opens.
- `results.compare.open` is now a quick action of `WS-ANALYSIS`, while `results.legacy_compare.open` keeps the direct compare viewer module available from `WS-TOOLS`.
- The active route now reads as `WS-ANALYSIS -> prepare context -> open comparison`, with legacy/direct compare reserved for fallback and special cases.

## Follow-Up Applied: Native WS-ANALYSIS Chart Preview

The next implementation change aligns `WS-ANALYSIS` with the user-pipeline graph before handoff to animation/diagnostics:

- `ResultsWorkspacePage` now exposes `RS-CHART-PREVIEW` plus `RS-CHART-PREVIEW-TABLE`.
- `DesktopResultsRuntime.chart_preview_rows(...)` reads the current NPZ result and extracts numeric series names, point counts, shapes and value ranges.
- The hosted page shows graph readiness inside `WS-ANALYSIS`, so the operator can confirm that result series exist before opening detailed comparison or moving to `WS-ANIMATOR`.
- The active route now reads as `WS-BASELINE/WS-OPTIMIZATION -> WS-ANALYSIS chart preview -> compare/animation/diagnostics handoff`.

## Follow-Up Applied: Selection-Aware WS-ANALYSIS Preview

The next implementation change makes the analysis workspace follow the operator's selected material instead of always showing only the latest result:

- `RS-ARTIFACTS-TABLE` selection now refreshes `RS-COMPARE-PREVIEW` and `RS-CHART-PREVIEW`.
- The selected artifact is passed through `DesktopResultsRuntime.compare_viewer_path(...)` and `chart_preview_rows(...)`, so the preview matches the material that would be opened by `results.compare.open`.
- This closes a pipeline-level ambiguity: the user can choose a result artifact, inspect its graph readiness and then continue to compare/animation/diagnostics with the same context.

## Follow-Up Applied: WS-ANALYSIS To WS-ANIMATOR Handoff

The next implementation change preserves the selected result across the user-pipeline edge from analysis to animation:

- `results.animation.prepare` is now a hosted `WS-ANALYSIS` command with stable `RS-BTN-HANDOFF-ANIMATION` automation id.
- `DesktopResultsRuntime.write_analysis_animation_handoff(...)` writes `latest_analysis_animation_handoff.json` as a read-only sidecar produced by `WS-ANALYSIS` and consumed by `WS-ANIMATOR`.
- `AnimationWorkspacePage` now checks `DesktopResultsRuntime.animation_handoff_artifact(...)` before falling back to latest result artifacts.
- Scene preview, animator launch and mnemo launch use the selected analysis artifact when a handoff exists, so the route is `select result -> handoff -> animation preview/check` without silently switching back to the latest result.

## Follow-Up Applied: WS-ANIMATOR To WS-DIAGNOSTICS Handoff

The next implementation change preserves animation context before the final diagnostics/archive step:

- `animation.diagnostics.prepare` is now a hosted `WS-ANIMATOR` command with stable `AM-BTN-HANDOFF-DIAGNOSTICS` automation id.
- `DesktopResultsRuntime.write_animation_diagnostics_handoff(...)` writes `latest_animation_diagnostics_handoff.json` as a read-only sidecar produced by `WS-ANIMATOR` and consumed by `WS-DIAGNOSTICS`.
- `DiagnosticsWorkspacePage` now exposes `DG-ANIMATION-HANDOFF` and shows the selected animation material, scene NPZ, pointer JSON and next archive step.
- SEND bundle creation now embeds the handoff as `animation/latest_animation_diagnostics_handoff.json` and reports it through optional evidence row `BND-023`.
- The active route now reads as `WS-ANALYSIS selected result -> WS-ANIMATOR scene check -> WS-DIAGNOSTICS archive check`, without silently dropping the visual context.

## Follow-Up Applied: Hosted WS-ANIMATOR Launch Handoff

The tenth implementation change moves the primary animation and mnemo launches behind the animation workspace context:

- `animation.animator.launch` is now a hosted action routed through `AnimationWorkspacePage`.
- The hosted page checks `DesktopResultsRuntime.animator_args(..., follow=True)` before launching, so the detailed animator receives the current pointer/NPZ context instead of opening as a blind fallback.
- `animation.mnemo.launch` is now a hosted action routed through `AnimationWorkspacePage`.
- `DesktopResultsRuntime` now exposes `mnemo_args(..., follow=True)` and `launch_mnemo(...)`, so the mnemo viewer receives the current pointer/NPZ context from the active workspace.
- `AM-DETACH` now represents the active “open animator” handoff from `WS-ANIMATOR`; `animation.legacy_animator.open` remains a direct fallback command in `WS-TOOLS`.
- `AM-BTN-DETACH-MNEMO` now represents the active “check scheme” handoff from `WS-ANIMATOR`; `animation.legacy_mnemo.open` remains a direct fallback command in `WS-TOOLS`.
- The active route now reads as `WS-ANALYSIS -> WS-ANIMATOR readiness -> check movement/check scheme with current scene data`.

## Follow-Up Applied: Native WS-ANIMATOR Scene Preview

The eleventh implementation change adds the first native animation data preview inside the hosted animation lane:

- `AnimationWorkspacePage` now exposes `AM-SCENE-PREVIEW` plus `AM-SCENE-PREVIEW-TABLE`.
- The preview table is populated from `DesktopResultsRuntime` artifacts: `latest_npz`, `latest_pointer`, `mnemo_event_log` and `capture_export_manifest`.
- Filenames and artifact preview lines are preserved as user-facing evidence, while operator status labels still use the normal shell wording.
- The active route now reads as `WS-ANALYSIS -> WS-ANIMATOR scene preview -> check movement/check scheme with current scene data`.

## Follow-Up Applied: Native WS-ANALYSIS Chart Canvas

The next implementation change removes one more dependency on the external comparison window for first-pass result review:

- `ResultsWorkspacePage` now exposes `RS-CHART-NATIVE-PREVIEW` under the existing `RS-CHART-PREVIEW` chart section.
- `DesktopResultsRuntime.chart_preview_series_samples(...)` reads the selected `.npz`, keeps only numeric finite values and returns a bounded sample for shell rendering.
- The hosted analysis workspace draws a lightweight native preview for the selected numeric series and updates it when the selected artifact changes.
- The active route now reads as `WS-ANALYSIS table summary -> native chart preview -> compare/animation handoff`, so the operator can confirm a result shape before opening detailed plotting.

## Follow-Up Applied: Native WS-ANIMATOR Scene Canvas

The next implementation change starts embedded scene controls without trying to host the full external Animator:

- `AnimationWorkspacePage` now exposes `AM-SCENE-NATIVE-PREVIEW` under the existing `AM-SCENE-PREVIEW` scene section.
- `DesktopResultsRuntime.animation_scene_preview_points(...)` reads the selected `.npz`, keeps finite numeric coordinates and returns a bounded sample for shell rendering.
- The hosted animation workspace draws a lightweight native movement contour for the selected scene and updates it when the analysis-to-animation handoff selects a different artifact.
- The active route now reads as `WS-ANALYSIS selected result -> WS-ANIMATOR native scene contour -> detailed animator/mnemo fallback only when needed`.

## Remaining Gaps Against Master V1

| Gap | Master V1 source | Current state | Next action |
| --- | --- | --- | --- |
| Ring editor must dominate as step 2 | V21 `CUR-RING-NOT-DOMINANT`, V20/V19 ring graphs, V13 ring migration | hosted segment-editing surface; legacy editor fallback remains | extend native WS-RING with advanced road/event editors when those panels are safe to re-host |
| Suite must read as consumer after ring | V21 `CUR-WIN-SUITE`, V20 `WS-SUITE` graph | hosted table/check/snapshot surface is the active command route; legacy test center fallback remains | expand native suite editing beyond enable/check/save once mutation rules are ready |
| Baseline setup must not be a side launcher | V20 `WS-BASELINE`, route cost scenarios | setup/readiness, launch-request preparation, background execution, cancel, artifact-open actions and selected-result review details are hosted; explicit review/adopt remains required | continue toward native optimization execution wiring |
| Optimization needs one primary route | V21 `CUR-SHELL-OPT-PAGE`, V17 path-cost data | setup/readiness plus native background execution, soft/hard stop and artifact opening are hosted; advanced optimizer center remains fallback | add richer native progress/result handoff once optimizer emits a stable embedded progress surface |
| Analysis compare must be primary inside analysis | V21 `CUR-WIN-COMPARE` | analysis/compare preparation, native compare preview, selection-aware chart-series table, native chart canvas, analysis-to-animation handoff and compare viewer handoff are hosted; detailed plots still delegated to the external viewer | re-host richer plot controls once plotting state is separated from external viewers |
| Animation is route-visible but still external | V20 `WS-ANIMATOR` | route-aware readiness hub, native scene table, native movement contour canvas, animator/mnemo launch handoffs and diagnostics handoff are hosted; diagnostics state/summary now record the animation handoff as checkable evidence; SEND bundle embeds the handoff as optional `BND-023`; detailed graphics still delegated to external viewers | re-host mnemo/core scene controls once the graphics runtime exposes a safe embedded surface |
| Ring and suite mutation depth is still partial | V21 route dominance notes, V20 workspace graphs | input editing and ring segment editing are now hosted; suite still keeps detailed mutation in fallback windows | apply the same hosted-first pattern to suite row/detail mutation |

## Next Implementation Order

1. Finish route-first overview hardening and keep tests that prevent legacy/external launchpoints from returning to the overview quick-action row.
2. Implement hosted `WS-RING` as the next route-critical workspace. Done as hosted segment-editing surface; advanced road/event panels remain fallback.
3. Implement hosted `WS-SUITE` as consumer of the ring/source snapshot. Done as hosted table/check/snapshot surface.
4. Move baseline run setup into hosted `WS-BASELINE`. Done as hosted setup/readiness surface with native launch-request preparation and background execution; post-run review UX remains next.
5. Move the primary optimization controls into hosted `WS-OPTIMIZATION`. Done as hosted setup/readiness, background execution, stop and artifact-open surface; richer progress/result handoff remains next.
6. Move latest results and primary compare summary into hosted `WS-ANALYSIS`. Done as hosted analysis, compare-preparation, native compare-preview, selection-aware chart-series preview, analysis-to-animation handoff and compare-open handoff surface; richer native plots remain next.
7. Convert `WS-ANIMATOR` from external-window hub to hosted control hub. Done as hosted readiness hub, native scene preview, context-aware animator/mnemo launch handoffs and diagnostics handoff; full scene/mnemo re-host remains next.
8. Continue removing legacy primary actions from route-critical workspaces. `WS-INPUTS`, `WS-RING`, the primary `WS-SUITE` action, WS-BASELINE background run/cancel/artifact/review-detail actions, WS-OPTIMIZATION execution actions, WS-ANALYSIS compare handoff/native chart preview and WS-ANIMATOR scene/visual handoffs are hosted; next candidate is embedded mnemo/core scene controls.

## Validation Added

- `tests/test_desktop_gui_spec_shell_contract.py` now asserts that overview quick actions are workspace-only.
- The same test asserts that overview result and diagnostics cards open workspaces, not legacy/action commands.
- Existing diagnostics hosted tests remain responsible for proving that `diagnostics.collect_bundle` still works from the diagnostics lane and global command routing.
- `tests/test_desktop_gui_spec_shell_contract.py` now asserts that WS-RING is a hosted workspace and its active editor command is hosted.
- `tests/test_desktop_gui_spec_shell_runtime_contract.py` now opens `ring_editor` offscreen and verifies that the shell hosts `RingWorkspacePage`.
- `tests/test_desktop_gui_spec_shell_contract.py` now asserts that `ring.editor.open` is hosted while `ring.legacy_editor.open` remains the fallback launch command.
- `tests/test_desktop_gui_spec_shell_runtime_contract.py` and `tests/test_desktop_gui_spec_workspace_pages_contract.py` now verify the hosted ring segment table, object names and command routing.
- `tests/test_desktop_gui_spec_shell_contract.py` now asserts that WS-SUITE and `test.center.open` are hosted while `test.legacy_center.open` remains the fallback launch command.
- `tests/test_desktop_gui_spec_shell_runtime_contract.py` and `tests/test_desktop_gui_spec_workspace_pages_contract.py` now verify the hosted suite page, command routing, stable object names, route-forward baseline action and advanced fallback action.
- `tests/test_desktop_gui_spec_shell_contract.py` now asserts that baseline setup is hosted while `baseline.legacy_run_setup.open` remains the advanced fallback.
- `tests/test_desktop_gui_spec_shell_runtime_contract.py` and `tests/test_desktop_gui_spec_workspace_pages_contract.py` now verify the hosted baseline setup panel and command routing.
- `tests/test_desktop_gui_spec_workspace_pages_contract.py` now verifies that WS-BASELINE writes a native launch request, prepares input/suite files and builds a `desktop_single_run` command plan without opening the legacy run setup center.
- `tests/test_desktop_gui_spec_workspace_pages_contract.py` now verifies that `baseline.run.execute` starts a native background request, records completion, writes a result summary path and appends a review-only baseline history candidate.
- `tests/test_desktop_gui_spec_shell_contract.py` now asserts that the baseline cancel/log/result actions are hosted commands with stable automation ids.
- `tests/test_desktop_gui_spec_workspace_pages_contract.py` now verifies that the hosted baseline page can cancel a running process and open the latest run log/result folder.
- `tests/test_desktop_gui_spec_workspace_pages_contract.py` now verifies the hosted `BL-REVIEW-DETAILS` card, selected result paths, optimizer readiness and mismatch-specific next-step guidance.
- `tests/test_desktop_gui_spec_shell_contract.py` now asserts that optimization setup is hosted while `optimization.legacy_center.open` remains the advanced fallback.
- `tests/test_desktop_gui_spec_shell_runtime_contract.py` and `tests/test_desktop_gui_spec_workspace_pages_contract.py` now verify the hosted optimization setup panel and command routing.
- `tests/test_desktop_gui_spec_shell_contract.py` now asserts that optimization execute/stop/artifact commands are hosted with stable automation ids.
- `tests/test_desktop_gui_spec_workspace_pages_contract.py` now verifies that the hosted optimization page starts the primary runtime, requests soft/hard stop and opens the latest log/run directory without launching the legacy optimizer center.
- `tests/test_desktop_gui_spec_shell_contract.py` now asserts that analysis setup is hosted while `results.legacy_center.open` remains the advanced fallback.
- `tests/test_desktop_gui_spec_shell_runtime_contract.py` and `tests/test_desktop_gui_spec_workspace_pages_contract.py` now verify the hosted analysis panel, compare context preparation and diagnostics evidence preparation.
- `tests/test_desktop_gui_spec_shell_contract.py` now asserts that `results.compare.open` is hosted and `results.legacy_compare.open` is the direct fallback module command.
- `tests/test_desktop_gui_spec_workspace_pages_contract.py` now verifies that hosted analysis opens comparison through `DesktopResultsRuntime` using the latest result context and renders the `RS-COMPARE-PREVIEW` table.
- `tests/test_desktop_gui_spec_workspace_pages_contract.py` now verifies that hosted analysis renders `RS-CHART-PREVIEW` from runtime chart-series rows before detailed plotting.
- `tests/test_desktop_gui_spec_workspace_pages_contract.py` now verifies that selecting a row in `RS-ARTIFACTS-TABLE` updates both compare and chart previews for that selected artifact.
- `tests/test_desktop_gui_spec_workspace_pages_contract.py` now verifies that `RS-CHART-NATIVE-PREVIEW` renders a native graphics scene from bounded runtime samples and follows the selected artifact.
- `tests/test_desktop_gui_spec_workspace_pages_contract.py` now verifies that `results.animation.prepare` writes a selected-artifact handoff and `WS-ANIMATOR` consumes it for scene preview and animator launch.
- `tests/test_desktop_gui_spec_shell_contract.py` now asserts that animation and mnemo primary commands are hosted while separate graphical windows remain fallback commands.
- `tests/test_desktop_gui_spec_shell_runtime_contract.py` and `tests/test_desktop_gui_spec_workspace_pages_contract.py` now verify the hosted animation hub and command routing.
- `tests/test_desktop_gui_spec_shell_contract.py` now asserts that `animation.animator.launch` is a hosted command with stable `AM-DETACH` automation id.
- `tests/test_desktop_gui_spec_workspace_pages_contract.py` now verifies that hosted animation launches the animator through `DesktopResultsRuntime` with current pointer/scene data.
- `tests/test_desktop_gui_spec_shell_contract.py` now asserts that `animation.mnemo.launch` is a hosted command with stable `AM-BTN-DETACH-MNEMO` automation id.
- `tests/test_desktop_gui_spec_workspace_pages_contract.py` now verifies that hosted animation launches the mnemo viewer through `DesktopResultsRuntime` with current pointer/scene data.
- `tests/test_desktop_gui_spec_workspace_pages_contract.py` now verifies that hosted animation renders `AM-SCENE-PREVIEW` from current scene/pointer/mnemo/capture artifacts without changing artifact filenames.
- `tests/test_desktop_gui_spec_workspace_pages_contract.py` now verifies that `AM-SCENE-NATIVE-PREVIEW` renders a native movement contour from bounded runtime samples and follows the analysis-to-animation handoff artifact.
- `tests/test_desktop_gui_spec_shell_contract.py` now asserts that `animation.diagnostics.prepare` is a hosted command with stable `AM-BTN-HANDOFF-DIAGNOSTICS` automation id.
- `tests/test_desktop_gui_spec_workspace_pages_contract.py`, `tests/test_desktop_gui_spec_diagnostics_hosted_contract.py` and `tests/test_v32_diagnostics_send_bundle_evidence.py` now verify the animation-to-diagnostics handoff, its hosted `DG-ANIMATION-HANDOFF` display, its persistence into diagnostics center-state/summary evidence and its optional `BND-023` SEND-bundle evidence row.
- `tests/test_desktop_gui_spec_shell_contract.py` now asserts that `input.editor.open` is hosted while `input.legacy_editor.open` remains the fallback launch command.
- `tests/test_desktop_gui_spec_shell_runtime_contract.py` and `tests/test_desktop_gui_spec_workspace_pages_contract.py` now verify the hosted input editor table, object names and command routing.
