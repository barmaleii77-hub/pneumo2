# Autonomous Testing Center (GUI)

GUI: `pneumo_solver_ui/tools/test_center_gui.py`

Назначение:
- автономно запускать разные наборы тестов и диагностик
- собирать логи в отдельный run‑каталог
- при необходимости сразу собирать send‑bundle

## Запуск
На Windows: `python -m pneumo_solver_ui.tools.test_center_gui` (из корня проекта).

## Что уже умеет
См. список шагов в окне:
- запуск autotest (`run_autotest.py`)
- диагностики и отчёты
- сборка send‑bundle

## Улучшения Testy639
- заголовок окна теперь корректно показывает релиз (`UNIFIED_v6_...` из VERSION.txt/
  PNEUMO_RELEASE)

