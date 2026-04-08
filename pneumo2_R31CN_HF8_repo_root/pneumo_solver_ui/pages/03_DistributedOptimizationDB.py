"""Legacy Streamlit page: Distributed Experiments DB viewer."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st
from pneumo_solver_ui.distributed_expdb_viewer_helpers import (
    find_expdb_paths,
    flatten_trial_rows,
    load_packaging_params_for_run,
    safe_float,
)
from pneumo_solver_ui.packaging_surface_helpers import enrich_packaging_surface_df
from pneumo_solver_ui.packaging_surface_ui import (
    apply_packaging_surface_filters,
    packaging_surface_result_columns,
    render_packaging_surface_metrics,
)
from pneumo_solver_ui.ui_bootstrap import bootstrap
from pneumo_solver_ui.ui_persistence import autosave_if_enabled

try:
    import pandas as pd  # type: ignore
except Exception:  # pragma: no cover
    pd = None


bootstrap(st)
autosave_if_enabled(st)

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _default_db_path() -> str:
    candidates = find_expdb_paths(REPO_ROOT)
    if candidates:
        return str(candidates[0])
    return str(REPO_ROOT / "runs_distributed" / "experiments.duckdb")


def main() -> None:
    st.title("Distributed Experiments DB")
    st.caption("Legacy DB viewer now uses the current ExperimentDB API and the shared packaging verdict surface.")

    try:
        from pneumo_solver_ui.pneumo_dist.expdb import ExperimentDB
    except ModuleNotFoundError:
        from pneumo_dist.expdb import ExperimentDB

    db_path_text = st.text_input(
        "DB path (experiments.duckdb / .sqlite)",
        value=_default_db_path(),
    ).strip()
    if not db_path_text:
        st.stop()

    db_path = Path(db_path_text)
    if not db_path.exists():
        st.warning("DB file not found. Provide a valid path.")
        st.stop()

    db = ExperimentDB(str(db_path))
    db.init_schema()
    try:
        runs = db.list_runs(limit=200)
        if not runs:
            st.info("No runs in DB yet.")
            return

        if pd is None:
            st.warning("pandas is required for the distributed DB viewer.")
            return

        rows = []
        for run in runs:
            rows.append(
                {
                    "run_id": str(run.get("run_id") or ""),
                    "created_ts": run.get("created_ts"),
                    "problem_hash": str(run.get("problem_hash") or ""),
                    "state": db.get_run_state(str(run.get("run_id") or "")),
                }
            )
        df_runs = pd.DataFrame(rows)
        st.subheader("Runs")
        st.dataframe(df_runs, width="stretch")

        run_ids = df_runs["run_id"].tolist()
        run_id = st.selectbox("Select run_id", run_ids, index=0)
        run_detail = db.get_run(run_id) or {}
        run_spec = dict(run_detail.get("spec") or {}) if isinstance(run_detail.get("spec"), dict) else {}
        run_cfg = dict(run_spec.get("cfg") or {}) if isinstance(run_spec.get("cfg"), dict) else {}
        objective_keys = [
            str(x).strip()
            for x in list(run_cfg.get("objective_keys") or [])
            if str(x).strip()
        ]
        penalty_key = str(run_cfg.get("penalty_key") or "штраф_физичности_сумма")
        packaging_params = load_packaging_params_for_run(db, run_id, db_path, REPO_ROOT)

        with st.expander("Run details", expanded=False):
            st.json(
                {
                    "run_detail": run_detail,
                    "resolved_packaging_params": {
                        key: packaging_params.get(key)
                        for key in (
                            "autoverif_spring_host_min_clearance_m",
                            "autoverif_spring_pair_min_clearance_m",
                            "autoverif_spring_cap_min_margin_m",
                            "autoverif_midstroke_t0_max_error_m",
                            "autoverif_coilbind_min_margin_m",
                        )
                        if key in packaging_params
                    },
                }
            )

        st.subheader("Status counts")
        st.json(db.count_by_status(run_id))

        st.subheader("Metrics")
        metrics = db.fetch_metrics(run_id, limit=5000)
        if metrics:
            metric_rows = []
            for metric in metrics:
                blob = dict(metric.get("json") or {}) if isinstance(metric.get("json"), dict) else {}
                metric_rows.append(
                    {
                        "ts": metric.get("ts"),
                        "key": str(metric.get("key") or ""),
                        "value": safe_float(metric.get("value")),
                        "completed": int(blob.get("completed", 0) or 0),
                        "hypervolume": safe_float(blob.get("hypervolume")),
                        "best_obj1": safe_float(blob.get("best_obj1")),
                        "best_obj2": safe_float(blob.get("best_obj2")),
                        "n_feasible": int(blob.get("n_feasible", 0) or 0),
                    }
                )
            df_metrics = pd.DataFrame(metric_rows)
            chart_cols = [
                col
                for col in ("hypervolume", "best_obj1", "best_obj2", "n_feasible")
                if col in df_metrics.columns and df_metrics[col].notna().any()
            ]
            if chart_cols:
                index_col = "completed" if (df_metrics["completed"] > 0).any() else "ts"
                st.line_chart(df_metrics.set_index(index_col)[chart_cols])
            st.dataframe(df_metrics.tail(200), width="stretch", height=220)
        else:
            st.info("No metrics yet.")

        st.subheader("Trials / packaging")
        limit = st.slider("How many trials to load", min_value=50, max_value=5000, value=500, step=50)
        trials = db.fetch_trials(run_id, limit=int(limit), order="finished_ts")
        df_trials = flatten_trial_rows(trials)
        if not df_trials.empty:
            df_trials = enrich_packaging_surface_df(df_trials, params=packaging_params)
            df_trials = df_trials.sort_values(
                by=[c for c in ("finished_ts", "created_ts") if c in df_trials.columns],
                ascending=False,
                na_position="last",
            )

        render_packaging_surface_metrics(st, df_trials)
        statuses = sorted(str(x) for x in df_trials["status"].dropna().unique()) if "status" in df_trials.columns else []
        chosen_statuses = st.multiselect(
            "Trial statuses",
            options=statuses,
            default=statuses,
            key="dist_db_trials_status_filter",
        )
        df_trials_view = df_trials.copy()
        if chosen_statuses and "status" in df_trials_view.columns:
            df_trials_view = df_trials_view[df_trials_view["status"].astype(str).isin(chosen_statuses)]
        df_trials_view = apply_packaging_surface_filters(
            st,
            df_trials_view,
            key_prefix="dist_db",
            compact=False,
        )

        leading_cols = [
            "trial_id",
            "status",
            "attempt",
            "worker_tag",
            "host",
            "error_text",
            "finished_ts",
        ]
        if penalty_key in df_trials_view.columns:
            leading_cols.insert(5, penalty_key)
        show_cols = packaging_surface_result_columns(df_trials_view, leading=leading_cols)
        if len(objective_keys) > 0 and objective_keys[0] in df_trials_view.columns and objective_keys[0] not in show_cols:
            show_cols.insert(5, objective_keys[0])
        if len(objective_keys) > 1 and objective_keys[1] in df_trials_view.columns and objective_keys[1] not in show_cols:
            show_cols.insert(6, objective_keys[1])

        st.dataframe(
            df_trials_view[show_cols] if show_cols else df_trials_view,
            width="stretch",
            height=360,
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
