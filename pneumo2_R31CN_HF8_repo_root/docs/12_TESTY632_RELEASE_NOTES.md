# Testy632 release notes (over UNIFIED_v6_32_WINSAFE)

Дата сборки: 2026-01-30

## Критические фиксы

1) **send_results_gui.py**
- добавлен `import sys` (исправляет краш при записи в `sys.stderr` в блоке `except`).
- аварийные логи пишутся в **актуальный** log_dir (учитывает `PNEUMO_LOG_DIR`).

2) **validate_send_bundle.py**
- добавлен `import os` (исправляет краш при чтении `PNEUMO_RELEASE`).

3) **test_center_gui.py**
- исправлен заголовок окна (теперь корректно показывает релиз).

## Надёжность и полнота логирования

1) **Строгий JSONL `schema=ui` (loglint strict)**
- `pneumo_solver_ui/diag/eventlog.py`
- `pneumo_solver_ui/pneumo_ui_app.py`

2) **JSON-safe сериализация**
- добавлен модуль `pneumo_solver_ui/diag/json_safe.py`:
  - рекурсивно приводит значения к JSON-совместимым
  - заменяет NaN/Inf на `null`
  - использует `allow_nan=False`

3) **Сессионные директории**
- UI выбирает `LOG_DIR/WORKSPACE_DIR` по env (`PNEUMO_LOG_DIR/PNEUMO_WORKSPACE_DIR/PNEUMO_SESSION_DIR`).

## Патчи и диффы
См. `patches/Testy632_patch_from_UNIFIED_v6_32.patch` и `patches/Testy632_changed_files.txt`.
