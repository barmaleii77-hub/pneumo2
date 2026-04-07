# R58 — Distributed Optimization (Ray / Dask + Experiment DB)

## What this adds

Release 58 adds a **distributed evaluation layer** for multi-factor optimization:

- **Ray or Dask agents** to evaluate candidates on multiple computers.
- **Single experiment DB** (SQLite or DuckDB) for:
  - deduplication (no repeated evaluation of the same parameters),
  - resumability,
  - reproducibility.
- **Smarter hypervolume monitoring**:
  - objective normalization (robust quantile scaling),
  - dynamic / robust reference point for HV.
- **Optional BoTorch proposer** (qNEHVI, constrained) that can run on **GPU**.

Everything is implemented as an *add-on* layer that reuses the existing:
- `model_*.py` physics model
- `opt_worker_v3_margins_energy.py` evaluation logic

so that the results are comparable to local runs.

---

## Key files

### Coordinator

- `pneumo_solver_ui/tools/dist_opt_coordinator.py`

This is the **single-writer** process:
- proposes candidates (random LHS warmup → optional qNEHVI)
- writes to DB
- dispatches evaluation tasks to Ray/Dask workers
- tracks progress and exports CSV/JSON summaries

### Workers (evaluation)

- `pneumo_solver_ui/pneumo_dist/eval_core.py`

Each Ray actor / Dask worker runs `EvaluatorCore`, which:
- loads the model module from a file path
- maps `x_u ∈ [0,1]^d` into a concrete `params` dict using current ranges
- calls `eval_candidate(...)` from the existing worker

### Experiment DB

- `pneumo_solver_ui/pneumo_dist/expdb.py`

Tables:
- `runs`
- `trials`
- `cache` (dedup across runs)
- `run_metrics` (HV progress, etc.)

The DB is **single-writer by design** (coordinator only). Workers do **not** touch the DB.

Supported engines:
- SQLite (`sqlite3`, stdlib)
- DuckDB (`duckdb`, optional)

### Hypervolume and normalization

- `pneumo_solver_ui/pneumo_dist/hv_tools.py`

Provides:
- Pareto filtering for minimization
- objective normalization (quantile scaling)
- robust ref-point inference for HV

### Optional MOBO proposer

- `pneumo_solver_ui/pneumo_dist/mobo_propose.py`

If `torch + botorch + gpytorch` are installed, coordinator can run:
- constrained qNEHVI candidate selection
- with `X_pending` to avoid proposing points that are already in flight

---

## Why single-writer DB

### SQLite
SQLite WAL gives better reader/writer concurrency (readers don’t block writer and vice versa) but still has **one writer at a time**.

Docs:
- https://sqlite.org/wal.html

### DuckDB
DuckDB supports concurrency within a single process, but with a *single writer process* for persistent DBs.

Docs:
- https://duckdb.org/docs/stable/connect/concurrency.html

**Therefore**: we keep DB writes in coordinator only. Workers evaluate candidates and return results back to coordinator.

---

## How to run (Windows)

> Recommended workflow: start a cluster (Ray or Dask) and run the coordinator from your main PC.

### 1) Install optional dependencies

- `INSTALL_OPTIONAL_DISTRIBUTED_RAY_WINDOWS.bat`
- `INSTALL_OPTIONAL_DISTRIBUTED_DASK_WINDOWS.bat`
- `INSTALL_OPTIONAL_MOBO_BOTORCH_WINDOWS.bat` (optional)

### 2) Run locally on one PC (quick start)

- `RUN_DISTRIBUTED_RAY_LOCAL_WINDOWS.bat`

This will:
- try to connect to an existing Ray cluster
- if none is found, start a local `ray.init()` and run locally

### 3) Run on multiple PCs (Ray)

**On head node** (main PC):

1. Run:
   - `RAY_START_HEAD_WINDOWS.bat`
2. Note the printed address (IP:PORT).

**On each worker PC**:

1. Run:
   - `RAY_START_WORKER_WINDOWS.bat`
2. Enter head address when asked.

**Back on head PC**:

Run coordinator:

```bat
cd pneumo_solver_ui
python tools\dist_opt_coordinator.py --backend ray --ray-address auto --budget 500 --db ..\runs\exp.sqlite
```

### GPU usage (Ray)

Ray supports requesting GPUs per task/actor using `num_gpus=...`, and will set `CUDA_VISIBLE_DEVICES` for that process.

Docs:
- https://docs.ray.io/en/latest/ray-core/scheduling/accelerators.html
- https://docs.ray.io/en/latest/ray-core/api/doc/ray.get_gpu_ids.html

In this release:
- evaluation actors are CPU by default (physics sim)
- MOBO proposer can be GPU (if BoTorch installed)

---

## Dask mode

Start a scheduler and workers, then run coordinator with `--backend dask`.

Docs:
- Futures + as_completed: https://docs.dask.org/en/latest/futures.html
- Worker plugins: https://distributed.dask.org/en/stable/plugins.html

---

## Hypervolume monitoring details

Problems:
- objectives are in very different scales (seconds vs m/s² vs microjoules)
- HV is very sensitive to scaling and reference point

What we do:

1) **Robust objective normalization** using quantiles (default 10–90%).
2) **Reference point** computed as "worse-than-observed" per objective (in normalized space).

This makes HV progress a lot more stable and comparable between runs.

---

## Resume / reproducibility

Coordinator writes:
- `runs/<run_id>/spec.json` (problem + objective keys + normalization config)
- `runs/<run_id>/progress.csv` (HV progress)
- `runs/<run_id>/trials_export.csv` (export)

DB stores:
- a stable `problem_hash`
- a stable `param_hash` per candidate

This enables:
- resume without duplicated evaluation
- compare runs that share the same problem hash

---

## Next improvements (planned)

- Add UI page for reading the experiment DB and plotting HV/Pareto.
- Add optional per-worker local JSON artifact writing (for crash recovery in multi-node).
- Add distributed "portfolio" proposer (random + qNEHVI + local search).
- Add advanced scheduling strategies (Ray placement groups, node affinity).
