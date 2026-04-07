# NPZ schema (pneumo_npz_v1)

Файл NPZ используется для:
- Desktop Animator
- Calibration / Autopilot / сравнение прогонов

Экспорт выполняется модулем:
- `pneumo_solver_ui/npz_bundle.py`

## Ключи в NPZ

### Обязательные
- `main_cols` : 1D array строк — имена колонок `df_main`
- `main_values` : 2D array float `[N, M]` — значения `df_main`
- `meta_json` : строка JSON с метаданными

### Опциональные (если available)
- `p_cols`, `p_values` : давления по узлам/линиям
- `q_cols`, `q_values` : расходы (mdot)
- `open_cols`, `open_values` : степени открытия клапанов/состояния

## Pointer для follow‑режима

`workspace/exports/anim_latest.json` содержит:
```json
{
  "npz_path": "anim_latest.npz",
  "updated_utc": "2026-01-27T12:34:56+00:00",
  "meta": {
    "test_name": "...",
    "cache_key": "..."
  }
}
```

Desktop Animator в режиме `--follow` читает pointer и автоматически перезагружает NPZ при изменениях.
