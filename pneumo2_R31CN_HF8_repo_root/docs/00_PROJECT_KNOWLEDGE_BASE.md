# Единая база знаний проекта

## Назначение

Этот документ собирает в одном месте текущий рабочий канон проекта, активные требования, backlog, исполняемые контракты и архивные слои контекста.

Цель документа:

- дать один стартовый источник для AI и разработчиков;
- уменьшить повторное чтение десятков `TODO/WISHLIST/addendum` файлов;
- явно разделить:
  - что является законом и каноном;
  - что является активным планом работ;
  - что является исполняемым контрактом;
  - что является историей и архивом.

Этот файл не заменяет канонические документы. Он задаёт порядок приоритетов и краткую сводку по ним.

## Как использовать

Если нужно начать новую работу, сначала читать этот файл, а затем переходить по слоям приоритета сверху вниз.

Если два источника противоречат друг другу, приоритет определяется разделом `Порядок приоритета`.

## Правило пополнения базы знаний

Начиная с текущего рабочего цикла, база знаний должна пополняться не только из файлов репозитория, но и из рабочих чатов проекта.

Обязательное правило:

- все новые пользовательские хотелки, явно сформулированные в чатах этого проекта, должны фиксироваться в knowledge-base слое;
- все новые планы работ, decomposition, migration plans и prompt-packages, которые генерируют чаты этого проекта, тоже должны фиксироваться в knowledge-base слое;
- если желание или план пока не оформлены в код, они всё равно должны быть занесены как проектное требование, решение или рабочее направление;
- knowledge-base запись не заменяет канон, но становится частью рабочего контекста для следующих задач.

Для этого в базе знаний используются два специальных журнала:

- [docs/13_CHAT_REQUIREMENTS_LOG.md](./13_CHAT_REQUIREMENTS_LOG.md)
- [docs/14_CHAT_PLANS_LOG.md](./14_CHAT_PLANS_LOG.md)
- machine-readable store: [docs/15_CHAT_KNOWLEDGE_BASE.json](./15_CHAT_KNOWLEDGE_BASE.json)

Рабочий инструмент синхронизации:

- `python -m pneumo_solver_ui.tools.knowledge_base_sync ...`

Operational note:

- команды `add-requirement` и `add-plan` в `knowledge_base_sync` по умолчанию рассчитаны на autosave в git: stage, commit и push можно выполнять в том же вызове без отдельного ручного шага;
- если нужен только локальный апдейт без git, используется `--no-git-sync`.

Если в будущем появляются новые существенные решения из чатов, их нужно добавлять туда в том же рабочем цикле.

## Порядок приоритета

### 1. Абсолютный канон

1. [00_READ_FIRST__ABSOLUTE_LAW.md](../00_READ_FIRST__ABSOLUTE_LAW.md)
2. [01_PARAMETER_REGISTRY.md](../01_PARAMETER_REGISTRY.md)
3. [DATA_CONTRACT_UNIFIED_KEYS.md](../DATA_CONTRACT_UNIFIED_KEYS.md)

### 2. Канон запуска, desktop GUI и источников

4. [README.md](../README.md)
5. [docs/17_WINDOWS_DESKTOP_CAD_GUI_CANON.md](./17_WINDOWS_DESKTOP_CAD_GUI_CANON.md)
6. [docs/18_PNEUMOAPP_WINDOWS_GUI_SPEC.md](./18_PNEUMOAPP_WINDOWS_GUI_SPEC.md)
7. [docs/context/gui_spec_imports/v38_actualized_with_v10/README.md](./context/gui_spec_imports/v38_actualized_with_v10/README.md)
8. [docs/context/gui_spec_imports/v38_actualized_with_v10/TECHNICAL_SPECIFICATION.md](./context/gui_spec_imports/v38_actualized_with_v10/TECHNICAL_SPECIFICATION.md)
9. [docs/context/gui_spec_imports/v38_actualized_with_v10/GUI_SPEC.yaml](./context/gui_spec_imports/v38_actualized_with_v10/GUI_SPEC.yaml)
10. [docs/context/gui_spec_imports/v38_actualized_with_v10/LAUNCHER_HIERARCHY_RECONCILIATION_V10.md](./context/gui_spec_imports/v38_actualized_with_v10/LAUNCHER_HIERARCHY_RECONCILIATION_V10.md)
11. [docs/context/gui_spec_imports/v38_actualized_with_v10/V10_RECONCILIATION_MATRIX.csv](./context/gui_spec_imports/v38_actualized_with_v10/V10_RECONCILIATION_MATRIX.csv)
12. [docs/context/gui_spec_imports/v38_actualized_with_v10/REQUIREMENTS_MATRIX.csv](./context/gui_spec_imports/v38_actualized_with_v10/REQUIREMENTS_MATRIX.csv)
13. [docs/context/release_readiness/V38_ACTUALIZED_WITH_V10_KB_IMPORT_AUDIT_2026-04-19.md](./context/release_readiness/V38_ACTUALIZED_WITH_V10_KB_IMPORT_AUDIT_2026-04-19.md)
14. [docs/context/gui_spec_imports/v19_graph_iteration/README.md](./context/gui_spec_imports/v19_graph_iteration/README.md)
15. [docs/context/gui_spec_imports/v19_graph_iteration/EXEC_SUMMARY.json](./context/gui_spec_imports/v19_graph_iteration/EXEC_SUMMARY.json)
16. [docs/context/gui_spec_imports/v19_graph_iteration/GRAPH_ANALYSIS_REPORT_V19.md](./context/gui_spec_imports/v19_graph_iteration/GRAPH_ANALYSIS_REPORT_V19.md)
17. [docs/context/gui_spec_imports/v19_graph_iteration/SEMANTIC_FIX_PRIORITY_V19.md](./context/gui_spec_imports/v19_graph_iteration/SEMANTIC_FIX_PRIORITY_V19.md)
18. [docs/context/gui_spec_imports/v19_graph_iteration/USER_ACTION_FEEDBACK_MATRIX_V19.csv](./context/gui_spec_imports/v19_graph_iteration/USER_ACTION_FEEDBACK_MATRIX_V19.csv)
19. [docs/context/gui_spec_imports/v19_graph_iteration/TASK_CHECK_BLOCK_LOOP_MATRIX_V19.csv](./context/gui_spec_imports/v19_graph_iteration/TASK_CHECK_BLOCK_LOOP_MATRIX_V19.csv)
20. [docs/context/gui_spec_imports/v19_graph_iteration/COGNITIVE_VISIBILITY_MATRIX_V19.csv](./context/gui_spec_imports/v19_graph_iteration/COGNITIVE_VISIBILITY_MATRIX_V19.csv)
21. [docs/context/gui_spec_imports/v19_graph_iteration/TREE_DIRECT_OPEN_MATRIX_V19.csv](./context/gui_spec_imports/v19_graph_iteration/TREE_DIRECT_OPEN_MATRIX_V19.csv)
22. [docs/context/gui_spec_imports/v19_graph_iteration/DOCK_WINDOW_AND_DOCK_WIDGET_MATRIX_V19.csv](./context/gui_spec_imports/v19_graph_iteration/DOCK_WINDOW_AND_DOCK_WIDGET_MATRIX_V19.csv)
23. [docs/context/gui_spec_imports/v12_window_internal_routes/README.md](./context/gui_spec_imports/v12_window_internal_routes/README.md)
24. [docs/context/gui_spec_imports/v12_window_internal_routes/WINDOW_FIRST_SCREEN_CONTRACT_V12.md](./context/gui_spec_imports/v12_window_internal_routes/WINDOW_FIRST_SCREEN_CONTRACT_V12.md)
25. [docs/context/gui_spec_imports/v12_window_internal_routes/WINDOW_ACTION_FEEDBACK_MATRIX_V12.csv](./context/gui_spec_imports/v12_window_internal_routes/WINDOW_ACTION_FEEDBACK_MATRIX_V12.csv)
26. [docs/context/gui_spec_imports/v12_window_internal_routes/SEMANTIC_REWRITE_MATRIX_V12.csv](./context/gui_spec_imports/v12_window_internal_routes/SEMANTIC_REWRITE_MATRIX_V12.csv)
27. [docs/context/gui_spec_imports/v12_window_internal_routes/DIRECT_TREE_OPEN_AND_DOCK_ROLE_V12.csv](./context/gui_spec_imports/v12_window_internal_routes/DIRECT_TREE_OPEN_AND_DOCK_ROLE_V12.csv)
28. [docs/context/release_readiness/HUMAN_GUI_REPORT_ONLY_V12_WINDOW_INTERNAL_ROUTES_2026-04-20.md](./context/release_readiness/HUMAN_GUI_REPORT_ONLY_V12_WINDOW_INTERNAL_ROUTES_2026-04-20.md)
29. [docs/context/gui_spec_imports/v15_state_continuity_repair_loops/README.md](./context/gui_spec_imports/v15_state_continuity_repair_loops/README.md)
30. [docs/context/gui_spec_imports/v15_state_continuity_repair_loops/STATE_CONTINUITY_AND_REPAIR_LOOP_CONTRACT_V15.md](./context/gui_spec_imports/v15_state_continuity_repair_loops/STATE_CONTINUITY_AND_REPAIR_LOOP_CONTRACT_V15.md)
31. [docs/context/gui_spec_imports/v15_state_continuity_repair_loops/WINDOW_STATE_MARKER_MATRIX_V15.csv](./context/gui_spec_imports/v15_state_continuity_repair_loops/WINDOW_STATE_MARKER_MATRIX_V15.csv)
32. [docs/context/gui_spec_imports/v15_state_continuity_repair_loops/REPAIR_LOOP_POLICY_V15.csv](./context/gui_spec_imports/v15_state_continuity_repair_loops/REPAIR_LOOP_POLICY_V15.csv)
33. [docs/context/gui_spec_imports/v15_state_continuity_repair_loops/CONTEXT_RESTORE_AND_RETURN_TARGETS_V15.csv](./context/gui_spec_imports/v15_state_continuity_repair_loops/CONTEXT_RESTORE_AND_RETURN_TARGETS_V15.csv)
34. [docs/context/release_readiness/HUMAN_GUI_REPORT_ONLY_V15_STATE_CONTINUITY_REPAIR_LOOPS_2026-04-21.md](./context/release_readiness/HUMAN_GUI_REPORT_ONLY_V15_STATE_CONTINUITY_REPAIR_LOOPS_2026-04-21.md)
35. [docs/context/gui_spec_imports/v16_visibility_priority/README.md](./context/gui_spec_imports/v16_visibility_priority/README.md)
36. [docs/context/gui_spec_imports/v16_visibility_priority/VISIBILITY_PRIORITY_POLICY_V16.md](./context/gui_spec_imports/v16_visibility_priority/VISIBILITY_PRIORITY_POLICY_V16.md)
37. [docs/context/gui_spec_imports/v16_visibility_priority/MUST_SEE_STATE_MATRIX_V16.csv](./context/gui_spec_imports/v16_visibility_priority/MUST_SEE_STATE_MATRIX_V16.csv)
38. [docs/context/gui_spec_imports/v16_visibility_priority/ALWAYS_VISIBLE_CONDITIONAL_INSPECTOR_MATRIX_V16.csv](./context/gui_spec_imports/v16_visibility_priority/ALWAYS_VISIBLE_CONDITIONAL_INSPECTOR_MATRIX_V16.csv)
39. [docs/context/gui_spec_imports/v16_visibility_priority/DOCK_REGION_VISIBILITY_POLICY_V16.csv](./context/gui_spec_imports/v16_visibility_priority/DOCK_REGION_VISIBILITY_POLICY_V16.csv)
40. [docs/context/gui_spec_imports/v16_visibility_priority/WORKSPACE_FIRST_5_SECONDS_V16.csv](./context/gui_spec_imports/v16_visibility_priority/WORKSPACE_FIRST_5_SECONDS_V16.csv)
41. [docs/context/release_readiness/HUMAN_GUI_REPORT_ONLY_V16_VISIBILITY_PRIORITY_2026-04-21.md](./context/release_readiness/HUMAN_GUI_REPORT_ONLY_V16_VISIBILITY_PRIORITY_2026-04-21.md)
14. [docs/context/gui_spec_imports/v38_github_kb_commit_ready/README.md](./context/gui_spec_imports/v38_github_kb_commit_ready/README.md)
15. [docs/context/gui_spec_imports/v38_github_kb_commit_ready/TECHNICAL_SPECIFICATION.md](./context/gui_spec_imports/v38_github_kb_commit_ready/TECHNICAL_SPECIFICATION.md)
16. [docs/context/gui_spec_imports/v38_github_kb_commit_ready/GUI_SPEC.yaml](./context/gui_spec_imports/v38_github_kb_commit_ready/GUI_SPEC.yaml)
17. [docs/context/release_readiness/V38_KB_IMPORT_AUDIT_2026-04-18.md](./context/release_readiness/V38_KB_IMPORT_AUDIT_2026-04-18.md)
18. [docs/context/release_readiness/GUI_TEXT_SEMANTIC_AUDIT_2026-04-19.md](./context/release_readiness/GUI_TEXT_SEMANTIC_AUDIT_2026-04-19.md)
19. [docs/context/release_readiness/HUMAN_GUI_SIMULATION_AUDIT_V5_2026-04-19.md](./context/release_readiness/HUMAN_GUI_SIMULATION_AUDIT_V5_2026-04-19.md)
20. [docs/context/release_readiness/HUMAN_GUI_REPORT_ONLY_V6_2026-04-19.md](./context/release_readiness/HUMAN_GUI_REPORT_ONLY_V6_2026-04-19.md)
21. [docs/context/release_readiness/HUMAN_GUI_REPORT_ONLY_V10_LAUNCHER_HIERARCHY_2026-04-19.md](./context/release_readiness/HUMAN_GUI_REPORT_ONLY_V10_LAUNCHER_HIERARCHY_2026-04-19.md)
22. [docs/context/gui_spec_imports/v37_github_kb_supplement/README.md](./context/gui_spec_imports/v37_github_kb_supplement/README.md)
23. [docs/context/gui_spec_imports/v33_connector_reconciled/README.md](./context/gui_spec_imports/v33_connector_reconciled/README.md)
24. [docs/context/gui_spec_imports/v33_connector_reconciled/COMPLETENESS_ASSESSMENT.md](./context/gui_spec_imports/v33_connector_reconciled/COMPLETENESS_ASSESSMENT.md)
25. [docs/context/gui_spec_imports/v32_connector_reconciled/README.md](./context/gui_spec_imports/v32_connector_reconciled/README.md)
26. [docs/context/gui_spec_imports/v32_connector_reconciled/PARALLEL_CHAT_WORKSTREAMS.md](./context/gui_spec_imports/v32_connector_reconciled/PARALLEL_CHAT_WORKSTREAMS.md)
27. [docs/context/gui_spec_imports/v32_connector_reconciled/RELEASE_GATE_ACCEPTANCE_MAP.md](./context/gui_spec_imports/v32_connector_reconciled/RELEASE_GATE_ACCEPTANCE_MAP.md)
28. [docs/context/gui_spec_imports/v32_connector_reconciled/WS_INPUTS_HANDOFF_EVIDENCE_NOTE.md](./context/gui_spec_imports/v32_connector_reconciled/WS_INPUTS_HANDOFF_EVIDENCE_NOTE.md)
29. [docs/context/gui_spec_imports/v32_connector_reconciled/PRODUCER_ANIMATOR_TRUTH_EVIDENCE_NOTE.md](./context/gui_spec_imports/v32_connector_reconciled/PRODUCER_ANIMATOR_TRUTH_EVIDENCE_NOTE.md)
30. [docs/context/gui_spec_imports/v32_connector_reconciled/COMPARE_OBJECTIVE_INTEGRITY_EVIDENCE_NOTE.md](./context/gui_spec_imports/v32_connector_reconciled/COMPARE_OBJECTIVE_INTEGRITY_EVIDENCE_NOTE.md)
31. [docs/context/gui_spec_imports/v32_connector_reconciled/GEOMETRY_REFERENCE_EVIDENCE_NOTE.md](./context/gui_spec_imports/v32_connector_reconciled/GEOMETRY_REFERENCE_EVIDENCE_NOTE.md)
32. [docs/context/gui_spec_imports/v32_connector_reconciled/MNEMO_TRUTH_GRAPHICS_EVIDENCE_NOTE.md](./context/gui_spec_imports/v32_connector_reconciled/MNEMO_TRUTH_GRAPHICS_EVIDENCE_NOTE.md)
33. [docs/context/gui_spec_imports/v32_connector_reconciled/DIAGNOSTICS_RELEASE_EVIDENCE_NOTE.md](./context/gui_spec_imports/v32_connector_reconciled/DIAGNOSTICS_RELEASE_EVIDENCE_NOTE.md)
34. [docs/context/gui_spec_imports/v32_connector_reconciled/DIAGNOSTICS_PRODUCER_GAPS_HANDOFF.md](./context/gui_spec_imports/v32_connector_reconciled/DIAGNOSTICS_PRODUCER_GAPS_HANDOFF.md)
35. [docs/context/gui_spec_imports/v32_connector_reconciled/ENGINEERING_ANALYSIS_EVIDENCE_NOTE.md](./context/gui_spec_imports/v32_connector_reconciled/ENGINEERING_ANALYSIS_EVIDENCE_NOTE.md)
36. [docs/context/gui_spec_imports/v32_connector_reconciled/RUNTIME_RELEASE_EVIDENCE_NOTE.md](./context/gui_spec_imports/v32_connector_reconciled/RUNTIME_RELEASE_EVIDENCE_NOTE.md)
37. [docs/context/release_readiness/WORKTREE_TRIAGE_2026-04-17.md](./context/release_readiness/WORKTREE_TRIAGE_2026-04-17.md)
38. [docs/context/release_readiness/SELF_CHECK_WARNINGS_REVIEW_2026-04-17.md](./context/release_readiness/SELF_CHECK_WARNINGS_REVIEW_2026-04-17.md)
39. [docs/context/release_readiness/V32_16_ACCEPTANCE_NOTE_2026-04-17.md](./context/release_readiness/V32_16_ACCEPTANCE_NOTE_2026-04-17.md)
40. [docs/context/release_readiness/PROJECT_KB_CONFORMANCE_AUDIT_2026-04-17.md](./context/release_readiness/PROJECT_KB_CONFORMANCE_AUDIT_2026-04-17.md)
41. [docs/context/release_readiness/DESKTOP_STARTUP_VISIBLE_PROOF_2026-04-17.md](./context/release_readiness/DESKTOP_STARTUP_VISIBLE_PROOF_2026-04-17.md)
42. [docs/context/release_readiness/BRANCH_CLEANUP_AND_NEXT_WORK_PLAN_2026-04-18.md](./context/release_readiness/BRANCH_CLEANUP_AND_NEXT_WORK_PLAN_2026-04-18.md)
43. [docs/gui_chat_prompts/14_PLAN_MODE_PARALLEL_START_PROMPTS.md](./gui_chat_prompts/14_PLAN_MODE_PARALLEL_START_PROMPTS.md)
44. [docs/context/release_readiness/CODE_TREE_AUDIT_2026-04-18.md](./context/release_readiness/CODE_TREE_AUDIT_2026-04-18.md)
45. [docs/gui_chat_prompts/15_CODE_AUDIT_PLAN_MODE_START_PROMPTS.md](./gui_chat_prompts/15_CODE_AUDIT_PLAN_MODE_START_PROMPTS.md)
46. [docs/context/release_readiness/BRANCH_TREE_RECOVERY_AUDIT_2026-04-18.md](./context/release_readiness/BRANCH_TREE_RECOVERY_AUDIT_2026-04-18.md)
47. [docs/context/release_readiness/QUARANTINE_7823DC2_RESOLUTION_2026-04-18.md](./context/release_readiness/QUARANTINE_7823DC2_RESOLUTION_2026-04-18.md)
48. [docs/gui_chat_prompts/16_RECOVERY_PLAN_MODE_START_PROMPTS.md](./gui_chat_prompts/16_RECOVERY_PLAN_MODE_START_PROMPTS.md)
49. [docs/gui_chat_prompts/17_POST_ACCEPTANCE_V38_PLAN_MODE_PROMPTS.md](./gui_chat_prompts/17_POST_ACCEPTANCE_V38_PLAN_MODE_PROMPTS.md)
50. [docs/context/release_readiness/CHAT_WORKTREE_ACCEPTANCE_CLEANUP_2026-04-18.md](./context/release_readiness/CHAT_WORKTREE_ACCEPTANCE_CLEANUP_2026-04-18.md)
51. [docs/gui_chat_prompts/18_POST_CHAT_WORKTREE_CLEANUP_V38_PLAN_MODE_PROMPTS.md](./gui_chat_prompts/18_POST_CHAT_WORKTREE_CLEANUP_V38_PLAN_MODE_PROMPTS.md)
52. [docs/PROJECT_SOURCES.md](./PROJECT_SOURCES.md)
53. [AI_INTEGRATION_PLAYBOOK.yaml](../AI_INTEGRATION_PLAYBOOK.yaml)

### 3. Активные требования и рабочий backlog

13. [docs/01_RequirementsFromContext.md](./01_RequirementsFromContext.md)
14. [docs/10_NextStepsPlan.md](./10_NextStepsPlan.md)
15. [docs/11_TODO.md](./11_TODO.md)
16. [docs/12_Wishlist.md](./12_Wishlist.md)
17. [docs/12_AI_Wishlist_Canonical_Omnibus_2026-04-08.md](./12_AI_Wishlist_Canonical_Omnibus_2026-04-08.md)

### 4. Исполняемые контракты и registries

18. `pneumo_solver_ui/contracts/*`
19. `pneumo_solver_ui/*contract*.py`
20. `tests/test_*contract*`

### 5. История и архив

21. `TODO_MASTER_*`, `WISHLIST_MASTER_*`
22. `TODO_WISHLIST_R31*_ADDENDUM_*.md`
23. `docs/consolidated/*`
24. `docs/context/WISHLIST*`
25. `docs/_legacy_DOCS_upper/*`

## Непереговорные правила проекта

Источник: [00_READ_FIRST__ABSOLUTE_LAW.md](../00_READ_FIRST__ABSOLUTE_LAW.md)

1. Нельзя выдумывать параметры.
2. Нельзя вводить алиасы и псевдо-совместимость вместо исправления контракта.
3. Производные и сервисные сигналы должны быть явно помечены, а не маскироваться под модельные.
4. Геометрия, координаты и физические сигналы должны идти из модели и экспорта, а не придумыватьcя UI или Animator.
5. Любой drift между слоями должен исправляться в контракте и быть видимым в диагностике.

Практический вывод:

- нельзя чинить несовместимость временными мостами;
- нельзя подменять authored data в viewer-слое;
- нельзя добавлять новые ключи без обновления канона и registry.

## Канонические ключи и data contract

Источник: [01_PARAMETER_REGISTRY.md](../01_PARAMETER_REGISTRY.md), [DATA_CONTRACT_UNIFIED_KEYS.md](../DATA_CONTRACT_UNIFIED_KEYS.md)

Главные источники канонических данных:

- `pneumo_solver_ui/default_base.json`
- `pneumo_solver_ui/default_ranges.json`
- `pneumo_solver_ui/default_suite.json`
- `pneumo_solver_ui/contracts/param_registry.yaml`
- `pneumo_solver_ui/contracts/generated/keys_registry.yaml`

Критично помнить:

- suite/test transport использует канонические ключи вроде `dt`, `t_end`, `auto_t_end_from_len`, `road_len_m`, `vx0_м_с`, `road_csv`, `axay_csv`;
- sidecar/meta transport для анимации и diagnostics должен использовать те же ключи без alias-слоя;
- `anim_latest`, `scenario_json`, `road_csv`, `axay_csv`, `meta_json`, `validation` и diagnostics surfaces не должны расходиться по названиям и смыслу полей.

Запрещённые практики:

- legacy-ключи вместо канонических;
- параллельные словари для одного и того же сигнала;
- silent remap без явного contract update.

## Канон источников проекта

Источник: [docs/PROJECT_SOURCES.md](./PROJECT_SOURCES.md), [README.md](../README.md), [AI_INTEGRATION_PLAYBOOK.yaml](../AI_INTEGRATION_PLAYBOOK.yaml)

Проект признаёт несколько слоёв источников:

- локальный канон в репозитории;
- локальные digests и snapshots AI-контекста;
- current imported V38 actualized with V10 GUI/TZ/spec knowledge-base layer,
  with previous V38/V10 layers retained as provenance and evidence;
- human GUI simulation/report-only audits V5/V6/V10/V12/V15/V16 as evidence-first,
  route-hierarchy and first-screen/action-feedback clarification layers for
  launcher hierarchy, first-class `Редактор кольца`, archive check/send route,
  compare differentiation, truth-state markers, direct tree open and
  under-proven window internals, state continuity, repair loops, visibility
  priority and first-5-seconds comprehension;
- connector-reconciled GUI/TZ digest v33, with v32 retained as previous
  workstream/release-gate evidence layer;
- внешние архивы и Google Drive как контекст и история;
- исполняемые contracts и tests как проверяемое поведение.

Правило приоритета:

- внешние источники и AI snapshots не заменяют локальный канон;
- при конфликте между архивом и текущим каноном исправляется код и экспорт, а не добавляются alias-мосты.

## Активная инженерная повестка

Источник: [docs/10_NextStepsPlan.md](./10_NextStepsPlan.md), [docs/11_TODO.md](./11_TODO.md), [docs/12_Wishlist.md](./12_Wishlist.md)

### Текущие активные направления

- корректность ring и road profile генерации;
- truth-preserving export для animator, compare, validation и diagnostics;
- производительность UI и playback;
- достоверная геометрия подвески, колёс, цилиндров и packaging;
- улучшение дорожной поверхности, contact patch и visual truthfulness;
- optimisation workflow, distributed optimisation и experiment DB;
- единый diagnostics/send-bundle flow;
- улучшение инженерной observability: self-check, energy, thermo, validation.

### Крупные долгосрочные темы

- world coordinates и корректное движение автомобиля по дороге;
- two-cylinder-per-corner и расширенная геометрия креплений;
- длинные прогоны, температура и нагрузка;
- автоанализ численной нестабильности;
- relevance против каталогов и паспортов;
- fully differentiable model;
- совместная финальная анимация механики и пневматики.

### Часто повторяющиеся wishlist-мотивы

- catalogue-aware packaging;
- adaptive road mesh;
- truthful 3D wheel geometry;
- screen-aware layouts;
- browser/GUI performance observability;
- explicit ring closure policy;
- стабильность GL и viewer-контуров;
- устранение drift между authored geometry и displayed geometry.

## GUI-first рабочее направление

Источник: активное решение по развитию проекта, согласованное в текущем рабочем цикле, при опоре на существующие требования и backlog.

Текущее рабочее направление:

- проект переносит операторские сценарии из WEB в классический desktop GUI под Windows;
- WEB временно используется как источник текущего поведения и legacy reference, но не как желаемая целевая платформа;
- перенос должен быть без потери функциональности;
- специализированные окна `Desktop Animator`, `Compare Viewer`, `Desktop Mnemo` остаются отдельными доменами и не должны без необходимости дублироваться;
- GUI-архитектура должна оставаться модульной, чтобы разные окна и подсистемы можно было двигать параллельно разными чатами.

## Канон Windows desktop GUI

Главный desktop GUI source для GUI-first направления:

- [docs/17_WINDOWS_DESKTOP_CAD_GUI_CANON.md](./17_WINDOWS_DESKTOP_CAD_GUI_CANON.md)
- [docs/18_PNEUMOAPP_WINDOWS_GUI_SPEC.md](./18_PNEUMOAPP_WINDOWS_GUI_SPEC.md)
- [docs/context/gui_spec_imports/v38_actualized_with_v10/README.md](./context/gui_spec_imports/v38_actualized_with_v10/README.md)
- [docs/context/gui_spec_imports/v38_actualized_with_v10/TECHNICAL_SPECIFICATION.md](./context/gui_spec_imports/v38_actualized_with_v10/TECHNICAL_SPECIFICATION.md)
- [docs/context/gui_spec_imports/v38_actualized_with_v10/GUI_SPEC.yaml](./context/gui_spec_imports/v38_actualized_with_v10/GUI_SPEC.yaml)
- [docs/context/gui_spec_imports/v38_actualized_with_v10/WORKSPACE_CONTRACT_MATRIX.csv](./context/gui_spec_imports/v38_actualized_with_v10/WORKSPACE_CONTRACT_MATRIX.csv)
- [docs/context/gui_spec_imports/v38_actualized_with_v10/PARAMETER_CATALOG.csv](./context/gui_spec_imports/v38_actualized_with_v10/PARAMETER_CATALOG.csv)
- [docs/context/gui_spec_imports/v38_actualized_with_v10/PARAMETER_VISIBILITY_MATRIX.csv](./context/gui_spec_imports/v38_actualized_with_v10/PARAMETER_VISIBILITY_MATRIX.csv)
- [docs/context/gui_spec_imports/v38_actualized_with_v10/ACCEPTANCE_MATRIX.csv](./context/gui_spec_imports/v38_actualized_with_v10/ACCEPTANCE_MATRIX.csv)
- [docs/context/gui_spec_imports/v38_actualized_with_v10/PIPELINE_OPTIMIZED.dot](./context/gui_spec_imports/v38_actualized_with_v10/PIPELINE_OPTIMIZED.dot)
- [docs/context/gui_spec_imports/v38_actualized_with_v10/LAUNCHER_HIERARCHY_RECONCILIATION_V10.md](./context/gui_spec_imports/v38_actualized_with_v10/LAUNCHER_HIERARCHY_RECONCILIATION_V10.md)
- [docs/context/gui_spec_imports/v38_actualized_with_v10/V10_RECONCILIATION_MATRIX.csv](./context/gui_spec_imports/v38_actualized_with_v10/V10_RECONCILIATION_MATRIX.csv)
- [docs/context/release_readiness/V38_ACTUALIZED_WITH_V10_KB_IMPORT_AUDIT_2026-04-19.md](./context/release_readiness/V38_ACTUALIZED_WITH_V10_KB_IMPORT_AUDIT_2026-04-19.md)
- [docs/context/gui_spec_imports/v38_github_kb_commit_ready/README.md](./context/gui_spec_imports/v38_github_kb_commit_ready/README.md)
- [docs/context/gui_spec_imports/v38_github_kb_commit_ready/TECHNICAL_SPECIFICATION.md](./context/gui_spec_imports/v38_github_kb_commit_ready/TECHNICAL_SPECIFICATION.md)
- [docs/context/gui_spec_imports/v38_github_kb_commit_ready/GUI_SPEC.yaml](./context/gui_spec_imports/v38_github_kb_commit_ready/GUI_SPEC.yaml)
- [docs/context/gui_spec_imports/v38_github_kb_commit_ready/WORKSPACE_CONTRACT_MATRIX.csv](./context/gui_spec_imports/v38_github_kb_commit_ready/WORKSPACE_CONTRACT_MATRIX.csv)
- [docs/context/gui_spec_imports/v38_github_kb_commit_ready/PARAMETER_CATALOG.csv](./context/gui_spec_imports/v38_github_kb_commit_ready/PARAMETER_CATALOG.csv)
- [docs/context/gui_spec_imports/v38_github_kb_commit_ready/PARAMETER_VISIBILITY_MATRIX.csv](./context/gui_spec_imports/v38_github_kb_commit_ready/PARAMETER_VISIBILITY_MATRIX.csv)
- [docs/context/gui_spec_imports/v38_github_kb_commit_ready/ACCEPTANCE_MATRIX.csv](./context/gui_spec_imports/v38_github_kb_commit_ready/ACCEPTANCE_MATRIX.csv)
- [docs/context/gui_spec_imports/v38_github_kb_commit_ready/PIPELINE_OPTIMIZED.dot](./context/gui_spec_imports/v38_github_kb_commit_ready/PIPELINE_OPTIMIZED.dot)
- [docs/context/release_readiness/V38_KB_IMPORT_AUDIT_2026-04-18.md](./context/release_readiness/V38_KB_IMPORT_AUDIT_2026-04-18.md)
- [docs/context/gui_spec_imports/v37_github_kb_supplement/README.md](./context/gui_spec_imports/v37_github_kb_supplement/README.md)
- [docs/context/gui_spec_imports/v33_connector_reconciled/README.md](./context/gui_spec_imports/v33_connector_reconciled/README.md)
- [docs/context/gui_spec_imports/v33_connector_reconciled/COMPLETENESS_ASSESSMENT.md](./context/gui_spec_imports/v33_connector_reconciled/COMPLETENESS_ASSESSMENT.md)
- [docs/context/gui_spec_imports/v32_connector_reconciled/README.md](./context/gui_spec_imports/v32_connector_reconciled/README.md)
- [docs/context/gui_spec_imports/v32_connector_reconciled/COMPLETENESS_ASSESSMENT.md](./context/gui_spec_imports/v32_connector_reconciled/COMPLETENESS_ASSESSMENT.md)
- [docs/context/gui_spec_imports/v32_connector_reconciled/PARALLEL_CHAT_WORKSTREAMS.md](./context/gui_spec_imports/v32_connector_reconciled/PARALLEL_CHAT_WORKSTREAMS.md)
- [docs/context/gui_spec_imports/v32_connector_reconciled/RELEASE_GATE_ACCEPTANCE_MAP.md](./context/gui_spec_imports/v32_connector_reconciled/RELEASE_GATE_ACCEPTANCE_MAP.md)
- [docs/context/gui_spec_imports/v32_connector_reconciled/RELEASE_GATE_HARDENING_MATRIX.csv](./context/gui_spec_imports/v32_connector_reconciled/RELEASE_GATE_HARDENING_MATRIX.csv)
- [docs/context/gui_spec_imports/v32_connector_reconciled/GAP_TO_EVIDENCE_ACTION_MAP.csv](./context/gui_spec_imports/v32_connector_reconciled/GAP_TO_EVIDENCE_ACTION_MAP.csv)
- [docs/context/gui_spec_imports/v32_connector_reconciled/WS_INPUTS_HANDOFF_EVIDENCE_NOTE.md](./context/gui_spec_imports/v32_connector_reconciled/WS_INPUTS_HANDOFF_EVIDENCE_NOTE.md)
- [docs/context/gui_spec_imports/v32_connector_reconciled/PRODUCER_ANIMATOR_TRUTH_EVIDENCE_NOTE.md](./context/gui_spec_imports/v32_connector_reconciled/PRODUCER_ANIMATOR_TRUTH_EVIDENCE_NOTE.md)
- [docs/context/gui_spec_imports/v32_connector_reconciled/COMPARE_OBJECTIVE_INTEGRITY_EVIDENCE_NOTE.md](./context/gui_spec_imports/v32_connector_reconciled/COMPARE_OBJECTIVE_INTEGRITY_EVIDENCE_NOTE.md)
- [docs/context/gui_spec_imports/v32_connector_reconciled/GEOMETRY_REFERENCE_EVIDENCE_NOTE.md](./context/gui_spec_imports/v32_connector_reconciled/GEOMETRY_REFERENCE_EVIDENCE_NOTE.md)
- [docs/context/gui_spec_imports/v32_connector_reconciled/MNEMO_TRUTH_GRAPHICS_EVIDENCE_NOTE.md](./context/gui_spec_imports/v32_connector_reconciled/MNEMO_TRUTH_GRAPHICS_EVIDENCE_NOTE.md)
- [docs/context/gui_spec_imports/v32_connector_reconciled/ENGINEERING_ANALYSIS_EVIDENCE_NOTE.md](./context/gui_spec_imports/v32_connector_reconciled/ENGINEERING_ANALYSIS_EVIDENCE_NOTE.md)
- [docs/context/gui_spec_imports/v32_connector_reconciled/DIAGNOSTICS_RELEASE_EVIDENCE_NOTE.md](./context/gui_spec_imports/v32_connector_reconciled/DIAGNOSTICS_RELEASE_EVIDENCE_NOTE.md)
- [docs/context/gui_spec_imports/v32_connector_reconciled/DIAGNOSTICS_PRODUCER_GAPS_HANDOFF.md](./context/gui_spec_imports/v32_connector_reconciled/DIAGNOSTICS_PRODUCER_GAPS_HANDOFF.md)
- [docs/context/gui_spec_imports/v32_connector_reconciled/RUNTIME_RELEASE_EVIDENCE_NOTE.md](./context/gui_spec_imports/v32_connector_reconciled/RUNTIME_RELEASE_EVIDENCE_NOTE.md)
- [docs/context/release_readiness/WORKTREE_TRIAGE_2026-04-17.md](./context/release_readiness/WORKTREE_TRIAGE_2026-04-17.md)
- [docs/context/release_readiness/SELF_CHECK_WARNINGS_REVIEW_2026-04-17.md](./context/release_readiness/SELF_CHECK_WARNINGS_REVIEW_2026-04-17.md)
- [docs/context/release_readiness/V32_16_ACCEPTANCE_NOTE_2026-04-17.md](./context/release_readiness/V32_16_ACCEPTANCE_NOTE_2026-04-17.md)
- [docs/context/release_readiness/PROJECT_KB_CONFORMANCE_AUDIT_2026-04-17.md](./context/release_readiness/PROJECT_KB_CONFORMANCE_AUDIT_2026-04-17.md)
- [docs/context/release_readiness/DESKTOP_STARTUP_VISIBLE_PROOF_2026-04-17.md](./context/release_readiness/DESKTOP_STARTUP_VISIBLE_PROOF_2026-04-17.md)
- [docs/context/release_readiness/BRANCH_CLEANUP_AND_NEXT_WORK_PLAN_2026-04-18.md](./context/release_readiness/BRANCH_CLEANUP_AND_NEXT_WORK_PLAN_2026-04-18.md)
- [docs/gui_chat_prompts/14_PLAN_MODE_PARALLEL_START_PROMPTS.md](./gui_chat_prompts/14_PLAN_MODE_PARALLEL_START_PROMPTS.md)
- [docs/context/release_readiness/CODE_TREE_AUDIT_2026-04-18.md](./context/release_readiness/CODE_TREE_AUDIT_2026-04-18.md)
- [docs/gui_chat_prompts/15_CODE_AUDIT_PLAN_MODE_START_PROMPTS.md](./gui_chat_prompts/15_CODE_AUDIT_PLAN_MODE_START_PROMPTS.md)
- [docs/context/release_readiness/BRANCH_TREE_RECOVERY_AUDIT_2026-04-18.md](./context/release_readiness/BRANCH_TREE_RECOVERY_AUDIT_2026-04-18.md)
- [docs/context/release_readiness/QUARANTINE_7823DC2_RESOLUTION_2026-04-18.md](./context/release_readiness/QUARANTINE_7823DC2_RESOLUTION_2026-04-18.md)
- [docs/gui_chat_prompts/16_RECOVERY_PLAN_MODE_START_PROMPTS.md](./gui_chat_prompts/16_RECOVERY_PLAN_MODE_START_PROMPTS.md)
- [docs/gui_chat_prompts/17_POST_ACCEPTANCE_V38_PLAN_MODE_PROMPTS.md](./gui_chat_prompts/17_POST_ACCEPTANCE_V38_PLAN_MODE_PROMPTS.md)
- [docs/context/release_readiness/CHAT_WORKTREE_ACCEPTANCE_CLEANUP_2026-04-18.md](./context/release_readiness/CHAT_WORKTREE_ACCEPTANCE_CLEANUP_2026-04-18.md)
- [docs/gui_chat_prompts/18_POST_CHAT_WORKTREE_CLEANUP_V38_PLAN_MODE_PROMPTS.md](./gui_chat_prompts/18_POST_CHAT_WORKTREE_CLEANUP_V38_PLAN_MODE_PROMPTS.md)

Что задаёт общий canon:

- project-wide baseline для shell, editor-окон, viewport/workspace-поверхностей и analysis/workflow-модулей;
- командную поверхность по умолчанию: `menu bar + toolbar + dockable/floating/auto-hide panes + command search + status/progress strip`;
- правило `ribbon optional, not default`;
- обязательную keyboard-first, accessibility, High-DPI и performance discipline;
- нативное Windows windowing behavior: title bar, system menu, drag/maximize/snap semantics и сохранение dock/floating layouts;
- различение `status`, `in-window progress` и taskbar progress reflection;
- `Per-Monitor V2` и `WM_DPICHANGED` suggested-rectangle policy для Win32 path.

Что задаёт project-specific target spec:

- целевую top-level архитектуру `главный shell + specialized windows` для `Animator`, `Compare Viewer` и `Desktop Mnemo`;
- active desktop route трактует `specialized windows` как дочерние `dock/floating`-поверхности внутри одного `WIN-MAIN-SHELL` по образцу `Desktop Animator`: дерево/command-search открывает или фокусирует dock-панель напрямую, а standalone legacy-процессы разрешены только как явный `support_fallback`;
- workflow-first contract: `Исходные данные -> Тест-набор / Сценарии -> Baseline -> Optimization -> Analysis / Animator / Diagnostics`;
- матрицу `web -> desktop` как обязательный артефакт сохранения функциональности при миграции;
- один selector optimization-mode, видимые `objective stack`, `hard gate` и baseline policy `автообновлять / не автообновлять`;
- `Ring Editor` как единственный source-of-truth сценариев и derived-only статус для preview/export/artifacts;
- first-class diagnostics contract: `Собрать диагностику`, bundle contents, latest ZIP, health/self-check, autosave on exit/crash;
- честную truth-state model для `Animator`: `truth complete`, `truth partial`, `truth absent`, без fake geometry и с explainable degraded mode;
- обязательные tooltip и question-mark help, которые дополняют layout, но не заменяют его;
- обязательные графические input surfaces, source markers и время построения для расчётных previews и графиков;
- refined Windows title-bar/system-menu/Snap Layout behavior, `UI Automation`, `WM_DPICHANGED`, idle CPU, hidden-pane budget и ETW-style instrumentation policy для desktop GUI.

Публичный launcher contract:

- единственный пользовательский вход верхнего уровня - `START_PNEUMO_APP.*`;
- внутри него должны быть две явные кнопки запуска: `Запустить WEB` для Streamlit и `Запустить GUI` для desktop GUI;
- `Запустить GUI` запускает `pneumo_solver_ui.tools.desktop_main_shell_qt` / Desktop Main Shell, потому что это primary route с реальными рабочими окнами: input editor, ring/scenario editor, test center, baseline run, optimizer, results, animator, diagnostics;
- `desktop_gui_spec_shell` не является primary route и не должен подменять Desktop Main Shell; это support/dev поверхность для проверки contracts;
- кнопка с общим названием `Запустить` запрещена, потому что скрывает, какой интерфейс стартует;
- прямые `START_DESKTOP_*` wrappers остаются support/dev entrypoints для диагностики, восстановления и прямой проверки конкретного окна; они не должны выглядеть как основной пользовательский launcher в portable-поверхности;
- `pneumo_solver_ui/START_PNEUMO_UI.pyw` - historical WEB wrapper и не должен подменять `START_PNEUMO_APP.*` как публичный launcher.

GUI canonical window memory от 2026-04-23:

- источник: `pneumo_chat_consolidated_master_v1 (2).zip`, V38 actualized with V10, graph iterations V15...V21 and human reports V11...V16;
- durable note: `docs/context/release_readiness/GUI_CANONICAL_WINDOW_MEMORY_2026-04-23.md`;
- главное правило: левое дерево открывает нужный dock/widget/window напрямую, без launcher-grid, "центра окон" и второго выбора;
- Desktop Main Shell / `desktop_main_shell_qt` является public `Запустить GUI` target; `desktop_gui_spec_shell` остаётся только support/dev surface;
- `Редактор кольца` является единственным editable source-of-truth сценариев; набор испытаний только потребляет сценарный snapshot;
- `Диагностика` имеет один first-class route, где `Собрать диагностику` primary, а отправка результатов secondary после готового bundle.

Что добавляет V38 actualized with V10 KB layer:

- текущий активный imported layer для GUI/TZ/spec и базы знаний после
  `v38_github_kb_commit_ready`;
- 115-файловый self-contained package
  `pneumo_codex_tz_spec_connector_reconciled_v38_actualized_with_v10`;
- V10 findings встроены в V38 как требования `REQ-046` ... `REQ-050`,
  acceptance/test rows и reconciliation matrix;
- стартовый shell обязан показывать один доминирующий 8-шаговый маршрут:
  `Исходные данные -> Редактор кольца / сценариев -> Набор испытаний ->
  Базовый прогон -> Оптимизация -> Анализ результатов -> Анимация ->
  Диагностика`;
- `Редактор кольца` усиливается как доминирующий сценарный центр и
  единственный editable source-of-truth сценариев;
- отправка результатов не является отдельным стартовым путём, а живёт внутри
  диагностики после готового пакета диагностики;
- встроенное сравнение в анализе является основным compare-route, отдельное
  окно сравнения остаётся расширенным режимом из анализа;
- `Desktop Mnemo` и инструменты остаются доступными, но являются
  secondary/advanced surfaces и не конкурируют с основным маршрутом первых
  минут;
- локальный audit
  `V38_ACTUALIZED_WITH_V10_KB_IMPORT_AUDIT_2026-04-19.md` фиксирует read
  coverage, приоритет и открытые ограничения;
- explicit non-runtime boundary: producer-side truth, cylinder packaging,
  browser performance trace/viewport gating and Windows visual/runtime
  acceptance остаются открытыми до named evidence.

Что добавляет V19 graph/action-feedback iteration:

- active detailed refinement layer после V38 actualized with V10 для четырёх
  route-critical workspaces: `WS-INPUTS`, `WS-RING`, `WS-OPTIMIZATION`,
  `WS-DIAGNOSTICS`;
- фокус не на количестве кнопок, а на связке `действие пользователя -> проверка
  системы -> блокировка/loop -> видимый feedback -> следующий шаг`;
- `WS-INPUTS`: графический двойник, видимость C1/C2 как первой/второй пружины,
  режим/метод/остаток выравнивания, зеркальная симметрия и validated snapshot
  должны быть видимы до ощущения, что числовое редактирование завершено;
- `WS-RING`: семантика сегмента, тип поворота, единый crossfall-параметр,
  seam gate, auto-close последнего сегмента и stale export state становятся
  обязательными first-class состояниями;
- `WS-OPTIMIZATION`: один активный режим, summary контракта целевых показателей,
  live rows стадий, причины underfill/условия допуска/продвижения кандидата и
  provenance истории не прячутся в служебные вкладки;
- `WS-DIAGNOSTICS`: один доминирующий маршрут сбора, самопроверка/runtime
  provenance на первом экране, preview состава перед сбором и отправка только
  после готового архива диагностики;
- V19 не является runtime-closure proof: current internals для этих workspace-ов
  остаются evidence-bound до отдельного runtime/visual artifact.

Что добавляет V16 visibility-priority report-only layer:

- V16 уточняет, какие состояния обязаны быть видимы сразу, какие должны
  эскалироваться при конфликте и какие можно оставлять только в inspector/help.
- Must-see states не должны жить только в правом инспекторе, подсказке или логе,
  если они меняют доверие к данным, интерпретацию результата, repair-route или
  следующий шаг пользователя.
- Первый экран каждого workspace должен за 3-5 секунд объяснять, где находится
  пользователь, с каким контекстом он работает, какое главное состояние важно,
  есть ли конфликт/недоверие и что делать дальше.
- Top/message/bottom/inline surfaces отвечают за active project, route,
  conflict, blocker, progress and repair visibility; right inspector остаётся
  слоем provenance/help/details, а не местом для скрытия критичных состояний.
- V16 не является runtime-closure proof: он фиксирует целевую visibility policy,
  но не доказывает live visual/runtime acceptance текущего GUI.

Что остаётся от V38 commit-ready KB layer:

- предыдущий `v38_github_kb_commit_ready` сохраняется как predecessor
  provenance для сравнения требований, acceptance, pipeline и package
  adoption;
- 33-файловый import-ready subtree, `V38_KB_IMPORT_AUDIT_2026-04-18.md` и
  `GUI_TEXT_SEMANTIC_AUDIT_2026-04-19.md` больше не являются самым свежим
  GUI/TZ/spec слоем, но остаются полезными evidence и audit-документами.

Что добавляет Human GUI report-only V6:

- report-only слой без кода и без готовых исправлений; он уточняет маршрут
  пользователя, но не заменяет V38 actualized with V10/V5;
- главный риск: не нехватка кнопок, а слабая иерархия после запуска;
- один видимый стартовый маршрут пользователя вместо россыпи равных входов;
- `Редактор кольца` как верхнеуровневый первоклассный вход для сценариев;
- одно доминирующее действие диагностики: `Собрать диагностику`;
- убрать дублирование compare-маршрута с первого уровня интерфейса;
- крупные состояния достоверности для графики, анимации, схемы и результатов;
- стартовые кнопки должны объяснять, что откроется, когда это нужно и что
  пользователь сможет сделать внутри;
- расширенные инженерные и вычислительные настройки оптимизации должны быть
  скрыты до явного запроса пользователя;
- окна, отмеченные в V6 как `launchpoint_only`, нельзя считать визуально
  принятыми без отдельной проверки внутренних экранов.

Что остаётся за V37 predecessor layer:

- V37 сохраняется как predecessor provenance/reference layer для сравнения
  требований, параметров, acceptance и open gaps;
- V37 не является runtime-closure proof и не должен использоваться выше V38
  для новых GUI/TZ/spec решений.

Что добавляет connector-reconciled v32 layer:

- source authority, reading order и conflict policy для архива `pneumo_codex_tz_spec_connector_reconciled_v32.zip`;
- 12 workspace contracts: `WS-SHELL`, `WS-PROJECT`, `WS-INPUTS`, `WS-RING`, `WS-SUITE`, `WS-BASELINE`, `WS-OPTIMIZATION`, `WS-ANALYSIS`, `WS-ANIMATOR`, `WS-DIAGNOSTICS`, `WS-SETTINGS`, `WS-TOOLS`;
- machine-readable scope: 45 requirements, 45 acceptance rows, 61 screen rows, 704 UI element rows и 488 parameter rows;
- acceptance playbooks для producer truth, diagnostics bundle, parity/migration, scenario canon, Windows runtime, performance trace и objective contract;
- release-gate hardening, runtime artifact schema, evidence-required-by-gate и open-gap-to-evidence map;
- checked-in release-gate extracts: `RELEASE_GATE_HARDENING_MATRIX.csv`,
  `GAP_TO_EVIDENCE_ACTION_MAP.csv` и
  `RELEASE_GATE_ACCEPTANCE_MAP.md` для локальных docs/tests/helpers;
- explicit open gaps: producer-side hardpoints/solver_points truth, cylinder packaging passport, measured perf trace, viewport gating, ring seam, geometry runtime proof, `default_base.json` cleanup, `road_width_m` canonicalization и Windows visual acceptance.
- completeness assessment: v32 достаточен как contract/planning/reference layer,
  но не является runtime closure proof; self-checksum `PACKAGE_MANIFEST.json`
  и V30 label в `CODEx_CONSUMPTION_ORDER.md` зафиксированы как caveats.
- parallel chat workstreams: дальнейшая работа разбита на 16 independent lanes
  с русскими названиями, owned scope, handoff boundaries и стартовыми промтами.

Что добавляет connector-reconciled v33 layer:

- active replacement/уточнение v32 для package integrity и repo-canon conformance;
- `PACKAGE_MANIFEST.json` больше не хэширует сам себя, integrity policy вынесен
  в `PACKAGE_INTEGRITY_POLICY.md` и `PACKAGE_SELFCHECK_REPORT.json`;
- dedicated `PLAYBOOK_CURRENT_HISTORICAL_STALE_CONTEXT.md` закрывает v32 caveat
  по `PB-008`;
- `REPO_CANON_READ_ORDER.csv` и `REPO_CANON_GATE_MAPPING.csv` фиксируют связь
  `PROJECT_SOURCES -> 17 -> 18 -> parity/TODO` с package release gates;
- v33 completeness assessment сохраняет runtime limits: producer truth,
  cylinder packaging, measured performance, Windows visual acceptance и
  imported-layer runtime proof не считаются закрытыми без живых artifacts.

Что добавляет release-readiness triage:

- текущий mixed dirty tree разложен по V32 lanes, gate/open-gap links,
  required evidence и targeted tests;
- V32-16-owned files отделены от runtime/domain draft work;
- triage не является runtime closure proof и не разрешает staging без
  owner-approved lane-пакета.
- V32-16 acceptance note фиксирует docs/helper scope, focused validation и
  дальнейший порядок интеграции lane-пакетов.
- V32-02/V32-04 inputs/suite handoff evidence note фиксирует frozen
  `inputs_snapshot.json`, read-only `WS-RING`/`WS-SUITE` consumption,
  `validated_suite_snapshot.json`, `HO-005` baseline gate и stale/current
  banners; это handoff acceptance, а не solver/runtime closure.
- V32-14/V32-09 producer/animator truth evidence note фиксирует
  solver-points, hardpoints, geometry acceptance, packaging passport и animator
  truth-gate contracts; `OG-001` и `OG-002` остаются open до named release
  bundle и complete cylinder packaging passport.
- V32-06/V32-08 compare/objective integrity evidence note фиксирует objective
  contract persistence, compare contracts, mismatch banners и
  current/historical/stale provenance для `RGH-013`, `RGH-014`, `RGH-015`;
  это contract acceptance, а не runtime gap closure.
- V32-12 geometry reference evidence note фиксирует geometry reference
  snapshots, artifact freshness, road-width/packaging provenance и diagnostics
  handoff sidecars; `OG-006` остаётся imported-layer/runtime-proof open question
  до named release artifact и SEND-bundle proof.
- V32-10 Desktop Mnemo truth graphics evidence note фиксирует dataset contract,
  source markers, scheme fidelity, provenance и unavailable-state policy;
  это acceptance специализированного mnemo window, а не runtime gap closure.
- V32-13 Engineering Analysis evidence note фиксирует `HO-007`
  selected-run contract, compare influence surfaces, unit catalog, report
  provenance, `HO-008` animator link и `HO-009` diagnostics evidence manifest;
  это contract/provenance acceptance, а не diagnostics/SEND runtime closure.
- V32-11 diagnostics evidence note фиксирует SEND-bundle evidence manifest,
  latest pointer/SHA proof, health-after-triage и trigger provenance contract;
  это lane acceptance, а не финальная release closure без durable bundle path.
- Diagnostics producer gaps handoff фиксирует оставшиеся producer-owned warnings
  после SEND-bundle hardening и оставляет их warning-only до появления реальных
  artifacts у owner lanes.
- Self-check warnings review фиксирует, что generated
  `REPORTS/SELF_CHECK_SILENT_WARNINGS.*` snapshot чистый
  (`fail_count=0`, `warn_count=0`), но это не supersedes и не закрывает
  V32-11 diagnostics/SEND warning state.
- V32-15 runtime evidence note фиксирует hard-gate validator для browser perf,
  viewport gating и animator frame-budget artifacts; текущий workspace probe
  hard-fails missing measured artifacts, поэтому `OG-003` и `OG-004` остаются
  open до named SEND bundle/runtime evidence.
- Desktop startup visible proof фиксирует controlled real-Windows startup
  для Qt main shell и Desktop Mnemo (`PASS` automated visible startup), но
  оставляет manual visual, Snap Layouts, second-monitor, mixed-DPI и
  long-running stability acceptance pending.
- Branch cleanup and next-work plan фиксирует, что временные Codex branches
  собраны в `codex/work`, лишние ветки удалены, а следующая параллельная
  работа должна стартовать только от `codex/work` с disjoint file ownership.
- Plan-mode parallel start prompts фиксируют готовые самодостаточные промты
  для новых чатов: первый запуск только в Plan mode, без правок до
  подтверждения, с owned/forbidden files и focused test expectations.
- Code tree audit исторически фиксирует dirty-файлы по lane, prepared
  worktrees, code hotspots и unsafe ignored-artifact cleanup boundary до
  recovery-pass.
- Code-audit Plan-mode prompts обновляют стартовые промты для тех же 10
  параллельных чатов с учётом dirty tree; после recovery-pass считать этот
  файл historical comparison layer.
- Branch/tree recovery audit фиксирует, что primary `codex/work` снова чистый,
  локальные duplicate worktrees/branches удалены, а последующая судьба
  смешанного GUI-кода зафиксирована в quarantine resolution note.
- Quarantine 7823dc2 resolution фиксирует, что локальный quarantine patch
  разобран, перенесён в `codex/work` cherry-pick-ом и проверен focused
  desktop/docs/no-mojibake тестами без runtime-closure claims.
- Recovery Plan-mode prompts остаются historical starter pack до приемки
  результатов 10 параллельных GUI-чатов.
- Post-acceptance V38 Plan-mode prompts остаются historical starter pack
  после первой приемки GUI handoffs.
- Chat-worktree acceptance cleanup фиксирует перенос полезных локальных
  chat-worktree изменений в `codex/work`, исключение generated runtime
  artifacts и уборку временных worktree/веток после validation.
- Post-chat-worktree cleanup V38 Plan-mode prompts являются текущим starter
  pack для тех же 10 параллельных чатов: старт только от clean
  `origin/codex/work`, старые worktree/ветки не являются рабочим источником,
  принятые handoffs не переизобретать, обязательно проводить V38
  visual/runtime acceptance и проверять соответствие `PIPELINE_OPTIMIZED.dot`
  без лишних user-flow шагов; tree/search/selection sync из главного окна
  является навигацией, а служебные статусы и implementation labels не
  являются пользовательской информацией.
- GUI text semantic audit фиксирует нормализованную vocabulary и текущие
  расхождения desktop GUI: `workspace`, `contract`, `legacy`, `runtime`,
  `handoff`, `provenance`, `bundle` и английские служебные подписи не должны
  быть operator-facing текстом; `Animator`, `Desktop Mnemo` и `Compare Viewer`
  являются развиваемыми специализированными окнами, а не запретными зонами.

Связанные, но вспомогательные UX-источники:

- [docs/UX_BEST_PRACTICES_SOURCES.md](./UX_BEST_PRACTICES_SOURCES.md)
- [docs/UX_SOURCES_RU.md](./UX_SOURCES_RU.md)

Их роль:

- они помогают обосновывать отдельные UX-решения;
- они не переопределяют desktop GUI canon и не конкурируют с ним как с главным baseline;
- при конфликте между старым WEB/Streamlit UX-решением и desktop GUI canon приоритет у desktop GUI canon.

## Исполняемые требования

Главная идея: часть требований живёт не в prose-документах, а в коде и тестах.

### Основные contract/registry файлы

- `pneumo_solver_ui/contracts/param_registry.yaml`
- `pneumo_solver_ui/contracts/generated/keys_registry.yaml`
- `pneumo_solver_ui/contracts/registry.py`
- `pneumo_solver_ui/data_contract.py`
- `pneumo_solver_ui/param_contract.py`
- `pneumo_solver_ui/geometry_acceptance_contract.py`
- `pneumo_solver_ui/anim_export_contract.py`
- `pneumo_solver_ui/optimization_input_contract.py`
- `pneumo_solver_ui/optimization_objective_contract.py`
- `pneumo_solver_ui/solver_points_contract.py`
- `pneumo_solver_ui/workspace_contract.py`
- `pneumo_solver_ui/tools/send_bundle_contract.py`

### Вспомогательные инструменты сборки и валидации канона

- `pneumo_solver_ui/tools/build_key_registry.py`
- `pneumo_solver_ui/tools/param_contract_check.py`
- `pneumo_solver_ui/tools/validate_anim_export_contract.py`
- `pneumo_solver_ui/tools/aggregate_todo_wishlist.py`
- `pneumo_solver_ui/tools/extract_requirements_from_context.py`

### Тесты как часть базы знаний

Особенно важны:

- `tests/test_*contract*`
- `tests/test_*requirements*`
- acceptance/regression tests вокруг:
  - animator/export/meta;
  - compare/validation;
  - diagnostics/send bundle;
  - optimization contract surfaces;
  - geometry and packaging.

Если prose-документ и живой contract-тест расходятся, это сигнал к разбору, а не повод silently подгонять реализацию.

## Что считать активным backlog

Активным backlog считать:

- [docs/10_NextStepsPlan.md](./10_NextStepsPlan.md)
- [docs/11_TODO.md](./11_TODO.md)
- [docs/12_Wishlist.md](./12_Wishlist.md)
- [docs/12_AI_Wishlist_Canonical_Omnibus_2026-04-08.md](./12_AI_Wishlist_Canonical_Omnibus_2026-04-08.md)
- [docs/13_CHAT_REQUIREMENTS_LOG.md](./13_CHAT_REQUIREMENTS_LOG.md)
- [docs/14_CHAT_PLANS_LOG.md](./14_CHAT_PLANS_LOG.md)

Их роль:

- `NextStepsPlan` — направление и крупные блоки;
- `TODO` — текущие рабочие и инженерные задачи;
- `Wishlist` — желаемые улучшения;
- `AI Wishlist Omnibus` — AI-friendly digest внешнего контекста, который не имеет права переопределять канон.

## Что считать архивом

Архивом, а не каноном, считать:

- `TODO_MASTER_*`
- `WISHLIST_MASTER_*`
- `TODO_WISHLIST_R31*_ADDENDUM_*`
- `docs/consolidated/*`
- `docs/context/WISHLIST*`
- `docs/_legacy_DOCS_upper/*`
- старые release notes и historical addendum-файлы, если они не переопределены активным TODO/Wishlist

Использовать их можно:

- для поиска утраченных решений;
- для понимания эволюции требований;
- для сверки происхождения feature request;
- для восстановления контекста старых релизов.

Но нельзя использовать их как единственный источник для новых ключей, новых alias-правил или новых контрактов.

## Рекомендуемый порядок чтения перед новой задачей

### Минимальный старт

1. [00_READ_FIRST__ABSOLUTE_LAW.md](../00_READ_FIRST__ABSOLUTE_LAW.md)
2. [01_PARAMETER_REGISTRY.md](../01_PARAMETER_REGISTRY.md)
3. [DATA_CONTRACT_UNIFIED_KEYS.md](../DATA_CONTRACT_UNIFIED_KEYS.md)
4. этот файл

### Если задача затрагивает требования и roadmap

5. [docs/PROJECT_SOURCES.md](./PROJECT_SOURCES.md)
6. [docs/01_RequirementsFromContext.md](./01_RequirementsFromContext.md)
7. [docs/10_NextStepsPlan.md](./10_NextStepsPlan.md)
8. [docs/11_TODO.md](./11_TODO.md)
9. [docs/12_Wishlist.md](./12_Wishlist.md)
10. [docs/13_CHAT_REQUIREMENTS_LOG.md](./13_CHAT_REQUIREMENTS_LOG.md)
11. [docs/14_CHAT_PLANS_LOG.md](./14_CHAT_PLANS_LOG.md)

### Если задача AI/bootstrap или большой merge

12. [docs/12_AI_Wishlist_Canonical_Omnibus_2026-04-08.md](./12_AI_Wishlist_Canonical_Omnibus_2026-04-08.md)
13. [AI_INTEGRATION_PLAYBOOK.yaml](../AI_INTEGRATION_PLAYBOOK.yaml)

### Если задача затрагивает runtime/exports/contracts

14. relevant `*contract*.py`, registries и contract tests

## Короткий operational summary

Для практической работы можно опираться на следующий сжатый набор правил:

1. Канон важнее истории.
2. Контракт важнее convenience alias.
3. Экспорт и viewer должны честно показывать authored/model data.
4. Drift между слоями надо исправлять в contract boundary, а не замазывать UI.
5. Новый функционал должен подкрепляться tests и, при необходимости, registry update.
6. GUI является основным направлением развития операторских сценариев.
7. WEB используется как reference до полного переноса функциональности.

## Статус документа

Этот файл является синтезирующей картой знаний и навигацией по источникам.

Он должен обновляться, когда:

- меняется канон источников;
- появляется новый рабочий backlog-слой;
- меняется приоритет GUI/WEB направления;
- добавляется новый существенный contract layer.

## Chat consolidated master V1

`docs/context/gui_spec_imports/chat_consolidated_master_v1/` is the repo-local
import of `pneumo_chat_consolidated_master_v1.zip`. It gives the project one
deduplicated reading order for the latest chat-derived GUI/TZ/KB materials.

Read first:

- `docs/context/gui_spec_imports/chat_consolidated_master_v1/REPO_IMPORT_NOTE.md`
- `docs/context/gui_spec_imports/chat_consolidated_master_v1/README.md`
- `docs/context/gui_spec_imports/chat_consolidated_master_v1/06_INDEX/MASTER_EXEC_SUMMARY.json`
- `docs/context/gui_spec_imports/chat_consolidated_master_v1/06_INDEX/LINEAGE_AND_READING_ORDER.md`
- `docs/context/gui_spec_imports/chat_consolidated_master_v1/06_INDEX/INCLUDED_ARTIFACTS.csv`
- `docs/context/gui_spec_imports/chat_consolidated_master_v1/06_INDEX/SUPERSEDED_AND_EXCLUDED.csv`
- `docs/context/release_readiness/CHAT_CONSOLIDATED_MASTER_V1_KB_IMPORT_AUDIT_2026-04-21.md`
- `docs/context/release_readiness/CHAT_CONSOLIDATED_MASTER_V1_GUI_ROUTE_AUDIT_2026-04-21.md`

What it adds:

- source context plus final `v38_actualized_with_v10`;
- `v34_repo_audit` and KB alignment evidence;
- graph layers `v17 + v19 + v20 + v21`, including `GRAPH_ANALYSIS_REPORT_V21.md`,
  `GRAPH_ANALYSIS_REPORT_V20.md` and `GRAPH_ANALYSIS_REPORT_V17.md`;
- human reports `v10..v16`;
- explicit superseded/excluded register to avoid treating older noisy packages as active sources.

Boundary: this layer is not runtime-closure proof. It is used for lineage,
provenance and gap-finding; live GUI acceptance still needs separate runtime,
visual and release evidence.

Implementation follow-up: `CHAT_CONSOLIDATED_MASTER_V1_GUI_ROUTE_AUDIT_2026-04-21.md`
is the current bridge from the consolidated master archive to desktop GUI work.
It records the V21 route-level finding, the current `desktop_spec_shell` evidence,
and the decision that overview quick actions must open workspaces instead of
legacy or external launchpoints.
