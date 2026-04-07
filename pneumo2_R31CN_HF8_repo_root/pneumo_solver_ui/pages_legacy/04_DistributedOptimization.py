# -*- coding: utf-8 -*-
"""Streamlit page: Distributed Optimization (R57)

Read-only monitor for ExperimentDB produced by:
- tools/run_ray_distributed_opt.py
- tools/run_dask_distributed_opt.py

This page does not require Ray/Dask, only `pneumo_dist.expdb`.

"""

from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
import streamlit as st
from pneumo_solver_ui.streamlit_compat import safe_set_page_config

from pneumo_solver_ui.ui_bootstrap import bootstrap
from pneumo_solver_ui.ui_persistence import autosave_if_enabled

bootstrap(st)
autosave_if_enabled(st)

try:
    import pandas as pd  # type: ignore
except Exception:  # pragma: no cover
    pd = None

import matplotlib.pyplot as plt


REPO_ROOT = Path(__file__).resolve().parents[2]

# Ensure repo root is importable (fixes ModuleNotFoundError in multipage/pages)
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _find_db_paths() -> List[Path]:
    candidates: List[Path] = []
    for p in (REPO_ROOT / "runs" / "dist_runs").glob("**/experiments.*"):
        if p.suffix.lower() in {".sqlite", ".db", ".sqlite3", ".duckdb"}:
            candidates.append(p)
    # newest first
    candidates.sort(key=lambda x: x.stat().st_mtime, reverse=True)
    return candidates


def _safe_float(x: Any) -> float:
    try:
        return float(x)
    except Exception:
        return float("nan")


def main() -> None:
    safe_set_page_config(page_title="Distributed Optimization", layout="wide")
    st.title("Distributed Optimization (ExperimentDB)")

    try:
        from pneumo_solver_ui.pneumo_dist.expdb import ExperimentDB
    except ModuleNotFoundError:
        from pneumo_dist.expdb import ExperimentDB
    try:
        from pneumo_solver_ui.pneumo_dist.hv_tools import pareto_front_2d_max
    except ModuleNotFoundError:
        from pneumo_dist.hv_tools import pareto_front_2d_max

    db_paths = _find_db_paths()
    if not db_paths:
        st.info("DB не найдена. Запусти distributed runner -> появится runs/dist_runs/*/experiments.sqlite|duckdb")
        return

    sel = st.selectbox("Experiment DB", options=[str(p) for p in db_paths], index=0)
    db_path = Path(sel)

    db = ExperimentDB(str(db_path))
    db.connect(); db.init_schema()

    runs = db.list_runs(limit=50)
    if not runs:
        st.warning("В DB нет записей runs")
        return

    run_ids = [str(r.get("run_id")) for r in runs]
    run_id = st.selectbox("Run", options=run_ids, index=0)

    # Run meta
    run_row = next((r for r in runs if str(r.get("run_id")) == run_id), None)
    with st.expander("Run meta", expanded=False):
        st.json(run_row or {})

    # Status counts
    st.subheader("Status")
    st.json(db.count_status(run_id))

    # Metrics timeseries
    st.subheader("Progress")
    metrics = db.fetch_metrics(run_id, limit=50000)
    if metrics:
        rows = []
        for m in metrics:
            rows.append({
                "completed": int(m.get("completed", 0) or 0),
                "hypervolume": _safe_float(m.get("hypervolume")),
                "best_obj1": _safe_float(m.get("best_obj1")),
                "best_obj2": _safe_float(m.get("best_obj2")),
                "n_feasible": int(m.get("n_feasible", 0) or 0),
            })
        if pd is not None:
            df = pd.DataFrame(rows).sort_values("completed")
            df = df.drop_duplicates(subset=["completed"], keep="last")
            df = df.set_index("completed")
            col1, col2 = st.columns(2)
            with col1:
                st.line_chart(df[["hypervolume"]])
            with col2:
                st.line_chart(df[["best_obj1", "best_obj2", "n_feasible"]])
        else:
            st.dataframe(rows)
    else:
        st.info("run_metrics пусто (ещё не было тиков или run слишком маленький)")

    # Dataset + Pareto
    st.subheader("Pareto (feasible)")
    X_u, Y_min, pen = db.fetch_dataset_arrays(run_id)
    feasible_tol = st.number_input("feasible_tol", value=1e-9, format="%.3e")

    if Y_min.size:
        feas = np.isfinite(pen) & (pen <= float(feasible_tol))
        if np.any(feas):
            Y_max = -Y_min[feas]
            P = pareto_front_2d_max(Y_max)
            Yp_min = -P
            st.write(f"feasible: {int(np.sum(feas))} / {int(len(pen))}")

            fig, ax = plt.subplots()
            ax.scatter(Yp_min[:, 0], Yp_min[:, 1], s=12)
            ax.set_xlabel("obj1 (min)")
            ax.set_ylabel("obj2 (min)")
            ax.grid(True, alpha=0.3)
            st.pyplot(fig, clear_figure=True)
        else:
            st.warning("Нет feasible точек по текущему feasible_tol")
            fig, ax = plt.subplots()
            ax.scatter(Y_min[:, 0], Y_min[:, 1], s=8)
            ax.set_xlabel("obj1 (min)")
            ax.set_ylabel("obj2 (min)")
            ax.grid(True, alpha=0.3)
            st.pyplot(fig, clear_figure=True)
    else:
        st.info("Пока нет результатов")

    # Trials table
    st.subheader("Trials (latest)")
    limit = st.slider("limit", min_value=50, max_value=5000, value=200, step=50)
    trials = db.fetch_trials(run_id, limit=int(limit))
    st.dataframe(trials, width='stretch')


if __name__ == "__main__":
    main()
