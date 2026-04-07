# RELEASE NOTES — R59 (2026‑01‑26)

This release focuses on **distributed multi-objective optimization** stability & integration.

## Major changes

### 1) Fixed: broken integration between coordinator and ExperimentDB

Previous packages contained an inconsistent API between:

- `tools/dist_opt_coordinator.py`
- `pneumo_dist/expdb.py`
- `pneumo_dist/hv_tools.py` / `pneumo_dist/mobo_propose.py`

R59 aligns all interfaces, adds missing DB methods, and ensures the coordinator can:

- create/resume runs
- reserve trials with dedup + cache
- track PENDING/RUNNING/DONE/ERROR states
- compute hypervolume and log to DB
- export results to CSV

### 2) New: GPU pool for proposers (Ray)

When using the Ray backend you can start one or more proposer actors with GPU resources:

- each actor runs qNEHVI / portfolio propose
- evaluation actors still run on CPU

This allows using **multiple GPUs simultaneously** on the proposer side.

### 3) New: per-trial artifacts

Each completed trial produces a JSON artifact:

`runs/run_<run_id>/artifacts/trials/<trial_id>.json`

It contains x_u, params, y, g, metrics, status.

### 4) Safer portability: relative paths + Ray runtime_env support

Coordinator uses **portable problem_hash** (paths resolved relative to `pneumo_solver_ui/`), and supports shipping code to a Ray cluster using `runtime_env.working_dir` + `.rayignore`.

## How to run (quick)

```bat
cd pneumo_solver_ui
python -m pip install -r requirements_distributed_ray.txt
python -m pip install -r requirements_mobo_botorch.txt
python tools\dist_opt_coordinator.py --backend ray --hv-log --budget 200 --proposer portfolio --ray-num-proposers 2
```

More detail: `docs/31_DistributedOptimization_R59.md`.

## Known limitations

- ExperimentDB is **single-writer** by design (coordinator only).
- SQLite on network shares can be problematic; prefer local DB + coordinator machine.
- For multi-coordinator / multi-writer: plan PostgreSQL storage.

## Next

- PostgreSQL experiment storage + robust distributed locking
- UI browse runs / plot pareto / HV chart
- staged optimization (cheap tests first)
