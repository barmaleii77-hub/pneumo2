# Параметрический staging (поэтапная калибровка параметров)

## Зачем это нужно

Когда мы пытаемся фитить **все параметры одновременно**, оптимизатор часто сталкивается с:
- сильной корреляцией параметров (практическая неидентифицируемость),
- локальными минимумами,
- плохой условностью Jacobian/JTJ,
- "рваным" ландшафтом при наличии дискретной логики.

**Staging** — простой инженерный приём: сначала оптимизируем **ограниченный** поднабор параметров,
потом постепенно включаем новые, при этом разрешая уже подогнанным параметрам немного пересогласоваться.

В этом бандле staging реализован двумя уровнями:
- `param_staging_v1.py` строит список стадий и `stage_ranges/*.json`.
- `pipeline_npz_iterative_signals_v2.py` и `pipeline_npz_autopilot_v8.py` умеют запускать
  **последовательность fit'ов** по этим стадиям.

---

## Быстрый старт

### 1) Сгенерировать стадии

Из корня `pneumo_v7/`:

```bash
python calibration/param_staging_v1.py \
  --fit_ranges_json default_ranges.json \
  --signals_csv calibration_runs/RUN_.../FINAL_SIGNALS.csv \
  --out_dir calibration_runs/RUN_.../param_staging \
  --method auto
```

Выход:
- `param_staging/stages.json` — описание стадий
- `param_staging/stage_ranges/stage0_ranges.json`, `stage1_ranges.json`, ... — **union‑диапазоны**

### 2) Запустить staged fit вручную

```bash
python calibration/fit_worker_v3_suite_identify.py \
  --model model_pneumo_v8_energy_audit_vacuum_patched_smooth_all.py \
  --worker opt_worker_v3_margins_energy.py \
  --suite_json default_suite.json \
  --osc_dir <OSC_DIR> \
  --mapping_json <mapping.json> \
  --base_json default_base.json \
  --fit_ranges_json param_staging/stage_ranges/stage0_ranges.json \
  --out_json stage0_base.json \
  --report_json stage0_report.json \
  --details_json stage0_details.json

python calibration/fit_worker_v3_suite_identify.py \
  --base_json stage0_base.json \
  --fit_ranges_json param_staging/stage_ranges/stage1_ranges.json \
  --out_json stage1_base.json \
  --report_json stage1_report.json \
  --details_json stage1_details.json
```

---

## Как staging устроен в `param_staging_v1.py`

### Метод `heuristic`
По имени параметров выделяются категории:
- **volumes**: `объём_*`, `volume` …
- **throttles**: `открытие_дросселя*`, `throttle`, `orifice` …
- **pressure_thresholds**: `давление_Pmin/Pmid/Pmax*`, `Pmin` …
- **mechanics**: `пружина*`, `spring`, `stiffness` …
- **other**: всё остальное

Порядок стадий адаптируется по `signals.csv`:
- если доля сигналов `sig_group=kinematics` заметна, `mechanics` не откладывается "в самый конец".

### Метод `sensitivity`
Если есть `oed_report.json` от `oed_worker_v1_fim.py`, можно ранжировать параметры по
`sens_rms` и делать stage0 как набор, покрывающий `--top_fraction` общей чувствительности.

---

## Флаги

- `--method auto|heuristic|sensitivity`
- `--min_stage_size` — минимальный размер стадии (малые стадии будут объединяться)
- `--top_fraction` — доля суммарной чувствительности для stage0 (для sensitivity)

---

## Практические заметки

- Если staging ухудшает результат — выключите (`--param_staging off`) и сравните.
- На очень шумных данных staging лучше включать **только на финальной итерации сигналов**
  (`--staging_only_final`), чтобы не раздувать число прогонов.

