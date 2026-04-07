# Patch v4: Suite-fit + Profile Likelihood

Этот патч добавляет следующий этап для **идентификации параметров матмодели**:

1) **fit по suite + NPZ из UI** (мульти‑тестовый фит, честно использующий build_test_suite)
2) **profile likelihood** (профили + доверительные интервалы по χ² для loss="linear")

---

## 1) fit по нескольким тестам: `fit_worker_v3_suite_identify.py`

### Входы
- `--model` : файл модели (`simulate(params,test,dt,t_end,...)`)
- `--worker`: `opt_worker_v3_margins_energy.py` (нужен `build_test_suite`)
- `--suite_json`: список тестов (например `default_suite.json`)
- `--osc_dir`: папка из UI `osc_logs/<run_tag>/` с `tests_index.csv` и `Txx_osc.npz`
- `--base_json`: базовые параметры
- `--fit_ranges_json`: какие параметры подгоняем и границы
- `--mapping_json`: что сравниваем (какие колонки)

### Запуск
```bash
python fit_worker_v3_suite_identify.py ^
  --model model_pneumo_v8_energy_audit_vacuum_patched_smooth_all.py ^
  --worker opt_worker_v3_margins_energy.py ^
  --suite_json default_suite.json ^
  --osc_dir osc_logs/RUN_... ^
  --base_json default_base.json ^
  --fit_ranges_json fit_ranges.json ^
  --mapping_json mapping_npz_example_v2.json ^
  --out_json fitted_base.json ^
  --report_json fit_report.json ^
  --use_smoothing_defaults
```

---

## 2) Profile likelihood: `profile_worker_v1_likelihood.py`

### Идея
Для каждого параметра φ строим сетку значений φ_j.
На каждом φ_j фиксируем φ=φ_j и переоптимизируем остальные параметры.
На выходе: профили SSE и приближённые доверительные интервалы по LRT (χ², df=1).

### Запуск
```bash
python profile_worker_v1_likelihood.py ^
  --model model_pneumo_v8_energy_audit_vacuum_patched_smooth_all.py ^
  --worker opt_worker_v3_margins_energy.py ^
  --suite_json default_suite.json ^
  --osc_dir osc_logs/RUN_... ^
  --theta_star_json fitted_base.json ^
  --fit_ranges_json fit_ranges.json ^
  --mapping_json mapping_npz_example_v2.json ^
  --profile_params "пружина_масштаб,жёсткость_шины" ^
  --out_json profile_report.json ^
  --out_dir profile_out ^
  --use_smoothing_defaults
```

### Что получится
- `profile_report.json` — общий отчёт по всем профилям
- `profile_out/profile_<param>.csv` — CSV на каждый параметр для графика (fixed_value, sse, delta_chi2)

---

## Практические советы
- Для статистически корректных CI используйте `--loss linear`.
- Если модель негладкая — включайте `--use_smoothing_defaults`.
- Начинайте с 1–3 параметров профиля; профили дорогие (много переоптимизаций).

