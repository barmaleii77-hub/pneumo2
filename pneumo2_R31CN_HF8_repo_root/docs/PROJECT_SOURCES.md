# Источники проекта и контекста

## Канон внутри релиза

1. `00_READ_FIRST__ABSOLUTE_LAW.md` — абсолютный закон проекта.
2. `01_PARAMETER_REGISTRY.md` — единый реестр параметров.
3. `DATA_CONTRACT_UNIFIED_KEYS.md` — единый контракт ключей.
4. `docs/context/PROJECT_CONTEXT_ANALYSIS.md` — локальная сводка контекста.
5. `docs/11_TODO.md` — рабочий TODO-снимок.
6. `docs/12_Wishlist.md` — рабочий wishlist-снимок.

## GUI knowledge stack

### Human-readable canon

- `docs/17_WINDOWS_DESKTOP_CAD_GUI_CANON.md` — project-wide Windows desktop/CAD baseline.
- `docs/18_PNEUMOAPP_WINDOWS_GUI_SPEC.md` — project-specific GUI contract для `Пневмоподвески`.

### Imported detailed reference

- `docs/context/gui_spec_imports/README.md` — верхний source note для imported GUI-spec layers.
- `docs/context/gui_spec_imports/foundations/README.md` — upstream prompt layer, предшествующий серии архивов `v1…v13`.
- `docs/context/gui_spec_imports/foundations/prompt_gui_windows_cad_pneumo_augmented_v2_2026-04-13.md` — foundational prompt source (`PROMPT_V2`).
- `docs/context/gui_spec_imports/v38_actualized_with_v10/README.md` — current active successor consolidated GUI-spec / knowledge-base layer из `pneumo_codex_tz_spec_connector_reconciled_v38_actualized_with_v10.zip`; актуализирует V38 с учётом V10 launcher hierarchy и не является runtime-closure proof.
- `docs/context/gui_spec_imports/v38_actualized_with_v10/TECHNICAL_SPECIFICATION.md` — active V38+V10 human-readable technical specification with launcher hierarchy actualization.
- `docs/context/gui_spec_imports/v38_actualized_with_v10/GUI_SPEC.yaml` — active V38+V10 machine-readable GUI-spec/TZ connector.
- `docs/context/gui_spec_imports/v38_actualized_with_v10/LAUNCHER_HIERARCHY_RECONCILIATION_V10.md` — V10 reconciliation: один доминирующий 8-шаговый маршрут, nested send-results, primary embedded compare and secondary Mnemo/Tools.
- `docs/context/gui_spec_imports/v38_actualized_with_v10/V10_RECONCILIATION_MATRIX.csv` — matrix integration of V10 findings into V38.
- `docs/context/gui_spec_imports/v38_actualized_with_v10/REQUIREMENTS_MATRIX.csv` — requirements matrix with `REQ-046` ... `REQ-050`.
- `docs/context/release_readiness/V38_ACTUALIZED_WITH_V10_KB_IMPORT_AUDIT_2026-04-19.md` — local V38+V10 import audit: read coverage, priority, conflict resolution and open runtime gaps.
- `docs/context/gui_spec_imports/v19_graph_iteration/README.md` — active graph/action-feedback refinement layer for `WS-INPUTS`, `WS-RING`, `WS-OPTIMIZATION` and `WS-DIAGNOSTICS`; imported from `pneumo_gui_graph_iteration_v19.zip` and not a runtime-closure proof.
- `docs/context/gui_spec_imports/v19_graph_iteration/EXEC_SUMMARY.json` — V19 package metrics and workspace scope.
- `docs/context/gui_spec_imports/v19_graph_iteration/GRAPH_ANALYSIS_REPORT_V19.md` — action-to-feedback graph analysis and evidence boundary.
- `docs/context/gui_spec_imports/v19_graph_iteration/SEMANTIC_FIX_PRIORITY_V19.md` — semantic label/microcopy priority list.
- `docs/context/gui_spec_imports/v19_graph_iteration/USER_ACTION_FEEDBACK_MATRIX_V19.csv` — user action -> feedback route matrix.
- `docs/context/gui_spec_imports/v19_graph_iteration/TASK_CHECK_BLOCK_LOOP_MATRIX_V19.csv` — task/check/block/loop contract matrix.
- `docs/context/gui_spec_imports/v19_graph_iteration/COGNITIVE_VISIBILITY_MATRIX_V19.csv` — cognitive visibility requirements.
- `docs/context/gui_spec_imports/v19_graph_iteration/TREE_DIRECT_OPEN_MATRIX_V19.csv` — direct-open route requirements.
- `docs/context/gui_spec_imports/v19_graph_iteration/DOCK_WINDOW_AND_DOCK_WIDGET_MATRIX_V19.csv` — dock/window expectations.
- `docs/context/gui_spec_imports/v19_graph_iteration/GUI_LABEL_SEMANTIC_AUDIT_V19.csv` — label semantic audit for optimized/current graph nodes.
- `docs/context/gui_spec_imports/v19_graph_iteration/SUBGRAPH_OPTIMIZED_WS-INPUTS_V19.dot` — optimized `WS-INPUTS` subgraph; companion current/optimized DOT files cover `WS-RING`, `WS-OPTIMIZATION` and `WS-DIAGNOSTICS`.
- `docs/context/gui_spec_imports/v12_window_internal_routes/README.md` — current report-only first-screen/internal-route layer из `pneumo_human_gui_report_only_v12_window_internal_routes.zip`; separate from historical `v12_design_recovery` and not a runtime-closure proof.
- `docs/context/gui_spec_imports/v12_window_internal_routes/WINDOW_FIRST_SCREEN_CONTRACT_V12.md` — first-screen contracts для поверхности проверки и отправки архива, подробного сравнения результатов, исходных данных проекта и набора испытаний.
- `docs/context/gui_spec_imports/v12_window_internal_routes/WINDOW_ACTION_FEEDBACK_MATRIX_V12.csv` — primary action -> feedback matrix для четырех окон.
- `docs/context/gui_spec_imports/v12_window_internal_routes/DIRECT_TREE_OPEN_AND_DOCK_ROLE_V12.csv` — direct tree open, window role and dock role rules.
- `docs/context/gui_spec_imports/v12_window_internal_routes/SEMANTIC_REWRITE_MATRIX_V12.csv` — semantic rewrite matrix for operator-facing labels and implementation-term leaks.
- `docs/context/gui_spec_imports/v12_window_internal_routes/LIMITS_AND_NOT_OPENED_V12.md` — evidence boundary: current internals are not proven by this layer.
- `docs/context/release_readiness/HUMAN_GUI_REPORT_ONLY_V12_WINDOW_INTERNAL_ROUTES_2026-04-20.md` — local V12 import audit and KB reconciliation for four under-proven windows.
- `docs/context/gui_spec_imports/v15_state_continuity_repair_loops/README.md` — current report-only state-continuity and repair-loop layer из `pneumo_human_gui_report_only_v15_state_continuity_repair_loops.zip`; not a runtime-closure proof.
- `docs/context/gui_spec_imports/v15_state_continuity_repair_loops/STATE_CONTINUITY_AND_REPAIR_LOOP_CONTRACT_V15.md` — human-readable continuity contract for dirty/invalid/stale/mismatch/degraded states.
- `docs/context/gui_spec_imports/v15_state_continuity_repair_loops/WINDOW_STATE_MARKER_MATRIX_V15.csv` — workspace state -> visible marker/action/return-target matrix.
- `docs/context/gui_spec_imports/v15_state_continuity_repair_loops/REPAIR_LOOP_POLICY_V15.csv` — trigger -> first feedback -> repair action -> resolved state policy.
- `docs/context/gui_spec_imports/v15_state_continuity_repair_loops/CONTEXT_RESTORE_AND_RETURN_TARGETS_V15.csv` — handoff/repair return target and selection restore matrix.
- `docs/context/gui_spec_imports/v15_state_continuity_repair_loops/ENTRY_STATE_REPAIR_GRAPH_V15.dot` — state repair graph for entry/return flows.
- `docs/context/release_readiness/HUMAN_GUI_REPORT_ONLY_V15_STATE_CONTINUITY_REPAIR_LOOPS_2026-04-21.md` — local V15 import audit and KB reconciliation for continuity/repair-loop rules.
- `docs/context/gui_spec_imports/v16_visibility_priority/README.md` — current report-only visibility-priority and must-see state layer из `pneumo_human_gui_report_only_v16_visibility_priority.zip`; not a runtime-closure proof.
- `docs/context/gui_spec_imports/v16_visibility_priority/VISIBILITY_PRIORITY_POLICY_V16.md` — visibility hierarchy: always visible, conditionally escalated and inspector/help/details.
- `docs/context/gui_spec_imports/v16_visibility_priority/MUST_SEE_STATE_MATRIX_V16.csv` — must-see state matrix for user trust, next action and result interpretation.
- `docs/context/gui_spec_imports/v16_visibility_priority/ALWAYS_VISIBLE_CONDITIONAL_INSPECTOR_MATRIX_V16.csv` — placement policy for always-visible, conditional and inspector-only states.
- `docs/context/gui_spec_imports/v16_visibility_priority/DOCK_REGION_VISIBILITY_POLICY_V16.csv` — dock/message/status/inspector visibility policy.
- `docs/context/gui_spec_imports/v16_visibility_priority/WORKSPACE_FIRST_5_SECONDS_V16.csv` — first 3-5 seconds workspace comprehension contract.
- `docs/context/gui_spec_imports/v16_visibility_priority/VISIBILITY_ESCALATION_GRAPH_V16.dot` — escalation graph from hidden detail to message/bar/blocker/return-route state.
- `docs/context/release_readiness/HUMAN_GUI_REPORT_ONLY_V16_VISIBILITY_PRIORITY_2026-04-21.md` — local V16 import audit and KB reconciliation for visibility priority and inspector/help boundaries.
- `docs/context/gui_spec_imports/v38_github_kb_commit_ready/README.md` — predecessor consolidated GUI-spec / knowledge-base commit-ready layer из `pneumo_codex_tz_spec_connector_reconciled_v38_github_kb_commit_ready.zip`; не является runtime-closure proof.
- `docs/context/gui_spec_imports/v38_github_kb_commit_ready/TECHNICAL_SPECIFICATION.md` — V38 human-readable technical specification with local ambiguity audit boundary.
- `docs/context/gui_spec_imports/v38_github_kb_commit_ready/GUI_SPEC.yaml` — V38 machine-readable successor GUI-spec/TZ connector.
- `docs/context/gui_spec_imports/v38_github_kb_commit_ready/WORKSPACE_CONTRACT_MATRIX.csv` — V38 workspace contract matrix.
- `docs/context/gui_spec_imports/v38_github_kb_commit_ready/PARAMETER_CATALOG.csv` — V38 consolidated parameter catalog.
- `docs/context/gui_spec_imports/v38_github_kb_commit_ready/PARAMETER_PIPELINE_MATRIX.csv` — V38 связь параметров с pipeline.
- `docs/context/gui_spec_imports/v38_github_kb_commit_ready/PARAMETER_VISIBILITY_MATRIX.csv` — V38 visibility/editability matrix для параметров.
- `docs/context/gui_spec_imports/v38_github_kb_commit_ready/ACCEPTANCE_MATRIX.csv` — V38 acceptance matrix.
- `docs/context/gui_spec_imports/v38_github_kb_commit_ready/REQUIREMENTS_MATRIX.csv` — V38 requirements matrix.
- `docs/context/gui_spec_imports/v38_github_kb_commit_ready/REPO_OPEN_GAPS_TO_KEEP_OPEN.csv` — V38 gaps, которые нельзя скрывать как закрытые.
- `docs/context/gui_spec_imports/v38_github_kb_commit_ready/NON_RUNTIME_CLOSURE_NOTICE.md` — явное ограничение: V38 не является runtime-closure proof.
- `docs/context/release_readiness/V38_KB_IMPORT_AUDIT_2026-04-18.md` — local V38 import audit: полный read coverage, ambiguity resolution and current read order.
- `docs/context/release_readiness/GUI_TEXT_SEMANTIC_AUDIT_2026-04-19.md` — semantic audit кнопок, надписей, user-facing vocabulary, V38 naming ambiguities and `PIPELINE_OPTIMIZED.dot` alignment for desktop GUI.
- `docs/context/gui_spec_imports/v37_github_kb_supplement/README.md` — predecessor consolidated GitHub knowledge-base supplement layer; не является runtime-closure proof.
- `docs/context/gui_spec_imports/v37_github_kb_supplement/TECHNICAL_SPECIFICATION.md` — predecessor human-readable ТЗ/spec connector для Windows desktop GUI.
- `docs/context/gui_spec_imports/v37_github_kb_supplement/GUI_SPEC.yaml` — predecessor machine-readable GUI-spec/TZ connector.
- `docs/context/gui_spec_imports/v37_github_kb_supplement/WORKSPACE_CONTRACT_MATRIX.csv` — workspace contract matrix.
- `docs/context/gui_spec_imports/v37_github_kb_supplement/PARAMETER_CATALOG.csv` — consolidated parameter catalog.
- `docs/context/gui_spec_imports/v37_github_kb_supplement/PARAMETER_PIPELINE_MATRIX.csv` — связь параметров с pipeline.
- `docs/context/gui_spec_imports/v37_github_kb_supplement/PARAMETER_VISIBILITY_MATRIX.csv` — visibility/editability matrix для параметров.
- `docs/context/gui_spec_imports/v37_github_kb_supplement/ACCEPTANCE_MATRIX.csv` — acceptance matrix для требований.
- `docs/context/gui_spec_imports/v37_github_kb_supplement/REQUIREMENTS_MATRIX.csv` — requirements matrix.
- `docs/context/gui_spec_imports/v37_github_kb_supplement/REPO_GITHUB_KB_SUPPLEMENT.md` — summary того, что v37 добавляет к GitHub KB.
- `docs/context/gui_spec_imports/v37_github_kb_supplement/REPO_OPEN_GAPS_TO_KEEP_OPEN.csv` — открытые gaps, которые нельзя скрывать как закрытые.
- `docs/context/gui_spec_imports/v37_github_kb_supplement/NON_RUNTIME_CLOSURE_NOTICE.md` — явное ограничение: v37 не является runtime-closure proof.
- `docs/context/gui_spec_imports/v33_connector_reconciled/README.md` — active connector-reconciled GUI/TZ digest из `pneumo_codex_tz_spec_connector_reconciled_v33.zip`; фиксирует v33 integrity policy, selfcheck/remediation, repo-canon read-order/gate mapping и dedicated PB-008 playbook.
- `docs/context/gui_spec_imports/v33_connector_reconciled/COMPLETENESS_ASSESSMENT.md` — оценка полноты и достаточности v33: structural checks, coverage checks, caveats и runtime limits.
- `docs/context/gui_spec_imports/v32_connector_reconciled/README.md` — previous connector-reconciled GUI/TZ digest из `pneumo_codex_tz_spec_connector_reconciled_v32.zip`; фиксирует source authority, reading order, 12 workspaces, v32 playbooks, release gates, open gaps и runtime-evidence policy.
- `docs/context/gui_spec_imports/v32_connector_reconciled/COMPLETENESS_ASSESSMENT.md` — оценка полноты и достаточности v32: structural checks, coverage checks, caveats и границы применимости.
- `docs/context/gui_spec_imports/v32_connector_reconciled/PARALLEL_CHAT_WORKSTREAMS.md` — матрица независимых параллельных workstreams и стартовые промты для чатов.
- `docs/context/gui_spec_imports/v32_connector_reconciled/RELEASE_GATE_ACCEPTANCE_MAP.md` — local release-gate/acceptance/evidence map для `V32-16`.
- `docs/context/gui_spec_imports/v32_connector_reconciled/RELEASE_GATE_HARDENING_MATRIX.csv` — checked-in v32 extract: 20 release hardening rows.
- `docs/context/gui_spec_imports/v32_connector_reconciled/GAP_TO_EVIDENCE_ACTION_MAP.csv` — checked-in v32 extract: 6 open gap -> evidence action rows.
- `docs/context/gui_spec_imports/v32_connector_reconciled/WS_INPUTS_HANDOFF_EVIDENCE_NOTE.md` — V32-02/V32-04 frozen inputs/suite handoff evidence note для `WS-INPUTS`, `WS-RING`, `WS-SUITE`, `WS-BASELINE`, `HO-002`, `HO-003`, `HO-004`, `HO-005`.
- `docs/context/gui_spec_imports/v32_connector_reconciled/PRODUCER_ANIMATOR_TRUTH_EVIDENCE_NOTE.md` — V32-14/V32-09 producer/animator truth evidence note для `PB-001`, `RGH-001`, `RGH-002`, `RGH-003`, `RGH-018`, `OG-001`, `OG-002`.
- `docs/context/gui_spec_imports/v32_connector_reconciled/COMPARE_OBJECTIVE_INTEGRITY_EVIDENCE_NOTE.md` — V32-06/V32-08 compare/objective integrity evidence note для `PB-007`, `PB-008`, `RGH-013`, `RGH-014`, `RGH-015`.
- `docs/context/gui_spec_imports/v32_connector_reconciled/GEOMETRY_REFERENCE_EVIDENCE_NOTE.md` — V32-12 geometry reference/imported-layer boundary evidence note для `PB-001`, `PB-008`, `RGH-018`, `OG-001`, `OG-002`, `OG-006`.
- `docs/context/gui_spec_imports/v32_connector_reconciled/MNEMO_TRUTH_GRAPHICS_EVIDENCE_NOTE.md` — V32-10 Desktop Mnemo truth-graphics evidence note для dataset contract, source markers, scheme fidelity и unavailable states.
- `docs/context/gui_spec_imports/v32_connector_reconciled/ENGINEERING_ANALYSIS_EVIDENCE_NOTE.md` — V32-13 Engineering Analysis/Calibration/Influence evidence note для `WS-ANALYSIS`, `HO-007`, `HO-008`, `HO-009`.
- `docs/context/gui_spec_imports/v32_connector_reconciled/DIAGNOSTICS_RELEASE_EVIDENCE_NOTE.md` — V32-11 diagnostics/SEND-bundle evidence note для `PB-002`, `RGH-006`, `RGH-007`, `RGH-016`, `OG-005`.
- `docs/context/gui_spec_imports/v32_connector_reconciled/DIAGNOSTICS_PRODUCER_GAPS_HANDOFF.md` — producer-owned diagnostics warning handoff после SEND-bundle hardening; фиксирует missing producer artifacts без runtime closure claim.
- `docs/context/gui_spec_imports/v32_connector_reconciled/RUNTIME_RELEASE_EVIDENCE_NOTE.md` — V32-15 runtime evidence hard-gate note для `PB-006`, `RGH-011`, `RGH-012`, `RGH-019`, `OG-003`, `OG-004`.
- `docs/context/release_readiness/WORKTREE_TRIAGE_2026-04-17.md` — release-readiness triage текущего dirty tree по V32 lane, gate/gap, evidence и targeted tests; не является runtime closure proof.
- `docs/context/release_readiness/SELF_CHECK_WARNINGS_REVIEW_2026-04-17.md` — review note для `REPORTS/SELF_CHECK_SILENT_WARNINGS.*`: clean self-check snapshot (`fail_count=0`, `warn_count=0`) без diagnostics/SEND closure claim.
- `docs/context/release_readiness/V32_16_ACCEPTANCE_NOTE_2026-04-17.md` — V32-16 integration note: accepted docs/helper scope, validation status and no-runtime-closure rule.
- `docs/context/release_readiness/PROJECT_KB_CONFORMANCE_AUDIT_2026-04-17.md` — синхронизационный аудит проекта против активной KB, conformance matrix и план доработки без runtime-closure claim.
- `docs/context/release_readiness/DESKTOP_STARTUP_VISIBLE_PROOF_2026-04-17.md` — controlled real-Windows visible startup proof for Qt main shell and Desktop Mnemo; automated startup `PASS`, manual visual/Snap/DPI/second-monitor acceptance remains pending.
- `docs/context/release_readiness/BRANCH_CLEANUP_AND_NEXT_WORK_PLAN_2026-04-18.md` — branch cleanup record after consolidating temporary Codex branches into `codex/work`, plus the next safe parallel-work plan.
- `docs/gui_chat_prompts/14_PLAN_MODE_PARALLEL_START_PROMPTS.md` — copy-paste starter prompts for parallel chats whose first launch is in Plan mode, with owned/forbidden file boundaries and no-edit-before-plan rules.
- `docs/context/release_readiness/CODE_TREE_AUDIT_2026-04-18.md` — historical code-tree audit: dirty files by lane, prepared worktrees, ignored-artifact cleanup boundary and code hotspots before recovery quarantine.
- `docs/gui_chat_prompts/15_CODE_AUDIT_PLAN_MODE_START_PROMPTS.md` — historical self-contained starter prompts for the same 10 Plan-mode chats before branch/tree recovery.
- `docs/context/release_readiness/BRANCH_TREE_RECOVERY_AUDIT_2026-04-18.md` — recovery audit after quarantining the mixed GUI dirty tree and removing duplicate local worktrees/branches; current clean-start policy for new chats.
- `docs/context/release_readiness/QUARANTINE_7823DC2_RESOLUTION_2026-04-18.md` — integration note for resolving local quarantine commit `7823dc2` by cherry-pick into `codex/work`, with targeted validation results and non-closure boundaries.
- `docs/gui_chat_prompts/16_RECOVERY_PLAN_MODE_START_PROMPTS.md` — historical post-quarantine self-contained Plan-mode starter prompts for the same 10 chats after branch/tree recovery and `7823dc2` integration; superseded after acceptance of the 10 GUI handoffs.
- `docs/gui_chat_prompts/17_POST_ACCEPTANCE_V38_PLAN_MODE_PROMPTS.md` — current post-acceptance self-contained Plan-mode starter prompts for the same 10 chats after `ed9c4cd`; requires V38 visual/runtime checks, optimized user-pipeline checks and service-jargon leak checks.
- `docs/context/gui_spec_imports/v3/README.md` — active detailed reference layer из `pneumo_gui_codex_package_v3.zip`.
- `docs/context/gui_spec_imports/v3/pneumo_gui_codex_spec_v3_refined.json` — главный machine-readable GUI-spec.
- `docs/context/gui_spec_imports/v3/current_macro.dot` — текущий macro workflow graph.
- `docs/context/gui_spec_imports/v3/optimized_macro.dot` — целевой macro workflow graph.
- `docs/context/gui_spec_imports/v3/current_element_graph.dot` — текущий element graph.
- `docs/context/gui_spec_imports/v3/optimized_element_graph.dot` — целевой element graph.
- `docs/context/gui_spec_imports/v3/ui_element_catalog.csv` — catalog UI-элементов.
- `docs/context/gui_spec_imports/v3/field_catalog.csv` — catalog полей.
- `docs/context/gui_spec_imports/v3/help_catalog.csv` — catalog help topics.
- `docs/context/gui_spec_imports/v3/tooltip_catalog.csv` — catalog tooltip topics.
- `docs/context/gui_spec_imports/v3/migration_matrix.csv` — machine-readable migration contract `web -> desktop`.
- `docs/context/gui_spec_imports/v3/source_of_truth_matrix.csv` — matrix источников истины и производных представлений.
- `docs/context/gui_spec_imports/v3/ui_state_matrix.csv` — matrix состояний UI-элементов.
- `docs/context/gui_spec_imports/v3/keyboard_matrix.csv` — keyboard и access-key contract.
- `docs/context/gui_spec_imports/v3/docking_matrix.csv` — docking/floating/second-monitor contract.
- `docs/context/gui_spec_imports/v3/pipeline_observability.csv` — observability contract для GUI pipeline.
- `docs/context/gui_spec_imports/v3/best_practices_sources.csv` — curated external best-practices baseline.
- `docs/context/gui_spec_imports/v3/acceptance_criteria.csv` — acceptance layer.
- `docs/context/gui_spec_imports/v3/pipeline_verification.csv` — pipeline verification layer.
- `docs/context/gui_spec_imports/v3/test_suite.csv` — catalog GUI-spec tests.
- `docs/context/gui_spec_imports/v13_ring_editor_migration/README.md` — специализированный imported addendum для `WS-RING` и ring migration.
- `docs/context/gui_spec_imports/v13_ring_editor_migration/pneumo_gui_codex_spec_v13_ring_editor_migration.json` — главный machine-readable ring-editor migration spec.
- `docs/context/gui_spec_imports/v13_ring_editor_migration/ring_editor_schema_contract_v13.json` — каноническая схема данных кольцевого сценария.
- `docs/context/gui_spec_imports/v13_ring_editor_migration/ring_editor_screen_blueprints_v13.csv` — screen/mode blueprints рабочего пространства `WS-RING`.
- `docs/context/gui_spec_imports/v13_ring_editor_migration/ring_editor_element_catalog_v13.csv` — catalog элементов интерфейса ring editor.
- `docs/context/gui_spec_imports/v13_ring_editor_migration/ring_editor_field_catalog_v13.csv` — catalog полей ring editor.
- `docs/context/gui_spec_imports/v13_ring_editor_migration/ring_editor_state_machine_v13.json` — state machine сценарного контура.
- `docs/context/gui_spec_imports/v13_ring_editor_migration/ring_editor_user_pipeline_v13.dot` — ring-level user pipeline graph.
- `docs/context/gui_spec_imports/v13_ring_editor_migration/web_to_desktop_migration_matrix_v13.csv` — специализированная ring-level migration matrix `web -> desktop`.
- `docs/context/gui_spec_imports/v13_ring_editor_migration/ring_editor_acceptance_gates_v13.csv` — acceptance gates для `WS-RING`.
- `docs/context/gui_spec_imports/v13_ring_editor_migration/ring_to_suite_link_contract_v13.json` — handoff contract `WS-RING -> WS-SUITE`.
- `docs/context/gui_spec_imports/v12_design_recovery/README.md` — historical design-recovery layer из `v12`.
- `docs/context/gui_spec_imports/v12_design_recovery/pneumo_gui_codex_spec_v12_design_recovery.json` — design-recovery delta после implementation-веток.
- `docs/context/gui_spec_imports/v12_design_recovery/ring_editor_canonical_contract_v12.json` — precursor ring contract перед `v13`.
- `docs/context/gui_spec_imports/v12_design_recovery/optimization_control_plane_contract_v12.json` — precursor optimization control-plane contract.
- `docs/context/gui_spec_imports/v12_design_recovery/truthful_graphics_contract_v12.json` — precursor truthful-graphics contract.
- `docs/context/gui_spec_imports/v12_design_recovery/workspace_delta_v12.json` — workspace-level recovery delta.
- `docs/context/GUI_SPEC_ARCHIVE_LINEAGE.md` — human-readable lineage `v1…v13`.
- `docs/context/gui_spec_archive_lineage.json` — machine-readable lineage inventory `v1…v13`.

### Historical import

- `docs/context/gui_spec_imports/v2/README.md` — historical detailed import из `v2`.
- `docs/context/gui_spec_imports/v2/pneumo_gui_codex_spec_v2_detailed.json` — historical detailed machine-readable spec.
- `docs/context/gui_spec_imports/pneumo_gui_codex_spec_v1.json` — historical machine-readable import из `v1`.
- `docs/context/gui_spec_imports/current_pipeline.dot` — historical current workflow graph.
- `docs/context/gui_spec_imports/optimized_pipeline.dot` — historical optimized workflow graph.

### Parity and migration

- `docs/context/desktop_web_parity_map.json` — machine-readable parity map, синхронизированный с `migration_matrix.csv`.
- `docs/context/DESKTOP_WEB_PARITY_SUMMARY.md` — human-readable summary того же migration/parity contract.

### Lane-level implementation prompts

- `docs/gui_chat_prompts/00_INDEX.md` — entrypoint в lane-level prompt docs.
- `docs/gui_chat_prompts/13_RELEASE_GATES_KB_ACCEPTANCE.md` — prompt для V32-16 scope: KB, release gates, acceptance map и docs-contract tests.
- `docs/gui_chat_prompts/*` — implementation prompts, которые обязаны ссылаться на `17/18` и active detailed reference.

## Правило приоритета

1. `17_WINDOWS_DESKTOP_CAD_GUI_CANON.md`
2. `18_PNEUMOAPP_WINDOWS_GUI_SPEC.md`
3. `docs/context/gui_spec_imports/foundations/*` как upstream intent/provenance layer
4. `docs/context/gui_spec_imports/v38_actualized_with_v10/*` как current active successor KB/TZ/spec layer, плюс `docs/context/release_readiness/V38_ACTUALIZED_WITH_V10_KB_IMPORT_AUDIT_2026-04-19.md` для снятия неоднозначностей; не runtime-closure proof
5. `docs/context/gui_spec_imports/v19_graph_iteration/*` как graph/action-feedback refinement для `WS-INPUTS`, `WS-RING`, `WS-OPTIMIZATION` и `WS-DIAGNOSTICS`; не runtime-closure proof
6. `docs/context/gui_spec_imports/v12_window_internal_routes/*` как report-only first-screen/internal-route refinement для поверхности проверки и отправки архива, подробного сравнения результатов, исходных данных проекта и набора испытаний; не runtime-closure proof
7. `docs/context/gui_spec_imports/v15_state_continuity_repair_loops/*` как report-only continuity/repair-loop refinement для stale/dirty/mismatch/degraded states, visible markers, repair actions and restore targets; не runtime-closure proof
8. `docs/context/gui_spec_imports/v16_visibility_priority/*` как report-only visibility-priority/must-see-state refinement для always-visible, conditionally escalated, inspector/help-only boundaries and first-5-seconds comprehension; не runtime-closure proof
6. `docs/context/gui_spec_imports/v38_github_kb_commit_ready/*` как predecessor V38 KB/TZ/spec layer, плюс `docs/context/release_readiness/V38_KB_IMPORT_AUDIT_2026-04-18.md`
7. `docs/context/gui_spec_imports/v37_github_kb_supplement/*` как predecessor KB/TZ/spec supplement/provenance layer
8. `docs/context/gui_spec_imports/v33_connector_reconciled/README.md` как connector-reconciled GUI/TZ digest
9. `docs/context/gui_spec_imports/v32_connector_reconciled/README.md`, `PARALLEL_CHAT_WORKSTREAMS.md` и `RELEASE_GATE_ACCEPTANCE_MAP.md` как previous digest/workstream/release-evidence layer
10. `docs/context/gui_spec_imports/v3/*`
11. `docs/context/gui_spec_imports/v13_ring_editor_migration/*` для `WS-RING` и handoff `WS-RING -> WS-SUITE`
12. `docs/context/gui_spec_imports/v12_design_recovery/*` как historical design-recovery layer
13. `docs/context/gui_spec_archive_lineage.json` и `docs/context/GUI_SPEC_ARCHIVE_LINEAGE.md`
14. older versions в `docs/context/gui_spec_imports/*`
15. `docs/gui_chat_prompts/*`

## Зафиксированные внешние AI snapshots

- `docs/12_AI_Wishlist_Canonical_Omnibus_2026-04-08.md` — human-readable выжимка external snapshots от `2026-04-08`.
- `docs/12_AI_Wishlist_Canonical_Omnibus_2026-04-08.json` — машиночитаемый digest той же пары для AI/bootstrap сценариев.
- `docs/context/AI_SNAPSHOT_WORKING_DELTA_2026-04-08.md` — короткая рабочая delta-заметка.
- `workspace/external_context_snapshots/AI_WISHLIST_CANONICAL_OMNIBUS_LLM_SLIM_2026-04-08.json.gz` — локальная mirror-копия default external AI source. Workspace-слой gitignored.
- `workspace/external_context_snapshots/AI_WISHLIST_CANONICAL_OMNIBUS_DIRECT_CHAT_SUPPLEMENT_2026-04-08.json.gz` — локальная mirror-копия provenance/evidence snapshot. Workspace-слой gitignored.

## Внешние источники контекста

- `Downloads` — [Google Drive folder 1](https://drive.google.com/drive/folders/1INCx3J11p24XZIgY_th3-J2ZBCltQiwX?usp=sharing)
- `Downloads` — [Google Drive folder 2](https://drive.google.com/drive/folders/147bS-lCxGY4jsQ6jCnsq9Os6pk7U6zE7?usp=sharing)
- `пневмоподвеска` — [Google Drive folder 3](https://drive.google.com/drive/folders/1tEJwV4UtRNwsbX2Jgf-O-GihTktWHBfN?usp=sharing)

## Правило использования

- Внешние ссылки не заменяют локальный канон.
- Для GUI-first задач сначала читать `17`, затем `18`, затем `gui_spec_imports/foundations/*`, затем `gui_spec_imports/v38_actualized_with_v10/*` и `context/release_readiness/V38_ACTUALIZED_WITH_V10_KB_IMPORT_AUDIT_2026-04-19.md` для active KB/TZ/spec reconciliation, затем `gui_spec_imports/v19_graph_iteration/*` для action-feedback уточнений `WS-INPUTS`/`WS-RING`/`WS-OPTIMIZATION`/`WS-DIAGNOSTICS`, затем `gui_spec_imports/v12_window_internal_routes/*` для first-screen/internal-route уточнений четырех under-proven окон, затем `gui_spec_imports/v15_state_continuity_repair_loops/*` для continuity/repair-loop уточнений stale/dirty/mismatch/degraded states, restore targets и visible markers, затем `gui_spec_imports/v16_visibility_priority/*` для visibility priority, must-see states, first-5-seconds comprehension и inspector/help boundaries, затем `gui_spec_imports/v38_github_kb_commit_ready/*` и `context/release_readiness/V38_KB_IMPORT_AUDIT_2026-04-18.md` как predecessor V38 provenance, затем `gui_spec_imports/v37_github_kb_supplement/*`, затем `gui_spec_imports/v33_connector_reconciled/README.md` и `COMPLETENESS_ASSESSMENT.md`, затем `gui_spec_imports/v32_connector_reconciled/PARALLEL_CHAT_WORKSTREAMS.md`, `gui_spec_imports/v32_connector_reconciled/RELEASE_GATE_ACCEPTANCE_MAP.md`, затем `gui_spec_imports/v3/*`, parity docs и только потом lane-level prompts.
- Для release-readiness merge сначала сверять `docs/context/release_readiness/WORKTREE_TRIAGE_2026-04-17.md`, `docs/context/release_readiness/V32_16_ACCEPTANCE_NOTE_2026-04-17.md`, `docs/context/release_readiness/PROJECT_KB_CONFORMANCE_AUDIT_2026-04-17.md`, `docs/context/release_readiness/DESKTOP_STARTUP_VISIBLE_PROOF_2026-04-17.md` и `docs/context/release_readiness/BRANCH_CLEANUP_AND_NEXT_WORK_PLAN_2026-04-18.md`, затем принимать V32-16 docs/helper patch и только после этого разбирать lane-пакеты с их evidence.
- Для новых parallel-chat starts после приемки 10 GUI handoffs, `7823dc2` resolution и V38+V10 import сначала сверять `docs/context/release_readiness/BRANCH_TREE_RECOVERY_AUDIT_2026-04-18.md`, `docs/context/release_readiness/QUARANTINE_7823DC2_RESOLUTION_2026-04-18.md`, `docs/context/release_readiness/V38_ACTUALIZED_WITH_V10_KB_IMPORT_AUDIT_2026-04-19.md`, active V38+V10 `GUI_SPEC.yaml`, `WORKSPACE_CONTRACT_MATRIX.csv`, `ACCEPTANCE_MATRIX.csv`, `PIPELINE_OPTIMIZED.dot`, `LAUNCHER_HIERARCHY_RECONCILIATION_V10.md` и использовать текущие GUI prompt packs; historical chat branches and worktrees are not working sources.
- Imported JSON/DOT/CSV используются как reference artifacts, а не как единственный источник правды.
- При конфликте между imported sources и текущим каноном приоритет у `17/18`.

## Chat consolidated master V1 source set

The KB also registers `docs/context/gui_spec_imports/chat_consolidated_master_v1/`
as a consolidated master reference imported from `pneumo_chat_consolidated_master_v1.zip`.
It should be read after `17/18` and foundations when a task needs the deduplicated
chat-derived reading order, source provenance or superseded/excluded decisions.

Registered entrypoints:

- `docs/context/gui_spec_imports/chat_consolidated_master_v1/REPO_IMPORT_NOTE.md`
- `docs/context/gui_spec_imports/chat_consolidated_master_v1/README.md`
- `docs/context/gui_spec_imports/chat_consolidated_master_v1/06_INDEX/MASTER_EXEC_SUMMARY.json`
- `docs/context/gui_spec_imports/chat_consolidated_master_v1/06_INDEX/INCLUDED_ARTIFACTS.csv`
- `docs/context/gui_spec_imports/chat_consolidated_master_v1/06_INDEX/SUPERSEDED_AND_EXCLUDED.csv`
- `docs/context/gui_spec_imports/chat_consolidated_master_v1/06_INDEX/LINEAGE_AND_READING_ORDER.md`
- `docs/context/gui_spec_imports/chat_consolidated_master_v1/02_CODEX_SPEC_FINAL/v38_actualized_with_v10/TECHNICAL_SPECIFICATION.md`
- `docs/context/gui_spec_imports/chat_consolidated_master_v1/03_REPO_AUDIT/v34_repo_audit/AUDIT_REPORT.md`
- `docs/context/gui_spec_imports/chat_consolidated_master_v1/04_GRAPH_ANALYSIS/00_MASTER_SUMMARY.md`
- `docs/context/gui_spec_imports/chat_consolidated_master_v1/04_GRAPH_ANALYSIS/01_reconciliation_v21/GRAPH_ANALYSIS_REPORT_V21.md`
- `docs/context/gui_spec_imports/chat_consolidated_master_v1/04_GRAPH_ANALYSIS/02_workspace_graphs_v20/GRAPH_ANALYSIS_REPORT_V20.md`
- `docs/context/gui_spec_imports/chat_consolidated_master_v1/04_GRAPH_ANALYSIS/04_cost_entropy_v17/GRAPH_ANALYSIS_REPORT_V17.md`
- `docs/context/gui_spec_imports/chat_consolidated_master_v1/05_HUMAN_REPORTS/00_MASTER_SUMMARY.md`
- `docs/context/release_readiness/CHAT_CONSOLIDATED_MASTER_V1_KB_IMPORT_AUDIT_2026-04-21.md`

Boundary: `chat_consolidated_master_v1` is not runtime-closure proof. It is a
consolidated reference/provenance layer for V38+V10, V34 audit, graph V17/V19/V20/V21
and human reports V10-V16.
