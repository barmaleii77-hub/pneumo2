# Chat Prompt: Редактор И Генератор Сценариев Колец

## Канонический слой

- Сначала читать [17_WINDOWS_DESKTOP_CAD_GUI_CANON.md](../17_WINDOWS_DESKTOP_CAD_GUI_CANON.md),
  затем [18_PNEUMOAPP_WINDOWS_GUI_SPEC.md](../18_PNEUMOAPP_WINDOWS_GUI_SPEC.md).
- Общий detailed layer для shell и GUI registries:
  [gui_spec_imports/v3/README.md](../context/gui_spec_imports/v3/README.md).
- Специализированный addendum для ring editor и миграции `web -> desktop`:
  [pneumo_gui_codex_spec_v13_ring_editor_migration.json](../context/gui_spec_imports/v13_ring_editor_migration/pneumo_gui_codex_spec_v13_ring_editor_migration.json),
  [ring_editor_schema_contract_v13.json](../context/gui_spec_imports/v13_ring_editor_migration/ring_editor_schema_contract_v13.json),
  [ring_editor_screen_blueprints_v13.csv](../context/gui_spec_imports/v13_ring_editor_migration/ring_editor_screen_blueprints_v13.csv),
  [ring_editor_element_catalog_v13.csv](../context/gui_spec_imports/v13_ring_editor_migration/ring_editor_element_catalog_v13.csv),
  [ring_editor_field_catalog_v13.csv](../context/gui_spec_imports/v13_ring_editor_migration/ring_editor_field_catalog_v13.csv),
  [ring_editor_state_machine_v13.json](../context/gui_spec_imports/v13_ring_editor_migration/ring_editor_state_machine_v13.json),
  [web_to_desktop_migration_matrix_v13.csv](../context/gui_spec_imports/v13_ring_editor_migration/web_to_desktop_migration_matrix_v13.csv),
  [ring_editor_acceptance_gates_v13.csv](../context/gui_spec_imports/v13_ring_editor_migration/ring_editor_acceptance_gates_v13.csv),
  [ring_to_suite_link_contract_v13.json](../context/gui_spec_imports/v13_ring_editor_migration/ring_to_suite_link_contract_v13.json).

## Контекст

Ring workflow больше не должен жить в WEB. Нужен отдельный desktop editor для сегментов, дорог, событий, diagnostics и генерации артефактов.

## Наследование desktop-канона

- Перед локальными решениями сначала следуй [17_WINDOWS_DESKTOP_CAD_GUI_CANON.md](../17_WINDOWS_DESKTOP_CAD_GUI_CANON.md), затем [18_PNEUMOAPP_WINDOWS_GUI_SPEC.md](../18_PNEUMOAPP_WINDOWS_GUI_SPEC.md).
- Для ring editor нужен viewport/preview-first layout: в центре preview кольца и артефактов, а не только таблица параметров.
- Левая pane допустима для segment tree, event tree или scenario browser только при реальной иерархии; справа должен быть context-sensitive inspector/properties pane.
- Если preview становится 3D, обязателен orientation widget уровня `ViewCube`. Для всех числовых полей использовать названия и единицы измерения.
- Считай ring editor единственным source-of-truth сценариев; `road_csv`, `axay_csv`, `scenario_json` и diagnostics views остаются только derived representations.
- Учитывай `v13` как специализированный contract: `WS-RING` является единственным пользовательским источником истины, а `WS-SUITE` только потребляет экспорт и не дублирует геометрию сценария.

## Цель

Перенести весь ring-scenario workflow из WEB в отдельный desktop GUI: редактор сегментов, направление поворота, тип дороги, события, ISO/SINE параметры, diagnostics, preview кольца, генерация `spec/road/axay`.

## Можно менять

- новые GUI файлы:
  - `pneumo_solver_ui/tools/desktop_ring_scenario_editor.py`
  - `pneumo_solver_ui/desktop_ring_editor_model.py`
  - `pneumo_solver_ui/desktop_ring_editor_runtime.py`
  - `pneumo_solver_ui/desktop_ring_editor_panels.py`
- shell adapter/catalog только если добавляется новое окно

## Можно читать как источник поведения

- [ui_scenario_ring.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/ui_scenario_ring.py)
- [scenario_ring.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/scenario_ring.py)
- [ring_visuals.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/ring_visuals.py)
- [scenario_generator.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/scenario_generator.py)
- [optimization_auto_ring_suite.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/optimization_auto_ring_suite.py)
- [build_optimization_auto_ring_suite.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/tools/build_optimization_auto_ring_suite.py)
- imported v13 reference layer в `docs/context/gui_spec_imports/v13_ring_editor_migration/*`

## Нельзя менять

- desktop input editor
- optimizer GUI, кроме интеграции по готовому output
- compare viewer
- desktop animator
- desktop mnemo
- WEB pages

## Правила

- Это отдельное окно, не встраивай сложный ring editor в input editor.
- Опирайся на canonical backend logic из `scenario_ring.py`.
- Удерживай layout `RG-HEADER / RG-LEFT / RG-PLAN / RG-LONG / RG-CROSSFALL / RG-FOOTER`, а детальные поля сегмента оставляй в правом глобальном инспекторе, а не в скрытых модалках.
- Не создавай второй пользовательский источник истины вне `WS-RING` и не переноси редактирование геометрии в `WS-SUITE`.
- UI дели на панели: segments, road, motion, events, diagnostics, export.
- Не сваливай весь workflow в одну длинную форму без устойчивого preview и явных scrollbars/resizers.

## Готовый промт

```text
Работай только в lane "Редактор И Генератор Сценариев Колец".

Сначала прочитай docs/17_WINDOWS_DESKTOP_CAD_GUI_CANON.md, затем docs/18_PNEUMOAPP_WINDOWS_GUI_SPEC.md и соблюдай их как project-wide baseline и augmented A–M project-specific contract.

Контекст: ring workflow уходит из WEB. Нужен отдельный desktop editor с понятным UX для сегментов, дорог, событий и генерации артефактов.

Цель: перенести весь ring-scenario workflow из WEB в отдельный desktop GUI. Нужны: редактор сегментов, направление поворота, тип дороги, события, ISO/SINE параметры, diagnostics, preview кольца, генерация spec/road/axay артефактов.

Можно менять только:
- новые desktop_ring_* модули
- shell adapter/catalog только если добавляется новое окно
- targeted tests для ring editor GUI

Можно читать как источник поведения:
- pneumo_solver_ui/ui_scenario_ring.py
- pneumo_solver_ui/scenario_ring.py
- pneumo_solver_ui/ring_visuals.py
- pneumo_solver_ui/scenario_generator.py
- pneumo_solver_ui/optimization_auto_ring_suite.py
- pneumo_solver_ui/tools/build_optimization_auto_ring_suite.py

Нельзя менять:
- desktop_input_editor.py
- optimizer GUI, кроме интеграции по готовому output
- compare viewer
- desktop animator
- desktop mnemo
- WEB pages

Правила:
- это отдельное окно, не встраивай сложный ring editor в input editor
- опирайся на canonical backend logic из scenario_ring.py
- UI дели на панели: segments, road, motion, events, diagnostics, export
- держи preview или viewport в центре, а browser/properties panes вокруг него
- все величины подписывай названием и единицей измерения, кроме очевидно безразмерных

Сделай первый или следующий логичный шаг по desktop ring editor и сохрани модульность.
```
