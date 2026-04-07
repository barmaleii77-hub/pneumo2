# Лог‑схема UI (строгий JSONL) — что и где

В проекте есть строгая валидация логов `pneumo_solver_ui/tools/loglint.py`.
Она запускается:
- в `pneumo_solver_ui/tools/run_autotest.py` (после прогонов)
- в `pneumo_solver_ui/tools/make_send_bundle.py` (при сборке zip)

Ключевой режим: `--schema ui --strict --check_seq --check_spans`.

## Где лежат логи
- **Основная папка логов сессии** берётся из `PNEUMO_LOG_DIR`.
  - её выставляет лаунчер (`START_PNEUMO_APP.py/pyw`) и тест‑раннер (`run_autotest.py`).
  - если переменная не задана — используется дефолт `pneumo_solver_ui/logs`.

## Какие файлы должны проходить loglint
Любой файл `*.jsonl` в папке логов.

В типичном UI‑запуске:
- `metrics_<session_id>.jsonl`
- `metrics_combined.jsonl`
- `events.jsonl`
- `autoselfcheck.json` (это **не** jsonl, loglint его не трогает)

## Обязательные поля (ui schema)
`loglint.py` для schema `ui` ожидает:

**Required (обычный режим):**
- `ts` — ISO‑timestamp (`datetime.fromisoformat`)
- `event` — строка
- `release` — строка
- `session_id` — строка
- `pid` — int

**Strict mode добавляет:**
- `schema` — строго `"ui"`
- `schema_version` — semver строка (например `"1.2.0"`)
- `event_id` — строка
- `seq` — int (монотонный по `session_id`)
- `trace_id` — строка

## check_seq (монотонность)
При `--check_seq` loglint проверяет, что `seq` **растёт** для каждого `session_id`.
Поэтому:
- `session_id` должен быть уникален для запуска (обычно `UI_YYYYMMDD_HHMMSS_*`)
- генератор событий должен хранить счётчик `seq` на сессию.

## Реализация в этом релизе

### 1) UI‑логгер
`pneumo_solver_ui/pneumo_ui_app.py`:
- `log_event(...)` формирует запись с обязательными полями и пишет её в JSONL.
- `session_id` берётся из `PNEUMO_RUN_ID` (если задан) или генерируется.
- `seq` хранится в `st.session_state["_log_seq"]`.
- сериализация — через `pneumo_solver_ui/diag/json_safe.py` (strict JSON: `allow_nan=False`).

### 2) Global eventlog
`pneumo_solver_ui/diag/eventlog.py`:
- все события (`warn`, `error`, `diagnostics`) пишутся в `events.jsonl` строго по UI‑схеме.
- если в `emit()` кто‑то передал поля, конфликтующие с reserved‑ключами схемы — они сохраняются в `"_extra_reserved"`, чтобы не ломать валидатор.

## Примечания
- Наличие валидного `events.jsonl` критично: `make_send_bundle.py` проверяет папку логов рекурсивно.
- Логи **никогда** не должны ломать приложение: ошибки логгирования глушатся (best‑effort), но всё, что можно — пишется.
