# Imported GUI-Spec Reference Layers

Этот каталог хранит imported GUI-spec артефакты из внешних пакетов Codex.

Важно:

- это reference-layer, а не вручную поддерживаемый продуктовый канон;
- human-readable source of truth для проекта остаётся в
  [17_WINDOWS_DESKTOP_CAD_GUI_CANON.md](../../17_WINDOWS_DESKTOP_CAD_GUI_CANON.md)
  и
  [18_PNEUMOAPP_WINDOWS_GUI_SPEC.md](../../18_PNEUMOAPP_WINDOWS_GUI_SPEC.md);
- lane-доки в [docs/gui_chat_prompts](../../gui_chat_prompts/00_INDEX.md) обязаны
  ссылаться на канон и не спорить с ним;
- raw `.zip` в репозиторий не добавляется.

## Текущая иерархия версий

- `foundations/` — upstream prompt sources, предшествующие серии архивов
  `v1…v13`;
- `v33_connector_reconciled/` — active connector-reconciled knowledge digest из
  `pneumo_codex_tz_spec_connector_reconciled_v33.zip`; использовать как
  текущий v33 source-priority, integrity/selfcheck/remediation и repo-canon
  gate-mapping слой поверх v32;
- `v32_connector_reconciled/` — active connector-reconciled knowledge digest из
  `pneumo_codex_tz_spec_connector_reconciled_v32.zip`; использовать как
  предыдущий connector-reconciled слой и как workstream-decomposition layer
  через `PARALLEL_CHAT_WORKSTREAMS.md`, поверх
  `v3`, `v12` и `v13`, не заменяя `17/18`; внутри также лежат
  `COMPLETENESS_ASSESSMENT.md`, `PARALLEL_CHAT_WORKSTREAMS.md`,
  `RELEASE_GATE_ACCEPTANCE_MAP.md`, checked-in
  `RELEASE_GATE_HARDENING_MATRIX.csv` и
  `GAP_TO_EVIDENCE_ACTION_MAP.csv`, plus lane evidence notes such as
  `WS_INPUTS_HANDOFF_EVIDENCE_NOTE.md`,
  `PRODUCER_ANIMATOR_TRUTH_EVIDENCE_NOTE.md`,
  `COMPARE_OBJECTIVE_INTEGRITY_EVIDENCE_NOTE.md`,
  `GEOMETRY_REFERENCE_EVIDENCE_NOTE.md`,
  `MNEMO_TRUTH_GRAPHICS_EVIDENCE_NOTE.md`,
  `ENGINEERING_ANALYSIS_EVIDENCE_NOTE.md`,
  `DIAGNOSTICS_RELEASE_EVIDENCE_NOTE.md`,
  `DIAGNOSTICS_PRODUCER_GAPS_HANDOFF.md` and
  `RUNTIME_RELEASE_EVIDENCE_NOTE.md`;
- `v3/` — active detailed machine-readable reference layer из
  `pneumo_gui_codex_package_v3.zip`;
- `v12_design_recovery/` — historical design-recovery layer из
  `pneumo_gui_codex_preservation_and_design_recovery_v12.zip`;
- `v13_ring_editor_migration/` — специализированный ring-editor migration
  addendum из `pneumo_gui_codex_design_v13_ring_editor_migration.zip`;
- `v2/` — historical detailed import-layer из
  `pneumo_gui_codex_package_v2.zip`;
- корневые `pneumo_gui_codex_spec_v1.json`, `current_pipeline.dot`,
  `optimized_pipeline.dot` — historical import-layer из
  `pneumo_gui_codex_package_v1.zip`.
- Эволюция `v1…v13` в виде knowledge-base summary зафиксирована в
  `docs/context/GUI_SPEC_ARCHIVE_LINEAGE.md` и
  `docs/context/gui_spec_archive_lineage.json`.

## Что использовать в работе

1. Сначала читать `17` и `18` как канон для людей.
2. Если нужен upstream provenance исходного design-intent, читать
   `foundations/*` как pre-`v1` prompt layer.
3. Затем читать `v33_connector_reconciled/README.md` как active
   connector-reconciled digest для V33: integrity policy, selfcheck,
   remediation, repo-canon read order, gate mapping и PB-008 provenance
   playbook.
4. Для контекста V32 и параллельной разработки читать
   `v32_connector_reconciled/README.md` и
   `v32_connector_reconciled/PARALLEL_CHAT_WORKSTREAMS.md`; если нужно понять
   достаточность архива, читать `v32_connector_reconciled/COMPLETENESS_ASSESSMENT.md`.
5. Если задача касается release gates, acceptance evidence или open gaps, читать
   `v32_connector_reconciled/RELEASE_GATE_ACCEPTANCE_MAP.md` и local checked-in
   extracts `RELEASE_GATE_HARDENING_MATRIX.csv`,
   `GAP_TO_EVIDENCE_ACTION_MAP.csv`; for frozen inputs/suite handoff
   acceptance, also read
   `v32_connector_reconciled/WS_INPUTS_HANDOFF_EVIDENCE_NOTE.md`;
   for producer/animator truth acceptance,
   also read `v32_connector_reconciled/PRODUCER_ANIMATOR_TRUTH_EVIDENCE_NOTE.md`;
   for compare/objective integrity, also read
   `v32_connector_reconciled/COMPARE_OBJECTIVE_INTEGRITY_EVIDENCE_NOTE.md`;
   for geometry reference/imported-layer boundary proof, also read
   `v32_connector_reconciled/GEOMETRY_REFERENCE_EVIDENCE_NOTE.md`;
   for Desktop Mnemo truth graphics, also read
   `v32_connector_reconciled/MNEMO_TRUTH_GRAPHICS_EVIDENCE_NOTE.md`;
   for Engineering Analysis/Calibration/Influence evidence, also read
   `v32_connector_reconciled/ENGINEERING_ANALYSIS_EVIDENCE_NOTE.md`;
   for diagnostics/SEND-bundle acceptance,
   also read `v32_connector_reconciled/DIAGNOSTICS_RELEASE_EVIDENCE_NOTE.md`;
   for producer-owned diagnostics warning handoff, also read
   `v32_connector_reconciled/DIAGNOSTICS_PRODUCER_GAPS_HANDOFF.md`;
   for runtime/perf evidence gates, also read
   `v32_connector_reconciled/RUNTIME_RELEASE_EVIDENCE_NOTE.md`.
6. Затем использовать `v3/*` как checked-in detailed machine-readable reference для:
   layout, UI elements, field/help/tooltip catalogs, migration matrix,
   acceptance criteria, pipeline verification, source-of-truth, docking,
   keyboard, UI state и observability contracts.
7. Если нужно понять, как текущий канон вырос из старых архивов, читать
   `GUI_SPEC_ARCHIVE_LINEAGE.md` и `gui_spec_archive_lineage.json`.
8. Для `WS-RING` и handoff `WS-RING -> WS-SUITE` дополнительно использовать
   `v13_ring_editor_migration/*` как специализированный addendum поверх `v3`:
   schema contract, screen blueprints, state machine, ring-level migration
   matrix, acceptance gates и suite-link contract.
9. `v12_design_recovery/*` использовать как historical design-recovery layer:
   он фиксирует возврат в design-first ветку, канон ring editor, optimization
   control plane и truthful graphics перед `v13`.
10. `v2` и `v1` использовать только как historical imports и источник для
   сравнения эволюции GUI-spec.

## Политика обновления

- CSV, DOT и JSON сохраняются максимально близко к архивному источнику;
- markdown prompt sources в `foundations/` сохраняются максимально близко к
  внешнему upstream-источнику;
- нормализация допускается только в производных docs/tests, а не в imported
  source artifacts;
- при конфликте между imported sources и текущим каноном приоритет у `17/18`,
  затем у `v33_connector_reconciled/README.md` как active connector-reconciled
  digest, затем у `v32_connector_reconciled/README.md` как previous
  connector-reconciled digest/workstream layer и его release/evidence extracts,
  затем у `foundations/*` как upstream intent layer только для provenance,
  затем у checked-in detailed layer `v3`, затем у специализированного addendum
  `v13_ring_editor_migration` в пределах `WS-RING` и ring-to-suite handoff,
  затем у `v12_design_recovery` как historical design-recovery layer, затем у
  остальных historical imports.
