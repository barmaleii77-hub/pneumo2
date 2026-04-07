# RELEASE NOTES — Realizatsiya optimizatsii Release54

Дата: 2026-01-25

## Главные изменения

### 1) Distributed evaluation / optimization (Ray + Dask)

Добавлены 2 координатора:
- `pneumo_solver_ui/tools/run_ray_distributed_async.py`
- `pneumo_solver_ui/tools/run_dask_distributed_async.py`

Они позволяют:
- запускать вычисление кандидатов в кластере (несколько ПК),
- держать очередь задач, собирать результаты,
- возобновлять run после перезапуска,
- получать hv/pareto прогресс.

### 2) Единая Experiment DB (DuckDB/SQLite)

Новый модуль: `pneumo_solver_ui/pneumo_dist/expdb.py`

Схема:
- `runs` — метаинформация о запуске (config, problem_hash)
- `trials` — отдельные кандидаты, статус, метрики, objectives
- `cache` — дедуп (problem_hash + param_hash)

### 3) Hypervolume tools (умный reference point + нормализация)

Новый модуль: `pneumo_solver_ui/pneumo_dist/hv_tools.py`

- Конверсия minimization → maximization
- Pareto extraction (2D)
- Reference point heuristic (nadir - margin*(ideal-nadir))
- Нормализация по квантилям (q10-q90)

### 4) (Опционально) BoTorch proposer

Новый модуль: `pneumo_solver_ui/pneumo_dist/mobo_propose.py`

Если установлены torch+botorch:
- qNEHVI / qLogNEHVI propose
- поддержка X_pending (чтобы не предлагать одинаковые точки)
- возможен запуск proposer'а на GPU через Ray (actor num_gpus=1)

### 5) Streamlit страница DB

- `pneumo_solver_ui/pages/04_ExperimentDB_Distributed.py`

Показывает:
- список run’ов
- таблицы trials
- scatter (obj1 vs obj2)
- hv оценку

## One-click bat

- Установка опциональных зависимостей: `INSTALL_OPTIONAL_*.bat`
- Старт/подключение к кластерам: `RAY_START_*.bat`, `DASK_START_*.bat`
- Запуск координаторов: `RUN_DISTRIBUTED_*.bat`

## Известные ограничения

- Hypervolume реализован для 2 целей.
- Mixed/discrete параметры пока не подключены в distributed runner.
- БД single-writer (координатор). Это выбранное решение для надёжности.

## Следующий шаг

- Mixed (continuous + categorical) + VNR группы.
- Multi-GPU proposer pool.
- UI: управление distributed run прямо из Streamlit.
