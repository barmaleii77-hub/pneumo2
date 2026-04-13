# GUI-Only Migration Chat Prompts

Дата: 2026-04-12

Этот документ заменяет WEB-centric планирование. Цель теперь простая: весь пользовательский функционал переносится в понятное классическое Windows GUI-приложение без потери возможностей и без новых WEB-монолитов.

## Базовая установка

- WEB больше не является целевой платформой для развития.
- WEB-файлы ниже используются только как источник текущего поведения и требований к паритету.
- Новые пользовательские возможности нужно добавлять в desktop GUI.
- Не дублировать `desktop_animator`, `qt_compare_viewer` и `desktop_mnemo` внутри других окон.
- Не строить новый монолит: делить окна на `*_model.py`, `*_runtime.py`, `*_panel.py`, `*_bridge.py`, если модуль растёт.

## Общие правила для всех чатов

- Один чат = один модульный lane.
- Не трогать чужие lane-файлы.
- Не делать сквозные рефакторинги через весь проект.
- Если нужен shared seam, выносить его рядом с целевым GUI-модулем, а не в случайный общий файл.
- `pneumo_ui_app.py` и `pages/*` читать можно, развивать в них новые возможности нельзя.
- Для shell-интеграции менять только `adapter/spec/catalog`, а не тащить feature-логику в shell.

## Shared Danger Zone

Эти файлы не должны меняться параллельно разными чатами без явной координации:

- [pneumo_ui_app.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/pneumo_ui_app.py)
- [page_registry.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/page_registry.py)
- [registry.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/desktop_shell/registry.py)
- [launcher_catalog.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/desktop_shell/launcher_catalog.py)
- [contracts.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/desktop_shell/contracts.py)
- [desktop_input_model.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/desktop_input_model.py)
- [qt_compare_viewer.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/qt_compare_viewer.py)
- [app.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/desktop_animator/app.py)
- [app.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/desktop_mnemo/app.py)

## Chat A: Главное Окно Приложения

### Цель

Собрать главное классическое многооконное Windows-приложение: верхнее меню, toolbar, рабочая область, статусная строка, единая навигация по встроенным окнам и запуск внешних специализированных GUI.

### Target files

- [main_window.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/desktop_shell/main_window.py)
- [workspace.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/desktop_shell/workspace.py)
- [menu_builder.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/desktop_shell/menu_builder.py)
- [toolbar.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/desktop_shell/toolbar.py)
- [home_view.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/desktop_shell/home_view.py)
- [navigation.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/desktop_shell/navigation.py)
- [lifecycle.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/desktop_shell/lifecycle.py)
- [desktop_main_shell.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/tools/desktop_main_shell.py)

### WEB files to mine for behavior only

- [pneumo_ui_app.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/pneumo_ui_app.py)
- [page_registry.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/page_registry.py)

### Готовый промт

```text
Работай только в lane "Главное Окно Приложения".

Цель: развивать главное классическое Windows GUI-приложение как основной вход в систему. Нужен понятный shell с верхним меню, toolbar, home screen, рабочей областью со встроенными окнами и единым пользовательским маршрутом без WEB.

Можно менять только:
- pneumo_solver_ui/desktop_shell/main_window.py
- pneumo_solver_ui/desktop_shell/workspace.py
- pneumo_solver_ui/desktop_shell/menu_builder.py
- pneumo_solver_ui/desktop_shell/toolbar.py
- pneumo_solver_ui/desktop_shell/home_view.py
- pneumo_solver_ui/desktop_shell/navigation.py
- pneumo_solver_ui/desktop_shell/lifecycle.py
- pneumo_solver_ui/tools/desktop_main_shell.py
- tests/test_desktop_main_shell_contract.py

Можно читать как источник поведения:
- pneumo_solver_ui/pneumo_ui_app.py
- pneumo_solver_ui/page_registry.py

Нельзя менять:
- feature-логику отдельных окон
- desktop_animator
- qt_compare_viewer
- desktop_mnemo
- WEB pages

Правила:
- не превращай main_window.py в новый монолит
- выноси новые seams в отдельные shell-модули
- shell должен быть центром приложения, а не свалкой feature-кода
- сохраняй классический desktop UX под Windows

Сделай следующий логичный шаг по shell core, реализуй его до конца и прогони shell-targeted tests.
```

## Chat B: Ввод Исходных Данных

### Цель

Главный GUI ввода исходных параметров с разделением на кластеры: геометрия, пневматика, механика, статическая настройка, компоненты, reference-данные.

### Target files

- [desktop_input_editor.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/tools/desktop_input_editor.py)
- [desktop_input_model.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/desktop_input_model.py)

### WEB and canonical source files to mine

- [pneumo_ui_app.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/pneumo_ui_app.py)
- [10_SuspensionGeometry.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/pages/10_SuspensionGeometry.py)
- [13_CamozziCylindersCatalog.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/pages/13_CamozziCylindersCatalog.py)
- [14_SpringsGeometry_CoilBind.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/pages/14_SpringsGeometry_CoilBind.py)
- [spring_geometry_ui.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/spring_geometry_ui.py)
- [spring_table.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/spring_table.py)
- [01_PARAMETER_REGISTRY.md](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/01_PARAMETER_REGISTRY.md)

### Готовый промт

```text
Работай только в lane "Ввод Исходных Данных".

Цель: сделать основное окно ввода исходных данных понятным для инженера и пользователя. Оно должно быть cluster-based: Геометрия, Пневматика, Механика, Статическая настройка, Компоненты, Справочные данные. WEB больше не является целевым UI, его можно читать только как источник поведения.

Можно менять только:
- pneumo_solver_ui/tools/desktop_input_editor.py
- pneumo_solver_ui/desktop_input_model.py
- tests/test_desktop_input_editor_contract.py

Можно читать как источник поведения:
- pneumo_solver_ui/pneumo_ui_app.py
- pneumo_solver_ui/pages/10_SuspensionGeometry.py
- pneumo_solver_ui/pages/13_CamozziCylindersCatalog.py
- pneumo_solver_ui/pages/14_SpringsGeometry_CoilBind.py
- pneumo_solver_ui/spring_geometry_ui.py
- pneumo_solver_ui/spring_table.py
- 01_PARAMETER_REGISTRY.md

Нельзя менять:
- shell core
- optimizer GUI
- compare viewer
- desktop animator
- desktop mnemo
- WEB pages

Правила:
- не дублируй compare/animator/mnemo
- не складывай всё в один огромный Tk-класс
- если нужны новые blocks, выноси их в отдельные panel/model helpers
- сохраняй понятный desktop UX: секции, пресеты, профили, snapshots, быстрый поиск

Сделай следующий полезный шаг именно по окну ввода исходных данных и прогони его targeted tests.
```

## Chat C: Настройка Расчёта

### Цель

Отдельный GUI-контур для настроек расчёта: режим запуска, dt, длительность, baseline/detail/full, cache, export, auto-check, запись логов, runtime policy, очереди прогонов.

### Target files

- [desktop_input_editor.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/tools/desktop_input_editor.py)
- [desktop_single_run.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/tools/desktop_single_run.py)
- новые файлы рядом с lane при необходимости:
  - `pneumo_solver_ui/tools/desktop_run_setup_center.py`
  - `pneumo_solver_ui/desktop_run_setup_model.py`
  - `pneumo_solver_ui/desktop_run_setup_runtime.py`

### WEB and canonical source files to mine

- [pneumo_ui_app.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/pneumo_ui_app.py)
- [test_center_gui.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/tools/test_center_gui.py)
- [run_full_diagnostics_gui.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/tools/run_full_diagnostics_gui.py)
- [ui_results_runtime_helpers.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/ui_results_runtime_helpers.py)

### Готовый промт

```text
Работай только в lane "Настройка Расчёта".

Цель: выделить и развить понятный desktop GUI для настройки расчёта. Пользователь должен настраивать режим запуска, точность, длительность, baseline/detail/full run, экспорт и runtime policy без WEB UI.

Можно менять только:
- pneumo_solver_ui/tools/desktop_input_editor.py в части run-setup
- pneumo_solver_ui/tools/desktop_single_run.py
- новые desktop_run_setup_* модули рядом с этим lane
- tests, связанные с desktop input / desktop runs

Можно читать как источник поведения:
- pneumo_solver_ui/pneumo_ui_app.py
- pneumo_solver_ui/tools/test_center_gui.py
- pneumo_solver_ui/tools/run_full_diagnostics_gui.py
- pneumo_solver_ui/ui_results_runtime_helpers.py

Нельзя менять:
- shell core
- ring editor
- optimizer GUI
- compare viewer
- desktop animator
- desktop mnemo
- WEB pages

Правила:
- не смешивай физические параметры и runtime-настройки в один бесформенный экран
- если логика растёт, вынеси её в отдельный run setup module
- не дублируй test center, а выделяй понятный pre-run configuration workflow

Сделай следующий шаг по desktop run setup и доведи его до рабочего состояния.
```

## Chat D: Редактор И Генератор Сценариев Колец

### Цель

Сделать отдельный GUI для создания, редактирования, визуальной проверки и генерации ring-сценариев, включая preview структуры кольца и экспорт spec/road/axay артефактов.

### Target files

- новые GUI файлы:
  - `pneumo_solver_ui/tools/desktop_ring_scenario_editor.py`
  - `pneumo_solver_ui/desktop_ring_editor_model.py`
  - `pneumo_solver_ui/desktop_ring_editor_runtime.py`
  - `pneumo_solver_ui/desktop_ring_editor_panels.py`

### Canonical source files to mine

- [ui_scenario_ring.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/ui_scenario_ring.py)
- [scenario_ring.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/scenario_ring.py)
- [ring_visuals.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/ring_visuals.py)
- [scenario_generator.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/scenario_generator.py)
- [optimization_auto_ring_suite.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/optimization_auto_ring_suite.py)
- [build_optimization_auto_ring_suite.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/tools/build_optimization_auto_ring_suite.py)

### Готовый промт

```text
Работай только в lane "Редактор И Генератор Сценариев Колец".

Цель: перенести весь ring-scenario workflow из WEB в отдельный desktop GUI. Нужны: редактор сегментов, направление поворота, тип дороги, события, ISO/SINE параметры, diagnostics, preview кольца, генерация spec/road/axay артефактов.

Можно менять только:
- новые desktop_ring_* модули
- возможно shell adapter/catalog только если добавляется новое окно
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

Сделай первый или следующий логичный шаг по desktop ring editor и сохрани модульность.
```

## Chat E: Compare Viewer

### Цель

Сделать `qt_compare_viewer` главным специализированным окном сравнения, absorbing compare/results/validation use-cases из WEB.

### Target files

- [qt_compare_viewer.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/qt_compare_viewer.py)
- compare-related helpers рядом с ним при необходимости

### WEB and canonical source files to mine

- [compare_npz_web.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/compare_npz_web.py)
- [compare_npz.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/compare_npz.py)
- [compare_session.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/compare_session.py)
- [compare_ui.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/compare_ui.py)
- [validation_cockpit_web.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/validation_cockpit_web.py)
- [12_ResultsViewer.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/pages/12_ResultsViewer.py)
- [20_CompareRuns.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/pages/20_CompareRuns.py)
- [21_CompareRuns_Quick.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/pages/21_CompareRuns_Quick.py)
- `ui_results_*` helpers

### Готовый промт

```text
Работай только в lane "Compare Viewer".

Цель: сделать qt_compare_viewer основным специализированным GUI сравнения и постепенно поглотить compare/results/validation сценарии, которые раньше жили в WEB.

Можно менять только:
- pneumo_solver_ui/qt_compare_viewer.py
- compare-specific helper modules рядом с ним
- compare-specific tests

Можно читать как источник поведения:
- pneumo_solver_ui/compare_npz_web.py
- pneumo_solver_ui/compare_npz.py
- pneumo_solver_ui/compare_session.py
- pneumo_solver_ui/compare_ui.py
- pneumo_solver_ui/validation_cockpit_web.py
- pneumo_solver_ui/pages/12_ResultsViewer.py
- pneumo_solver_ui/pages/20_CompareRuns.py
- pneumo_solver_ui/pages/21_CompareRuns_Quick.py
- pneumo_solver_ui/ui_results_* helpers

Нельзя менять:
- desktop_shell/*
- desktop_animator
- desktop_mnemo
- WEB compare pages

Правила:
- treat qt_compare_viewer as standalone specialized app
- не распыляйся на shell и WEB
- переносить именно рабочие compare/results функции, а не просто тексты

Сделай следующий локальный шаг по compare viewer и проверь его targeted tests.
```

## Chat F: Desktop Mnemo

### Цель

Сделать Desktop Mnemo основным GUI схемы/мнемосхемы и перенести туда WEB mnemo/scheme functionality.

### Target files

- [app.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/desktop_mnemo/app.py)
- связанные `desktop_mnemo/*`

### WEB and canonical source files to mine

- [15_PneumoScheme_Mnemo.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/pages/15_PneumoScheme_Mnemo.py)
- [scheme_integrity.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/scheme_integrity.py)
- `ui_svg_*` helpers
- [validation_cockpit_web.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/validation_cockpit_web.py)

### Готовый промт

```text
Работай только в lane "Desktop Mnemo".

Цель: развивать Desktop Mnemo как основное окно схемы и мнемосхемы. Нужно постепенно перенести туда WEB-side mnemo/scheme functionality и оставить WEB только как legacy source поведения.

Можно менять только:
- pneumo_solver_ui/desktop_mnemo/*
- mnemo-specific tests

Можно читать как источник поведения:
- pneumo_solver_ui/pages/15_PneumoScheme_Mnemo.py
- pneumo_solver_ui/scheme_integrity.py
- pneumo_solver_ui/ui_svg_* helpers
- pneumo_solver_ui/validation_cockpit_web.py

Нельзя менять:
- desktop_shell/*
- desktop_input_editor.py
- qt_compare_viewer.py
- desktop_animator
- WEB pages

Правила:
- не переносить mnemo logic в shell
- не дублировать animator и compare viewer
- удерживать отдельное специализированное окно

Сделай следующий локальный шаг по Desktop Mnemo и проверь только mnemo-relevant tests.
```

## Chat G: Desktop Animator

### Цель

Сделать Desktop Animator основным GUI анимации и инженерного просмотра результатов, absorbing animation cockpit и related result UX из WEB.

### Target files

- [app.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/desktop_animator/app.py)
- связанные `desktop_animator/*`

### WEB and canonical source files to mine

- [animation_cockpit_web.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/animation_cockpit_web.py)
- [11_AnimationCockpit_Web.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/pages/11_AnimationCockpit_Web.py)
- [anim_export_meta.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/anim_export_meta.py)
- [ring_visuals.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/ring_visuals.py)
- `ui_animation_results_*`

### Готовый промт

```text
Работай только в lane "Desktop Animator".

Цель: развивать Desktop Animator как основное окно анимации и инженерного просмотра. Нужно перенести туда animation cockpit, ring/cockpit overlays и другие related UX, которые ещё остались в WEB.

Можно менять только:
- pneumo_solver_ui/desktop_animator/*
- animator-specific tests

Можно читать как источник поведения:
- pneumo_solver_ui/animation_cockpit_web.py
- pneumo_solver_ui/pages/11_AnimationCockpit_Web.py
- pneumo_solver_ui/anim_export_meta.py
- pneumo_solver_ui/ring_visuals.py
- pneumo_solver_ui/ui_animation_results_*

Нельзя менять:
- desktop_shell/*
- qt_compare_viewer.py
- desktop_mnemo/*
- WEB pages

Правила:
- не переноси animator logic в shell
- treat animator as specialized standalone app
- работай через маленькие panels/runtime helpers, а не через один giant file

Сделай следующий шаг по animator и проверь только animator-relevant tests.
```

## Chat H: Оптимизатор Со Всеми Настройками

### Цель

Сделать полноценный desktop optimizer center со всеми настройками, runtime, distributed mode, history, results, handoff, packaging и operator workflow.

### Target files

- новые GUI файлы:
  - `pneumo_solver_ui/tools/desktop_optimizer_center.py`
  - `pneumo_solver_ui/desktop_optimizer_model.py`
  - `pneumo_solver_ui/desktop_optimizer_runtime.py`
  - `pneumo_solver_ui/desktop_optimizer_panels.py`
  - при необходимости `pneumo_solver_ui/desktop_optimizer_tabs/*`

### WEB and canonical source files to mine

- [03_Optimization.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/pages/03_Optimization.py)
- [04_DistributedOptimization.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/pages/04_DistributedOptimization.py)
- [04_DistributedOptimization_R58.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/pages/04_DistributedOptimization_R58.py)
- [30_Optimization.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/pages/30_Optimization.py)
- все `optimization_*.py`
- [opt_stage_runner_v1.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/opt_stage_runner_v1.py)
- [opt_worker_v3_margins_energy.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/opt_worker_v3_margins_energy.py)
- [ui_optimization_page_shell_helpers.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/ui_optimization_page_shell_helpers.py)

### Готовый промт

```text
Работай только в lane "Оптимизатор Со Всеми Настройками".

Цель: перенести optimization workflow из WEB в полноценный desktop GUI center. Нужны: scope, search space, objectives, stage policy, distributed settings, runtime launch, live progress, history, finished jobs, handoff, packaging, objective contract и operator-oriented UX.

Можно менять только:
- новые desktop_optimizer_* модули
- optimization-specific desktop tests
- shell adapter/catalog only if adding new optimizer window

Можно читать как источник поведения:
- pneumo_solver_ui/pages/03_Optimization.py
- pneumo_solver_ui/pages/04_DistributedOptimization.py
- pneumo_solver_ui/pages/04_DistributedOptimization_R58.py
- pneumo_solver_ui/pages/30_Optimization.py
- все optimization_*.py
- pneumo_solver_ui/opt_stage_runner_v1.py
- pneumo_solver_ui/opt_worker_v3_margins_energy.py
- pneumo_solver_ui/ui_optimization_page_shell_helpers.py

Нельзя менять:
- pneumo_ui_app.py
- desktop_input_editor.py
- compare viewer
- desktop animator
- desktop mnemo
- WEB pages как target

Правила:
- optimization GUI дели по панелям и вкладкам
- не тащи сюда WEB view code напрямую, переносить нужно поведение и shared runtime logic
- избегай нового гигантского single-file optimizer window

Сделай первый или следующий логичный шаг по desktop optimizer center и сохрани модульность.
```

## Chat I: Диагностика И Send Bundle Center

### Цель

Собрать единый desktop GUI для диагностики, сборки bundle, inspect, health, send workflow.

### Target files

- [run_full_diagnostics_gui.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/tools/run_full_diagnostics_gui.py)
- [send_results_gui.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/tools/send_results_gui.py)
- при необходимости новые:
  - `pneumo_solver_ui/tools/desktop_diagnostics_center.py`
  - `pneumo_solver_ui/desktop_diagnostics_model.py`

### WEB and canonical source files to mine

- [99_Diagnostics.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/pages/99_Diagnostics.py)
- [98_BuildBundle_ZIP.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/pages/98_BuildBundle_ZIP.py)
- [98_SendBundle.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/pages/98_SendBundle.py)
- [diagnostics_entrypoint.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/diagnostics_entrypoint.py)
- [diagnostics_unified.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/diagnostics_unified.py)
- [send_bundle.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/send_bundle.py)
- [send_bundle_contract.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/tools/send_bundle_contract.py)

### Готовый промт

```text
Работай только в lane "Диагностика И Send Bundle Center".

Цель: сделать единый desktop GUI diagnostics/send center без WEB. Пользователь должен уметь запускать полную диагностику, собирать bundle, смотреть summary, inspect, health и отправку результатов из desktop flow.

Можно менять только:
- pneumo_solver_ui/tools/run_full_diagnostics_gui.py
- pneumo_solver_ui/tools/send_results_gui.py
- новые desktop_diagnostics_* модули
- diagnostics/send desktop tests

Можно читать как источник поведения:
- pneumo_solver_ui/pages/99_Diagnostics.py
- pneumo_solver_ui/pages/98_BuildBundle_ZIP.py
- pneumo_solver_ui/pages/98_SendBundle.py
- pneumo_solver_ui/diagnostics_entrypoint.py
- pneumo_solver_ui/diagnostics_unified.py
- pneumo_solver_ui/send_bundle.py
- pneumo_solver_ui/tools/send_bundle_contract.py

Нельзя менять:
- test_center_gui.py кроме явной интеграции
- desktop_input_editor.py
- compare viewer
- WEB pages как target

Правила:
- не дублируй WEB pages один в один, строй нормальный desktop operator flow
- выноси summary/runtime helpers в отдельные модули при росте сложности
- сохрани hosted/standalone compatibility

Сделай следующий шаг по diagnostics/send desktop center и прогони targeted tests.
```

## Chat J: Центр Тестов, Валидации И Результатов

### Цель

Собрать desktop центр тестового workflow: запуск тестов, validation overview, results browsing, ссылки на compare/animator/diagnostics.

### Target files

- [test_center_gui.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/tools/test_center_gui.py)
- новые при необходимости:
  - `pneumo_solver_ui/tools/desktop_results_center.py`
  - `pneumo_solver_ui/desktop_results_model.py`

### WEB and canonical source files to mine

- [08_ValidationCockpit_Web.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/pages/08_ValidationCockpit_Web.py)
- [09_Validation_Web.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/pages/09_Validation_Web.py)
- [12_ResultsViewer.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/pages/12_ResultsViewer.py)
- [validation_cockpit_web.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/validation_cockpit_web.py)
- [npz_anim_diagnostics.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/npz_anim_diagnostics.py)
- `ui_results_*`

### Готовый промт

```text
Работай только в lane "Центр Тестов, Валидации И Результатов".

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
- desktop_animator/*
- send_results_gui.py кроме интеграции
- WEB pages как target

Правила:
- test center должен быть orchestration window, а не копией compare viewer или animator
- глубокую графику оставляй compare viewer и animator
- удерживай понятный operator flow

Сделай следующий шаг по desktop test/validation/results center и проверь targeted tests.
```

## Chat K: Геометрия, Каталоги И Справочники

### Цель

Сделать отдельный desktop reference-workspace для геометрии, пружин, цилиндров и параметрических справочников.

### Target files

- новые:
  - `pneumo_solver_ui/tools/desktop_geometry_reference_center.py`
  - `pneumo_solver_ui/desktop_geometry_reference_model.py`
- плюс возможно:
  - [spring_geometry_ui.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/spring_geometry_ui.py)
  - [spring_table.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/spring_table.py)

### WEB and canonical source files to mine

- [10_SuspensionGeometry.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/pages/10_SuspensionGeometry.py)
- [13_CamozziCylindersCatalog.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/pages/13_CamozziCylindersCatalog.py)
- [14_SpringsGeometry_CoilBind.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/pages/14_SpringsGeometry_CoilBind.py)
- [20_ParamsGuide.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/pages/20_ParamsGuide.py)
- [spring_geometry_ui.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/spring_geometry_ui.py)
- [spring_table.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/spring_table.py)

### Готовый промт

```text
Работай только в lane "Геометрия, Каталоги И Справочники".

Цель: перенести geometry/catalog/reference workflow из WEB в отдельный desktop workspace. Нужны: просмотр геометрии подвески, справочник цилиндров, геометрия пружин, coil bind, parameter guides.

Можно менять только:
- новые desktop_geometry_reference_* модули
- pneumo_solver_ui/spring_geometry_ui.py
- pneumo_solver_ui/spring_table.py
- related tests

Можно читать как источник поведения:
- pneumo_solver_ui/pages/10_SuspensionGeometry.py
- pneumo_solver_ui/pages/13_CamozziCylindersCatalog.py
- pneumo_solver_ui/pages/14_SpringsGeometry_CoilBind.py
- pneumo_solver_ui/pages/20_ParamsGuide.py
- pneumo_solver_ui/spring_geometry_ui.py
- pneumo_solver_ui/spring_table.py

Нельзя менять:
- desktop_input_editor.py кроме интеграции
- optimizer GUI
- WEB pages как target

Правила:
- это справочно-инженерный desktop workspace, не тащи его внутрь input editor
- переносить нужно рабочий смысл, а не WEB layout

Сделай первый или следующий шаг по desktop geometry/reference center.
```

## Chat L: Инженерный Анализ, Калибровка И Influence

### Цель

Перенести в desktop GUI расширенные инженерные surfaces: calibration NPZ, design advisor, system influence, subsystem influence, uncertainty, param influence.

### Target files

- новые:
  - `pneumo_solver_ui/tools/desktop_engineering_analysis_center.py`
  - `pneumo_solver_ui/desktop_engineering_analysis_model.py`
  - `pneumo_solver_ui/desktop_engineering_analysis_runtime.py`

### WEB and canonical source files to mine

- [02_Calibration_NPZ.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/pages/02_Calibration_NPZ.py)
- [03_Design_Advisor.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/pages/03_Design_Advisor.py)
- [03_DesignAdvisor.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/pages/03_DesignAdvisor.py)
- [03_SystemInfluence.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/pages/03_SystemInfluence.py)
- [04_SubsystemsInfluence.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/pages/04_SubsystemsInfluence.py)
- [04_Uncertainty.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/pages/04_Uncertainty.py)
- [05_ParamInfluence.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/pages/05_ParamInfluence.py)
- [05_ParamsInfluence.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/pages/05_ParamsInfluence.py)
- [compare_influence.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/compare_influence.py)
- [compare_influence_time.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/compare_influence_time.py)

### Готовый промт

```text
Работай только в lane "Инженерный Анализ, Калибровка И Influence".

Цель: перенести расширенные инженерные WEB surfaces в отдельный desktop analysis center. Это отдельный профессиональный модуль для calibration/design/influence/uncertainty, а не часть main shell logic.

Можно менять только:
- новые desktop_engineering_analysis_* модули
- narrowly related helper modules
- analysis-specific tests

Можно читать как источник поведения:
- pages/02_Calibration_NPZ.py
- pages/03_Design_Advisor.py
- pages/03_DesignAdvisor.py
- pages/03_SystemInfluence.py
- pages/04_SubsystemsInfluence.py
- pages/04_Uncertainty.py
- pages/05_ParamInfluence.py
- pages/05_ParamsInfluence.py
- compare_influence.py
- compare_influence_time.py

Нельзя менять:
- optimizer center
- desktop_input_editor
- WEB pages как target

Правила:
- делай отдельное инженерное окно, а не прячь всё это в optimizer или test center
- переносить нужно функциональность и сценарии работы, а не Streamlit layout

Сделай первый или следующий шаг по desktop engineering analysis center.
```

## Что пользователь ещё не назвал, но это тоже надо перенести

- `Диагностика и send bundle`
- `Центр тестов, валидации и результатов`
- `Геометрия, каталоги и справочники`
- `Инженерный анализ, калибровка и influence`

Именно эти блоки сейчас часто забываются при разговоре о миграции, но без них WEB всё равно останется живым.

## Рекомендуемый порядок запуска чатов

1. Chat A — Главное Окно Приложения
2. Chat B — Ввод Исходных Данных
3. Chat C — Настройка Расчёта
4. Chat D — Редактор И Генератор Сценариев Колец
5. Chat H — Оптимизатор Со Всеми Настройками
6. Chat J — Центр Тестов, Валидации И Результатов
7. Chat I — Диагностика И Send Bundle Center
8. Chat E — Compare Viewer
9. Chat G — Desktop Animator
10. Chat F — Desktop Mnemo
11. Chat K — Геометрия, Каталоги И Справочники
12. Chat L — Инженерный Анализ, Калибровка И Influence

## Короткая формула миграции

- главное окно собирает приложение;
- ввод исходных данных и настройка расчёта становятся основным входом;
- сценарии колец получают отдельный нормальный editor;
- optimizer получает свой desktop center;
- compare, animator и mnemo остаются специализированными окнами;
- тесты, валидация, результаты, диагностика и bundle уходят в desktop workflow;
- WEB перестаёт быть местом развития и остаётся только временным наследием до полного вывода из эксплуатации.
