# Калибровка матмодели по NPZ-логам (osc_dir из UI)

Этот пакет дополняет/исправляет скрипты **fit_worker_v3_suite_identify.py** и **profile_worker_v1_likelihood.py**
для калибровки по осциллограммам, которые UI сохраняет в формате **NPZ**.

## Что исправлено в v5

В UI логирование устроено так, что:
- `main` таблица часто пишется на каждом шаге интегрирования,
- а `p/q/open/E*` — реже (с шагом `log_stride`/`record_stride`).

Из-за этого разные таблицы внутри одного `Txx_osc.npz` могут иметь **разные оси времени** и **разную длину**.

**v5**:
- корректно берёт `t_meas` отдельно для каждой таблицы (`main/p/q/open/...`),
- корректно берёт `t_sim` отдельно для каждой таблицы выходов модели,
- умеет `--time_col auto` (обычно выбирается `время_с`).

## Быстрый порядок действий

### 0) Сгенерируйте осциллограммы в UI

В UI включите логирование (`log_enable`), выберите `log_format=NPZ`.
На выходе получите папку вида:
- `osc_logs/RUN_.../tests_index.csv`
- `osc_logs/RUN_.../T01_osc.npz`, `T02_osc.npz`, ...

### 1) Посмотрите содержимое NPZ

```bash
python npz_inspect_v1.py --osc_dir osc_logs/RUN_... --test_num 1
```

Скрипт напечатает, какие таблицы присутствуют (`main/p/q/open/...`) и список колонок.

### 2) Соберите mapping JSON

Стартовый вариант: `mapping_npz_minimal_example.json`.

Расширенный шаблон: `mapping_npz_extended_template.json`.

**Правило:**
- если измерение берётся из таблицы `p`, то `meas_table="p"`,
  а `model_key` должен быть `p:<колонка>`.
- аналогично для `q`, `open`.

### 3) Запустите подгонку

```bash
python fit_worker_v3_suite_identify.py \
  --model model_pneumo_v8_energy_audit_vacuum_patched_smooth_all.py \
  --worker opt_worker_v3_margins_energy.py \
  --suite_json default_suite.json \
  --osc_dir osc_logs/RUN_... \
  --base_json default_base.json \
  --fit_ranges_json default_ranges.json \
  --mapping_json mapping_npz_minimal_example.json \
  --time_col auto \
  --n_init 32 --n_best 6 \
  --loss soft_l1 --f_scale 1.0 \
  --record_stride 1 \
  --use_smoothing_defaults \
  --out_json fitted_base.json \
  --report_json fit_report.json
```

Доп. опции, которые чаще всего нужны на реальных логах:

- `--auto_scale mad` — автонормировка вкладов сигналов по MAD (устойчиво к выбросам). Удобно, если в mapping много разных шкал.
- `--meas_stride N` — проредить измерения по времени (брать каждый N-й отсчёт). Полезно для ускорения «coarse» шага.
- `--holdout_tests "имя1,имя2"` — исключить тесты из подгонки, но посчитать их в `details_json` как контроль/валидацию.
- `--details_json details.json` — сохранить детализацию по каждому тесту и каждому сигналу (SSE/RMSE, веса, scale).

Пример:

```bash
python fit_worker_v3_suite_identify.py \
  ... \
  --auto_scale mad \
  --holdout_tests "инерция_крен_ay3" \
  --details_json fit_details.json

```

### 4) Профили правдоподобия (идентифицируемость)

```bash
python profile_worker_v1_likelihood.py \
  --model model_pneumo_v8_energy_audit_vacuum_patched_smooth_all.py \
  --worker opt_worker_v3_margins_energy.py \
  --suite_json default_suite.json \
  --osc_dir osc_logs/RUN_... \
  --theta_star_json fitted_base.json \
  --fit_ranges_json default_ranges.json \
  --mapping_json mapping_npz_minimal_example.json \
  --profile_params "ресивер_объём_м3,аккумулятор_объём_м3" \
  --time_col auto \
  --loss linear \
  --out_json profile_report.json \
  --out_dir profile_out \
  --use_smoothing_defaults
```

## Практические советы

- **Не смешивайте шкалы без весов.** Давления (Па) почти всегда надо масштабировать (`weight ~ 1e-5` для перевода в бар),
  иначе углы/перемещения модель перестанет «видеть».

- **Если используете `p/q/open` из NPZ** и хотите ускорить расчёт, можно поставить `--record_stride` равным `log_stride`,
  с которым писали логи. Но при сильном разрежении динамику можно потерять.


## One-click пайплайн (inspect → mapping → fit → отчёт → profile)

Если не хочется вручную собирать mapping и руками запускать несколько скриптов, используйте оркестратор:

```bash
python calibration/pipeline_npz_oneclick_v1.py --osc_dir osc_logs/RUN_... \
  --mode extended \
  --auto_scale mad \
  --holdout_frac 0.2 \
  --use_smoothing_defaults \
  --run_profile
```

Что создастся в `calibration_runs/RUN_YYYYMMDD_HHMMSS/`:
- `mapping_auto.json` — сгенерированный mapping
- `holdout_selection.json` — какие тесты ушли в holdout
- `fitted_base.json` — найденные параметры
- `fit_report.json`, `fit_details.json` — машинные отчёты
- `report.md`, `tests.csv`, `signals.csv` — человекочитаемый отчёт
- `profile_out/`, `profile_report.json` — профили правдоподобия (если включено)

---

## Пайплайн "из signals.csv" (полностью автоматический список сигналов)

Если у вас уже есть `signals.csv` (например, из предыдущего запуска отчёта),
можно сделать *повторный* запуск калибровки, используя именно этот список сигналов.

Это удобно, если вы:
- вручную выключили часть сигналов (добавили колонку `enabled/use`),
- хотите взять только топ-N сигналов по SSE,
- хотите фиксировать веса через `w_raw`.

Команда:

```bash
python calibration/pipeline_npz_from_signals_csv_v2.py \
  --osc_dir osc_logs/RUN_... \
  --signals_csv calibration_runs/RUN_.../signals.csv \
  --auto_scale mad \
  --holdout_frac 0.2 \
  --use_smoothing_defaults \
  --run_oed \
  --run_profile
```

Скрипт:
- соберёт `mapping_from_signals.json` из `signals.csv` (и проверит по NPZ),
- выполнит fit,
- сгенерирует новый отчёт,
- опционально выполнит OED/FIM и профили правдоподобия.

---

## Итеративный автоматический режим (signals.csv → refine → re-fit)

Если хочется максимально устойчивый "автомат" без ручной фильтрации сигналов,
используйте итеративный запуск:

```bash
python calibration/pipeline_npz_iterative_signals_v1.py \
  --osc_dir osc_logs/RUN_... \
  --signals_csv auto \
  --iters 2 \
  --auto_scale mad \
  --use_smoothing_defaults
```

Он:
1) берёт `signals.csv` (или делает bootstrap из NPZ);
2) запускает fit;
3) автоматически создаёт `signals_refined.csv` (enabled/weight) по метрикам ошибки;
4) запускает fit повторно на очищенном наборе.

Подробности: `calibration/README_ITERATIVE_RU.md`.

