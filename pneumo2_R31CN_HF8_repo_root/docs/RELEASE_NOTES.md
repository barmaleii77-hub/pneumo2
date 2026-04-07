# Release Notes — RealizatsiyaOptimizatsii632

База: **UnifiedPneumoApp_UNIFIED_v6_32_WINSAFE**

## Изменения (важное)

### 1) Исправлена «потеря продолжения» оптимизации
**Проблема:** `problem_hash` (и, следовательно, папка `opt_runs/.../prob_*`) менялись, когда менялся baseline (оптимизируемые параметры), а UI при каждом старте перезаписывал `base.json` / `suite.json` / `ranges.json`. В результате ...

**Решение:**
- `problem_hash` теперь считается от `base_override` **без ключей из `ranges_override`** (то есть оптимизируемые параметры не «ломают» идентификатор задачи).
- `base.json/suite.json/ranges.json` теперь **“frozen once”**: создаются один раз и дальше не перезаписываются. При каждом старте пишутся `*_latest.json` для аудита.

Затронуто: `pneumo_solver_ui/pneumo_ui_app.py`

### 2) Autoupdate baseline действительно обновляет baseline и базу
**Проблема:** stage‑runner писал `baseline_best.json`, но фактическая базовая `base.json` в run_dir не обновлялась → следующий запуск стартовал со старой базы.

**Решение:** stage‑runner теперь:
- делает бэкап `run_dir/base_before_autoupdate.json` (один раз),
- применяет лучшие параметры к `base_params`,
- записывает обновлённый `base.json` (тот же путь, что передан `--base_json`),
- ведёт `baselines/baseline_best.json` и `baseline_best_score.json` как раньше.

Затронуто: `pneumo_solver_ui/opt_stage_runner_v1.py`

### 3) Восстановлена совместимость со скриптами распределённой оптимизации
**Проблема:** часть инструментов (Ray/Dask) импортировала `stable_hash_problem/stable_hash_params`, но в `trial_hash.py` их не было (в результате скрипты падали при запуске).

**Решение:** добавлены обратнос совместимые обёртки `stable_hash_*` (как в legacy‑релизах).

Затронуто:
- `pneumo_solver_ui/pneumo_dist/trial_hash.py`
- `pneumo_dist/trial_hash.py`

## Что проверить пользователю
1) UI → оптимизация → запуск → остановка → повторный запуск: должна продолжаться в той же `prob_*` папке.
2) Включить `Автообновлять baseline` → дождаться улучшения → проверить, что изменился `run_dir/base.json` и `baselines/baseline_best.json`.
3) Запустить `tools/run_ray_distributed_opt.py` (или `run_dask_distributed_opt.py`) — не должно быть ImportError/AttributeError по `stable_hash_*`.

## Следующие шаги (план)
- Подключить `ExperimentDB` к локальному stage‑runner (чтобы результаты гарантированно попадали в общую БД и использовались в последующих запусках/на других ПК).
- Добавить в UI “Resume from existing run” и выбор существующего `run_dir` + выбор `out_csv` для продолжения.
- Улучшить формирование reference point для HV с учётом baseline/квантили в стабильном нормализованном пространстве.
