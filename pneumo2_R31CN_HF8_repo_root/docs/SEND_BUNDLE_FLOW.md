# Send‑bundle: сбор, валидация, копирование ZIP

## Цель
Сделать так, чтобы **после закрытия приложения** получался один ZIP, который можно отправить в чат, и чтобы в этом ZIP были:
- все нужные логи и артефакты
- отчёты о качестве логов (loglint/logstats)
- снимок окружения
- мини‑дашборд

## Как работает (в общих чертах)
1) Запуск UI идёт через `START_PNEUMO_APP.py/pyw` (или `tools/launch_ui.py`).
2) Launcher создаёт папку сессии `runs/ui_sessions/UI_YYYY...` и выставляет env:
   - `PNEUMO_SESSION_DIR`
   - `PNEUMO_LOG_DIR` → `<session>/logs`
   - `PNEUMO_WORKSPACE_DIR` → `<session>/workspace`
   - `PNEUMO_RUN_ID` / `PNEUMO_TRACE_ID`
3) UI пишет логи/артефакты в эти папки.
4) После завершения UI launcher запускает `pneumo_solver_ui/tools/make_send_bundle.py`.
   Скрипт:
   - собирает данные (логи, workspace, autotest_runs, diagnostics, build_info)
   - делает loglint/logstats/sqlite‑метрики
   - кладёт всё в zip
   - валидирует zip `validate_send_bundle.py`
5) Открывается GUI `pneumo_solver_ui/tools/send_results_gui.py`.
   В интерфейсе **одна кнопка**: "Copy ZIP to Clipboard".

## Где лежат zip‑файлы
`send_bundles/` в корне проекта.

## Как контролировать размер
Переменная окружения:
- `PNEUMO_SEND_BUNDLE_MAX_FILE_MB` — лимит на размер включаемых файлов.

