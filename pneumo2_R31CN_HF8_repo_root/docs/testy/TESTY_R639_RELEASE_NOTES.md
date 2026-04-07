# Testy R639 — Release Notes (поверх UNIFIED_v6_39)

## Цели релиза

1. **Автономность**: после закрытия UI автоматически формируется send bundle ZIP на диске.
2. **Надёжность**: диагностика и отчёты best‑effort, не должны ронять приложение.
3. **Максимальное логирование**:
   - единый строгий JSONL (совместимо с `loglint --schema ui --strict`)
   - сохранение stdout/stderr проверок
   - health‑report с агрегацией ключевых сигналов

## Главное, что сделано

### Логи
- UI JSONL (`metrics_*.jsonl`, `metrics_combined.jsonl`) теперь соответствует строгому UI‑schema.
- `events.jsonl` переведён на тот же строгий формат.
- Root‑логгер пишет в session‑каталог (если задан `PNEUMO_LOG_DIR`) и включена ротация.

### Автопроверки
- Добавлен `selfcheck_suite` (compileall + import_smoke + preflight_gate).
- Добавлен `health_report` (validation + loglint(strict) + selfcheck + triage).
- `make_send_bundle` автоматически включает эти отчёты внутрь ZIP.

### Фиксы багов
- `validate_send_bundle.py` — добавлен `import os`.
- `run_autotest_gui.py`, `test_center_gui.py` — исправлен `RELEASE` + корректные заголовки.
- `send_results_gui.py` — добавлен `import sys`, улучшено логирование ошибок в `PNEUMO_LOG_DIR`.
- `run_registry.py` — сигнатура `log_send_bundle_created` совместима с `make_send_bundle` + поддержка доп.полей.

## Изменённые/добавленные файлы

### Изменены
- `pneumo_solver_ui/pneumo_ui_app.py`
- `pneumo_solver_ui/diag/eventlog.py`
- `pneumo_solver_ui/diag/bootstrap.py`
- `pneumo_solver_ui/tools/make_send_bundle.py`
- `pneumo_solver_ui/tools/validate_send_bundle.py`
- `pneumo_solver_ui/tools/run_autotest_gui.py`
- `pneumo_solver_ui/tools/test_center_gui.py`
- `pneumo_solver_ui/tools/send_results_gui.py`
- `pneumo_solver_ui/run_registry.py`

### Добавлены
- `pneumo_solver_ui/tools/selfcheck_suite.py`
- `pneumo_solver_ui/tools/health_report.py`
- `README_TESTY_R639.md`
- `docs/testy/TESTY_R639_RELEASE_NOTES.md`
- `diffs/Testy639_over_UNIFIED_v6_39.diff`
- `patches/Testy639_over_UNIFIED_v6_39.patch`

## Что дальше (коротко)

- Довести до «железобетона» проверку JSONL схемы непосредственно при записи (опционально, режим STRICT_WRITE).
- Расширить selfcheck_suite: версии зависимостей, проверка диска/прав, smoke‑run `make_send_bundle --dry_run`.
- Добавить GUI‑панель прогресса для selfcheck в Test Center.

