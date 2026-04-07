# Release Notes – v6.33 pack (base v6.32)

Date: 2026-01-30

This pack is the next engineering step for **UnifiedPneumoApp** focusing on:
- making optimization continuous and reusable;
- staging + promotion (multi-fidelity);
- ensuring scenarios (mass/temperature) actually affect the model;
- speeding up world-road simulations.

## Key changes

### 1) Staged runner: correct ranking + robust warmstart
- Fixed metric name mismatch (energy column) between worker and stage runner.
- Error filtering now supports both `ошибка` and `error` columns.
- Warmstart from global archive and surrogate now tolerates **partial parameter coverage**.

### 2) Multi-fidelity promotion
- Stage runner now generates **seed points** for each stage:
  - promoted leaders from the previous stage;
  - best points from the global archive.
- Seeds are passed to the worker via `--seed_points_json`.

### 3) Model: scenarios and caching
- `добавочная_масса_кг` now affects body mass (`масса_рамы`).
- `T_AIR_К` now overrides the isothermal air temperature used by pneumatic flow equations.
- Added memory + disk cache for world-road precompute (`WORLDROAD_CACHE_DIR`).

### 4) UI improvements
- If the same `problem_hash` exists in another run folder, the UI resumes it automatically.
- `baseline_best.json` is auto-loaded as initial baseline (can be disabled in code if needed).

## Changed files
See `diffs/changed_files.txt`.

## Patch
See `diffs/v6_32_to_v6_33.patch`.
