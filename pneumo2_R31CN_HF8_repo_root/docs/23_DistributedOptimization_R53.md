# Distributed Optimization (R53)

## Архитектура

**Coordinator**
- держит состояние оптимизации (история X/Y/penalty),
- делает предложение кандидатов (random/LHS, или BoTorch qNEHVI),
- пишет всё в ExperimentDB,
- держит очередь вычислений заполненной (async).

**Evaluators**
- процессы/акторы на разных машинах,
- грузят модель один раз,
- считают `eval_candidate(...)` для присланного params,
- возвращают (obj1,obj2,penalty,row).

## Почему async
Async режим (q=1) позволяет максимизировать загрузку кластера: как только один воркер освободился, ему сразу выдаётся новая задача, без ожидания полного батча.

## Ray vs Dask
- Ray удобнее для stateful actors (напр., отдельный DB actor и GPU proposers).
- Dask проще стартовать в некоторых Windows окружениях (scheduler + workers) и удобен для “потокового” `as_completed`.

Скрипты:
- Ray: `pneumo_solver_ui/tools/run_ray_distributed_async.py`
- Dask: `pneumo_solver_ui/tools/run_dask_distributed_async.py`
