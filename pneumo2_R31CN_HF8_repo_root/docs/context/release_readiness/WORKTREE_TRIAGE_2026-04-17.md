# Worktree Triage 2026-04-17

Purpose: release-readiness triage for the current mixed dirty tree after the
V32/V33 gate-map pass. This is not a runtime closure claim. It assigns every
currently modified or untracked repo file to a V32 lane, required gate/gap
evidence and a next integration decision.

Active reference order:

1. `00_READ_FIRST__ABSOLUTE_LAW.md`
2. `01_PARAMETER_REGISTRY.md`
3. `DATA_CONTRACT_UNIFIED_KEYS.md`
4. `docs/17_WINDOWS_DESKTOP_CAD_GUI_CANON.md`
5. `docs/18_PNEUMOAPP_WINDOWS_GUI_SPEC.md`
6. `docs/context/gui_spec_imports/v33_connector_reconciled/README.md`
7. `docs/context/gui_spec_imports/v32_connector_reconciled/PARALLEL_CHAT_WORKSTREAMS.md`
8. `docs/context/gui_spec_imports/v32_connector_reconciled/RELEASE_GATE_ACCEPTANCE_MAP.md`

Allowed status values: `keep`, `rework`, `defer`, `needs-review`.

## V32-16 Owned Rows

These rows are owned by `V32-16` for the next integration pass: KB logs,
source-authority docs, v32 gate/gap extracts, release-readiness triage,
gate/workspace metadata helpers and docs-contract tests. `release_gate.py`
is intentionally marked cross-lane because it also contains V32-15 runtime
evidence draft behavior.

## File Triage

| path | status | owner_lane | gate_or_gap | evidence_required | tests | decision |
| --- | --- | --- | --- | --- | --- | --- |
| `.tmp_mnemo_runtime_debug/desktop_mnemo_runtime_bundle.npz` | defer | V32-10 | local debug artifact | Not release evidence; replace with named bundle if needed | `n/a` | Defer from release patch. |
| `.tmp_mnemo_runtime_trace.txt` | defer | V32-10 | local debug artifact | Not release evidence; replace with named trace if needed | `n/a` | Defer from release patch. |
| `.tmp_mnemo_npz_hang_debug/runtime_dataset_exception.npz` | defer | V32-10 | local debug artifact | Not release evidence; replace with named Mnemo runtime bundle if needed | `n/a` | Defer from release patch. |
| `.tmp_mnemo_npz_hang_debug/settings_exception.ini` | defer | V32-10 | local debug artifact | Not release evidence; replace with named Mnemo settings proof if needed | `n/a` | Defer from release patch. |
| `.tmp_mnemo_npz_hang_debug/runtime_dataset_after_fix.desktop_mnemo_events.json` | defer | V32-10 | local debug artifact | Not release evidence; replace with named Mnemo event trace if needed | `n/a` | Defer from release patch. |
| `.tmp_mnemo_npz_hang_debug/runtime_dataset_after_fix.npz` | defer | V32-10 | local debug artifact | Not release evidence; replace with named Mnemo runtime bundle if needed | `n/a` | Defer from release patch. |
| `.tmp_mnemo_npz_hang_debug/settings_after_fix.ini` | defer | V32-10 | local debug artifact | Not release evidence; replace with named Mnemo settings proof if needed | `n/a` | Defer from release patch. |
| `REPORTS/SELF_CHECK_SILENT_WARNINGS.json` | needs-review | V32-16/V32-11 | release self-check warnings | Generated warning report provenance | `release_gate --level quick --run-pytest` | Review generated report before staging. |
| `REPORTS/SELF_CHECK_SILENT_WARNINGS.md` | needs-review | V32-16/V32-11 | release self-check warnings | Human warning report provenance | `release_gate --level quick --run-pytest` | Review generated report before staging. |
| `START_DESKTOP_MAIN_SHELL.py` | needs-review | V32-01 | RGH-009 RGH-020 OG-005 | desktop main shell launcher proof | `tests/test_desktop_gui_spec_shell_contract.py` | Review shell launcher entrypoint. |
| `docs/00_PROJECT_KNOWLEDGE_BASE.md` | keep | V32-16 | v33-v32 source order | KB link evidence | `tests/test_gui_spec_docs_contract.py` | Keep as source map update. |
| `docs/PROJECT_SOURCES.md` | keep | V32-16 | v33-v32 source order | Active release-readiness source link | `tests/test_gui_spec_docs_contract.py` | Keep triage reference in source map. |
| `docs/13_CHAT_REQUIREMENTS_LOG.md` | keep | V32-16 | KB capture | KB generated log | `tests/test_knowledge_base_sync_contract.py` | Keep generated KB entry. |
| `docs/14_CHAT_PLANS_LOG.md` | keep | V32-16 | KB capture | KB generated log | `tests/test_knowledge_base_sync_contract.py` | Keep generated plan entry. |
| `docs/15_CHAT_KNOWLEDGE_BASE.json` | keep | V32-16 | KB capture | Machine-readable KB store | `tests/test_knowledge_base_sync_contract.py` | Keep JSON store update. |
| `docs/context/gui_spec_imports/README.md` | keep | V32-16 | v33-v32 source order | Active reference links | `tests/test_gui_spec_docs_contract.py` | Keep active layer alignment. |
| `docs/context/gui_spec_imports/v32_connector_reconciled/COMPLETENESS_ASSESSMENT.md` | keep | V32-16 | v32 caveat and extracts | Link to checked-in gate extracts | `tests/test_gui_spec_docs_contract.py` | Keep extract caveat. |
| `docs/context/gui_spec_imports/v32_connector_reconciled/PARALLEL_CHAT_WORKSTREAMS.md` | keep | V32-16 | V32-16 prompt | Updated lane startup prompt | `tests/test_gui_spec_docs_contract.py` | Keep V32-16 prompt alignment. |
| `docs/context/gui_spec_imports/v32_connector_reconciled/README.md` | keep | V32-16 | v32 gate extracts | Source-authority links | `tests/test_gui_spec_docs_contract.py` | Keep local extract registration. |
| `docs/context/gui_spec_imports/v32_connector_reconciled/GAP_TO_EVIDENCE_ACTION_MAP.csv` | keep | V32-16 | OG-001..OG-006 | Checked-in v32 gap map rows | `tests/test_gui_spec_docs_contract.py` | Keep minimal extract. |
| `docs/context/gui_spec_imports/v32_connector_reconciled/PRODUCER_ANIMATOR_TRUTH_EVIDENCE_NOTE.md` | keep | V32-14/V32-09/V32-16 | RGH-001 RGH-002 RGH-003 RGH-018 OG-001 OG-002 | Producer/animator truth evidence note with no gap closure | `tests/test_anim_latest_solver_points_contract_gate.py; tests/test_anim_export_contract_gate.py; tests/test_r52_anim_export_contract_blocks.py; tests/test_geometry_acceptance_release_gate.py; tests/test_r31bn_cylinder_truth_gate.py; tests/test_v32_desktop_animator_truth_contract.py` | Keep V32-14/V32-09 truth contract acceptance note; no gap closure. |
| `docs/context/gui_spec_imports/v32_connector_reconciled/COMPARE_OBJECTIVE_INTEGRITY_EVIDENCE_NOTE.md` | keep | V32-06/V32-08/V32-16 | RGH-013 RGH-014 RGH-015 | Compare/objective integrity evidence note with no runtime gap closure | `tests/test_qt_compare_viewer_compare_contract.py; tests/test_qt_compare_viewer_session_autoload_source.py; tests/test_qt_compare_offline_npz_anim_diagnostics.py; tests/test_qt_compare_viewer_dock_object_names.py; tests/test_optimization_objective_contract.py; tests/test_r31cw_optimization_run_history_objective_contract.py; tests/test_optimization_baseline_source_history.py; tests/test_optimization_resume_run_dir.py; tests/test_optimization_staged_resume_run_dir.py` | Keep V32-06/V32-08 contract/provenance acceptance note. |
| `docs/context/gui_spec_imports/v32_connector_reconciled/DIAGNOSTICS_RELEASE_EVIDENCE_NOTE.md` | keep | V32-11/V32-16 | RGH-006 RGH-016 OG-005 | Diagnostics evidence note with bundle paths | `tests/test_v32_diagnostics_send_bundle_evidence.py` | Keep V32-11 diagnostics evidence note. |
| `docs/context/gui_spec_imports/v32_connector_reconciled/PRODUCER_ANIMATOR_TRUTH_EVIDENCE_NOTE.md` | keep | V32-14/V32-09 | RGH-001 RGH-002 RGH-003 RGH-018 OG-001 OG-002 | Producer/animator truth evidence note | `tests/test_anim_export_contract_gate.py; tests/test_v32_desktop_animator_truth_contract.py` | Keep V32-14/V32-09 evidence note; no release closure. |
| `docs/context/gui_spec_imports/v32_connector_reconciled/RUNTIME_RELEASE_EVIDENCE_NOTE.md` | keep | V32-15/V32-16 | RGH-011 RGH-012 RGH-019 OG-003 OG-004 | Runtime evidence hard-gate note | `tests/test_v32_runtime_evidence_gates.py` | Keep V32-15 validator acceptance note; no gap closure. |
| `docs/context/gui_spec_imports/v32_connector_reconciled/WS_INPUTS_HANDOFF_EVIDENCE_NOTE.md` | keep | V32-02/V32-16 | WS-INPUTS HO-002 HO-003 HO-004 HO-005 | Frozen input handoff chain evidence note | `tests/test_gui_spec_docs_contract.py; tests/test_desktop_suite_snapshot.py` | Keep as refs/hash evidence, not runtime closure. |
| `docs/context/gui_spec_imports/v32_connector_reconciled/RELEASE_GATE_ACCEPTANCE_MAP.md` | keep | V32-16 | RGH and OG closure rules | Human release-gate map | `tests/test_gui_spec_docs_contract.py` | Keep as V32-16 anchor. |
| `docs/context/gui_spec_imports/v32_connector_reconciled/RELEASE_GATE_HARDENING_MATRIX.csv` | keep | V32-16 | RGH-001..RGH-020 | Checked-in hardening rows | `tests/test_gui_spec_docs_contract.py` | Keep minimal extract. |
| `docs/context/release_readiness/WORKTREE_TRIAGE_2026-04-17.md` | keep | V32-16 | release readiness triage | One row per dirty file | `tests/test_gui_spec_docs_contract.py` | Keep self-referential triage artifact. |
| `docs/context/release_readiness/V32_16_ACCEPTANCE_NOTE_2026-04-17.md` | keep | V32-16 | V32-16 acceptance pass | Accepted scope, checks and no-runtime-closure rule | `tests/test_gui_spec_docs_contract.py` | Keep V32-16 integration note. |
| `docs/gui_chat_prompts/00_INDEX.md` | keep | V32-16 | prompt index | V32-16 prompt link | `tests/test_gui_spec_docs_contract.py` | Keep index update. |
| `docs/gui_chat_prompts/13_RELEASE_GATES_KB_ACCEPTANCE.md` | keep | V32-16 | V32-16 prompt | Lane scope and no-runtime rule | `tests/test_gui_spec_docs_contract.py` | Keep lane prompt. |
| `pneumo_solver_ui/anim_export_contract.py` | needs-review | V32-14/V32-09 | RGH-001 RGH-002 RGH-018 OG-001 OG-002 | anim_latest contract and geometry acceptance report | `tests/test_anim_export_contract_gate.py` | Review as producer truth draft before merge. |
| `pneumo_solver_ui/anim_export_meta.py` | needs-review | V32-14/V32-09 | RGH-001 RGH-002 | sidecar metadata evidence | `tests/test_r32_triage_and_anim_sidecars.py` | Review with anim export contract. |
| `pneumo_solver_ui/browser_perf_artifacts.py` | keep | V32-15 | RGH-011 RGH-012 RGH-019 OG-003 OG-004 | measured trace artifact | `tests/test_r31bu_browser_perf_artifacts.py` | Keep browser perf evidence writers and summaries. |
| `pneumo_solver_ui/compare_session.py` | needs-review | V32-08 | RGH-014 RGH-015 | compare mismatch contract | `tests/test_qt_compare_viewer_session_autoload_source.py` | Review with compare contract. |
| `pneumo_solver_ui/components/playhead_ctrl/index.html` | keep | V32-15/V32-09 | RGH-019 OG-003 | frame cadence evidence | `tests/test_r78_animator_playback_speed_stability.py` | Keep perf snapshot event export hook; no release closure. |
| `pneumo_solver_ui/desktop_animator/app.py` | needs-review | V32-09 | RGH-002 RGH-003 RGH-019 OG-002 OG-003 | truth badge and frame-budget evidence | `tests/test_v32_desktop_animator_truth_contract.py` | Review animator truth integration. |
| `pneumo_solver_ui/desktop_animator/analysis_context.py` | needs-review | V32-09/V32-13 | RGH-003 WS-ANALYSIS | animator analysis context evidence | `tests/test_v32_desktop_animator_truth_contract.py` | Review animator analysis context helper. |
| `pneumo_solver_ui/desktop_animator/cylinder_truth_gate.py` | needs-review | V32-09/V32-14 | RGH-002 OG-002 | cylinder truth gate report | `tests/test_r31bn_cylinder_truth_gate.py` | Review against packaging passport gap. |
| `pneumo_solver_ui/desktop_animator/truth_contract.py` | needs-review | V32-09/V32-14 | RGH-003 OG-002 | truth-state contract evidence | `tests/test_v32_desktop_animator_truth_contract.py` | Review new animator contract. |
| `pneumo_solver_ui/desktop_diagnostics_model.py` | keep | V32-11 | RGH-006 RGH-016 OG-005 | diagnostics evidence manifest | `tests/test_v32_diagnostics_send_bundle_evidence.py` | Keep diagnostics model evidence surface. |
| `pneumo_solver_ui/desktop_diagnostics_runtime.py` | keep | V32-11 | RGH-006 RGH-016 OG-005 | diagnostics evidence manifest | `tests/test_v32_diagnostics_send_bundle_evidence.py` | Keep diagnostics runtime evidence surface. |
| `pneumo_solver_ui/desktop_engineering_analysis_model.py` | needs-review | V32-13 | WS-ANALYSIS | engineering report provenance | `tests/test_desktop_engineering_analysis_contract.py` | Review new analysis model. |
| `pneumo_solver_ui/desktop_engineering_analysis_runtime.py` | needs-review | V32-13 | WS-ANALYSIS | engineering report provenance | `tests/test_desktop_engineering_analysis_contract.py` | Review new analysis runtime. |
| `pneumo_solver_ui/desktop_geometry_reference_model.py` | needs-review | V32-12 | RGH-018 OG-002 OG-006 | geometry acceptance evidence | `tests/test_desktop_geometry_reference_center_contract.py` | Review geometry reference draft. |
| `pneumo_solver_ui/desktop_geometry_reference_runtime.py` | needs-review | V32-12 | RGH-018 OG-002 OG-006 | geometry acceptance evidence | `tests/test_desktop_geometry_reference_center_contract.py` | Review geometry runtime draft. |
| `pneumo_solver_ui/desktop_input_graphics.py` | needs-review | V32-02 | WS-INPUTS HO-002 HO-003 | source markers and input snapshot | `tests/test_desktop_input_editor_contract.py` | Review input graphic twin changes. |
| `pneumo_solver_ui/desktop_input_model.py` | needs-review | V32-02 | WS-INPUTS HO-002 HO-003 | frozen input snapshot | `tests/test_desktop_input_editor_contract.py` | Review input model changes. |
| `pneumo_solver_ui/desktop_mnemo/app.py` | needs-review | V32-10 | truth graphics policy | mnemo unavailable states | `tests/test_desktop_mnemo_dataset_contract.py` | Review mnemo UI draft. |
| `pneumo_solver_ui/desktop_mnemo/main.py` | needs-review | V32-10 | truth graphics policy | launcher and snapshot provenance | `tests/test_desktop_mnemo_launcher_contract.py` | Review mnemo launcher changes. |
| `pneumo_solver_ui/desktop_mnemo/settings_bridge.py` | needs-review | V32-10 | truth graphics policy | settings bridge evidence | `tests/test_desktop_mnemo_settings_bridge_contract.py` | Review settings bridge changes. |
| `pneumo_solver_ui/desktop_optimizer_model.py` | needs-review | V32-06 | RGH-013 PB-007 | objective contract persistence | `tests/test_desktop_optimizer_center_contract.py` | Review optimizer model changes. |
| `pneumo_solver_ui/desktop_optimizer_runtime.py` | needs-review | V32-06 | RGH-013 PB-007 | run contract and selected run export | `tests/test_desktop_optimizer_center_contract.py` | Review optimizer runtime changes. |
| `pneumo_solver_ui/desktop_optimizer_tabs/contract_tab.py` | needs-review | V32-06 | RGH-013 PB-007 | objective contract UI evidence | `tests/test_desktop_optimizer_center_contract.py` | Review contract tab changes. |
| `pneumo_solver_ui/desktop_qt_shell/coexistence.py` | needs-review | V32-01 | RGH-009 RGH-010 OG-005 | shell runtime proof | `tests/test_desktop_main_shell_qt_contract.py` | Review shell coexistence. |
| `pneumo_solver_ui/desktop_qt_shell/main_window.py` | needs-review | V32-01 | RGH-009 RGH-010 OG-005 | shell runtime proof | `tests/test_desktop_main_shell_qt_contract.py` | Review Qt shell changes. |
| `pneumo_solver_ui/desktop_qt_shell/project_context.py` | needs-review | V32-01 | HO-001 RGH-015 | project context and stale state | `tests/test_desktop_main_shell_qt_contract.py` | Review new project context helper. |
| `pneumo_solver_ui/desktop_qt_shell/runtime_proof.py` | needs-review | V32-01 | RGH-009 RGH-010 OG-005 | shell runtime proof artifact | `tests/test_desktop_main_shell_qt_contract.py` | Review runtime proof helper. |
| `pneumo_solver_ui/desktop_results_model.py` | needs-review | V32-07 | WS-ANALYSIS HO-009 | result evidence manifest input | `tests/test_test_center_results_center_contract.py` | Review results model draft. |
| `pneumo_solver_ui/desktop_results_runtime.py` | needs-review | V32-07 | WS-ANALYSIS HO-009 | validation report evidence | `tests/test_test_center_results_center_contract.py` | Review results runtime draft. |
| `pneumo_solver_ui/desktop_ring_editor_model.py` | needs-review | V32-03 | RGH-004 RGH-005 HO-004 | ring source export set | `tests/test_desktop_ring_editor_contract.py` | Review ring model changes. |
| `pneumo_solver_ui/desktop_ring_editor_panels.py` | needs-review | V32-03 | RGH-004 RGH-005 HO-004 | ring source export set | `tests/test_desktop_ring_editor_contract.py` | Review ring panel changes. |
| `pneumo_solver_ui/desktop_ring_editor_runtime.py` | needs-review | V32-03 | RGH-004 RGH-005 HO-004 | ring source export set | `tests/test_desktop_ring_editor_contract.py` | Review ring runtime changes. |
| `pneumo_solver_ui/desktop_run_setup_runtime.py` | needs-review | V32-04 | WS-SUITE HO-005 | validated suite snapshot | `tests/test_desktop_suite_snapshot.py` | Review suite handoff runtime. |
| `pneumo_solver_ui/desktop_shell/adapters/test_center_adapter.py` | needs-review | V32-07/V32-01 | WS-ANALYSIS RGH-020 | test center discoverability | `tests/test_test_center_results_center_contract.py` | Review shell adapter changes. |
| `pneumo_solver_ui/desktop_shell/adapters/desktop_engineering_analysis_center_adapter.py` | needs-review | V32-13/V32-01 | WS-ANALYSIS RGH-020 | engineering analysis discoverability | `tests/test_desktop_engineering_analysis_contract.py` | Review new shell adapter. |
| `pneumo_solver_ui/desktop_shell/command_search.py` | needs-review | V32-01 | RGH-020 | command search discoverability | `tests/test_desktop_main_shell_qt_contract.py` | Review command aliases. |
| `pneumo_solver_ui/desktop_shell/contracts.py` | needs-review | V32-01 | RGH-009 RGH-015 | shell contract metadata | `tests/test_desktop_main_shell_qt_contract.py` | Review shell contract change. |
| `pneumo_solver_ui/desktop_shell/main_window.py` | needs-review | V32-01 | RGH-009 RGH-010 | shell runtime proof | `tests/test_desktop_main_shell_qt_contract.py` | Review shell window changes. |
| `pneumo_solver_ui/desktop_shell/registry.py` | needs-review | V32-01 | RGH-020 | shell registry discoverability | `tests/test_desktop_shell_parity_contract.py` | Review shell registry changes. |
| `pneumo_solver_ui/desktop_spec_shell/main_window.py` | needs-review | V32-01 | RGH-009 RGH-020 | spec-shell window runtime/discoverability evidence | `tests/test_desktop_gui_spec_shell_contract.py` | Review spec-shell main window changes. |
| `pneumo_solver_ui/desktop_spec_shell/diagnostics_panel.py` | needs-review | V32-11/V32-01 | RGH-006 RGH-020 OG-005 | hosted diagnostics workspace evidence | `tests/test_desktop_gui_spec_diagnostics_hosted_contract.py` | Review hosted diagnostics panel integration. |
| `pneumo_solver_ui/desktop_spec_shell/registry.py` | needs-review | V32-01 | RGH-020 | discoverable entrypoints | `tests/test_desktop_gui_spec_shell_contract.py` | Review spec-shell registry. |
| `pneumo_solver_ui/desktop_spec_shell/workspace_pages.py` | needs-review | V32-01 | RGH-009 RGH-020 | spec-shell workspace page routing | `tests/test_desktop_gui_spec_workspace_pages_contract.py` | Review spec-shell workspace page changes. |
| `pneumo_solver_ui/desktop_spec_shell/workspace_runtime.py` | needs-review | V32-01/V32-15 | RGH-009 RGH-010 OG-005 | workspace runtime proof | `tests/test_desktop_shell_parity_contract.py` | Review spec-shell runtime helper. |
| `pneumo_solver_ui/desktop_suite_runtime.py` | needs-review | V32-04 | WS-SUITE HO-005 | validated suite snapshot | `tests/test_desktop_suite_snapshot.py` | Review new suite runtime helper. |
| `pneumo_solver_ui/desktop_suite_snapshot.py` | needs-review | V32-04 | WS-SUITE HO-005 | validated suite snapshot | `tests/test_desktop_suite_snapshot.py` | Review suite snapshot helper. |
| `pneumo_solver_ui/diagnostics_entrypoint.py` | keep | V32-11 | RGH-006 OG-005 | diagnostics latest pointer | `tests/test_v32_diagnostics_send_bundle_evidence.py` | Keep diagnostics latest pointer hook. |
| `pneumo_solver_ui/geometry_acceptance_contract.py` | needs-review | V32-14/V32-12 | RGH-018 OG-001 OG-006 | geometry acceptance report | `tests/test_geometry_acceptance_release_gate.py` | Review geometry contract changes. |
| `pneumo_solver_ui/npz_bundle.py` | needs-review | V32-11/V32-09 | RGH-006 RGH-019 | bundle sidecar evidence | `tests/test_r32_triage_and_anim_sidecars.py` | Review NPZ sidecar changes. |
| `pneumo_solver_ui/optimization_auto_ring_suite.py` | needs-review | V32-03/V32-04 | RGH-004 HO-004 HO-005 | ring-to-suite lineage | `tests/test_optimization_auto_ring_suite.py` | Review auto ring suite changes. |
| `pneumo_solver_ui/optimization_baseline_source.py` | needs-review | V32-05 | RGH-013 RGH-015 HO-006 | active baseline contract | `tests/test_optimization_baseline_source_history.py` | Review baseline source changes. |
| `pneumo_solver_ui/optimization_baseline_source_ui.py` | needs-review | V32-05 | RGH-013 RGH-015 HO-006 | active baseline contract | `tests/test_optimization_baseline_source_history.py` | Review baseline UI changes. |
| `pneumo_solver_ui/optimization_launch_plan_runtime.py` | needs-review | V32-06 | RGH-013 HO-007 | run contract persistence | `tests/test_optimization_resume_run_dir.py` | Review launch-plan runtime. |
| `pneumo_solver_ui/optimization_objective_contract.py` | needs-review | V32-06 | RGH-013 PB-007 | objective stack and hard gates | `tests/test_optimization_objective_contract.py` | Review objective contract changes. |
| `pneumo_solver_ui/optimization_run_history.py` | needs-review | V32-06/V32-05 | RGH-013 RGH-015 | historical run mismatch evidence | `tests/test_r31cw_optimization_run_history_objective_contract.py` | Review run-history changes. |
| `pneumo_solver_ui/qt_compare_viewer.py` | needs-review | V32-08 | RGH-014 RGH-015 | compare contract and mismatch banner | `tests/test_qt_compare_viewer_compare_contract.py` | Review compare viewer changes. |
| `pneumo_solver_ui/compare_contract.py` | needs-review | V32-08 | RGH-014 RGH-015 | compare contract hash | `tests/test_qt_compare_viewer_compare_contract.py` | Review new compare contract. |
| `pneumo_solver_ui/release_gate.py` | keep | V32-16/V32-15 | RGH-011 RGH-012 RGH-019 OG-003 OG-004 | source metadata and runtime trace evidence | `tests/test_gui_spec_docs_contract.py; tests/test_v32_runtime_evidence_gates.py` | Keep metadata helpers and optional runtime evidence hard gates. |
| `pneumo_solver_ui/run_artifacts.py` | needs-review | V32-07/V32-11 | HO-009 RGH-006 | artifact provenance and evidence manifest | `tests/test_v32_diagnostics_send_bundle_evidence.py` | Review run artifact changes. |
| `pneumo_solver_ui/runtime_evidence.py` | keep | V32-15 | RGH-011 RGH-012 RGH-019 OG-003 OG-004 | measured runtime evidence files | `tests/test_v32_runtime_evidence_gates.py` | Keep runtime evidence hard-fail validator. |
| `pneumo_solver_ui/scenario_generator.py` | needs-review | V32-03 | RGH-004 HO-004 | generator manifest and ring source hash | `tests/test_r56_ring_editor_canonical_segment_semantics.py` | Review generator changes. |
| `pneumo_solver_ui/scenario_ring.py` | needs-review | V32-03 | RGH-004 RGH-005 HO-004 | canonical ring scenario export | `tests/test_r56_ring_editor_canonical_segment_semantics.py` | Review scenario ring changes. |
| `pneumo_solver_ui/send_bundle.py` | keep | V32-11 | RGH-006 RGH-016 OG-005 | SEND bundle evidence manifest | `tests/test_v32_diagnostics_send_bundle_evidence.py` | Keep SEND bundle evidence integration. |
| `pneumo_solver_ui/tools/desktop_diagnostics_center.py` | keep | V32-11 | RGH-006 OG-005 | one-click diagnostics surface | `tests/test_desktop_diagnostics_center_contract.py` | Keep diagnostics center evidence surface. |
| `pneumo_solver_ui/tools/desktop_engineering_analysis_center.py` | needs-review | V32-13 | WS-ANALYSIS | engineering analysis launcher | `tests/test_desktop_engineering_analysis_contract.py` | Review new engineering center. |
| `pneumo_solver_ui/tools/desktop_geometry_reference_center.py` | needs-review | V32-12 | RGH-018 OG-002 OG-006 | geometry reference evidence | `tests/test_desktop_geometry_reference_center_contract.py` | Review geometry center. |
| `pneumo_solver_ui/tools/desktop_gui_spec_shell.py` | needs-review | V32-01 | RGH-009 RGH-020 | spec-shell launcher discoverability | `tests/test_desktop_gui_spec_shell_contract.py` | Review spec-shell launcher changes. |
| `pneumo_solver_ui/tools/desktop_input_editor.py` | needs-review | V32-02 | WS-INPUTS HO-002 HO-003 | input snapshot handoff | `tests/test_desktop_input_editor_contract.py` | Review input editor changes. |
| `pneumo_solver_ui/tools/desktop_optimizer_center.py` | needs-review | V32-06 | RGH-013 PB-007 | objective contract UI | `tests/test_desktop_optimizer_center_contract.py` | Review optimizer center. |
| `pneumo_solver_ui/tools/desktop_results_center.py` | needs-review | V32-07 | WS-ANALYSIS HO-009 | validation evidence surface | `tests/test_test_center_results_center_contract.py` | Review results center. |
| `pneumo_solver_ui/tools/desktop_ring_scenario_editor.py` | needs-review | V32-03 | RGH-004 HO-004 | ring source handoff | `tests/test_desktop_ring_editor_contract.py` | Review ring editor launcher. |
| `pneumo_solver_ui/tools/desktop_run_setup_center.py` | needs-review | V32-04 | WS-SUITE HO-005 | suite setup center evidence | `tests/test_desktop_run_setup_center_contract.py` | Review run setup center changes. |
| `pneumo_solver_ui/tools/health_report.py` | keep | V32-11 | RGH-006 RGH-007 OG-005 | health after final triage | `tests/test_health_report_inspect_send_bundle_anim_diagnostics.py` | Keep health evidence warning propagation. |
| `pneumo_solver_ui/tools/inspect_send_bundle.py` | keep | V32-11 | RGH-006 RGH-016 OG-005 | helper runtime provenance | `tests/test_health_report_inspect_send_bundle_anim_diagnostics.py` | Keep bundle inspection evidence. |
| `pneumo_solver_ui/tools/knowledge_base_sync.py` | keep | V32-16 | KB capture | seeded release-readiness entries | `tests/test_knowledge_base_sync_contract.py` | Keep KB seed update. |
| `pneumo_solver_ui/tools/desktop_main_shell_qt.py` | needs-review | V32-01 | RGH-009 RGH-020 OG-005 | main shell Qt launcher proof | `tests/test_desktop_main_shell_qt_contract.py` | Review shell launcher draft. |
| `pneumo_solver_ui/tools/launch_ui.py` | needs-review | V32-01 | RGH-009 RGH-020 | launcher discoverability | `tests/test_desktop_main_shell_qt_contract.py` | Review launcher changes. |
| `pneumo_solver_ui/tools/make_send_bundle.py` | keep | V32-11 | RGH-006 RGH-016 OG-005 | bundle evidence contents | `tests/test_v32_diagnostics_send_bundle_evidence.py` | Keep final evidence manifest and latest pointer flow. |
| `pneumo_solver_ui/tools/postmortem_watchdog.py` | keep | V32-11 | RGH-006 RGH-007 OG-005 | crash/exit diagnostics evidence | `tests/test_v32_diagnostics_send_bundle_evidence.py` | Keep watchdog trigger provenance. |
| `pneumo_solver_ui/tools/send_bundle_evidence.py` | keep | V32-11 | RGH-006 RGH-016 OG-005 | evidence manifest helper | `tests/test_v32_diagnostics_send_bundle_evidence.py` | Keep evidence manifest helper. |
| `pneumo_solver_ui/tools/test_center_gui.py` | needs-review | V32-07 | WS-ANALYSIS RGH-020 | test center result evidence | `tests/test_test_center_results_center_contract.py` | Review test center changes. |
| `pneumo_solver_ui/tools/validate_send_bundle.py` | keep | V32-11 | RGH-006 RGH-016 OG-005 | bundle validation evidence | `tests/test_v32_diagnostics_send_bundle_evidence.py` | Keep validation evidence warnings. |
| `pneumo_solver_ui/workspace_contract.py` | keep | V32-16 | workspace and handoff metadata | V32 workspace IDs and reference paths | `tests/test_gui_spec_docs_contract.py` | Keep metadata-only helper. |
| `START_DESKTOP_MAIN_SHELL.py` | needs-review | V32-01 | RGH-009 RGH-020 | desktop shell startup route | `tests/test_desktop_gui_spec_shell_contract.py` | Review desktop shell startup wrapper. |
| `START_PNEUMO_APP.py` | needs-review | V32-01 | RGH-009 RGH-020 | desktop app startup route | `tests/test_desktop_main_shell_qt_contract.py` | Review app startup wrapper. |
| `pneumo_solver_ui/desktop_animator/main.py` | needs-review | V32-09 | RGH-002 RGH-003 RGH-019 | animator desktop launcher evidence | `tests/test_v32_desktop_animator_truth_contract.py` | Review animator desktop launcher changes. |
| `pneumo_solver_ui/desktop_shell/adapters/desktop_animator_adapter.py` | needs-review | V32-09/V32-01 | RGH-019 RGH-020 | animator shell adapter discoverability | `tests/test_desktop_shell_parity_contract.py` | Review animator shell adapter changes. |
| `pneumo_solver_ui/optimization_stage_runner_config_ui.py` | needs-review | V32-06 | RGH-013 PB-007 | staged optimizer config UI | `tests/test_optimization_staged_resume_run_dir.py` | Review staged optimizer config UI changes. |
| `pneumo_solver_ui/pneumo_ui_app.py` | needs-review | V32-01/V32-04 | RGH-008 RGH-020 | legacy app entrypoint parity | `tests/test_desktop_main_shell_qt_contract.py` | Review app entrypoint changes. |
| `tests/test_codex_github_handoff_contract.py` | needs-review | V32-16 | docs contract | Codex/GitHub handoff contract tests | `tests/test_codex_github_handoff_contract.py` | Review GitHub handoff contract test. |
| `tests/test_r49_animator_layout_suspend_and_timer_budget.py` | needs-review | V32-09/V32-15 | RGH-019 OG-003 | animator layout suspend and timer-budget tests | `tests/test_r49_animator_layout_suspend_and_timer_budget.py` | Review animator timer-budget test draft. |
| `tests/test_r51_animator_display_rate_and_idle_stop.py` | needs-review | V32-09/V32-15 | RGH-019 OG-003 | animator display-rate and idle-stop tests | `tests/test_r51_animator_display_rate_and_idle_stop.py` | Review animator display-rate test draft. |
| `tests/test_anim_export_contract_gate.py` | needs-review | V32-14/V32-09 | RGH-001 RGH-002 | producer truth test coverage | `tests/test_anim_export_contract_gate.py` | Review with anim export contract. |
| `tests/test_desktop_engineering_analysis_contract.py` | needs-review | V32-13 | WS-ANALYSIS | engineering analysis contract test | `tests/test_desktop_engineering_analysis_contract.py` | Review new test. |
| `tests/test_desktop_engineering_analysis_center_contract.py` | needs-review | V32-13/V32-01 | WS-ANALYSIS RGH-020 | engineering analysis center contract test | `tests/test_desktop_engineering_analysis_center_contract.py` | Review new center test. |
| `tests/test_desktop_diagnostics_center_contract.py` | keep | V32-11 | RGH-006 OG-005 | diagnostics center contract test | `tests/test_desktop_diagnostics_center_contract.py` | Keep diagnostics center tests. |
| `tests/test_desktop_gui_spec_diagnostics_hosted_contract.py` | needs-review | V32-11/V32-01 | RGH-006 RGH-020 OG-005 | hosted diagnostics workspace contract test | `tests/test_desktop_gui_spec_diagnostics_hosted_contract.py` | Review hosted diagnostics spec-shell test. |
| `tests/test_desktop_gui_spec_shell_contract.py` | needs-review | V32-01 | RGH-009 RGH-020 | spec-shell contract tests | `tests/test_desktop_gui_spec_shell_contract.py` | Review spec-shell test changes. |
| `tests/test_desktop_gui_spec_workspace_pages_contract.py` | needs-review | V32-01 | RGH-009 RGH-020 | workspace page contract tests | `tests/test_desktop_gui_spec_workspace_pages_contract.py` | Review workspace page test changes. |
| `tests/test_desktop_geometry_reference_center_contract.py` | needs-review | V32-12 | RGH-018 OG-006 | geometry reference tests | `tests/test_desktop_geometry_reference_center_contract.py` | Review geometry tests. |
| `tests/test_desktop_input_editor_contract.py` | needs-review | V32-02 | WS-INPUTS HO-002 HO-003 | input editor tests | `tests/test_desktop_input_editor_contract.py` | Review input tests. |
| `tests/test_desktop_main_shell_qt_contract.py` | needs-review | V32-01 | RGH-009 RGH-010 | shell contract tests | `tests/test_desktop_main_shell_qt_contract.py` | Review shell tests. |
| `tests/test_desktop_mnemo_dataset_contract.py` | needs-review | V32-10 | truth graphics policy | mnemo dataset tests | `tests/test_desktop_mnemo_dataset_contract.py` | Review mnemo tests. |
| `tests/test_desktop_mnemo_launcher_contract.py` | needs-review | V32-10 | truth graphics policy | mnemo launcher tests | `tests/test_desktop_mnemo_launcher_contract.py` | Review mnemo launcher tests. |
| `tests/test_desktop_mnemo_settings_bridge_contract.py` | needs-review | V32-10 | truth graphics policy | settings bridge tests | `tests/test_desktop_mnemo_settings_bridge_contract.py` | Review settings tests. |
| `tests/test_desktop_mnemo_snapshot_contract.py` | needs-review | V32-10 | truth graphics policy | mnemo snapshot tests | `tests/test_desktop_mnemo_snapshot_contract.py` | Review snapshot tests. |
| `tests/test_desktop_mnemo_window_contract.py` | needs-review | V32-10 | truth graphics policy | mnemo window tests | `tests/test_desktop_mnemo_window_contract.py` | Review mnemo window tests. |
| `tests/test_desktop_optimizer_center_contract.py` | needs-review | V32-06 | RGH-013 PB-007 | optimizer center tests | `tests/test_desktop_optimizer_center_contract.py` | Review optimizer tests. |
| `tests/test_desktop_ring_editor_contract.py` | needs-review | V32-03 | RGH-004 HO-004 | ring editor tests | `tests/test_desktop_ring_editor_contract.py` | Review ring tests. |
| `tests/test_desktop_run_setup_center_contract.py` | needs-review | V32-04 | WS-SUITE HO-005 | run setup center tests | `tests/test_desktop_run_setup_center_contract.py` | Review run setup tests. |
| `tests/test_desktop_shell_parity_contract.py` | needs-review | V32-01 | RGH-009 RGH-020 | shell parity tests | `tests/test_desktop_shell_parity_contract.py` | Review shell parity tests. |
| `tests/test_desktop_suite_snapshot.py` | needs-review | V32-04 | WS-SUITE HO-005 | suite snapshot tests | `tests/test_desktop_suite_snapshot.py` | Review new suite tests. |
| `tests/test_geometry_acceptance_release_gate.py` | needs-review | V32-14/V32-12 | RGH-018 OG-006 | geometry release gate tests | `tests/test_geometry_acceptance_release_gate.py` | Review geometry gate tests. |
| `tests/test_gui_spec_docs_contract.py` | keep | V32-16 | docs contract | triage and source-order tests | `tests/test_gui_spec_docs_contract.py` | Keep docs contract update. |
| `tests/test_health_report_inspect_send_bundle_anim_diagnostics.py` | keep | V32-11/V32-09 | RGH-006 RGH-016 RGH-019 OG-005 | health/send-bundle/anim diagnostics tests | `tests/test_health_report_inspect_send_bundle_anim_diagnostics.py` | Keep diagnostics regression coverage. |
| `tests/test_knowledge_base_sync_contract.py` | keep | V32-16 | KB capture | KB release-readiness assertions | `tests/test_knowledge_base_sync_contract.py` | Keep KB test update. |
| `tests/test_optimization_auto_ring_suite.py` | needs-review | V32-03/V32-04 | RGH-004 HO-005 | auto ring suite tests | `tests/test_optimization_auto_ring_suite.py` | Review auto suite tests. |
| `tests/test_optimization_baseline_source_history.py` | needs-review | V32-05 | RGH-013 RGH-015 | baseline history tests | `tests/test_optimization_baseline_source_history.py` | Review baseline tests. |
| `tests/test_optimization_objective_contract.py` | needs-review | V32-06 | RGH-013 PB-007 | objective contract tests | `tests/test_optimization_objective_contract.py` | Review objective tests. |
| `tests/test_optimization_resume_run_dir.py` | needs-review | V32-06 | RGH-013 | resume mismatch tests | `tests/test_optimization_resume_run_dir.py` | Review resume tests. |
| `tests/test_optimization_staged_resume_run_dir.py` | needs-review | V32-06 | RGH-013 | staged resume tests | `tests/test_optimization_staged_resume_run_dir.py` | Review staged resume tests. |
| `tests/test_qt_compare_offline_npz_anim_diagnostics.py` | needs-review | V32-08/V32-09 | RGH-014 RGH-019 | compare animator diagnostics tests | `tests/test_qt_compare_offline_npz_anim_diagnostics.py` | Review compare diagnostics tests. |
| `tests/test_qt_compare_viewer_compare_contract.py` | needs-review | V32-08 | RGH-014 RGH-015 | compare contract tests | `tests/test_qt_compare_viewer_compare_contract.py` | Review new compare tests. |
| `tests/test_qt_compare_viewer_dock_object_names.py` | needs-review | V32-08/V32-01 | RGH-009 RGH-014 | compare dock tests | `tests/test_qt_compare_viewer_dock_object_names.py` | Review compare dock tests. |
| `tests/test_qt_compare_viewer_session_autoload_source.py` | needs-review | V32-08 | RGH-014 RGH-015 | compare session autoload tests | `tests/test_qt_compare_viewer_session_autoload_source.py` | Review compare autoload tests. |
| `tests/test_r31bn_cylinder_truth_gate.py` | needs-review | V32-09/V32-14 | RGH-002 OG-002 | cylinder truth tests | `tests/test_r31bn_cylinder_truth_gate.py` | Review cylinder truth tests. |
| `tests/test_r31bu_browser_perf_artifacts.py` | keep | V32-15 | RGH-011 OG-003 | browser perf artifact tests | `tests/test_r31bu_browser_perf_artifacts.py` | Keep browser perf artifact tests. |
| `tests/test_r31cw_optimization_run_history_objective_contract.py` | needs-review | V32-06 | RGH-013 RGH-015 | run history objective tests | `tests/test_r31cw_optimization_run_history_objective_contract.py` | Review run history tests. |
| `tests/test_r32_triage_and_anim_sidecars.py` | needs-review | V32-11/V32-09 | RGH-006 RGH-019 | sidecar diagnostics tests | `tests/test_r32_triage_and_anim_sidecars.py` | Review sidecar tests. |
| `tests/test_r42_bundle_stable_road_grid_and_aux_cadence_metrics.py` | keep | V32-11/V32-15 | RGH-006 RGH-019 | bundle cadence evidence tests | `tests/test_r42_bundle_stable_road_grid_and_aux_cadence_metrics.py` | Keep cadence evidence tests. |
| `tests/test_r52_anim_export_contract_blocks.py` | needs-review | V32-14/V32-09 | RGH-001 RGH-002 | anim export block tests | `tests/test_r52_anim_export_contract_blocks.py` | Review anim export tests. |
| `tests/test_r56_ring_editor_canonical_segment_semantics.py` | needs-review | V32-03 | RGH-004 HO-004 | ring segment semantics tests | `tests/test_r56_ring_editor_canonical_segment_semantics.py` | Review ring semantics tests. |
| `tests/test_r64_qt_compare_viewer_workspace_layout_runtime.py` | needs-review | V32-08/V32-15 | RGH-014 OG-003 | compare workspace runtime tests | `tests/test_r64_qt_compare_viewer_workspace_layout_runtime.py` | Review compare runtime test draft. |
| `tests/test_r65_qt_compare_viewer_real_bundle_runtime_smoke.py` | needs-review | V32-08/V32-15 | RGH-014 OG-004 | real bundle runtime smoke tests | `tests/test_r65_qt_compare_viewer_real_bundle_runtime_smoke.py` | Review real bundle smoke test draft. |
| `tests/test_r78_animator_playback_speed_stability.py` | keep | V32-09/V32-15 | RGH-019 OG-003 | animator frame cadence tests | `tests/test_r78_animator_playback_speed_stability.py` | Keep playback cadence evidence tests. |
| `tests/test_test_center_results_center_contract.py` | needs-review | V32-07 | WS-ANALYSIS HO-009 | results center tests | `tests/test_test_center_results_center_contract.py` | Review results tests. |
| `tests/test_v32_desktop_animator_truth_contract.py` | needs-review | V32-09/V32-14 | RGH-002 RGH-003 OG-002 | animator truth tests | `tests/test_v32_desktop_animator_truth_contract.py` | Review new animator tests. |
| `tests/test_v32_diagnostics_send_bundle_evidence.py` | keep | V32-11 | RGH-006 RGH-016 OG-005 | diagnostics evidence tests | `tests/test_v32_diagnostics_send_bundle_evidence.py` | Keep V32-11 diagnostics evidence suite. |
| `tests/test_v32_runtime_evidence_gates.py` | keep | V32-15 | RGH-011 RGH-012 RGH-019 OG-003 OG-004 | runtime evidence gate tests | `tests/test_v32_runtime_evidence_gates.py` | Keep runtime evidence hard-gate tests. |
