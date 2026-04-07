# 32_DBQueue_Postgres_R60

## Why DBQueue

Ray/Dask are great for “push” scheduling (coordinator submits tasks). However for **multiple computers** you often want:

- minimal orchestration,
- easy horizontal scaling (just start more workers),
- stable de-duplication + reproducibility,
- a single “source of truth” for trial states.

DBQueue implements a **pull model**:

```
DB (ExperimentDB) is the rendezvous point

coordinator ----> inserts PENDING trials
agent(s)  <---- claim PENDING (atomic), evaluate, write DONE/ERROR
```

This works with SQLite/DuckDB on a single workstation, but **for multi-PC you should use PostgreSQL**.

## Components

- `pneumo_solver_ui/pneumo_dist/expdb.py`
  - engine: sqlite / duckdb / postgres
  - `claim_pending` implements atomic “take one job” semantics
- `pneumo_solver_ui/tools/dbqueue_coordinator.py`
  - maintains `PENDING+RUNNING >= target_inflight`
  - uses BO (qNEHVI) when enough DONE trials exist
  - logs/export/hv
- `pneumo_solver_ui/tools/dbqueue_agent.py`
  - claims one trial
  - runs evaluation
  - writes results back

## PostgreSQL setup (recommended)

### Option A: Docker (fastest)

Create a `docker-compose.yml` like:

```yaml
services:
  postgres:
    image: postgres:16
    environment:
      POSTGRES_USER: pneumo
      POSTGRES_PASSWORD: pneumo
      POSTGRES_DB: pneumo
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
volumes:
  pgdata:
```

Then:

```bash
docker compose up -d
```

### Option B: Native install

Install PostgreSQL on a machine reachable by all worker PCs.

## Python deps

Install the optional driver:

```bat
INSTALL_OPTIONAL_POSTGRES_WINDOWS.bat
```

(or `pip install -r pneumo_solver_ui/requirements_experiment_db_postgres.txt`)

## Running the system

### 1) Start coordinator

```bat
python pneumo_solver_ui\tools\dbqueue_coordinator.py \
  --db-engine postgres \
  --db postgresql://user:pass@HOST:5432/pneumo \
  --target-inflight 256 \
  --budget 2000 \
  --export-every 25 \
  --hv-log
```

The coordinator prints a `RUN_ID`.

### 2) Start agents (on many PCs)

On each worker machine:

```bat
python pneumo_solver_ui\tools\dbqueue_agent.py \
  --db-engine postgres \
  --db postgresql://user:pass@HOST:5432/pneumo \
  --run-id <RUN_ID> \
  --worker-tag <MACHINE_NAME>
```

Start as many agents as you like. Each agent can run 1 process per CPU-core or 1 process per GPU (your choice).

## Operational notes

### Avoiding stale RUNNING tasks

- `dbqueue_coordinator.py` periodically calls `requeue_stale()` to move old `RUNNING` back to `PENDING`.
- `dbqueue_agent.py` heartbeats while evaluating.

### Where are results?

- DB contains all trials + cache.
- Coordinator exports CSV snapshots (and HV metrics) into `runs/run_<RUN_ID>/`.

### When to use Ray/Dask instead

Use `dist_opt_coordinator.py` if you want:
- remote execution with Ray/Dask without a DB-writer in each worker
- convenient resource scheduling with `num_cpus`/`num_gpus`

DBQueue is simpler when you want “start more worker processes and go”.
