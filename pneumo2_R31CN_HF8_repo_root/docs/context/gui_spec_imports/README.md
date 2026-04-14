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

- `v3/` — active detailed machine-readable reference layer из
  `pneumo_gui_codex_package_v3.zip`;
- `v2/` — historical detailed import-layer из
  `pneumo_gui_codex_package_v2.zip`;
- корневые `pneumo_gui_codex_spec_v1.json`, `current_pipeline.dot`,
  `optimized_pipeline.dot` — historical import-layer из
  `pneumo_gui_codex_package_v1.zip`.

## Что использовать в работе

1. Сначала читать `17` и `18` как канон для людей.
2. Затем использовать `v3/*` как active detailed machine-readable reference для:
   layout, UI elements, field/help/tooltip catalogs, migration matrix,
   acceptance criteria, pipeline verification, source-of-truth, docking,
   keyboard, UI state и observability contracts.
3. `v2` и `v1` использовать только как historical imports и источник для
   сравнения эволюции GUI-spec.

## Политика обновления

- CSV, DOT и JSON сохраняются максимально близко к архивному источнику;
- нормализация допускается только в производных docs/tests, а не в imported
  source artifacts;
- при конфликте между imported sources и текущим каноном приоритет у `17/18`,
  затем у active detailed layer `v3`, затем у historical imports.
