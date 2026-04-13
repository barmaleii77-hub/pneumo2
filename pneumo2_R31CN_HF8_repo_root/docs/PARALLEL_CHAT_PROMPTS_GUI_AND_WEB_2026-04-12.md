# Parallel Chat Prompts: GUI And WEB

Дата: 2026-04-12

Этот документ нужен для параллельной работы по проекту в нескольких чатах без конфликтов по файлам и зонам ответственности.

## Общие правила для всех чатов

- Не трогать чужие lane-файлы.
- Не делать массовых рефакторингов через весь проект.
- Не трогать `Desktop Mnemo`, если чат не назначен именно на него.
- Не дублировать `desktop_animator`, `qt_compare_viewer` и `desktop_mnemo` внутри shell или других GUI.
- Если нужен новый shared seam, сначала выносить его в отдельный модуль рядом со своим lane, а не в случайный общий файл.
- Если нужно добавить новый GUI-модуль в shell, менять только `adapter/spec/catalog`, не раздувая `main_window.py`.
- WEB сейчас держим в режиме сопровождения: исправления и локальные улучшения только внутри назначенного lane, без новых монолитов.

## Shared Danger Zone

Эти файлы нельзя менять параллельно разными чатами без явной координации:

- `C:\Users\Admin\Documents\GitHub\pneumo2\pneumo2_R31CN_HF8_repo_root\pneumo_solver_ui\pneumo_ui_app.py`
- `C:\Users\Admin\Documents\GitHub\pneumo2\pneumo2_R31CN_HF8_repo_root\pneumo_solver_ui\page_registry.py`
- `C:\Users\Admin\Documents\GitHub\pneumo2\pneumo2_R31CN_HF8_repo_root\pneumo_solver_ui\desktop_shell\registry.py`
- `C:\Users\Admin\Documents\GitHub\pneumo2\pneumo2_R31CN_HF8_repo_root\pneumo_solver_ui\desktop_shell\launcher_catalog.py`
- `C:\Users\Admin\Documents\GitHub\pneumo2\pneumo2_R31CN_HF8_repo_root\pneumo_solver_ui\desktop_shell\contracts.py`
- `C:\Users\Admin\Documents\GitHub\pneumo2\pneumo2_R31CN_HF8_repo_root\pneumo_solver_ui\desktop_input_model.py`
- `C:\Users\Admin\Documents\GitHub\pneumo2\pneumo2_R31CN_HF8_repo_root\pneumo_solver_ui\qt_compare_viewer.py`
- `C:\Users\Admin\Documents\GitHub\pneumo2\pneumo2_R31CN_HF8_repo_root\pneumo_solver_ui\desktop_animator\app.py`
- `C:\Users\Admin\Documents\GitHub\pneumo2\pneumo2_R31CN_HF8_repo_root\pneumo_solver_ui\desktop_mnemo\app.py`

## Chat 1: Desktop Shell Core

### Назначение

Классическое главное окно Windows-приложения: верхнее меню, toolbar, home, workspace, навигация, lifecycle hosted-вкладок.

### Файлы ownership

- `C:\Users\Admin\Documents\GitHub\pneumo2\pneumo2_R31CN_HF8_repo_root\pneumo_solver_ui\desktop_shell\main_window.py`
- `C:\Users\Admin\Documents\GitHub\pneumo2\pneumo2_R31CN_HF8_repo_root\pneumo_solver_ui\desktop_shell\workspace.py`
- `C:\Users\Admin\Documents\GitHub\pneumo2\pneumo2_R31CN_HF8_repo_root\pneumo_solver_ui\desktop_shell\menu_builder.py`
- `C:\Users\Admin\Documents\GitHub\pneumo2\pneumo2_R31CN_HF8_repo_root\pneumo_solver_ui\desktop_shell\toolbar.py`
- `C:\Users\Admin\Documents\GitHub\pneumo2\pneumo2_R31CN_HF8_repo_root\pneumo_solver_ui\desktop_shell\home_view.py`
- `C:\Users\Admin\Documents\GitHub\pneumo2\pneumo2_R31CN_HF8_repo_root\pneumo_solver_ui\desktop_shell\navigation.py`
- `C:\Users\Admin\Documents\GitHub\pneumo2\pneumo2_R31CN_HF8_repo_root\pneumo_solver_ui\desktop_shell\lifecycle.py`
- `C:\Users\Admin\Documents\GitHub\pneumo2\pneumo2_R31CN_HF8_repo_root\pneumo_solver_ui\tools\desktop_main_shell.py`

### Не трогать

- hosted GUI-модули
- adapters/catalog
- `desktop_animator`
- `qt_compare_viewer`
- `desktop_mnemo`

### Готовый промт

```text
Работай только в lane Desktop Shell Core.

Цель: развивать классическое главное окно Windows-приложения без превращения его в новый монолит. Нужен аккуратный modular shell: верхнее меню, toolbar, home, workspace, навигация по вкладкам, lifecycle встроенных окон.

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

Нельзя менять:
- hosted GUI modules
- desktop_shell/registry.py
- desktop_shell/launcher_catalog.py
- desktop_shell/contracts.py
- desktop_animator
- qt_compare_viewer
- desktop_mnemo
- WEB UI

Правила:
- не дублируй логику конкретных окон внутри shell
- новые улучшения делай через отдельные маленькие модули, а не раздувая main_window.py
- если нужен новый seam, выноси его рядом с текущим lane
- сохраняй классический Windows UX
- обязательно проверь targeted tests по shell

Сделай следующий логичный шаг по shell core, реализуй его до конца, прогони проверки и кратко опиши результат.
```

## Chat 2: Desktop Shell Catalog And Adapters

### Назначение

Каталог desktop-инструментов, hosted/external wiring, adapter-слой.

### Файлы ownership

- `C:\Users\Admin\Documents\GitHub\pneumo2\pneumo2_R31CN_HF8_repo_root\pneumo_solver_ui\desktop_shell\registry.py`
- `C:\Users\Admin\Documents\GitHub\pneumo2\pneumo2_R31CN_HF8_repo_root\pneumo_solver_ui\desktop_shell\launcher_catalog.py`
- `C:\Users\Admin\Documents\GitHub\pneumo2\pneumo2_R31CN_HF8_repo_root\pneumo_solver_ui\desktop_shell\contracts.py`
- `C:\Users\Admin\Documents\GitHub\pneumo2\pneumo2_R31CN_HF8_repo_root\pneumo_solver_ui\desktop_shell\adapters\`

### Не трогать

- shell layout
- feature-логику hosted окон

### Готовый промт

```text
Работай только в lane Desktop Shell Catalog And Adapters.

Цель: удерживать единый каталог GUI-модулей и аккуратный adapter-layer для shell, чтобы разные окна можно было подключать локально и без копипасты.

Можно менять только:
- pneumo_solver_ui/desktop_shell/registry.py
- pneumo_solver_ui/desktop_shell/launcher_catalog.py
- pneumo_solver_ui/desktop_shell/contracts.py
- pneumo_solver_ui/desktop_shell/adapters/*
- tests/test_desktop_main_shell_contract.py
- tests/test_desktop_control_center_contract.py

Нельзя менять:
- desktop_shell/main_window.py
- desktop_shell/workspace.py
- desktop_input_editor.py
- test_center_gui.py
- run_autotest_gui.py
- run_full_diagnostics_gui.py
- send_results_gui.py
- desktop_animator
- qt_compare_viewer
- desktop_mnemo
- WEB UI

Правила:
- при подключении нового окна меняй adapter/spec/catalog, а не shell core
- не встраивай в shell внешние Qt-окна как фальшивые hosted tabs
- не ломай существующие launchers
- проверяй targeted tests

Сделай следующий архитектурный шаг в adapter/catalog слое и сохрани модульность.
```

## Chat 3: Desktop Launcher Legacy

### Назначение

Отдельный launcher-центр desktop-инструментов вне main shell.

### Файлы ownership

- `C:\Users\Admin\Documents\GitHub\pneumo2\pneumo2_R31CN_HF8_repo_root\pneumo_solver_ui\tools\desktop_control_center.py`
- `C:\Users\Admin\Documents\GitHub\pneumo2\pneumo2_R31CN_HF8_repo_root\START_DESKTOP_CONTROL_CENTER.py`
- `C:\Users\Admin\Documents\GitHub\pneumo2\pneumo2_R31CN_HF8_repo_root\START_DESKTOP_CONTROL_CENTER.pyw`
- `C:\Users\Admin\Documents\GitHub\pneumo2\pneumo2_R31CN_HF8_repo_root\START_DESKTOP_CONTROL_CENTER.cmd`
- `C:\Users\Admin\Documents\GitHub\pneumo2\pneumo2_R31CN_HF8_repo_root\START_DESKTOP_CONTROL_CENTER.vbs`

### Готовый промт

```text
Работай только в lane Desktop Launcher Legacy.

Цель: поддерживать и улучшать отдельный launcher-центр desktop-инструментов, не смешивая его с новым main shell.

Можно менять только:
- pneumo_solver_ui/tools/desktop_control_center.py
- START_DESKTOP_CONTROL_CENTER.py
- START_DESKTOP_CONTROL_CENTER.pyw
- START_DESKTOP_CONTROL_CENTER.cmd
- START_DESKTOP_CONTROL_CENTER.vbs
- tests/test_desktop_control_center_contract.py

Нельзя менять:
- desktop_shell/*
- hosted GUI feature modules
- desktop_animator
- qt_compare_viewer
- desktop_mnemo
- WEB UI

Правила:
- используй общий launcher catalog, не создавай новый список вручную
- не дублируй main shell
- улучшай только launcher UX и устойчивость запуска

Сделай следующий локальный шаг по launcher-центру и проверь контрактные тесты.
```

## Chat 4: Desktop Input Editor

### Назначение

Главный GUI ввода исходных данных и настроек расчёта.

### Файлы ownership

- `C:\Users\Admin\Documents\GitHub\pneumo2\pneumo2_R31CN_HF8_repo_root\pneumo_solver_ui\tools\desktop_input_editor.py`
- `C:\Users\Admin\Documents\GitHub\pneumo2\pneumo2_R31CN_HF8_repo_root\pneumo_solver_ui\desktop_input_model.py`

### Не трогать

- shell core
- WEB optimization
- compare/animator/mnemo

### Готовый промт

```text
Работай только в lane Desktop Input Editor.

Цель: развивать нормальный desktop GUI для ввода исходных данных и настроек расчёта. Это основной GUI-first контур вместо WEB-форм.

Можно менять только:
- pneumo_solver_ui/tools/desktop_input_editor.py
- pneumo_solver_ui/desktop_input_model.py
- tests/test_desktop_input_editor_contract.py
- tests/test_desktop_main_shell_contract.py только если нужен adapter-contract

Нельзя менять:
- desktop_shell/main_window.py
- desktop_shell/workspace.py
- test_center_gui.py
- run_autotest_gui.py
- run_full_diagnostics_gui.py
- send_results_gui.py
- desktop_animator
- qt_compare_viewer
- desktop_mnemo
- WEB UI

Правила:
- не тащи в editor функции animator, compare viewer или mnemo
- не превращай editor в новый монолит: выноси shared helpers в desktop_input_model.py или в маленькие соседние модули
- сохраняй классический desktop UX: секции, пресеты, профили, снимки, quick/detail run
- прогони targeted tests

Сделай следующий полезный шаг именно по input editor как по основному окну ввода данных.
```

## Chat 5: Desktop Test Workflow

### Назначение

Desktop-контур прогонов, autotest, diagnostics и send bundle.

### Файлы ownership

- `C:\Users\Admin\Documents\GitHub\pneumo2\pneumo2_R31CN_HF8_repo_root\pneumo_solver_ui\tools\test_center_gui.py`
- `C:\Users\Admin\Documents\GitHub\pneumo2\pneumo2_R31CN_HF8_repo_root\pneumo_solver_ui\tools\run_autotest_gui.py`
- `C:\Users\Admin\Documents\GitHub\pneumo2\pneumo2_R31CN_HF8_repo_root\pneumo_solver_ui\tools\run_full_diagnostics_gui.py`
- `C:\Users\Admin\Documents\GitHub\pneumo2\pneumo2_R31CN_HF8_repo_root\pneumo_solver_ui\tools\send_results_gui.py`

### Готовый промт

```text
Работай только в lane Desktop Test Workflow.

Цель: развивать desktop-контур тестового workflow без WEB UI: test center, autotest harness, full diagnostics и send results.

Можно менять только:
- pneumo_solver_ui/tools/test_center_gui.py
- pneumo_solver_ui/tools/run_autotest_gui.py
- pneumo_solver_ui/tools/run_full_diagnostics_gui.py
- pneumo_solver_ui/tools/send_results_gui.py
- tests/test_desktop_main_shell_contract.py только если нужен hosted lifecycle contract
- tests/test_desktop_control_center_contract.py только если нужен launcher contract

Нельзя менять:
- desktop_input_editor.py
- desktop_shell/main_window.py
- qt_compare_viewer.py
- desktop_animator
- desktop_mnemo
- WEB diagnostics/send pages

Правила:
- не дублируй compare/animator/mnemo
- улучшай только desktop test flow
- если нужен shared seam, выноси его рядом с этим lane, не в shell core
- учитывай hosted mode inside shell и standalone launch

Сделай следующий полезный шаг по desktop test workflow и проверь targeted tests.
```

## Chat 6: Compare Viewer

### Назначение

Отдельный Qt viewer сравнения NPZ и прогонов.

### Файлы ownership

- `C:\Users\Admin\Documents\GitHub\pneumo2\pneumo2_R31CN_HF8_repo_root\pneumo_solver_ui\qt_compare_viewer.py`

### Готовый промт

```text
Работай только в lane Compare Viewer.

Цель: развивать qt_compare_viewer как отдельное специализированное окно сравнения, не смешивая его с shell и не таща его внутрь других GUI.

Можно менять только:
- pneumo_solver_ui/qt_compare_viewer.py
- compare-specific tests

Нельзя менять:
- desktop_shell/*
- desktop_input_editor.py
- desktop_animator
- desktop_mnemo
- WEB compare pages

Правила:
- treat this as standalone specialized Qt app
- не дублируй shell functionality
- не заходи в WEB compare surfaces

Сделай следующий локальный шаг по compare viewer и проверь только его целевые тесты.
```

## Chat 7: Desktop Animator

### Назначение

Специализированный PySide6 animator.

### Файлы ownership

- `C:\Users\Admin\Documents\GitHub\pneumo2\pneumo2_R31CN_HF8_repo_root\pneumo_solver_ui\desktop_animator\app.py`
- связанные animator-модули внутри `desktop_animator\`

### Готовый промт

```text
Работай только в lane Desktop Animator.

Цель: улучшать desktop animator как отдельный специализированный GUI-модуль.

Можно менять только:
- pneumo_solver_ui/desktop_animator/*
- animator-specific tests

Нельзя менять:
- desktop_shell/*
- desktop_input_editor.py
- qt_compare_viewer.py
- desktop_mnemo
- WEB UI

Правила:
- не переносить animator logic в shell
- не дублировать compare viewer или mnemo
- держать animator standalone, даже если он запускается из shell

Сделай следующий шаг именно по animator и проверь только animator-relevant tests.
```

## Chat 8: Desktop Mnemo

### Назначение

Отдельный GUI мнемосхемы.

### Файлы ownership

- `C:\Users\Admin\Documents\GitHub\pneumo2\pneumo2_R31CN_HF8_repo_root\pneumo_solver_ui\desktop_mnemo\app.py`
- связанные `desktop_mnemo\` модули

### Готовый промт

```text
Работай только в lane Desktop Mnemo.

Цель: развивать Desktop Mnemo как отдельное специализированное окно и не смешивать его с другими GUI.

Можно менять только:
- pneumo_solver_ui/desktop_mnemo/*
- mnemo-specific tests

Нельзя менять:
- desktop_shell/*
- desktop_input_editor.py
- qt_compare_viewer.py
- desktop_animator
- WEB mnemo pages

Правила:
- не переносить mnemo logic в shell или input editor
- не дублировать compare viewer и animator
- улучшать только отдельное окно Mnemo

Сделай следующий локальный шаг по Desktop Mnemo и проверь только mnemo-relevant tests.
```

## Chat 9: WEB Home And Main Heavy App

### Назначение

Главный heavy web entrypoint и базовый run/home UX.

### Файлы ownership

- `C:\Users\Admin\Documents\GitHub\pneumo2\pneumo2_R31CN_HF8_repo_root\pneumo_solver_ui\pneumo_ui_app.py`
- `C:\Users\Admin\Documents\GitHub\pneumo2\pneumo2_R31CN_HF8_repo_root\pneumo_solver_ui\app.py`

### Готовый промт

```text
Работай только в lane WEB Home And Main Heavy App.

Цель: сопровождать главный heavy WEB entrypoint без наращивания нового монолита. Сейчас приоритет низкий: только локальные правки и bridge-кнопки к desktop GUI.

Можно менять только:
- pneumo_solver_ui/pneumo_ui_app.py
- pneumo_solver_ui/app.py
- tests/test_ui_text_no_mojibake_contract.py
- tests/test_home_desktop_gui_launcher_contract.py

Нельзя менять:
- optimization pages
- diagnostics pages
- compare pages
- desktop_shell/*
- desktop_input_editor.py
- desktop_animator
- qt_compare_viewer
- desktop_mnemo

Правила:
- не строить новые крупные web surfaces
- если пользователь не просил иного, ограничиваться bridge-кнопками и локальными UX fixes
- не расползаться в другие web lanes

Сделай только локальный шаг по main WEB home/app и не расширяй WEB сверх необходимости.
```

## Chat 10: WEB Setup And System Pages

### Назначение

Стартовые и системные WEB-страницы.

### Файлы ownership

- `C:\Users\Admin\Documents\GitHub\pneumo2\pneumo2_R31CN_HF8_repo_root\pneumo_solver_ui\pages\00_Preflight.py`
- `C:\Users\Admin\Documents\GitHub\pneumo2\pneumo2_R31CN_HF8_repo_root\pneumo_solver_ui\pages\00_Setup.py`
- `C:\Users\Admin\Documents\GitHub\pneumo2\pneumo2_R31CN_HF8_repo_root\pneumo_solver_ui\pages\01_SchemeIntegrity.py`
- `C:\Users\Admin\Documents\GitHub\pneumo2\pneumo2_R31CN_HF8_repo_root\pneumo_solver_ui\pages\97_Settings.py`
- `C:\Users\Admin\Documents\GitHub\pneumo2\pneumo2_R31CN_HF8_repo_root\pneumo_solver_ui\pages\98_SelfCheck.py`
- `C:\Users\Admin\Documents\GitHub\pneumo2\pneumo2_R31CN_HF8_repo_root\pneumo_solver_ui\pages\99_EnvDiagnostics.py`

### Готовый промт

```text
Работай только в lane WEB Setup And System Pages.

Цель: локально поддерживать стартовые и системные WEB-страницы без захода в основной heavy app и без пересечения с diagnostics lane.

Можно менять только:
- pneumo_solver_ui/pages/00_Preflight.py
- pneumo_solver_ui/pages/00_Setup.py
- pneumo_solver_ui/pages/01_SchemeIntegrity.py
- pneumo_solver_ui/pages/97_Settings.py
- pneumo_solver_ui/pages/98_SelfCheck.py
- pneumo_solver_ui/pages/99_EnvDiagnostics.py
- related targeted tests

Нельзя менять:
- pneumo_ui_app.py
- optimization pages
- diagnostics bundle pages
- desktop GUI

Сделай следующий локальный шаг только по setup/system pages и не лезь в соседние lanes.
```

## Chat 11: WEB Calibration, Design, Influence, Uncertainty

### Назначение

Аналитические web-страницы калибровки и влияний.

### Файлы ownership

- `C:\Users\Admin\Documents\GitHub\pneumo2\pneumo2_R31CN_HF8_repo_root\pneumo_solver_ui\pages\02_Calibration_NPZ.py`
- `C:\Users\Admin\Documents\GitHub\pneumo2\pneumo2_R31CN_HF8_repo_root\pneumo_solver_ui\pages\03_Design_Advisor.py`
- `C:\Users\Admin\Documents\GitHub\pneumo2\pneumo2_R31CN_HF8_repo_root\pneumo_solver_ui\pages\03_DesignAdvisor.py`
- `C:\Users\Admin\Documents\GitHub\pneumo2\pneumo2_R31CN_HF8_repo_root\pneumo_solver_ui\pages\03_SystemInfluence.py`
- `C:\Users\Admin\Documents\GitHub\pneumo2\pneumo2_R31CN_HF8_repo_root\pneumo_solver_ui\pages\04_SubsystemsInfluence.py`
- `C:\Users\Admin\Documents\GitHub\pneumo2\pneumo2_R31CN_HF8_repo_root\pneumo_solver_ui\pages\04_Uncertainty.py`
- `C:\Users\Admin\Documents\GitHub\pneumo2\pneumo2_R31CN_HF8_repo_root\pneumo_solver_ui\pages\05_ParamInfluence.py`
- `C:\Users\Admin\Documents\GitHub\pneumo2\pneumo2_R31CN_HF8_repo_root\pneumo_solver_ui\pages\05_ParamsInfluence.py`

### Готовый промт

```text
Работай только в lane WEB Calibration, Design, Influence, Uncertainty.

Цель: улучшать аналитические web-страницы этой группы локально, без захода в optimization lane и main heavy app.

Можно менять только:
- pages/02_Calibration_NPZ.py
- pages/03_Design_Advisor.py
- pages/03_DesignAdvisor.py
- pages/03_SystemInfluence.py
- pages/04_SubsystemsInfluence.py
- pages/04_Uncertainty.py
- pages/05_ParamInfluence.py
- pages/05_ParamsInfluence.py
- narrowly related shared helpers

Нельзя менять:
- pneumo_ui_app.py
- optimization pages
- compare pages
- desktop GUI

Сделай следующий локальный шаг по этому аналитическому lane и не расползайся по проекту.
```

## Chat 12: WEB Optimization

### Назначение

Optimization UI, distributed optimization, DB surfaces.

### Файлы ownership

- `C:\Users\Admin\Documents\GitHub\pneumo2\pneumo2_R31CN_HF8_repo_root\pneumo_solver_ui\pages\03_Optimization.py`
- `C:\Users\Admin\Documents\GitHub\pneumo2\pneumo2_R31CN_HF8_repo_root\pneumo_solver_ui\pages\03_DistributedOptimizationDB.py`
- `C:\Users\Admin\Documents\GitHub\pneumo2\pneumo2_R31CN_HF8_repo_root\pneumo_solver_ui\pages\04_DistributedOptimization.py`
- `C:\Users\Admin\Documents\GitHub\pneumo2\pneumo2_R31CN_HF8_repo_root\pneumo_solver_ui\pages\04_DistributedOptimization_R58.py`
- `C:\Users\Admin\Documents\GitHub\pneumo2\pneumo2_R31CN_HF8_repo_root\pneumo_solver_ui\pages\04_ExperimentDB_Distributed.py`
- `C:\Users\Admin\Documents\GitHub\pneumo2\pneumo2_R31CN_HF8_repo_root\pneumo_solver_ui\pages\20_DistributedOptimization.py`
- `C:\Users\Admin\Documents\GitHub\pneumo2\pneumo2_R31CN_HF8_repo_root\pneumo_solver_ui\pages\30_Optimization.py`
- `C:\Users\Admin\Documents\GitHub\pneumo2\pneumo2_R31CN_HF8_repo_root\pneumo_solver_ui\pages\31_OptDatabase.py`
- optimization shared modules `optimization_*.py`

### Готовый промт

```text
Работай только в lane WEB Optimization.

Цель: поддерживать и улучшать optimization surfaces, distributed optimization и optimization DB, не заходя в main web home и не трогая desktop GUI.

Можно менять только:
- pneumo_solver_ui/pages/03_Optimization.py
- pneumo_solver_ui/pages/03_DistributedOptimizationDB.py
- pneumo_solver_ui/pages/04_DistributedOptimization.py
- pneumo_solver_ui/pages/04_DistributedOptimization_R58.py
- pneumo_solver_ui/pages/04_ExperimentDB_Distributed.py
- pneumo_solver_ui/pages/20_DistributedOptimization.py
- pneumo_solver_ui/pages/30_Optimization.py
- pneumo_solver_ui/pages/31_OptDatabase.py
- optimization_*.py
- narrowly related optimization tests

Нельзя менять:
- pneumo_ui_app.py
- diagnostics pages
- compare pages
- desktop GUI

Правила:
- не раздувай общий main web app
- держи изменения внутри optimization lane
- если нужен shared seam, делай его optimization-scoped

Сделай следующий локальный шаг по optimization lane и прогони его целевые tests.
```

## Chat 13: WEB Compare, Validation, Results

### Назначение

WEB compare, validation cockpit и results viewers.

### Файлы ownership

- `C:\Users\Admin\Documents\GitHub\pneumo2\pneumo2_R31CN_HF8_repo_root\pneumo_solver_ui\pages\06_CompareNPZ_Web.py`
- `C:\Users\Admin\Documents\GitHub\pneumo2\pneumo2_R31CN_HF8_repo_root\pneumo_solver_ui\pages\08_ValidationCockpit_Web.py`
- `C:\Users\Admin\Documents\GitHub\pneumo2\pneumo2_R31CN_HF8_repo_root\pneumo_solver_ui\pages\09_Validation_Web.py`
- `C:\Users\Admin\Documents\GitHub\pneumo2\pneumo2_R31CN_HF8_repo_root\pneumo_solver_ui\pages\11_AnimationCockpit_Web.py`
- `C:\Users\Admin\Documents\GitHub\pneumo2\pneumo2_R31CN_HF8_repo_root\pneumo_solver_ui\pages\12_ResultsViewer.py`
- `C:\Users\Admin\Documents\GitHub\pneumo2\pneumo2_R31CN_HF8_repo_root\pneumo_solver_ui\pages\20_CompareRuns.py`
- `C:\Users\Admin\Documents\GitHub\pneumo2\pneumo2_R31CN_HF8_repo_root\pneumo_solver_ui\pages\21_CompareRuns_Quick.py`
- `C:\Users\Admin\Documents\GitHub\pneumo2\pneumo2_R31CN_HF8_repo_root\pneumo_solver_ui\pages\21_ExperimentDB.py`

### Готовый промт

```text
Работай только в lane WEB Compare, Validation, Results.

Цель: локально развивать compare/validation/results surfaces в WEB, не заходя в Qt compare viewer и не трогая main heavy app.

Можно менять только:
- compare/validation/results pages
- compare_*.py
- compare_npz_web.py
- validation_cockpit_web.py
- related tests

Нельзя менять:
- qt_compare_viewer.py
- desktop_animator
- pneumo_ui_app.py
- diagnostics pages

Сделай следующий локальный шаг по compare/validation/results lane и не выходи за его границы.
```

## Chat 14: WEB Desktop Bridge Pages

### Назначение

WEB-страницы, которые открывают desktop/Qt windows.

### Файлы ownership

- `C:\Users\Admin\Documents\GitHub\pneumo2\pneumo2_R31CN_HF8_repo_root\pneumo_solver_ui\pages\06_CompareViewer_QT.py`
- `C:\Users\Admin\Documents\GitHub\pneumo2\pneumo2_R31CN_HF8_repo_root\pneumo_solver_ui\pages\07_CompareNPZ_QT.py`
- `C:\Users\Admin\Documents\GitHub\pneumo2\pneumo2_R31CN_HF8_repo_root\pneumo_solver_ui\pages\07_DesktopAnimator.py`
- `C:\Users\Admin\Documents\GitHub\pneumo2\pneumo2_R31CN_HF8_repo_root\pneumo_solver_ui\pages\08_DesktopAnimator.py`
- `C:\Users\Admin\Documents\GitHub\pneumo2\pneumo2_R31CN_HF8_repo_root\pneumo_solver_ui\pages\08_DesktopMnemo.py`
- `C:\Users\Admin\Documents\GitHub\pneumo2\pneumo2_R31CN_HF8_repo_root\pneumo_solver_ui\pages\40_DesktopAnimator.py`

### Готовый промт

```text
Работай только в lane WEB Desktop Bridge Pages.

Цель: поддерживать web bridge-страницы, которые запускают desktop/Qt окна, без изменения самих desktop окон.

Можно менять только:
- WEB desktop bridge pages
- bridge-related tests

Нельзя менять:
- qt_compare_viewer.py
- desktop_animator/*
- desktop_mnemo/*
- pneumo_ui_app.py, если это не явно согласовано

Сделай только локальный шаг по bridge pages и не заходи в сами desktop приложения.
```

## Chat 15: WEB Scheme, Mnemo, Graph

### Назначение

WEB scheme, graph, SVG/mnemo workbench.

### Файлы ownership

- `C:\Users\Admin\Documents\GitHub\pneumo2\pneumo2_R31CN_HF8_repo_root\pneumo_solver_ui\pages\15_PneumoScheme_Mnemo.py`
- `C:\Users\Admin\Documents\GitHub\pneumo2\pneumo2_R31CN_HF8_repo_root\pneumo_solver_ui\pages\16_PneumoScheme_Graph.py`
- `ui_svg_*.py`
- `scheme_integrity.py`
- `svg_autotrace.py`

### Готовый промт

```text
Работай только в lane WEB Scheme, Mnemo, Graph.

Цель: развивать web-side scheme/mnemo/graph surfaces, не заходя в Desktop Mnemo.

Можно менять только:
- pages/15_PneumoScheme_Mnemo.py
- pages/16_PneumoScheme_Graph.py
- ui_svg_*.py
- scheme_integrity.py
- svg_autotrace.py
- related tests

Нельзя менять:
- desktop_mnemo/*
- pneumo_ui_app.py
- other web lanes

Сделай следующий локальный шаг по web scheme/mnemo/graph lane и не пересекайся с desktop mnemo.
```

## Chat 16: WEB Geometry, Catalogs, Guides

### Назначение

WEB-страницы геометрии подвески, каталогов и guides.

### Файлы ownership

- `C:\Users\Admin\Documents\GitHub\pneumo2\pneumo2_R31CN_HF8_repo_root\pneumo_solver_ui\pages\10_SuspensionGeometry.py`
- `C:\Users\Admin\Documents\GitHub\pneumo2\pneumo2_R31CN_HF8_repo_root\pneumo_solver_ui\pages\13_CamozziCylindersCatalog.py`
- `C:\Users\Admin\Documents\GitHub\pneumo2\pneumo2_R31CN_HF8_repo_root\pneumo_solver_ui\pages\14_SpringsGeometry_CoilBind.py`
- `C:\Users\Admin\Documents\GitHub\pneumo2\pneumo2_R31CN_HF8_repo_root\pneumo_solver_ui\pages\20_ParamsGuide.py`

### Готовый промт

```text
Работай только в lane WEB Geometry, Catalogs, Guides.

Цель: улучшать geometry/catalog/guide surfaces в WEB локально и без пересечения с desktop input editor.

Можно менять только:
- pages/10_SuspensionGeometry.py
- pages/13_CamozziCylindersCatalog.py
- pages/14_SpringsGeometry_CoilBind.py
- pages/20_ParamsGuide.py
- related tests

Нельзя менять:
- desktop_input_editor.py
- desktop_input_model.py
- pneumo_ui_app.py
- other web lanes

Сделай следующий локальный шаг по geometry/catalog/guides lane и не заходи в desktop input editor.
```

## Chat 17: WEB Diagnostics, Bundle, Send

### Назначение

WEB-страницы диагностики, bundle и send flows.

### Файлы ownership

- `C:\Users\Admin\Documents\GitHub\pneumo2\pneumo2_R31CN_HF8_repo_root\pneumo_solver_ui\pages\98_BuildBundle_ZIP.py`
- `C:\Users\Admin\Documents\GitHub\pneumo2\pneumo2_R31CN_HF8_repo_root\pneumo_solver_ui\pages\98_SendBundle.py`
- `C:\Users\Admin\Documents\GitHub\pneumo2\pneumo2_R31CN_HF8_repo_root\pneumo_solver_ui\pages\99_Diagnostics.py`
- `C:\Users\Admin\Documents\GitHub\pneumo2\pneumo2_R31CN_HF8_repo_root\pneumo_solver_ui\diagnostics_entrypoint.py`
- `C:\Users\Admin\Documents\GitHub\pneumo2\pneumo2_R31CN_HF8_repo_root\pneumo_solver_ui\send_bundle.py`
- `C:\Users\Admin\Documents\GitHub\pneumo2\pneumo2_R31CN_HF8_repo_root\pneumo_solver_ui\tools\send_bundle_contract.py`

### Готовый промт

```text
Работай только в lane WEB Diagnostics, Bundle, Send.

Цель: поддерживать и улучшать web diagnostics/send bundle flow локально, не заходя в desktop send workflow.

Можно менять только:
- pages/98_BuildBundle_ZIP.py
- pages/98_SendBundle.py
- pages/99_Diagnostics.py
- pneumo_solver_ui/diagnostics_entrypoint.py
- pneumo_solver_ui/send_bundle.py
- pneumo_solver_ui/tools/send_bundle_contract.py
- related tests

Нельзя менять:
- send_results_gui.py
- test_center_gui.py
- run_full_diagnostics_gui.py
- pneumo_ui_app.py

Сделай следующий локальный шаг по diagnostics/send web lane и не пересекайся с desktop test workflow.
```

## Быстрое распределение по чатам

- Chat A: Desktop Shell Core
- Chat B: Desktop Shell Catalog And Adapters
- Chat C: Desktop Input Editor
- Chat D: Desktop Test Workflow
- Chat E: Compare Viewer
- Chat F: Desktop Animator
- Chat G: Desktop Mnemo
- Chat H: WEB Optimization
- Chat I: WEB Compare, Validation, Results
- Chat J: WEB Diagnostics, Bundle, Send
- Chat K: WEB Scheme, Mnemo, Graph
- Chat L: WEB Geometry, Catalogs, Guides

## Что лучше не делать в параллель

- `Desktop Input Editor` и `WEB Geometry` одновременно с правками одних и тех же shared model-файлов.
- `Shell Core` и `Shell Catalog And Adapters` одновременно без координации, если меняется contract layer.
- `WEB Home` и любой другой WEB lane, если нужно лезть в `pneumo_ui_app.py`.
- `Desktop Mnemo` и `WEB Scheme, Mnemo, Graph`, если меняются общие svg/mnemo helpers.

## Рекомендация по порядку

1. GUI-first:
   - Chat A
   - Chat B
   - Chat C
   - Chat D
2. Specialized desktop:
   - Chat E
   - Chat F
   - Chat G
3. WEB support only:
   - Chat H
   - Chat I
   - Chat J
   - Chat K
   - Chat L
