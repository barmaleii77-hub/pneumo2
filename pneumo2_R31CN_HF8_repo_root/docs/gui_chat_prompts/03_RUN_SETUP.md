# Chat Prompt: Настройка Расчёта

## Контекст

Это отдельный GUI-контур для настройки режимов запуска. Пользователь должен видеть не только физические параметры, но и понятную конфигурацию самого расчёта.

## Цель

Выделить и развить понятный desktop GUI для настройки расчёта: режим запуска, dt, длительность, baseline/detail/full, cache, export, auto-check, запись логов, runtime policy.

## Можно менять

- [desktop_input_editor.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/tools/desktop_input_editor.py)
- [desktop_single_run.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/tools/desktop_single_run.py)
- новые файлы рядом с lane:
  - `pneumo_solver_ui/tools/desktop_run_setup_center.py`
  - `pneumo_solver_ui/desktop_run_setup_model.py`
  - `pneumo_solver_ui/desktop_run_setup_runtime.py`

## Можно читать как источник поведения

- [pneumo_ui_app.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/pneumo_ui_app.py)
- [test_center_gui.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/tools/test_center_gui.py)
- [run_full_diagnostics_gui.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/tools/run_full_diagnostics_gui.py)
- [ui_results_runtime_helpers.py](C:/Users/Admin/Documents/GitHub/pneumo2/pneumo2_R31CN_HF8_repo_root/pneumo_solver_ui/ui_results_runtime_helpers.py)

## Нельзя менять

- shell core
- ring editor
- optimizer GUI
- compare viewer
- desktop animator
- desktop mnemo
- WEB pages

## Правила

- Не смешивай физические параметры и runtime-настройки в один бесформенный экран.
- Если логика растёт, вынеси её в отдельный run setup module.
- Не дублируй `test_center_gui`, а выделяй понятный pre-run configuration workflow.

## Готовый промт

```text
Работай только в lane "Настройка Расчёта".

Контекст: пользователь должен настраивать не только физические параметры, но и сам режим расчёта в отдельном desktop GUI.

Цель: сделать удобный desktop run setup для режима запуска, dt, длительности, baseline/detail/full run, export, cache, auto-check и runtime policy.

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
