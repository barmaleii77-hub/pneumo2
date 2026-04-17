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
- `v37_github_kb_supplement/` — import-ready successor knowledge-base
  supplement layer для GitHub/CODEX/TZ/spec reconciliation. Слой читается
  после `foundations/*`, но не выше `17/18`, и не является
  `runtime-closure proof`;
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
3. Для repo knowledge-base reconciliation, связки ТЗ с GUI-spec, workspace
   contract matrix, parameter catalogs, open gaps and acceptance matrix читать
   `v37_github_kb_supplement/*`. Этот слой является successor KB supplement,
   но не закрывает runtime acceptance без отдельного evidence layer.
4. Затем использовать `v3/*` как active detailed machine-readable reference для:
   layout, UI elements, field/help/tooltip catalogs, migration matrix,
   acceptance criteria, pipeline verification, source-of-truth, docking,
   keyboard, UI state и observability contracts.
5. Если нужно понять, как текущий канон вырос из старых архивов, читать
   `GUI_SPEC_ARCHIVE_LINEAGE.md` и `gui_spec_archive_lineage.json`.
6. Для `WS-RING` и handoff `WS-RING -> WS-SUITE` дополнительно использовать
   `v13_ring_editor_migration/*` как специализированный addendum поверх `v3`:
   schema contract, screen blueprints, state machine, ring-level migration
   matrix, acceptance gates и suite-link contract.
7. `v12_design_recovery/*` использовать как historical design-recovery layer:
   он фиксирует возврат в design-first ветку, канон ring editor, optimization
   control plane и truthful graphics перед `v13`.
8. `v2` и `v1` использовать только как historical imports и источник для
   сравнения эволюции GUI-spec.

## Политика обновления

- CSV, DOT и JSON сохраняются максимально близко к архивному источнику;
- markdown prompt sources в `foundations/` сохраняются максимально близко к
  внешнему upstream-источнику;
- нормализация допускается только в производных docs/tests, а не в imported
  source artifacts;
- при конфликте между imported sources и текущим каноном приоритет у `17/18`,
  затем у `foundations/*` как upstream intent layer только для provenance,
  затем у `v37_github_kb_supplement/*` как successor consolidated
  knowledge-base supplement, затем у active detailed layer `v3`, затем у
  специализированного addendum
  `v13_ring_editor_migration` в пределах `WS-RING` и ring-to-suite handoff,
  затем у `v12_design_recovery` как historical design-recovery layer, затем у
  остальных historical imports.
