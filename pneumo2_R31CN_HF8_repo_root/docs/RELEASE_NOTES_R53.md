# RELEASE53 — Distributed Optimization Engine (Ray/Dask) + ExperimentDB + HV (Matematika55 base)

База: **Matematika55** (`Matematika55.zip`).

## Что добавлено

### 1) Распределённая оценка кандидатов (multi‑PC)
- Ray async runner: `pneumo_solver_ui/tools/run_ray_distributed_async.py`
- Dask async runner: `pneumo_solver_ui/tools/run_dask_distributed_async.py`
- Параметры: `--budget`, `--queue_target`, `--penalty_tol`, `--min_points_for_botorch`

### 2) Единая БД экспериментов (DuckDB/SQLite)
- Модуль: `pneumo_solver_ui/pneumo_dist/expdb.py`
- Ключевые таблицы: `runs`, `trials`, `cache`, `run_metrics`
- Дедуп/кэш: `(problem_hash, param_hash)`.

### 3) Hypervolume прогресс
- Нормализация целей + HV в [0..1]^2: `pneumo_solver_ui/pneumo_dist/hv_tools.py`
- Метрики пишутся в `run_metrics`.

### 4) Опциональный BoTorch proposer (qNEHVI/qLogNEHVI)
- `pneumo_solver_ui/pneumo_dist/mobo_propose.py`
- Используется автоматически в distributed runner'ах после накопления min_points (иначе random/LHS).

### 5) UI просмотрщик DB
- Streamlit page: `pneumo_solver_ui/pages/03_DistributedOptimizationDB.py`

## Как запустить (Windows)

### Установить опциональные зависимости
- `INSTALL_OPTIONAL_DISTRIBUTED_WINDOWS.bat`
- `INSTALL_OPTIONAL_BOTORCH_WINDOWS.bat` (torch ставится отдельно под вашу CUDA)

### Ray (head + workers)
- `pneumo_solver_ui/tools/RAY_START_HEAD_WINDOWS.bat`
- `pneumo_solver_ui/tools/RAY_START_WORKER_WINDOWS.bat HEAD_IP:6379`
- Запуск: `RUN_DISTRIBUTED_RAY_WINDOWS.bat`

### Dask (scheduler + workers)
- `pneumo_solver_ui/tools/DASK_START_SCHEDULER_WINDOWS.bat`
- `pneumo_solver_ui/tools/DASK_START_WORKER_WINDOWS.bat tcp://HEAD_IP:8786`
- Запуск: `RUN_DISTRIBUTED_DASK_WINDOWS.bat`

## Артефакты результата

В `pneumo_solver_ui/runs_distributed/<run>/` создаются:
- `experiments.duckdb` или `experiments.sqlite`
- `progress.json`
- `trials_done.csv` (быстрый список DONE/ERROR)
- `export/` (через `tools/expdb_export.py`)

## Патчи/диффы
- `diffs/Release53_vs_Matematika55.patch`
- `patches/Release53_apply.patch`
