# GUI-Spec Archive Lineage PROMPT_V2 + v1–v13 + v37 + v38

Этот документ фиксирует, как upstream prompt source `PROMPT_V2` и серия
архивов `v1…v13`, а также successor supplements `v37` и `v38`, влияют на текущий
GUI-spec проекта и какие из них считаются active, historical, recovery или
knowledge-base слоями.

## Как читать lineage

- `PROMPT_V2` — pre-`v1` upstream prompt source, который задаёт исходный
  native Windows, no-web-first и no-feature-loss intent.
- `v1–v5` — design-first эволюция машиночитаемого GUI-spec.
- `v6–v11` — implementation-oriented passes: от экранного implementation
  planning до bootstrap, fill-in, interaction pass, backend adapters и
  execution wiring.
- `v12` — design-recovery слой, который сохраняет историю и возвращает проект
  в правильную каноническую ветку.
- `v13` — специализированный design addendum для `WS-RING` и handoff
  `WS-RING -> WS-SUITE`.
- `v12_window_internal_routes` — отдельный более поздний report-only слой с
  совпадающим номером V12. Он не входит в линейку `v1…v13` как replacement для
  `v12_design_recovery`; его роль - уточнить first-screen/internal-route
  contracts четырех текущих окон.
- `v15_state_continuity_repair_loops` — отдельный report-only слой после V12/V19.
  Он не входит в линейку `v1…v13` как replacement; его роль - уточнить state
  continuity, stale/dirty/mismatch/degraded markers, repair loops and context
  restore/return targets.
- `v16_visibility_priority` — отдельный report-only слой после V15. Он не
  входит в линейку `v1…v13` как replacement; его роль - уточнить visibility
  hierarchy, must-see states, first 3-5 seconds workspace comprehension and
  inspector/help-only boundaries.
- `v37` — predecessor import-ready GitHub KB/TZ/spec supplement. Он поднимает
  consolidated technical specification, workspace/parameter/acceptance
  matrices и open gaps в repo-local knowledge-base layer, но не является
  runtime-closure proof.
- `v38` — commit-ready successor GitHub KB/TZ/spec layer after `v37`. Он
  добавляет repo-import-ready subtree `v38_github_kb_commit_ready`, maintainer
  adoption context and local ambiguity audit, но не является runtime-closure
  proof.

## Версии

### PROMPT_V2

- Роль: upstream foundational prompt source до серии архивов `v1…v13`.
- Ключевой артефакт:
  `prompt_gui_windows_cad_pneumo_augmented_v2_2026-04-13.md`.
- Что фиксирует:
  native Windows desktop как целевую архитектуру,
  запрет web-first и feature-loss migration,
  diagnostics как first-class surface,
  ring editor как single source of truth,
  honest graphics и обязательные help/tooltip/unit rules.
- Статус: foundational provenance layer в
  `docs/context/gui_spec_imports/foundations/`.

### v1

- Роль: стартовый machine-readable GUI-spec.
- Ключевые артефакты: `pneumo_gui_codex_spec_v1.json`,
  `current_pipeline.dot`, `optimized_pipeline.dot`.
- Статус: historical import, уже хранится в `docs/context/gui_spec_imports/`.

### v2

- Роль: первый подробный detailed reference layer.
- Что добавил: macro/element graphs, catalogs полей/help/tooltip,
  migration matrix, acceptance и pipeline verification.
- Статус: historical detailed import в
  `docs/context/gui_spec_imports/v2/`.

### v3

- Роль: текущий active detailed machine-readable reference layer.
- Что добавил: source-of-truth matrix, keyboard/docking/ui-state matrices,
  pipeline observability и refined shell contract.
- Статус: active layer в `docs/context/gui_spec_imports/v3/`.

### v4

- Роль: ultra-design expansion.
- Что добавил: user step graphs, dialog catalog, screen blueprints, expanded
  shell/title bar/splitter/scrollbar contracts, richer state machine и visual
  verification.
- Статус: historical archive, используется как lineage knowledge, но не как
  active import-layer.

### v5

- Роль: master design layer после `v4`.
- Что добавил: archive evidence index, command search synonyms, microcopy,
  cognitive ergonomics, validation rules, graphics truth matrix, units labels,
  screen element positions и другие detailed matrices.
- Статус: historical archive; важен как родитель для `v12` и `v13`.

### v6

- Роль: implementation pass.
- Что добавил: workspace implementation packets, component library,
  viewmodel/event/command contracts и codex work orders.
- Статус: historical implementation archive; не должен подменять design canon.

### v7

- Роль: bootstrap source skeleton.
- Что добавил: стартовый PySide6/Qt6 shell scaffold, workspace registry,
  automation/help anchors и degraded-truth registry.
- Статус: historical implementation archive.

### v8

- Роль: fill-in поверх bootstrap.
- Что добавил: seeded workspaces, service hub, command registry, local test
  matrix и section-based views.
- Статус: historical implementation archive.

### v9

- Роль: interaction pass.
- Что добавил по смыслу линейки: screen-by-screen interactions и richer
  component usage.
- Примечание: присланный архив содержит шумные `pytest cache` файлы и не
  годится как чистый imported source layer.
- Статус: historical implementation archive, учитывается через lineage.

### v10

- Роль: backend adapter pass.
- Что добавил: реальные файлово-контрактные backend adapters для baseline,
  optimization, diagnostics, ring source-of-truth и producer-side truth.
- Статус: historical implementation archive.

### v11

- Роль: execution wiring pass.
- Что добавил по смыслу линейки: execution wiring поверх interactive shell.
- Примечание: присланные копии архива также содержат шумный `pytest cache`
  вместо чистого README, поэтому используются только как lineage evidence.
- Статус: historical implementation archive.

### v12

- Роль: preservation and design recovery.
- Что добавил: artifact lineage, continuation decision, workspace delta,
  ring-editor canonical contract, optimization control plane contract и
  truthful graphics contract.
- Статус: historical design-recovery layer, импортирован в
  `docs/context/gui_spec_imports/v12_design_recovery/`.

### v12_window_internal_routes

- Роль: report-only addendum по первому рабочему экрану и внутренним маршрутам
  окон.
- Архив:
  `pneumo_human_gui_report_only_v12_window_internal_routes.zip`.
- Что добавил: first-screen contracts, action-feedback matrix,
  direct-tree-open/dock-role matrix, semantic rewrite matrix and current vs
  canonical notes для поверхности проверки и отправки архива, подробного
  сравнения результатов, исходных данных проекта и набора испытаний.
- Статус: current report-only refinement в
  `docs/context/gui_spec_imports/v12_window_internal_routes/` с локальной
  KB-сводкой
  `docs/context/release_readiness/HUMAN_GUI_REPORT_ONLY_V12_WINDOW_INTERNAL_ROUTES_2026-04-20.md`.
- Ограничение: не runtime-closure proof и не доказательство визуальной приемки
  live current-окон.

### v15_state_continuity_repair_loops

- Роль: report-only addendum по state continuity, visible state markers and
  repair loops.
- Архив:
  `pneumo_human_gui_report_only_v15_state_continuity_repair_loops.zip`.
- Что добавляет: `STATE_CONTINUITY_AND_REPAIR_LOOP_CONTRACT_V15.md`,
  `WINDOW_STATE_MARKER_MATRIX_V15.csv`, `REPAIR_LOOP_POLICY_V15.csv`,
  `STALE_DIRTY_MISMATCH_TRUTH_MATRIX_V15.csv`,
  `CONTEXT_RESTORE_AND_RETURN_TARGETS_V15.csv`,
  `WINDOW_ENTRY_POLICY_V15.csv`, `COGNITIVE_MUST_SEE_MARKERS_V15.csv` and
  `ENTRY_STATE_REPAIR_GRAPH_V15.dot`.
- Статус: current report-only refinement в
  `docs/context/gui_spec_imports/v15_state_continuity_repair_loops/` с
  локальной KB-сводкой
  `docs/context/release_readiness/HUMAN_GUI_REPORT_ONLY_V15_STATE_CONTINUITY_REPAIR_LOOPS_2026-04-21.md`.
- Ограничение: не runtime-closure proof и не доказательство live state/repair
  acceptance текущего GUI.

### v16_visibility_priority

- Роль: report-only addendum по visibility priority, must-see states and
  inspector/help boundaries.
- Архив:
  `pneumo_human_gui_report_only_v16_visibility_priority.zip`.
- Что добавляет: `VISIBILITY_PRIORITY_POLICY_V16.md`,
  `MUST_SEE_STATE_MATRIX_V16.csv`,
  `ALWAYS_VISIBLE_CONDITIONAL_INSPECTOR_MATRIX_V16.csv`,
  `DOCK_REGION_VISIBILITY_POLICY_V16.csv`,
  `WORKSPACE_FIRST_5_SECONDS_V16.csv`,
  `COGNITIVE_LOAD_REDUCTION_V16.csv` and
  `VISIBILITY_ESCALATION_GRAPH_V16.dot`.
- Статус: current report-only refinement в
  `docs/context/gui_spec_imports/v16_visibility_priority/` с локальной
  KB-сводкой
  `docs/context/release_readiness/HUMAN_GUI_REPORT_ONLY_V16_VISIBILITY_PRIORITY_2026-04-21.md`.
- Ограничение: не runtime-closure proof и не доказательство live
  visibility/first-screen acceptance текущего GUI.

### v13

- Роль: специализированный ring-editor migration addendum.
- Что добавил: schema contract, screen blueprints, element/field catalogs,
  state machine, user pipeline, acceptance gates, ring-level migration matrix и
  handoff contract `WS-RING -> WS-SUITE`.
- Статус: specialized addendum в
  `docs/context/gui_spec_imports/v13_ring_editor_migration/`.

### v37

- Роль: predecessor GitHub knowledge-base supplement и TZ/spec connector.
- Архив: `pneumo_codex_tz_spec_connector_reconciled_v37_github_kb_supplement.zip`.
- Что добавил: import-ready subtree для
  `docs/context/gui_spec_imports/v37_github_kb_supplement/`,
  `TECHNICAL_SPECIFICATION.md`, `GUI_SPEC.yaml`, workspace contract matrix,
  parameter catalogs, requirements/acceptance matrices, repo canon alignment,
  maintainer checklist и список gaps, которые должны оставаться открытыми.
- Статус: predecessor KB supplement в
  `docs/context/gui_spec_imports/v37_github_kb_supplement/`.
- Ограничение: слой reference-first и не объявляет producer-side truth,
  measured perf trace или Windows runtime acceptance закрытыми без отдельного
  evidence layer.

### v38

- Роль: current successor GitHub KB/TZ/spec commit-ready layer.
- Архив:
  `pneumo_codex_tz_spec_connector_reconciled_v38_github_kb_commit_ready.zip`.
- Что добавил: import-ready subtree для
  `docs/context/gui_spec_imports/v38_github_kb_commit_ready/`,
  `TECHNICAL_SPECIFICATION.md`, `GUI_SPEC.yaml`, workspace contract matrix,
  parameter catalogs, requirements/acceptance matrices, repo canon alignment,
  optimized pipeline, maintainer adoption notes and open gaps that must remain
  open.
- Статус: current successor KB/TZ/spec layer в
  `docs/context/gui_spec_imports/v38_github_kb_commit_ready/`.
- Локальное уточнение:
  `docs/context/release_readiness/V38_KB_IMPORT_AUDIT_2026-04-18.md` fixes
  read coverage, wrapper/imported-layer identity and packaging-title
  ambiguities.
- Ограничение: слой reference-first и не объявляет producer-side truth,
  measured browser perf trace, viewport gating, cylinder packaging или Windows
  visual/runtime acceptance закрытыми без отдельного evidence layer.

## Итоговый приоритет

1. `docs/17_WINDOWS_DESKTOP_CAD_GUI_CANON.md`
2. `docs/18_PNEUMOAPP_WINDOWS_GUI_SPEC.md`
3. `docs/context/gui_spec_imports/foundations/*`
4. `docs/context/gui_spec_imports/v38_github_kb_commit_ready/*`
5. `docs/context/release_readiness/V38_KB_IMPORT_AUDIT_2026-04-18.md`
6. `docs/context/gui_spec_imports/v12_window_internal_routes/*` для
   first-screen/internal-route уточнений четырех окон
7. `docs/context/gui_spec_imports/v15_state_continuity_repair_loops/*` для
   state-continuity/repair-loop уточнений stale/dirty/mismatch/degraded states
8. `docs/context/gui_spec_imports/v16_visibility_priority/*` для
   visibility-priority/must-see state and inspector/help boundary уточнений
9. `docs/context/gui_spec_imports/v37_github_kb_supplement/*`
10. `docs/context/gui_spec_imports/v3/*`
11. `docs/context/gui_spec_imports/v13_ring_editor_migration/*` для `WS-RING`
   и ring-to-suite handoff
12. `docs/context/gui_spec_imports/v12_design_recovery/*`
13. lineage `PROMPT_V2 + v1…v13 + v37 + v38`
14. прочие historical imports и implementation archives

## Практическое правило

- Для текущих GUI-задач сначала опираемся на `17`, `18`, `foundations`,
  `v38` как current KB/TZ/spec supplement, V38 audit as local ambiguity
  resolution, `v37` как predecessor provenance и затем `v3`.
- Для ring editor и suite handoff обязательно добавляем `v13`.
- Для requirements, параметров, workspace coverage, acceptance и open gaps
  обязательно сверяемся с `v38`, но не выдаём его за runtime acceptance.
- Для surface проверки/отправки архива, подробного сравнения результатов,
  исходных данных проекта и набора испытаний дополнительно читаем
  `v12_window_internal_routes`, но не выдаём его за runtime acceptance.
- Для спорных вопросов о происхождении канона, design/recovery decisions и
  границе между design и implementation-pass читаем `v12` и lineage
  `PROMPT_V2 + v1…v13 + v37 + v38`.

## Связанный connector-reconciled слой V32

После этой lineage-цепочки добавлен отдельный knowledge-base слой
`docs/context/gui_spec_imports/v32_connector_reconciled/README.md` из архива
`pneumo_codex_tz_spec_connector_reconciled_v32.zip`.

V32 не является очередным imported implementation pass в линии `v1…v13`.
Его роль другая: собрать connector-reconciled GUI/TZ package с source authority,
workspace contracts, acceptance playbooks, release gates, runtime artifact
schema, evidence policy и open gaps. Поэтому для новых задач V32 читается после
`17/18` как актуальный digest, а этот lineage-документ остается картой
происхождения старых слоев.

## Chat consolidated master V1

`chat_consolidated_master_v1` is imported from `pneumo_chat_consolidated_master_v1.zip`
as the current consolidated master reference layer. It does not replace the
human-readable canon `17/18`, and it is not runtime-closure proof.

The layer includes:

- source context and prompt provenance in `01_SOURCE_CONTEXT/`;
- final CODEX spec package `v38_actualized_with_v10`;
- repo audit `v34_repo_audit`;
- graph analysis V17, V19, V20 and V21;
- human report-only layers V10 through V16;
- `06_INDEX/MASTER_EXEC_SUMMARY.json`, `INCLUDED_ARTIFACTS.csv`,
  `SUPERSEDED_AND_EXCLUDED.csv` and `LINEAGE_AND_READING_ORDER.md`.

For lineage work, start with
`docs/context/gui_spec_imports/chat_consolidated_master_v1/REPO_IMPORT_NOTE.md`
and `docs/context/release_readiness/CHAT_CONSOLIDATED_MASTER_V1_KB_IMPORT_AUDIT_2026-04-21.md`.
