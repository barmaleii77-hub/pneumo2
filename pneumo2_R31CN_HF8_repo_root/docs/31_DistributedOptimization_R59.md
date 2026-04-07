# Distributed optimization (Ray / Dask) — Release 59

This project now supports **distributed evaluation of candidates** on multiple machines, with:

- a **single-writer Experiment DB** (SQLite or DuckDB) for:
  - deduplication (don't re-evaluate same parameters)
  - reproducibility (run_id / trial_id / hashes)
  - resume after crash
- Ray / Dask backends for evaluation workers
- optional **BoTorch qNEHVI** proposer (GPU-friendly)
- optional **Ray GPU proposer pool** (uses multiple GPUs concurrently) for faster candidate generation
- artifacts export (JSON per trial + CSV export)

> Coordinator script: `pneumo_solver_ui/tools/dist_opt_coordinator.py`

---

## Architecture

**Coordinator (single process)**

- owns the optimization loop and is the **only DB writer**
- proposes candidates (random, qNEHVI, or portfolio)
- sends candidates to evaluation workers
- receives `(y, g, metrics)` and persists to DB

**Evaluation workers (many processes, many machines)**

- run `EvaluatorCore.evaluate(trial_id, x_u)`
- return:
  - `y`: objectives vector (minimization)
  - `g`: constraints vector (`<= 0` is feasible). By default: `g = penalty - tol`
  - `row`: extra metrics dict

**DB** (`runs/expdb.sqlite` by default)

- `runs`: high-level run metadata
- `trials`: each evaluated candidate (and its status)
- `cache`: global cache (problem_hash + param_hash) -> results
- `run_metrics`: time series (e.g., hypervolume)

---

## Why single-writer DB

SQLite/DuckDB are excellent embedded DBs, but **multi-writer from many machines** is a pain.

We keep it simple and robust:

- **workers never write**
- **coordinator writes**
- if you need multi-writer at scale later → move to PostgreSQL (planned)

---

## Ray: local (one machine)

1) Install

```bat
cd pneumo_solver_ui
python -m pip install -r requirements_distributed_ray.txt
python -m pip install -r requirements_mobo_botorch.txt
```

2) Run

```bat
python tools\dist_opt_coordinator.py --backend ray --budget 200 --hv-log --proposer auto
```

### GPU proposer pool (uses all GPUs)

```bat
python tools\dist_opt_coordinator.py --backend ray --budget 200 --hv-log --proposer portfolio --ray-num-proposers 2 --device cuda
```

- each proposer is a Ray actor with `num_gpus=1`
- Ray will set `CUDA_VISIBLE_DEVICES` for each actor
- qNEHVI runs on GPU inside the proposer actor

---

## Ray: cluster (multiple machines)

### Recommended method (simple)

- Run Ray head on coordinator machine.
- Run Ray workers on all machines.
- Start coordinator script on the head machine.

Key R59 feature: **runtime_env working_dir upload**.

If you run on a remote cluster, set:

```bat
python tools\dist_opt_coordinator.py --backend ray --ray-runtime-env on
```

This uploads `pneumo_solver_ui/` to the cluster for tasks/actors.

> Excludes are controlled by `pneumo_solver_ui/.rayignore`.

### Important note about file paths

For portability:

- Prefer **relative paths** for `--model` / `--worker` / JSON configs.
- Avoid absolute paths, otherwise remote nodes won't have those files.

---

## Dask: local / cluster

Install:

```bat
cd pneumo_solver_ui
python -m pip install -r requirements_distributed_dask.txt
python -m pip install -r requirements_mobo_botorch.txt
```

Local cluster:

```bat
python tools\dist_opt_coordinator.py --backend dask --budget 200 --hv-log
```

External scheduler:

```bat
python tools\dist_opt_coordinator.py --backend dask --dask-scheduler tcp://HOST:8786
```

---

## Resume after crash

Use the same DB + same problem definition. In HF8 that problem definition also includes the explicit objective/penalty contract (`objective_keys`, `penalty_key`, `penalty_tol`), so resume/cache no longer mix runs that changed the quality function or hard gate.

```bat
python tools\dist_opt_coordinator.py --backend ray --resume --hv-log
```

- coordinator finds latest run for this `problem_hash`
- stale RUNNING trials are requeued after `--stale-ttl-sec`
- PENDING trials are picked up first

---

## Outputs

For each run in `runs/run_<run_id>/`:

- `problem_spec.json` + `problem_hash.txt` + `run_id.txt`
- `run_spec.json` (backend + cluster info)
- `progress_hv.csv` (hypervolume over time, if enabled)
- `artifacts/trials/<trial_id>.json` (one JSON per completed trial)
- `export/` directory:
  - `trials.csv`
  - `run_metrics.csv`

---

## Troubleshooting

- If the coordinator exits but workers keep running: stop Ray / Dask cluster.
- If you see a lot of cache hits: that's expected; dedup is working.
- If qNEHVI is slow: enable GPU proposers and/or increase proposer buffer.

---

## Next (planned)

- PostgreSQL experiment storage (multi-writer, multi-coordinator)
- UI page: browse runs / plot Pareto front + hypervolume
- staged optimization: cheap tests first, expensive tests later
- richer constraint modeling (multiple g components)
