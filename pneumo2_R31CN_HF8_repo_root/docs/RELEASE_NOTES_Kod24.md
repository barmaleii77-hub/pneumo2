# RELEASE NOTES — Kod24 (base: Verifikatsiya R47)

## Главные изменения

### 1) Исправление "ложных" ошибок таблицы параметров
Streamlit сохраняет состояние `st.session_state` между перезагрузками/обновлениями кода.
Из‑за этого старая таблица могла содержать строки с нечисловыми параметрами (режимы/флаги),
и валидатор пытался сделать `float('thermal')`, что приводило к сообщениям:

- `Параметр 'термодинамика': пустое/некорректное базовое значение`
- `Параметр 'стенка_форма': ...`
- и т.п.

**Решение в Kod24:**
- Добавлен fingerprint/сигнатура структуры таблицы (keys/kinds/columns).
- При изменении сигнатуры выполняется миграция/пересборка таблицы.
- Добавлена кнопка "🔄 Сбросить таблицу параметров".

### 2) Unified profile.json (base+ranges+suite)
Добавлен модуль `pneumo_solver_ui/config_profile.py`:
- JSON Schema (draft‑07) + best-effort validation (если `jsonschema` установлен),
- авто‑приведение типов (doctor): bool/float/list, ремонт перевёрнутых диапазонов,
- удобный экспорт/импорт через UI (сайдбар).

Файлы:
- `pneumo_solver_ui/config_profile.py`
- `pneumo_solver_ui/profile_schema.json`

### 3) Надёжные atomic‑записи
Улучшены функции `_atomic_write_text/_atomic_write_csv`:
- уникальные temp‑файлы (`mkstemp`) вместо фиксированного `*.tmp`,
- `os.replace` для атомарной замены,
- best-effort `fsync`.

### 4) .env поддержка
Launchers (`START_PNEUMO_UI.pyw` и `pneumo_solver_ui/START_PNEUMO_UI.pyw`) пытаются загрузить `.env`
через `python-dotenv` (если установлен).

## Зависимости
`pneumo_solver_ui/requirements.txt` дополнен:
- `jsonschema`
- `python-dotenv`

## Совместимость
Kod24 не меняет физическую модель; изменения касаются UI/конфигурации/надёжности.

