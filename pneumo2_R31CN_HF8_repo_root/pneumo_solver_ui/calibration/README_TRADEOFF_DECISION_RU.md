# Decision support для multiobjective trade-off (Pareto vs ε-constraint)

Этот модуль добавляет в проект автоматическую "инженерную" стадию принятия решения
после построения множества компромиссных решений.

## Зачем

В реальных NPZ-логах часто есть **конфликтующие группы сигналов**:
- давления ↔ кинематика
- давления ↔ расходы
- кинематика ↔ энерго/потери

Если вы оптимизируете всё одной суммой, одна группа может "перетянуть" решение.
Поэтому мы строим фронт компромисса (Pareto) одним из двух способов:

1) **Pareto sweep (weighted-sum)**
   - мы меняем post-scale gain групп и выполняем серию независимых fit
   - быстро, удобно, хорошо покрывает выпуклые фронты
   - может пропускать невыпуклые части

2) **ε-constraint**
   - минимизируем цель A, а цель B ограничиваем сверху (B <= ε)
   - сканируем ε
   - лучше покрывает невыпуклые фронты, но дороже

Дальше возникает вопрос: **какой фронт лучше и какую точку брать в работу**.

## Что добавлено

### 1) `mo_metrics_v1.py`
Утилиты для 2D min-min:
- Pareto filter
- knee-point (distance-to-line в нормализованном пространстве)
- hypervolume (2D)
- hypervolume contribution
- spacing CV (равномерность)

### 2) `tradeoff_decision_support_v1.py`
Скрипт, который:
- читает `pareto_tradeoff/pareto_points.csv` и/или `epsilon_tradeoff/epsilon_points.csv`
- строит non-dominated fronts заново **в одном compare_mode**
- сравнивает фронты через hypervolume + spacing
- выбирает метод (pareto/epsilon)
- выбирает точку на фронте (по умолчанию knee)
- копирует итоговый base.json в `tradeoff_selected_base.json`

Выходные файлы в `RUN_*`:
- `tradeoff_decision.json`
- `tradeoff_decision.md`
- `tradeoff_front_compare.png`
- `tradeoff_selected_base.json` (если удалось скопировать)

## Как выбирается compare_mode (train/holdout)

- Если **и Pareto, и ε-constraint** содержат валидные `objA_holdout/objB_holdout` (есть хотя бы одно finite значение),
  то сравнение делается по **holdout**.
- Иначе сравнение делается по **train** (общий знаменатель).

Это сделано специально, чтобы сравнение было честным и не сводилось к "яблокам и апельсинам".

## Как выбирается лучший фронт

Критерий 1 (главный): **hv_norm_global**
- Это hypervolume фронта, нормированный на один и тот же прямоугольник
  `[(global_minA, global_minB) -> (refA, refB)]`.
- `refA/refB` выбираются как (maxA, maxB) по всем точкам, умноженные на (1+margin).

Критерий 2 (tie-breaker): **spacing_cv**
- грубая метрика равномерности распределения точек по фронту
- меньше = более равномерно

## Как выбирается точка решения

`--select_point`:
- `knee` (по умолчанию): max distance-to-line между экстремумами (NBI-style)
- `hvcontrib`: точка с максимальным hypervolume contribution
- `minimax`: минимизация `max(norm(objA), norm(objB))`

## Запуск вручную

Из корня `pneumo_v7`:

```bash
python calibration/tradeoff_decision_support_v1.py --run_dir calibration_runs/RUN_XXXX_autopilot_v5 \
  --select_point knee --margin 0.05
```

## Интеграция в Autopilot

В этом бандле Autopilot (v6) автоматически запускает decision support,
если вы включили `--run_pareto` и/или `--run_epsilon`.

Отключить можно флагом:

```bash
--skip_tradeoff_decision
```

## Практические советы

1) **Если fronts близки по hv_norm_global**, смотрите на:
   - реальное качество на holdout
   - физические ограничения/устойчивость (диагностика, action_plan)
   - интерпретируемость параметров

2) **Если ε-constraint выигрывает**, это часто означает, что фронт невыпуклый
   и weighted-sum действительно не покрывает важные решения.

3) **Если Pareto sweep выигрывает**, возможно:
   - фронт близок к выпуклому
   - ε-сетка слишком грубая или penalty слишком слабый

