from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Callable

from pneumo_solver_ui import run_artifacts


def build_run_pointer_meta_from_summary(
    summary: Any,
    *,
    selected_from: str = "optimization_history",
    now_text: str | None = None,
) -> dict[str, Any]:
    return {
        "backend": getattr(summary, "backend", ""),
        "pipeline_mode": getattr(summary, "pipeline_mode", ""),
        "status": getattr(summary, "status", ""),
        "rows": int(getattr(summary, "row_count", 0) or 0),
        "done_count": int(getattr(summary, "done_count", 0) or 0),
        "running_count": int(getattr(summary, "running_count", 0) or 0),
        "error_count": int(getattr(summary, "error_count", 0) or 0),
        "objective_keys": list(getattr(summary, "objective_keys", ()) or ()),
        "penalty_key": getattr(summary, "penalty_key", ""),
        "penalty_tol": getattr(summary, "penalty_tol", None),
        "selected_from": str(selected_from or "optimization_history"),
        "ts": str(now_text or time.strftime("%Y-%m-%d %H:%M:%S")),
    }


def save_run_pointer_to_latest(
    st: Any,
    run_dir: Path,
    meta: dict[str, Any],
    *,
    rerun_fn: Callable[[Any], None] | None = None,
    success_message: str = "latest_optimization pointer перепривязан к выбранному run_dir.",
    error_prefix: str = "Не удалось перепривязать latest_optimization",
    save_ptr_fn: Callable[[Path, dict[str, Any]], None] | None = None,
    autoload_session_fn: Callable[[Any], None] | None = None,
) -> bool:
    save_ptr = save_ptr_fn or run_artifacts.save_last_opt_ptr
    autoload = autoload_session_fn or run_artifacts.autoload_to_session
    try:
        save_ptr(run_dir, meta)
        autoload(st.session_state)
        st.success(success_message)
        if rerun_fn is not None:
            rerun_fn(st)
        return True
    except Exception as exc:
        st.error(f"{error_prefix}: {exc}")
        return False


def open_results_via_run_pointer(
    st: Any,
    run_dir: Path,
    meta: dict[str, Any],
    *,
    results_page: str = "pages/20_DistributedOptimization.py",
    fallback_message: str = "Откройте страницу 'Результаты оптимизации' в меню слева — pointer уже обновлён.",
    save_ptr_fn: Callable[[Path, dict[str, Any]], None] | None = None,
    autoload_session_fn: Callable[[Any], None] | None = None,
) -> bool:
    save_ptr = save_ptr_fn or run_artifacts.save_last_opt_ptr
    autoload = autoload_session_fn or run_artifacts.autoload_to_session
    try:
        save_ptr(run_dir, meta)
        autoload(st.session_state)
        st.switch_page(results_page)
        return True
    except Exception:
        st.info(fallback_message)
        return False


def render_optimization_run_pointer_actions(
    st: Any,
    summary: Any,
    *,
    key_prefix: str,
    rerun_fn: Callable[[Any], None] | None = None,
    selected_from: str = "optimization_history",
    make_latest_label: str = "Сделать текущей «последней оптимизацией»",
    make_latest_help: str = "Перепривязать глобальный latest_optimization pointer к выбранному run_dir.",
    open_results_label: str = "Открыть результаты выбранного run",
    open_results_help: str = "Сначала перепривязать latest_optimization, затем открыть страницу результатов.",
    results_page: str = "pages/20_DistributedOptimization.py",
) -> None:
    meta = build_run_pointer_meta_from_summary(summary, selected_from=selected_from)
    run_dir = Path(getattr(summary, "run_dir"))
    log_path = getattr(summary, "log_path", None)

    b1, b2, b3 = st.columns([1, 1, 2])
    with b1:
        if st.button(
            make_latest_label,
            key=f"{key_prefix}::make_latest::{run_dir}",
            help=make_latest_help,
        ):
            save_run_pointer_to_latest(st, run_dir, meta, rerun_fn=rerun_fn)
    with b2:
        if st.button(
            open_results_label,
            key=f"{key_prefix}::open_results::{run_dir}",
            help=open_results_help,
        ):
            open_results_via_run_pointer(st, run_dir, meta, results_page=results_page)
    with b3:
        if log_path is not None:
            st.caption(f"Лог: {log_path}")


__all__ = [
    "build_run_pointer_meta_from_summary",
    "open_results_via_run_pointer",
    "render_optimization_run_pointer_actions",
    "save_run_pointer_to_latest",
]
