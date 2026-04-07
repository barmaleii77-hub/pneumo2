# Archive & baseline (персистентность)

## 1) Персистентность прогонов

Каждый запуск оптимизации пишет результаты в **стабильную** папку:

```
workspace/opt_runs/<run_name>/prob_<problem_hash>/
  base.json
  ranges.json
  suite.json
  <stem>.csv                  # обычный режим
  <stem>_all.csv              # staged режим
  staged_progress.json        # staged прогресс
  STOP_OPTIMIZATION.txt       # файл остановки
  stage0_relevance/
  stage1_long/
  stage2_final/
```

`problem_hash` вычисляется из:
- hash модели
- hash base/ranges/suite
- explicit objective/penalty contract (`objective_keys`, `penalty_key`, `penalty_tol`)

Значит если вы не меняли задачу **и не меняли функцию качества / hard gate** — повторный запуск **продолжит** расчёт (CSV не меняется). Если objective stack или penalty contract поменялись, это уже новая задача и resume/cache не должны смешивать её со старой.

## 2) Global archive

StageRunner после каждого этапа добавляет новые строки в:

```
workspace/opt_archive/global_history.jsonl
```

Каждая строка — JSON со служебными метаданными (`run_dir`, `stage`, timestamp) + все поля из CSV.

Зачем:
- при изменении исходных данных/сьюта можно **не терять** прошлые результаты
- можно использовать архив для прогноза лидеров / warm-start

## 3) Warm-start (инициализация CEM)

Перед запуском этапа StageRunner:
- читает `global_history.jsonl`
- берёт top-K лучших точек (по penalty → цель1 → цель2)
- строит начальные `mu/cov` в нормализованных координатах
- сохраняет их в `*_cem_state.json` рядом с CSV этапа

Worker при старте подхватывает этот файл автоматически.

## 4) Baseline auto-update

Если включён флаг `Автообновлять baseline`:

StageRunner после финального этапа:
- выбирает лучшую строку из stage2
- извлекает параметры (`параметр__...`)
- пишет их в:

```
workspace/baselines/baseline_best.json
workspace/baselines/baseline_history.jsonl
```

Worker и UI теперь автоматически подхватывают этот baseline (см. `make_base_and_ranges()` в `opt_worker_v3_margins_energy.py`).

> Это отвечает требованию «бейзлайн должен обновляться если найдены параметры лучше».

## 5) Как сбросить baseline

Удалите или переименуйте:

```
workspace/baselines/baseline_best.json
```

После этого снова будет использоваться `pneumo_solver_ui/default_base.json`.
