# AnimaciyaR56 — изменения

База: `UnifiedPneumoApp_UNIFIED_v6_10_WINSAFE`.

Цель шага: **повысить информативность анимации и убрать ручные операции** вокруг Desktop Animator.

## 1) Исправления/улучшения (что было проблемой)

### 1.1. UI пытался экспортировать NPZ, но функции не было
В `pneumo_solver_ui/pneumo_ui_app.py` уже были вызовы `export_full_log_to_npz(...)`, но реализация отсутствовала.
Из‑за этого:
- авто‑экспорт `Txx_osc.npz` в `osc_dir` фактически не работал,
- Desktop Animator не мог получать данные штатным способом.

**Исправление:**
- добавлен единый модуль `pneumo_solver_ui/npz_bundle.py` с экспортом в формат, совместимый с Desktop Animator.

### 1.2. Desktop Animator «follow» ожидал pointer-файл, но UI его не создавал
Desktop Animator имеет режим `--follow`, который следит за `workspace/exports/anim_latest.json`.
Но UI не записывал `anim_latest.*`.

**Исправление:**
- добавлен авто‑экспорт `workspace/exports/anim_latest.npz` + `anim_latest.json` после детального прогона,
- добавлена ручная кнопка «Экспортировать anim_latest сейчас» рядом с анимацией.

### 1.3. One‑click запуск был не полностью one‑click
Раньше `START_PNEUMO_APP.pyw` запускал только Streamlit.

**Улучшение:**
- в лаунчер добавлена галка «Запустить Desktop Animator (follow)» (+ опционально `--no-gl`).

### 1.4. Web 3D траектория по умолчанию была «статичной»
Из‑за этого по умолчанию:
- скорость/повороты на 3D были неинформативными,
- «дорога изгибается» не чувствовалась.

**Улучшение:**
- по умолчанию 3D траектория теперь строится по `скорость_vx_м_с` + `yaw_рад` (если колонки присутствуют).
- «демо‑траектории» оставлены как дополнительная опция.

## 2) Что добавлено (где лежит)

- `pneumo_solver_ui/npz_bundle.py`
  - `export_full_log_to_npz(...)`
  - `export_anim_latest_bundle(...)` (пишет `anim_latest.npz` и `anim_latest.json`)

- `pneumo_solver_ui/pneumo_ui_app.py`
  - настройки детального прогона: ✅ авто‑экспорт anim_latest
  - expander рядом с анимацией: экспорт/запуск Desktop Animator
  - 3D path: новый режим «По vx/yaw из модели» (и авто‑выбор по умолчанию)

- `pneumo_solver_ui/pages/07_DesktopAnimator.py`
  - запуск Animator в режиме `--follow` одной кнопкой
  - показ статуса pointer/NPZ

- `START_PNEUMO_APP.pyw`
  - галка запуска Desktop Animator (follow)

## 3) Совместимость

- Сохранена функциональность старых «демо траекторий» (Прямая/Слалом/Поворот и т.д.).
- Формат NPZ совместим с Desktop Animator (`desktop_animator/data_bundle.py`).

