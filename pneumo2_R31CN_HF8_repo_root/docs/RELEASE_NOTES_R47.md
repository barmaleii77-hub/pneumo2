# RELEASE_NOTES_R47 — Verifikatsiya

Дата: 2026-01-25

Этот релиз — «следующий шаг» поверх **ObobshchenieR43**. Цель: убрать физические/логические баги, которые давали неверные силы/моменты, и добавить практические инструменты для робастной валидации (long-suite), не ломая существующий пайплайн.

## Ключевые изменения

### 1) Физика: шина/дорога (демпфер по относительной скорости)
**Проблема:** демпфер шины использовал `pen_dot = -zw_dot`, т.е. считалось, что дорога всегда статична. При движущейся дороге (профиль, задержки между колёсами, etc.) это даёт неверную силу демпфирования и может искажать оценки комфорта/удержания контакта.

**Исправление:**
- введена `road_dot_func` (если не задана — вычисляется конечными разностями от `road_func`);
- используется **правильная относительная скорость** проникновения:
  - `pen = z_road - z_wheel (+ wheel_radius для модели smooth_all)`
  - `pen_dot = z_road_dot - z_wheel_dot`

**Файлы:**
- `pneumo_solver_ui/model_pneumo_v8_energy_audit_vacuum_patched_smooth_all.py`
- `pneumo_solver_ui/model_pneumo_v8_energy_audit_vacuum_patched.py`
- `pneumo_solver_ui/model_pneumo_v8_energy_audit_vacuum.py`

### 2) Физика: правильный moment-arm для pitch/roll + знак по оси X
**Проблема:** момент инерционной силы по pitch считался с плечом `0.5*H` и неправильным знаком по `ax`.

**Исправление:**
- используется параметр `h_cg` (высота ЦТ);
- формулы приведены к единому виду:
  - `M_pitch = -sum(F_susp*x_pos) - m_body*ax*h_cg`
  - `M_roll  =  sum(F_susp*y_pos) + m_body*ay*h_cg`

**Файлы:**
- `pneumo_solver_ui/model_pneumo_v8_energy_audit_vacuum_patched_smooth_all.py`
- `pneumo_solver_ui/model_pneumo_v8_energy_audit_vacuum_patched.py`

### 3) Единые условия ANR для Qn/Nl/min
**Проблема:** часть моделей использовала `101325 Па` и `273.15 K` для «нормальных» условий, а паспорт компонентов (`component_passport.json`) опирается на **ANR**: `100000 Па` и `293.15 K`.

**Исправление:** в patched-моделях заменены дефолты:
- `P_N_DEFAULT = 100000.0`
- `T_N_DEFAULT = 293.15`

**Файлы:**
- `pneumo_solver_ui/model_pneumo_v8_energy_audit_vacuum_patched_smooth_all.py`
- `pneumo_solver_ui/model_pneumo_v8_energy_audit_vacuum_patched.py`

### 4) Геометрия: канонические ключи `база/колея` + безопасные дефолты
**Проблема:** в разных местах встречались разные ключи (`база_м/колея_м` vs `база/колея`) и «случайные» дефолты (2.7/1.6, 2.3/1.2), что могло ломать диагональную кочку и расчёт критических углов.

**Исправление:**
- в модели и воркере введена поддержка алиасов (`база_м`, `колея_м`) приоритетно через `база/колея`;
- дефолты унифицированы: `база=1.5 м`, `колея=1.0 м`.

**Файлы:**
- `pneumo_solver_ui/model_pneumo_v8_energy_audit_vacuum_patched_smooth_all.py`
- `pneumo_solver_ui/model_pneumo_v8_energy_audit_vacuum_patched.py`
- `pneumo_solver_ui/opt_worker_v3_margins_energy.py`

### 5) Наблюдаемость: дорога v/a, относительные скорости, проникновение/зазор
Добавлены диагностические каналы (особенно полезно при проверке контактной модели):
- `скорость_дороги_*`, `ускорение_дороги_*`
- `проникновение_шины_*`, `зазор_до_дороги_*`
- `колесо_относительно_дороги_*_vz/az`
- `колесо_относительно_рамы_*_vz/az`

**Файл:**
- `pneumo_solver_ui/model_pneumo_v8_energy_audit_vacuum_patched_smooth_all.py`

### 6) UI: playhead events (правильная отрисовка + events_max=0)
**Проблемы:**
- `events_max=0` не работал из-за `|| 300` (0 трактовался как false);
- события передавались как `{t: ...}` в Python, но JS ждал `{idx:...}`;
- события не вызывали `renderEvents()` при обновлении данных;
- команды от Python могли лишний раз эхо‑триггерить `sendToPython()`.

**Исправления:**
- корректная обработка `events_max` (nullish‑логика, 0 допустим);
- поддержка `t` (поиск ближайшего индекса по timeArr бинарным поиском);
- вызов `renderEvents()` при render;
- добавлена логика `restore_state` (включаемая/выключаемая) + reset при смене dataset;
- `applyCmd()` больше не делает echo в Python.

**Файл:**
- `pneumo_solver_ui/components/playhead_ctrl/index.html`

### 7) Оптимизация: per-test `params_override`
Добавлена возможность задавать в suite тестах поле:
```json
"params_override": {"масса_рамы": 750, "температура_окр_К": 273.15}
```
Эти параметры применяются **только** на время данного теста.

**Файлы:**
- `pneumo_solver_ui/opt_worker_v3_margins_energy.py`

### 8) Long-suite инструменты
Добавлены:
- генератор long-suite: `pneumo_solver_ui/tools/generate_long_suite.py`
- робастная пост‑валидация top‑K кандидатов: `pneumo_solver_ui/tools/post_validate_robust.py`
- пример long-suite: `pneumo_solver_ui/default_suite_long.json`

## Изменения по умолчанию
- В UI дефолтная модель переключена на:
  - `model_pneumo_v8_energy_audit_vacuum_patched_smooth_all.py`

Файл:
- `pneumo_solver_ui/pneumo_ui_app.py`

## Совместимость
- Все изменения добавлены так, чтобы старые конфиги продолжали работать (поддержка алиасов ключей, производные дороги — опциональны).

## Что дальше (R48+)
- Робастная оптимизация (встроить worst‑case/CVaR в целевую функцию, не ломая GP/BO);
- Статическое равновесие (поиск штока/давления для заданной массы);
- Калибровка параметров по экспериментальным данным.
