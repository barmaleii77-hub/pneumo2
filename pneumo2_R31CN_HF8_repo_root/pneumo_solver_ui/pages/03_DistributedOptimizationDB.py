"""
Streamlit page: Distributed Experiments DB viewer.

Shows runs, trials, metrics (HV over time) from experiments.duckdb/.sqlite.
"""

import os
import sys
import json
import pandas as pd
import streamlit as st
from pneumo_solver_ui.ui_bootstrap import bootstrap
from pneumo_solver_ui.ui_persistence import autosave_if_enabled

bootstrap(st)
autosave_if_enabled(st)

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJ_DIR = os.path.abspath(os.path.join(_THIS_DIR, ".."))
if _PROJ_DIR not in sys.path:
    sys.path.insert(0, _PROJ_DIR)

from pneumo_dist.expdb import ExperimentDB



st.title("Distributed Experiments DB (DuckDB/SQLite)")

db_path = st.text_input("DB path (experiments.duckdb / .sqlite)", value=os.path.join(_PROJ_DIR, "runs_distributed", "experiments.duckdb"))
if not db_path:
    st.stop()
if not os.path.exists(db_path):
    st.warning("DB file not found. Provide a valid path.")
    st.stop()

db = ExperimentDB(db_path)

runs = db._exec("SELECT run_id, created_ts, config_json FROM runs ORDER BY created_ts DESC;")
if not runs:
    st.info("No runs in DB yet.")
    st.stop()

df_runs = pd.DataFrame(runs, columns=["run_id", "created_ts", "config_json"])
st.subheader("Runs")
st.dataframe(df_runs, width="stretch")

run_id = st.selectbox("Select run_id", df_runs["run_id"].tolist(), index=0)

st.subheader("Trials (head)")
trials = db._exec(
    "SELECT trial_id,status,source,created_ts,started_ts,ended_ts,obj1,obj2,penalty,worker,error FROM trials WHERE run_id=? ORDER BY trial_id DESC LIMIT 500;",
    (run_id,),
)
df_trials = pd.DataFrame(trials, columns=["trial_id","status","source","created_ts","started_ts","ended_ts","obj1","obj2","penalty","worker","error"])
st.dataframe(df_trials, width="stretch", height=360)

st.subheader("Metrics (HV over time)")
metrics = db.list_metrics(run_id)
if metrics:
    df_m = pd.DataFrame(metrics, columns=["ts","hv_norm","n_done","n_feasible","note"])
    st.line_chart(df_m.set_index("ts")[["hv_norm"]])
    st.dataframe(df_m.tail(200), width="stretch", height=220)
else:
    st.info("No metrics yet.")

db.close()
