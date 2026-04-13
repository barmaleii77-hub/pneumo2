# Chat Prompt: Редактор И Генератор Сценариев Колец

## Контекст

Ring workflow больше не должен жить в WEB. Нужен отдельный desktop editor для сегментов, дорог, событий, diagnostics и генерации артефактов.

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
- UI дели на панели: segments, road, motion, events, diagnostics, export.

## Готовый промт

```text
Работай только в lane "Редактор И Генератор Сценариев Колец".

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

Сделай первый или следующий логичный шаг по desktop ring editor и сохрани модульность.
```
