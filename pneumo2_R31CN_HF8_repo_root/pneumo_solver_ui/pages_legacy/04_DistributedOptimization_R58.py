# -*- coding: utf-8 -*-
"""Streamlit page: Distributed Optimization (Release 58).

This page is intentionally minimal.
We do NOT start/stop clusters from Streamlit (process lifecycle & multi-host).
Instead we:
- provide copy-paste commands / batch files
- show ExperimentDB summary when available
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st
from pneumo_solver_ui.streamlit_compat import safe_set_page_config

from pneumo_solver_ui.ui_bootstrap import bootstrap
from pneumo_solver_ui.ui_persistence import autosave_if_enabled

bootstrap(st)
autosave_if_enabled(st)

try:
    import pandas as pd
except Exception:  # pragma: no cover
    pd = None  # type: ignore

try:
    from pneumo_dist.expdb import ExperimentDB
except Exception:
    ExperimentDB = None  # type: ignore


safe_set_page_config(page_title="Distributed Optimization (R58)", layout="wide")

st.title("Distributed Optimization (Release 58)")

st.markdown(
    """
This release adds:

- **Ray / Dask distributed evaluation** of candidates (multi-PC).
- **Single experiment DB** (SQLite / DuckDB) for deduplication and resumability.
- Smarter **hypervolume monitoring** with objective normalization.
- Optional **BoTorch qNEHVI** proposer (can use GPU for the surrogate / acquisition optimization).

Main entry point:
- `pneumo_solver_ui/tools/dist_opt_coordinator.py`

Docs:
- `docs/30_DistributedOptimization_R58.md`
"""
)

st.subheader("One-click (Windows)")

st.code(
    """# 1) Install base deps
INSTALL_WINDOWS.bat

# 2) Choose one distributed backend
INSTALL_OPTIONAL_RAY_WINDOWS.bat
# or
INSTALL_OPTIONAL_DASK_WINDOWS.bat

# 3) Optional: BoTorch proposer
INSTALL_OPTIONAL_BOTORCH_WINDOWS.bat

# 4) Run local distributed (single PC)
RUN_DISTRIBUTED_RAY_LOCAL_WINDOWS.bat
# or
RUN_DISTRIBUTED_DASK_LOCAL_WINDOWS.bat
""",
    language="text",
)

st.subheader("Multi-PC (Ray)")
st.code(
    """# On the HEAD machine:
RAY_START_HEAD_WINDOWS.bat

# On each WORKER machine:
RAY_START_WORKER_WINDOWS.bat  # edit HEAD_IP

# Then on the head (or any machine with access to project folder):
RUN_DISTRIBUTED_RAY_LOCAL_WINDOWS.bat
""",
    language="text",
)

st.subheader("Experiment DB status")

base_dir = Path(__file__).resolve().parents[1]
runs_dir = base_dir / "runs"
db_sqlite = runs_dir / "experiments.sqlite"
db_duckdb = runs_dir / "experiments.duckdb"

st.write(f"Runs dir: `{runs_dir}`")

if not runs_dir.exists():
    st.info("No runs directory yet. Start a distributed run and it will be created.")
else:
    st.write("Files:")
    st.code("\n".join(sorted([p.name for p in runs_dir.glob('*')])) or "(empty)", language="text")

if ExperimentDB is None:
    st.warning("ExperimentDB module not importable (missing files or dependencies).")
else:
    db_path = None
    engine = None
    if db_sqlite.exists():
        db_path = db_sqlite
        engine = "sqlite"
    elif db_duckdb.exists():
        db_path = db_duckdb
        engine = "duckdb"

    if db_path is None:
        st.info("No experiment DB found yet (runs/experiments.sqlite or runs/experiments.duckdb).")
    else:
        st.success(f"Found DB: {db_path.name} (engine={engine})")
        try:
            db = ExperimentDB(db_path, engine=engine)
            runs = db.list_runs(limit=30)
            if not runs:
                st.info("DB is empty (no runs yet).")
            else:
                if pd is not None:
                    st.dataframe(pd.DataFrame(runs))
                else:
                    st.json(runs)
        except Exception as e:
            st.error(f"Failed to open DB: {e}")
