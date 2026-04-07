# RELEASE NOTES — RealizatsiyaOptimizatsiiRelease55 (bundle)

Этот файл описывает изменения **в бандле Release55** относительно предыдущего бандла Release54.

## Главное

- ✅ Исправлены критические рассинхроны интерфейсов в distributed‑подсистеме:
  - ExperimentDB: init_schema/connect, reserve_trial возвращает (trial_id, inserted), добавлены алиасы mark_trial_*.
  - hv_tools: добавлены алиасы функций для Streamlit страницы (pareto_front_2d_max, choose_reference_point_max, hv_2d_max, y_min_to_max).
  - Streamlit страница `04_ExperimentDB_Distributed.py` снова работает с актуальными API DB/HV.
  - Переписаны и унифицированы `run_ray_distributed_async.py` и `run_dask_distributed_async.py` под реальные API Evaluator/DB.

- ✅ Добавлено:
  - таблица `run_metrics` (в БД) + методы `add_metric()/fetch_metrics()`
  - Resume (Ray/Dask): `--resume` + проверка `problem_hash` + requeue stale RUNNING через `--resume-requeue-ttl`
  - X_pending в proposer (BoTorch), чтобы снижать дубли точек при асинхронной постановке задач
  - Multi‑GPU proposer pool (Ray): `--proposer-actors N` + `--proposer-prefetch`

## Файлы (ключевые)

- `pneumo_solver_ui/pneumo_dist/expdb.py` — полностью усилен (schema, API, lazy-connect, run_metrics)
- `pneumo_solver_ui/pneumo_dist/hv_tools.py` — алиасы для страниц
- `pneumo_solver_ui/pneumo_dist/eval_core.py` — добавлены convenience методы dim/denormalize/normalize/bounds_u
- `pneumo_solver_ui/tools/run_ray_distributed_async.py` — переписан (работающий distributed coordinator)
- `pneumo_solver_ui/tools/run_dask_distributed_async.py` — переписан (работающий distributed coordinator)
- `README_DETAILED_RELEASE55.md` — новый подробный гайд
