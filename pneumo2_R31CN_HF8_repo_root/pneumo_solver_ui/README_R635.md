# Realizatsiya optimizatsii — Release on top of base v6.35 (WINSAFE)

Это пакет улучшений поверх **UnifiedPneumoApp_UNIFIED_v6_35_WINSAFE** (база).  
Цель шага: **сделать оптимизацию “неубиваемой” по резюму** + **автономные самопроверки** + **совместимость distributed-скриптов**.

---

## Что именно исправлено и добавлено (самое важное)

### 1) Исправлен “ломающийся resume” из‑за baseline promotion
**Проблема:** ранее `problem_hash` зависел от `base.json` целиком. Но `base.json` содержит и *фиксированные константы*, и *начальные значения оптимизируемых параметров*.  
Когда оптимизация обновляла бейслайн (autoupdate/promote), `base.json` менялся → менялся `problem_hash` → создавалась новая папка `prob_*` → **резюм слетал**, и оптимизация начинала “как с нуля”.

**Решение (в UI):**
- `problem_hash` теперь считает хэш **только от фиксированных констант** `base.json`, т.е. **из base исключаются ключи, которые присутствуют в `ranges.json`**.
- Это означает: **baseline promotion может менять оптимизируемые ключи в base.json, и resume не ломается**.

Файл: `pneumo_solver_ui/pneumo_ui_app.py`  
Маркер: `_strip_optimized_from_base(...)`

---

### 2) “Заморозка” входных файлов в run_dir (не перезатираем базу при повторном старте)
**Проблема:** UI каждый раз перезаписывал `run_dir/base.json`, `suite.json`, `ranges.json`.  
Если вы:
- уже считали оптимизацию,
- затем нажали “Start” снова,
- или включён baseline promotion,

то UI мог **перетереть** обновлённый бейслайн обратно “старыми” значениями.

**Решение:**
- `base.json/suite.json/ranges.json` пишутся **только если файла ещё нет** (frozen snapshot).
- При этом всегда сохраняются “последние значения из UI” в:
  - `base_latest_ui.json`
  - `suite_latest_ui.json`
  - `ranges_latest_ui.json`
- И отдельные frozen-копии:
  - `base_frozen.json`
  - `suite_frozen.json`
  - `ranges_frozen.json`

Файл: `pneumo_solver_ui/pneumo_ui_app.py`

---

### 3) Baseline promotion теперь реально обновляет base.json в run_dir (resume берёт улучшенный бейслайн)
**Проблема:** stage-runner сохранял `baseline_best.json`, но **не обновлял** `run_dir/base.json`.  
В результате:
- следующий resume мог стартовать не с улучшенного бейслайна,
- baseline promotion был “формальным”.

**Решение:**
- если найдено улучшение и включён `autoupdate_baseline`,
  stage-runner делает:
  - backup: `base_prev_YYYYMMDD_HHMMSS.json`
  - merge: старый base + `clean` (только оптимизируемые ключи)
  - запись: обновлённый `base.json`
  - отчёт: `baseline_promotion_last.json`

Файл: `pneumo_solver_ui/opt_stage_runner_v1.py`

---

### 4) Автономные самопроверки (self-check gate) встроены в запуск оптимизации
**Задача:** не тратить часы на запуск, который упадёт через 2 минуты из‑за:
- отсутствия нужных функций (например, `stable_hash_problem`),
- несовместимости формата suite,
- ошибок penalty/метрик,
- нарушения ключевых invariants.

**Решение:**
- UI перед стартом запускает `self_check.py --mode quick` и **останавливает запуск**, если проверки не прошли.
  - `SELF_CHECK_UI.json`
  - `SELF_CHECK_UI.log`
- Stage-runner перед прогоном стадий тоже запускает `self_check.py --mode quick`.
  - `SELF_CHECK_STAGE_RUNNER.json`
  - `SELF_CHECK_STAGE_RUNNER.log`

Файлы:
- `pneumo_solver_ui/self_check.py` (переписан: quick/full, json/log)
- интеграция:
  - `pneumo_solver_ui/pneumo_ui_app.py`
  - `pneumo_solver_ui/opt_stage_runner_v1.py`

---

### 5) Починен distributed-стек: добавлены stable_hash_* алиасы
В проекте есть инструменты (`tools/run_ray_distributed_opt.py`, `tools/run_dask_distributed_opt.py`), которые ожидают API:
- `stable_hash_problem`
- `stable_hash_params`
- `stable_hash_json_file`
- `stable_hash_file`

В базе v6.35 в `trial_hash.py` были функции `hash_problem/hash_params`, но **не было алиасов**, из‑за чего distributed-скрипты ломались.

**Решение:** добавлены backward-compatible алиасы в:
- `pneumo_dist/trial_hash.py`
- `pneumo_solver_ui/pneumo_dist/trial_hash.py`

---

## Где лежит что (карта проекта)

### Основной UI
- `pneumo_solver_ui/pneumo_ui_app.py` — Streamlit UI (запуск оптимизаций, выбор сценариев, контроль воркеров)

### Оптимизация (staged)
- `pneumo_solver_ui/opt_stage_runner_v1.py` — многостадийный раннер (progress json, архив, автоповышение бейслайна)

### Воркеры / вычисление метрик
- `pneumo_solver_ui/opt_worker_v3_margins_energy.py` — вычисляет кандидат, метрики, penalty, архивирование

### Модель
- `pneumo_solver_ui/model_pneumo_v8_energy_audit_vacuum.py` — модель (в т.ч. энерго‑аудит)

### Distributed
- `pneumo_solver_ui/tools/run_ray_distributed_opt.py` — Ray coordinator+workers (distributed evaluation)
- `pneumo_solver_ui/tools/run_dask_distributed_opt.py` — Dask вариант
- `pneumo_dist/*` — общий код distributed-слоя

### Самопроверки
- `pneumo_solver_ui/self_check.py` — quick/full проверки + JSON/log

### Данные
- `pneumo_solver_ui/default_base.json` — базовые параметры
- `pneumo_solver_ui/default_ranges.json` — диапазоны оптимизации
- `pneumo_solver_ui/default_suite.json` — набор тестов/сценариев

---

## Как запускать

### Вариант A — UI (Streamlit)
1) Установить зависимости (если надо):
   ```bat
   pip install -r requirements.txt
   ```
2) Запуск:
   ```bat
   streamlit run pneumo_solver_ui/pneumo_ui_app.py
   ```
3) Нажать Start Optimization.  
Перед стартом автоматически будет выполнен `SELF_CHECK_UI`.

---

### Вариант B — stage runner напрямую
```bat
python pneumo_solver_ui/opt_stage_runner_v1.py ^
  --run_dir pneumo_solver_ui/workspace/opt_runs/myrun/prob_xxxxxx ^
  --base_json pneumo_solver_ui/workspace/opt_runs/myrun/prob_xxxxxx/base.json ^
  --ranges_json pneumo_solver_ui/workspace/opt_runs/myrun/prob_xxxxxx/ranges.json ^
  --suite_json pneumo_solver_ui/workspace/opt_runs/myrun/prob_xxxxxx/suite.json
```

---

## Важные правила для корректного resume (и почему теперь работает)

1) **Resume “привязан” к problem_hash.**  
   Он зависит от:
   - модели
   - фиксированных базовых констант (base.json без optimizable keys)
   - ranges.json
   - suite.json

2) **Изменили suite/ranges/фиксированные константы → новый problem_hash → новая папка.**  
   Это корректно (другая задача).

3) **Baseline promotion меняет только optimizable keys.**  
   И они исключены из base_hash → problem_hash не меняется → resume работает.

---

## Диффы и патчи

- Патч к базе v6.35:
  - `diffs/RealizatsiyaOptimizatsii635.patch`
- Список изменённых файлов:
  - `diffs/RealizatsiyaOptimizatsii635_changed_files.txt`

---

## TODO (следующие крупные шаги)

Коротко (подробно — в TODO.md):
1) Полноценный *мультистадийный пайплайн* с наращиванием длительности/точности тестов (fast → medium → long).
2) Нормализация целей + корректный reference point для гиперобъёма (особенно при смене набора тестов).
3) Unified DB экспериментов (DuckDB/SQLite) с дедупом по `(problem_hash, params_hash, stage)` и автоматическим warm-start BO.
4) “Сценарная матрица”: реальные профили дорог/манёвров + вариация внешних условий (пассажиры/груз/температура/начальные давления).
5) Distributed evaluation по нескольким ПК (Ray cluster + общий expdb).

---

## Контрольные файлы после запуска

Внутри `pneumo_solver_ui/workspace/opt_runs/<run>/prob_<hash>/` вы увидите:
- `out.csv` — результаты
- `archive.jsonl` — архив кандидатов (для warm-start)
- `staged_progress.json` — прогресс стадий
- `SELF_CHECK_*.json/.log` — отчёты самопроверок
- `baseline_promotion_last.json` — если бейслайн был обновлён

---

## Примечания по “тяжёлым файлам контекста”
В архив **не включались** внешние большие пакеты контекста/логов/диагностик.  
Только рабочий код + лёгкая документация и патч.

