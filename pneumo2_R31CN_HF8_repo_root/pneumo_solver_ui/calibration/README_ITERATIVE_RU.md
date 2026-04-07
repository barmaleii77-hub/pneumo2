# Итеративная автоматическая калибровка по NPZ (signals.csv → refine → re-fit)

Актуальные скрипты:
- `pipeline_npz_iterative_signals_v4.py` — **текущий рекомендуемый** (resume + param staging + coarse-to-fine + coarse test subset)
- `pipeline_npz_iterative_signals_v3.py` — предыдущая версия (без coarse subset, без некоторых passthrough)
- `pipeline_npz_iterative_signals_v2.py` — ещё более ранняя версия (оставлена для совместимости)

---

## Зачем это нужно

Этот режим полезен, когда вы хотите, чтобы калибровка шла **полностью автоматически**:

1) берём `signals.csv` (или делаем bootstrap из NPZ, если `signals.csv` не задан)
2) строим `mapping.json`
3) запускаем fit по suite (опционально: staging по параметрам)
4) строим отчёт по качеству сигналов/тестов
5) автоматически «чистим» список сигналов (константы/битые/очень плохие)
6) повторяем fit ещё раз (обычно 1–2 итерации достаточно)

---

## Запуск (v4)

Из корня `pneumo_v7/`:

### Базовый режим (2 итерации)
```bash
python calibration/pipeline_npz_iterative_signals_v4.py \
  --osc_dir osc_logs/RUN_... \
  --signals_csv auto \
  --iters 2 \
  --auto_scale mad \
  --use_smoothing_defaults \
  --resume
```

### Coarse-to-fine (ускорение по времени)
```bash
python calibration/pipeline_npz_iterative_signals_v4.py \
  --osc_dir osc_logs/RUN_... \
  --signals_csv auto \
  --iters 2 \
  --coarse_to_fine \
  --coarse_meas_stride 5 \
  --coarse_max_nfev 80 \
  --meas_stride 1 \
  --auto_scale mad \
  --resume
```

### Coarse-to-fine + coarse subset тестов (ускорение по времени + по числу тестов)
```bash
python calibration/pipeline_npz_iterative_signals_v4.py \
  --osc_dir osc_logs/RUN_... \
  --signals_csv auto \
  --iters 2 \
  --coarse_to_fine \
  --coarse_meas_stride 5 \
  --coarse_test_subset_mode meas_variation \
  --coarse_test_subset_max_tests 6 \
  --meas_stride 1 \
  --auto_scale mad \
  --resume
```

### С параметрическим staging (поэтапная подгонка параметров)
```bash
python calibration/pipeline_npz_iterative_signals_v4.py \
  --osc_dir osc_logs/RUN_... \
  --signals_csv auto \
  --iters 2 \
  --param_staging fim_corr \
  --staging_only_final \
  --coarse_to_fine \
  --coarse_meas_stride 5 \
  --coarse_test_subset_mode meas_variation \
  --meas_stride 1 \
  --auto_scale mad \
  --resume
```

---

## Выход

Создаётся папка `calibration_runs/RUN_..._iter/`:

```
iter_00/
  mapping.json
  fitted_base.json
  fit_report.json
  fit_details.json
  report.md
  tests.csv
  signals.csv
  signals_refined.csv
  coarse_tests.json              (если включён coarse subset)
  coarse_tests_selected.txt      (если включён coarse subset)
iter_01/
  ...
FINAL_SIGNALS.csv
holdout_selection.json
```

Если включён coarse-to-fine, то в итерациях/стадиях появятся дополнительные файлы:
- `fitted_base_coarse.json`, `fit_report_coarse.json`, `fit_details_coarse.json`
- для staging: `fitted_base_stageK_coarse.json` и т.п.

---

## Правила «refine» (signals_refine_v1.py)

По умолчанию сигнал отключается, если:
- слишком мало точек `n_sum < min_total_points` (по всем тестам)
- `scale` невалиден или ~0 (часто значит константа / auto_scale не смог посчитать)
- `NRMSE = RMSE/scale` слишком большой (`>= disable_nrmse`)

Если `NRMSE` просто большой, но не экстремальный — сигнал остаётся, но его вес уменьшается.

> Важно: refine — эвристика для устойчивости. Для более строгой оценки используйте
> `profile_worker_v1_likelihood.py` и `oed_worker_v1_fim.py`.
