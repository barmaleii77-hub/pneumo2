# Autopilot калибровки по NPZ (v19 wrapper → v18 core)

Этот README описывает **максимально автоматизированный** сценарий калибровки параметров матмодели
по NPZ‑логам, которые пишет UI.

**Рекомендуемый скрипт:** `calibration/pipeline_npz_autopilot_v19.py`
- **v19** — обёртка: если `signals.csv` не найден, делает *bootstrap* (seed) через
  `pipeline_npz_oneclick_v1.py` и получает первый `signals.csv`.
- Затем v19 запускает **основной пайплайн**: `pipeline_npz_autopilot_v18.py`.

---

## Быстрый старт

Из папки `pneumo_v7/`:

```bash
python calibration/pipeline_npz_autopilot_v19.py \
  --osc_dir <OSC_DIR> \
  --signals_csv auto \
  --run_time_align \
  --run_oed \
  --run_profile_auto \
  --run_plots \
  --run_pareto \
  --run_epsilon
```

Где `<OSC_DIR>` — папка из UI, в которой лежит:
- `tests_index.csv`
- `T01_osc.npz`, `T02_osc.npz`, ...

Результаты появятся в `calibration_runs/RUN_YYYYMMDD_HHMMSS_autopilot_v19/`.

---

## Что делает Autopilot v18 (упрощённо)

`pipeline_npz_autopilot_v18.py` запускает цепочку:

1) **Iterative signals**: `pipeline_npz_iterative_signals_v4.py`
   - строит `mapping.json` из `signals.csv`
   - делает fit по suite
   - улучшает `signals.csv` (отключает/понижает вес плохих сигналов)
   - повторяет N итераций (обычно 2)

2) **(Опционально) Smooth→sharp continuation**: `pipeline_npz_smooth_continuation_v1.py`
   - серия фитов от более гладкой динамики к более «жёсткой»

3) **(Опционально) Group balance**: `pipeline_npz_group_balance_v3.py`
   - адаптивно подбирает веса групп (`sig_group`), чтобы не «перетягивать» одну группу

4) **(Опционально) Param prune**: `param_prune_v1.py`
   - отбрасывает параметры, которые упираются в границы и/или слабо наблюдаемы

5) **(Опционально) Time alignment**: `time_align_v1.py`
   - оценивает постоянную задержку `time_shift_s` (per-signal / per-group / global)
   - делает refit с учётом найденного сдвига

6) **(Опционально) OED/FIM**: `oed_worker_v1_fim.py`
   - оценивает информативность параметров и тестов (FIM/сенситивность)

7) **(Опционально) Profile likelihood**: `profile_worker_v1_likelihood.py`
   - проверяет идентифицируемость выбранных параметров

8) **(Опционально) Trade-off**
   - Pareto sweep и ε‑constraint для выбора компромисса по группам/целям

9) **Полный отчёт**: `report_full_from_run_v1.py` → `REPORT_FULL.md`

---

## Bootstrap (seed) в v19

Если `--signals_csv auto` не смог найти `signals.csv`:

- v19 запускает `pipeline_npz_oneclick_v1.py` в `out_dir/bootstrap_oneclick_seed/`.
- `oneclick` генерирует mapping эвристикой по NPZ (`npz_autosuggest_mapping_v2.py`), делает первый fit
  и создаёт `signals.csv`.
- дальше запускается v18 уже «по-настоящему», используя этот `signals.csv`.

Отключить bootstrap можно флагом `--no_bootstrap`.

---

## Практические рекомендации

- Для реальных логов почти всегда стоит включать `--run_time_align` (задержки датчиков/логгера).
- Если видите «неровную» сходимость — включайте continuation (в v18 это флаг `--run_smooth_continuation`).
- Если модель «подгоняет» одну группу сигналов за счёт другой — включайте group balance (`--run_group_balance`, стратегия `minimax` обычно самая безопасная).



---

## Глобальная инициализация (DE / surrogate / CEM)

Важный рычаг качества и скорости: перед локальным `least_squares` можно включить глобальную инициализацию, чтобы найти более удачные старты.

В Autopilot v18 это управляется флагами:
- `--coarse_global_init {none|de|surrogate|cem}` — для **coarse** шага (быстрого)
- `--global_init {none|de|surrogate|cem}` — для основного fit
- `--group_balance_global_init {none|de|surrogate|cem}` — для шага балансировки групп

Рекомендации:
- `surrogate` — обычно лучший компромисс «качество/время» (RF/GP суррогат + LCB).
- `cem` — полезен, когда суррогат «теряется» (сложная, разрывная поверхность SSE) или когда нужны **устойчивые** старты без доп. зависимостей.
- `de` — надёжно, но часто дороже по числу оценок.

Пример:
```bash
python calibration/pipeline_npz_autopilot_v19.py --osc_dir <OSC_DIR> --signals_csv auto --coarse_global_init cem --global_init cem --run_time_align
```
