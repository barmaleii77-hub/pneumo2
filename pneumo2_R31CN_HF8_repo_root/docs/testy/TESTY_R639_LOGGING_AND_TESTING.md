# Testy R639 — Архитектура логирования и автономного тестирования

Этот документ описывает **как устроены тесты, диагностика и сбор send-bundle ZIP**.

## 1) Сессионная модель (run/session aware)

Основная идея: **всё ценное пишем в каталог сессии**, чтобы потом 100% попало в ZIP.

### 1.1 Как создаётся сессия

- `pneumo_solver_ui/tools/launch_ui.py` генерирует `run_id` (вида `UI_YYYYMMDD_HHMMSS_pidXXXX`).
- Создаёт каталог:
  - `runs/ui_sessions/<run_id>/logs`
  - `runs/ui_sessions/<run_id>/workspace`
- Пробрасывает пути в окружение:
  - `PNEUMO_SESSION_DIR`
  - `PNEUMO_LOG_DIR`
  - `PNEUMO_WORKSPACE_DIR`
  - `PNEUMO_RUN_ID`
  - `PNEUMO_RELEASE`

### 1.2 Почему это важно

- UI/Streamlit может перезапускаться/перерисовываться; мы хотим иметь **одну** точку правды — каталог сессии.
- После закрытия UI watchdog собирает ZIP и прикладывает все артефакты.

## 2) Логи UI: строгий JSONL

### 2.1 Ключевые файлы

В `PNEUMO_LOG_DIR`:

- `python_root.log` — корневой логгер Python (включая Streamlit / зависимости), **rotating**
- `events.jsonl` — events от bootstrap/crash_guard (строгий JSONL)
- `metrics_<session>.jsonl` — события UI конкретной Streamlit-сессии
- `metrics_combined.jsonl` — объединённый поток событий UI
- `ui_<session>.log`, `ui_combined.log` — более "человеческие" лог-файлы

### 2.2 Минимальная схема события (loglint: schema=ui)

Обязательные поля:

- `ts` — timestamp (ISO-like)
- `event` — название события (строка)
- `release` — релиз приложения
- `session_id` — id сессии (строка)
- `pid` — PID процесса

Дополнительно в режиме `--strict`:

- `schema` = `ui`
- `schema_version` = `1.0.0`
- `event_id` — UUID hex
- `seq` — монотонный счётчик событий
- `trace_id` — общий идентификатор трассы/сессии

### 2.3 Почему strict JSON

Мы используем `pneumo_solver_ui/diag/json_safe.py`, который:

- сериализует в JSON **без NaN/Inf** (иначе JSON формально невалиден)
- приводит сложные типы к JSON-friendly виду (`Path`, `datetime`, `numpy`-типы и т.п.)

## 3) make_send_bundle: сбор ZIP

`pneumo_solver_ui/tools/make_send_bundle.py` — центральная точка упаковки.

### 3.1 Что включается

- `bundle/meta.json` — мета (release/run_id/env)
- `triage/*` — triage отчёты
- `validation/*` — отчёт валидатора ZIP
- `dashboard/*` — HTML-дашборд (если удалось)
- `selfcheck/*` — результат автономной самопроверки (см. ниже)
- `logs/*` — все логи (PNEUMO_LOG_DIR + запасные)
- `reports/*` — loglint/logstats/sqlite_metrics и др.
- `runs/*` — автотесты/диагностика (если запускались)

### 3.2 Точки контроля качества

- `loglint --schema ui --strict` на каталогах логов
- `logstats` (гистограммы событий, spans)
- `log2sqlite` (агрегация метрик в SQLite)
- `validate_send_bundle.py` (проверка структуры ZIP)

## 4) Selfcheck Suite

Новый компонент: `pneumo_solver_ui/tools/selfcheck_suite.py`.

Запускается:

- автоматически из `make_send_bundle` (best‑effort)
- вручную:
  - `python -m pneumo_solver_ui.tools.selfcheck_suite --level standard`

Что делает (standard):

1. `compileall` по `pneumo_solver_ui` (ловит синтаксические ошибки)
2. `import_smoke` (ловит NameError/ImportError на ключевых модулях)
3. `preflight_gate.py` (быстрые инварианты)

Результаты:

- `selfcheck/selfcheck_report.json`
- `selfcheck/selfcheck_report.md`
- `selfcheck/steps/.../stdout.txt|stderr.txt`

## 5) Health Report

`pneumo_solver_ui/tools/health_report.py` формирует **сводку** по ZIP:

- validation_ok
- selfcheck_ok
- loglint_strict errors
- triage severity

Выход:

- sidecar: `send_bundles/latest_health_report.(json|md)`
- внутри ZIP: `health/health_report.(json|md)`

## 6) GUI: отправка результатов и автономные тесты

### 6.1 Send Results GUI (1 кнопка)

`pneumo_solver_ui/tools/send_results_gui.py`:

- автоматически запускает сбор ZIP (в фоне)
- в UI остаётся **одна** кнопка: "Скопировать ZIP в буфер"

### 6.2 Autonomous Testing Center

`pneumo_solver_ui/tools/test_center_gui.py`:

- запуск `run_autotest.py`
- запуск `run_full_diagnostics.py`
- preflight gate
- make_send_bundle

## 7) Где смотреть что именно сломалось

Обычно хватает:

1. `health/health_report.md`
2. `validation/validation_report.json`
3. `reports/*/loglint_strict/loglint_report.md`
4. `triage/triage_report.md`
5. `selfcheck/selfcheck_report.md`

