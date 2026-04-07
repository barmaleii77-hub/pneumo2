# RELEASE_NOTES_R60

## Summary

Release 60 adds a production-oriented, multi-PC distributed evaluation mode:

- **ExperimentDB now supports PostgreSQL** (`engine=postgres`).
- New **DBQueue pull architecture**:
  - `tools/dbqueue_coordinator.py` fills a queue of `PENDING` trials.
  - `tools/dbqueue_agent.py` runs on any number of machines, claims tasks and writes results back.
- Added **HVMonitor** for more stable HV logging with optional freeze of normalizer/reference point.
- `tools/dist_opt_coordinator.py` now supports `--db-engine postgres` (DSN in `--db`) correctly.

## Why this matters

Ray/Dask are great for cluster scheduling (push mode), but a shared DB + pull agents is:
- extremely simple to deploy (copy code to machines, point to DB),
- resilient (agents can die/restart; coordinator can requeue stales),
- scalable (Postgres handles concurrent writers; no single coordinator bottleneck for evaluation).

## Main files added/changed

### New
- `pneumo_solver_ui/tools/dbqueue_coordinator.py`
- `pneumo_solver_ui/tools/dbqueue_agent.py`
- `pneumo_solver_ui/requirements_experiment_db_postgres.txt`
- `INSTALL_OPTIONAL_POSTGRES_WINDOWS.bat`
- `RUN_DBQUEUE_COORDINATOR_WINDOWS.bat`
- `RUN_DBQUEUE_AGENT_WINDOWS.bat`

### Changed
- `pneumo_solver_ui/pneumo_dist/expdb.py` (postgres engine + claim_pending)
- `pneumo_solver_ui/pneumo_dist/hv_tools.py` (HVMonitor)
- `pneumo_solver_ui/tools/dist_opt_coordinator.py` (postgres DB target handling)

## Compatibility

- Existing SQLite/DuckDB workflows continue to work.
- Postgres is optional.

## Next

- UI page for distributed run monitoring (browse runs, plot Pareto/HV).
- Optional: agent-side staged evaluation (cheap tests first).
- Better multi-coordinator logic (sharding) for very large budgets.
