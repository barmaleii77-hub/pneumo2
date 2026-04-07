# AlgOpt v6.33 (base v6.32) – Staged Promotion Seeds + WorldRoad Cache + Robust Resume

This note documents the engineering changes made in this pack.

## What problem it solves

1) **“Optimization starts from scratch again”**
- Even when there are already computed results, users often create a new run name,
  and the system would create a new run directory.
- Result: the staged pipeline would not reuse the existing stage CSVs, and the worker
  would need to re-explore.

✅ **Fix:** the UI now resolves an existing `prob_<problem_hash>` directory anywhere
under `workspace/opt_runs/*/` and continues there. If the user typed a new run name,
we write an `ALIASED_TO.txt` file in the requested folder.

2) **Wrong best-candidate selection due to column mismatch**
- Worker writes `ошибка` + energy metric `метрика_энергия_дроссели_микро_Дж`.
- Stage runner previously looked at `error` + `метрика_энергия__J`, which can cause:
  - wrong “best”,
  - incorrect baseline promotion,
  - misleading leaderboards.

✅ **Fix:** stage runner ranking accepts both error column names and supports energy
fallback keys.

3) **Scenario parameters not affecting the physics**
- Stage runner scenarios already changed:
  - `добавочная_масса_кг` (passengers / cargo)
  - `T_AIR_К` (air temperature)
- But the model did not use them.

✅ **Fix:**
- `m_body = масса_рамы + добавочная_масса_кг`
- `T_AIR` is now overridden per simulation from `T_AIR_К` / `температура_воздуха_К`.

4) **Slow repeated WorldRoad precompute**
- Precomputing a “world road” (surface + vehicle kinematics → wheel trajectories)
  is expensive and was repeated for every candidate.

✅ **Fix:**
- In-memory LRU cache per process.
- Optional disk cache (`WORLDROAD_CACHE_DIR`) storing `WorldRoadCache` as `.npz`.
- Stage runner automatically sets `WORLDROAD_CACHE_DIR` to `workspace/cache/worldroad`.

5) **Better multi-stage continuity**
- Stage runner now writes a `seed_points.json` per stage.
- The worker already supports `--seed_points_json`.

✅ **Fix:**
- Stage N receives promoted seed points from:
  - best of Stage N-1,
  - best from global archive.

This behaves like an “ASHA-style promotion” layer on top of CEM + guided mutation.

## Key files changed

- `pneumo_solver_ui/opt_stage_runner_v1.py`
  - scoring fix
  - partial warmstart (`PNEUMO_WARMSTART_MIN_COVERAGE`)
  - seed promotion (`seed_points.json` → `--seed_points_json`)
  - default `PNEUMO_GUIDED_MODE=auto`
  - sets `WORLDROAD_CACHE_DIR`

- `pneumo_solver_ui/model_pneumo_v9_mech_doublewishbone_worldroad.py`
  - scenario temperature and mass applied
  - worldroad precompute cache (RAM + disk)

- `pneumo_solver_ui/pneumo_ui_app.py`
  - resume by `problem_hash` across run names
  - autoload `workspace/baselines/baseline_best.json`

- `TODO.md`
  - updated roadmap

## Environment knobs

- `PNEUMO_WARMSTART_MIN_COVERAGE` (default: 0.6)
  - How much of the current parameter vector must exist in an archive record
    for that record to be used for warmstart / surrogate.

- `WORLDROAD_CACHE_DIR` (auto set by stage runner)
  - If set, the model will load/save precomputed `WorldRoadCache` to disk.

- `WORLDROAD_CACHE_MAX_ITEMS` (default: 8)
  - In-memory per-process cache size.

## Practical usage notes

- To **reuse all previous optimization work**, keep your test suite + ranges stable.
  Even if you change the run name, the UI will find the existing `prob_<hash>`.
- To **introduce a new suite** (new road/maneuver profiles), expect a new `problem_hash`.
  You still reuse history through the global archive + surrogate warmstart.

