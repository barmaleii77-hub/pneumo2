# -*- coding: utf-8 -*-
"""Distributed optimization ExperimentDB viewer.

Read-only page for monitoring distributed runs created by the DB queue / Ray /
Dask coordinators.
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import streamlit as st
from pneumo_solver_ui.distributed_expdb_viewer_helpers import (
    done_trials_objective_rows as _done_trials_objective_rows,
    find_expdb_paths as _find_db_paths,
    flatten_trial_rows as _flatten_trial_rows,
    load_packaging_params_for_run as _load_packaging_params_for_run,
    safe_float as _safe_float,
)
from pneumo_solver_ui.packaging_surface_helpers import enrich_packaging_surface_df
from pneumo_solver_ui.packaging_surface_ui import (
    apply_packaging_surface_filters,
    packaging_surface_result_columns,
    render_packaging_surface_metrics,
)
from pneumo_solver_ui.ui_bootstrap import bootstrap
from pneumo_solver_ui.ui_persistence import autosave_if_enabled


bootstrap(st)
autosave_if_enabled(st)

try:
    from pneumo_solver_ui.ui_bootstrap import bootstrap as _ui_bootstrap

    _ui_bootstrap(st)
except Exception:
    pass

try:
    import pandas as pd  # type: ignore
except Exception:  # pragma: no cover
    pd = None


REPO_ROOT = Path(__file__).resolve().parents[2]

# Ensure repo root is importable (fixes ModuleNotFoundError in multipage/pages)
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def main() -> None:
    st.title("Распределённая оптимизация (ExperimentDB)")
    st.caption("Выберите базу экспериментов и run_id — увидите прогресс, packaging verdicts и Pareto-фронт.")

    try:
        from pneumo_solver_ui.pneumo_dist.expdb import ExperimentDB
    except ModuleNotFoundError:
        from pneumo_dist.expdb import ExperimentDB
    try:
        from pneumo_solver_ui.pneumo_dist.hv_tools import pareto_front_2d_max
    except ModuleNotFoundError:
        from pneumo_dist.hv_tools import pareto_front_2d_max

    db_paths = _find_db_paths(REPO_ROOT)
    if not db_paths:
        st.info("DB не найдена. Запусти distributed runner -> появится runs/dist_runs/*/experiments.sqlite|duckdb")
        return

    sel = st.selectbox("Файл базы экспериментов (ExperimentDB)", options=[str(p) for p in db_paths], index=0)
    db_path = Path(sel)

    db = ExperimentDB(str(db_path))
    db.init_schema()

    runs = db.list_runs(limit=50)
    if not runs:
        st.warning("В DB нет записей runs")
        return

    run_ids = [str(r.get("run_id")) for r in runs]
    run_id = st.selectbox("Запуск (run_id)", options=run_ids, index=0)
    run_detail = db.get_run(run_id) or {}
    run_spec = dict(run_detail.get("spec") or {}) if isinstance(run_detail.get("spec"), dict) else {}
    run_meta = dict(run_detail.get("meta") or {}) if isinstance(run_detail.get("meta"), dict) else {}
    run_cfg = dict(run_spec.get("cfg") or {}) if isinstance(run_spec.get("cfg"), dict) else {}
    objective_keys = [str(x).strip() for x in list(run_cfg.get("objective_keys") or []) if str(x).strip()]
    penalty_key = str(run_cfg.get("penalty_key") or "штраф_физичности_сумма")
    packaging_params = _load_packaging_params_for_run(db, run_id, db_path, REPO_ROOT)

    with st.expander("Метаданные запуска", expanded=False):
        st.json(
            {
                "list_runs_row": next((r for r in runs if str(r.get("run_id")) == run_id), None),
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

    st.subheader("Статусы")
    st.json(db.count_by_status(run_id))

    st.subheader("Прогресс")
    metrics = db.fetch_metrics(run_id, limit=50000)
    if metrics:
        rows = []
        for m in metrics:
            blob = dict(m.get("json") or {}) if isinstance(m.get("json"), dict) else {}
            rows.append(
                {
                    "completed": int(blob.get("completed", 0) or 0),
                    "hypervolume": _safe_float(blob.get("hypervolume")),
                    "best_obj1": _safe_float(blob.get("best_obj1")),
                    "best_obj2": _safe_float(blob.get("best_obj2")),
                    "n_feasible": int(blob.get("n_feasible", 0) or 0),
                }
            )
        if pd is not None:
            df_metrics = pd.DataFrame(rows).sort_values("completed")
            df_metrics = df_metrics.drop_duplicates(subset=["completed"], keep="last")
            df_metrics = df_metrics.set_index("completed")
            col1, col2 = st.columns(2)
            with col1:
                st.line_chart(df_metrics[["hypervolume"]])
            with col2:
                st.line_chart(df_metrics[["best_obj1", "best_obj2", "n_feasible"]])
        else:
            st.dataframe(rows, width="stretch")
    else:
        st.info("run_metrics пусто (ещё не было тиков или run слишком маленький)")

    st.subheader("Trials / packaging")
    limit = st.slider("Сколько trials загрузить", min_value=50, max_value=5000, value=300, step=50)
    trials = db.fetch_trials(run_id, limit=int(limit), order="finished_ts")
    if pd is None:
        st.warning("pandas недоступен: показываю trials без packaging filters")
        st.dataframe(trials, width="stretch")
        return

    df_trials = _flatten_trial_rows(trials)
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
        "Статусы trials",
        options=statuses,
        default=statuses,
        key="dist_trials_status_filter",
    )
    df_trials_view = df_trials.copy()
    if chosen_statuses and "status" in df_trials_view.columns:
        df_trials_view = df_trials_view[df_trials_view["status"].astype(str).isin(chosen_statuses)]
    df_trials_view = apply_packaging_surface_filters(st, df_trials_view, key_prefix="dist", compact=False)

    st.subheader("Pareto-фронт (feasible)")
    feasible_tol = st.number_input(
        "Допуск по штрафу (feasible_tol)",
        value=1e-9,
        format="%.3e",
        help="Точки с penalty <= feasible_tol считаются допустимыми (feasible).",
    )

    done_objective_rows = _done_trials_objective_rows(
        df_trials_view,
        objective_keys=objective_keys,
        penalty_key=penalty_key,
    )
    if done_objective_rows:
        df_done = pd.DataFrame(done_objective_rows)
        feas = np.isfinite(df_done["penalty"].astype(float).values) & (
            df_done["penalty"].astype(float).values <= float(feasible_tol)
        )
        if np.any(feas):
            Y_min = df_done.loc[feas, ["obj1", "obj2"]].to_numpy(dtype=float)
            Y_max = -Y_min
            P = pareto_front_2d_max(Y_max)
            Yp_min = -P
            st.write(f"feasible after filters: {int(np.sum(feas))} / {int(len(df_done))}")
            if len(objective_keys) > 2:
                st.caption("Показаны только первые две objective оси distributed run.")

            fig, ax = plt.subplots()
            ax.scatter(Yp_min[:, 0], Yp_min[:, 1], s=12)
            ax.set_xlabel(objective_keys[0] if len(objective_keys) > 0 else "Цель 1 (минимизация)")
            ax.set_ylabel(objective_keys[1] if len(objective_keys) > 1 else "Цель 2 (минимизация)")
            ax.grid(True, alpha=0.3)
            st.pyplot(fig, clear_figure=True)
        else:
            st.warning("Нет feasible точек по текущему feasible_tol и текущим packaging filters")
            Y_min = df_done[["obj1", "obj2"]].to_numpy(dtype=float)
            fig, ax = plt.subplots()
            ax.scatter(Y_min[:, 0], Y_min[:, 1], s=8)
            ax.set_xlabel(objective_keys[0] if len(objective_keys) > 0 else "Цель 1 (минимизация)")
            ax.set_ylabel(objective_keys[1] if len(objective_keys) > 1 else "Цель 2 (минимизация)")
            ax.grid(True, alpha=0.3)
            st.pyplot(fig, clear_figure=True)
    else:
        st.info("Пока нет DONE trials с двумя objective значениями после текущих фильтров")

    st.subheader("Испытания (trials)")
    show_cols = packaging_surface_result_columns(
        df_trials_view,
        leading=[
            "trial_id",
            "status",
            "attempt",
            "worker_tag",
            "host",
            penalty_key,
            "верификация_флаги",
            "error_text",
            "finished_ts",
        ],
    )
    if len(objective_keys) > 0 and objective_keys[0] in df_trials_view.columns and objective_keys[0] not in show_cols:
        show_cols.insert(5, objective_keys[0])
    if len(objective_keys) > 1 and objective_keys[1] in df_trials_view.columns and objective_keys[1] not in show_cols:
        show_cols.insert(6, objective_keys[1])

    st.dataframe(df_trials_view[show_cols] if show_cols else df_trials_view, width="stretch", height=420)


if __name__ == "__main__":
    main()

# --- Автосохранение UI (лучшее усилие) ---
# Важно: значения, введённые на этой странице, не должны пропадать при refresh/перезапуске.
