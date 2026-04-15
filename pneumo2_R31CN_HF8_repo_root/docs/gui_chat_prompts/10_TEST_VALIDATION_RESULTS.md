# Chat Prompt: Test Validation Results Center

## Канонический слой

- Сначала читать [17_WINDOWS_DESKTOP_CAD_GUI_CANON.md](../17_WINDOWS_DESKTOP_CAD_GUI_CANON.md),
  затем [18_PNEUMOAPP_WINDOWS_GUI_SPEC.md](../18_PNEUMOAPP_WINDOWS_GUI_SPEC.md).
- Общий detailed layer для shell, migration и acceptance:
  [gui_spec_imports/v3/README.md](../context/gui_spec_imports/v3/README.md),
  [migration_matrix.csv](../context/gui_spec_imports/v3/migration_matrix.csv),
  [pipeline_verification.csv](../context/gui_spec_imports/v3/pipeline_verification.csv),
  [acceptance_criteria.csv](../context/gui_spec_imports/v3/acceptance_criteria.csv).
- Специализированный addendum для сценарного handoff:
  [ring_to_suite_link_contract_v13.json](../context/gui_spec_imports/v13_ring_editor_migration/ring_to_suite_link_contract_v13.json),
  [web_to_desktop_migration_matrix_v13.csv](../context/gui_spec_imports/v13_ring_editor_migration/web_to_desktop_migration_matrix_v13.csv),
  [ring_editor_acceptance_gates_v13.csv](../context/gui_spec_imports/v13_ring_editor_migration/ring_editor_acceptance_gates_v13.csv).

## Контекст

После запуска расчётов пользователь должен работать в desktop-центре тестов и результатов, а не разрываться между WEB validation/results страницами.

## Наследование desktop-канона

- Перед локальными решениями сначала следуй [17_WINDOWS_DESKTOP_CAD_GUI_CANON.md](../17_WINDOWS_DESKTOP_CAD_GUI_CANON.md), затем [18_PNEUMOAPP_WINDOWS_GUI_SPEC.md](../18_PNEUMOAPP_WINDOWS_GUI_SPEC.md).
- Results center может быть orchestration-oriented, но должен наследовать command discipline, keyboard-first, accessibility, High-DPI и performance policy.
- Если появляются previews, inspectors или result surfaces, располагай их как устойчивые panes, а не как web-style бесконечные страницы. `Ribbon` не использовать как default.
- Если workflow касается сценария кольца, `WS-SUITE` работает только как consumer канонического экспорта из `WS-RING`: геометрия сегментов не копируется в локальные editable поля.

## Цель

Развивать desktop test/results center как главный маршрут после запуска расчётов. Нужны: тестовые прогоны, validation overview, results browsing, переходы в compare viewer, animator и diagnostics/send center.

## Можно менять

- [test_center_gui.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/tools/test_center_gui.py)
- новые файлы рядом с lane:
  - `pneumo_solver_ui/tools/desktop_results_center.py`
  - `pneumo_solver_ui/desktop_results_model.py`
  - `pneumo_solver_ui/desktop_results_runtime.py`
- related desktop workflow tests

## Можно читать как источник поведения

- [08_ValidationCockpit_Web.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/pages/08_ValidationCockpit_Web.py)
- [09_Validation_Web.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/pages/09_Validation_Web.py)
- [12_ResultsViewer.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/pages/12_ResultsViewer.py)
- [validation_cockpit_web.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/validation_cockpit_web.py)
- [npz_anim_diagnostics.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/npz_anim_diagnostics.py)
- `ui_results_*`

## Нельзя менять

- [qt_compare_viewer.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/qt_compare_viewer.py)
- [app.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/desktop_animator/app.py)
- [send_results_gui.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/tools/send_results_gui.py) кроме интеграции
- WEB pages как target

## Правила

- `test_center_gui` должен быть orchestration window, а не копией compare viewer или animator.
- Глубокую графику оставляй compare viewer и animator.
- Удерживай понятный operator flow: run -> validate -> inspect -> branch into specialized tool.
- Для тестов типа `ring` показывай ссылку назад к каноническому сценарию и версию ring export; stale link обязан быть видимым warning, а не скрытым расхождением данных.

## Готовый промт

```text
Работай только в lane "Test Validation Results Center".

Сначала прочитай docs/17_WINDOWS_DESKTOP_CAD_GUI_CANON.md, затем docs/18_PNEUMOAPP_WINDOWS_GUI_SPEC.md и соблюдай их как project-wide baseline и augmented A–M project-specific contract.

Контекст: после запуска расчётов пользователь должен оставаться в desktop test/results center, а не уходить в WEB validation/results pages.

Цель: развивать desktop test/results center как главный маршрут после запуска расчётов. Нужны: тестовые прогоны, validation overview, results browsing, переходы в compare viewer, animator и diagnostics/send center.

Можно менять только:
- pneumo_solver_ui/tools/test_center_gui.py
- новые desktop_results_* модули
- related desktop workflow tests

Можно читать как источник поведения:
- pneumo_solver_ui/pages/08_ValidationCockpit_Web.py
- pneumo_solver_ui/pages/09_Validation_Web.py
- pneumo_solver_ui/pages/12_ResultsViewer.py
- pneumo_solver_ui/validation_cockpit_web.py
- pneumo_solver_ui/npz_anim_diagnostics.py
- pneumo_solver_ui/ui_results_* helpers

Нельзя менять:
- qt_compare_viewer.py
- desktop_animator/app.py
- send_results_gui.py кроме интеграции
- WEB pages как target

Правила:
- test_center_gui должен быть orchestration window, а не копией compare viewer или animator
- глубокую графику оставляй compare viewer и animator
- удерживай понятный operator flow: run -> validate -> inspect -> branch into specialized tool

Сделай следующий шаг по desktop test/validation/results center и проверь targeted tests.
```
