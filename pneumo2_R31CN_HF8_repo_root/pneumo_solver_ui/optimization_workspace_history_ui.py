from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from pneumo_solver_ui.optimization_active_runtime_summary import (
    active_handoff_provenance_caption,
    active_runtime_penalty_gate_caption,
    active_runtime_progress_caption,
    active_runtime_recent_errors_caption,
    active_runtime_trial_health_caption,
)
from pneumo_solver_ui.optimization_page_readonly_ui import (
    current_objective_keys,
)
from pneumo_solver_ui.optimization_run_history import (
    OptimizationRunSummary,
    discover_workspace_optimization_runs,
    format_run_choice,
)
from pneumo_solver_ui.optimization_run_history_details_ui import (
    render_selected_optimization_run_details,
)
from pneumo_solver_ui.optimization_run_pointer_actions_ui import (
    render_optimization_run_pointer_actions,
)


HANDOFF_SORT_OPTIONS = (
    "Лучшие для continuation",
    "Качество seed-bridge",
    "Минимальный budget",
)
_HISTORY_SELECTED_RUN_DIR_KEY = "__opt_history_selected_run_dir"
_ACTIVE_LAUNCH_CONTEXT_KEY = "__opt_active_launch_context"


def _run_dir_key(raw: Any) -> str:
    text = str(raw or "").strip()
    if not text:
        return ""
    try:
        return str(Path(text).resolve())
    except Exception:
        return text


def with_active_job_placeholder(summaries: Sequence[Any], *, active_job: Any) -> list[Any]:
    items = list(summaries or ())
    active_run_dir = getattr(active_job, "run_dir", None) if active_job is not None else None
    active_key = _run_dir_key(active_run_dir)
    if not active_key:
        return items
    if any(_run_dir_key(getattr(item, "run_dir", None)) == active_key for item in items):
        return items
    pipeline_mode = str(getattr(active_job, "pipeline_mode", "") or "").strip() or "coordinator"
    backend = str(getattr(active_job, "backend", "") or "active job")
    log_path = getattr(active_job, "log_path", None)
    log_path_resolved = Path(log_path).resolve() if log_path else None
    placeholder = OptimizationRunSummary(
        run_dir=Path(active_run_dir).resolve(),
        pipeline_mode=pipeline_mode,
        backend=backend,
        status="running",
        status_label="RUNNING",
        started_at="",
        updated_ts=float(getattr(active_job, "started_ts", 0.0) or 0.0),
        log_path=log_path_resolved,
        result_path=None,
        row_count=0,
        done_count=0,
        running_count=1 if pipeline_mode == "coordinator" else 0,
        error_count=0,
        note="Run запущен из текущей сессии; артефакты на диске ещё не появились.",
    )
    return [placeholder, *items]


def _active_launch_context_map(session_state: Mapping[str, Any] | None) -> dict[str, Any]:
    if not isinstance(session_state, Mapping):
        return {}
    raw = session_state.get(_ACTIVE_LAUNCH_CONTEXT_KEY)
    return dict(raw) if isinstance(raw, dict) else {}


def _active_handoff_target_run_dir(*, active_job: Any, active_launch_context: Mapping[str, Any] | None) -> str:
    context = dict(active_launch_context or {})
    if str(context.get("kind") or "").strip() != "handoff":
        return ""
    target_run_dir = _run_dir_key(context.get("run_dir"))
    if target_run_dir:
        return target_run_dir
    return _run_dir_key(getattr(active_job, "run_dir", None))


def build_handoff_overview_rows(
    summaries: Sequence[Any],
    *,
    active_job: Any = None,
    active_launch_context: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    active_target_run_dir = _active_handoff_target_run_dir(
        active_job=active_job,
        active_launch_context=active_launch_context,
    )
    for summary in list(summaries or ()):
        if str(getattr(summary, "pipeline_mode", "") or "") != "staged":
            continue
        if not bool(getattr(summary, "handoff_available", False)):
            continue
        target_run_dir = _run_dir_key(getattr(summary, "handoff_target_run_dir", "") or "")
        rows.append(
            {
                "__run_dir": _run_dir_key(getattr(summary, "run_dir", "") or ""),
                "__target_run_dir": target_run_dir,
                "run": str(getattr(getattr(summary, "run_dir", None), "name", "") or ""),
                "status": str(getattr(summary, "status_label", "") or ""),
                "live_now": "LIVE" if active_target_run_dir and target_run_dir == active_target_run_dir else "—",
                "preset": str(getattr(summary, "handoff_preset_tag", "") or ""),
                "budget": int(getattr(summary, "handoff_budget", 0) or 0),
                "seeds": int(getattr(summary, "handoff_seed_count", 0) or 0),
                "valid_rows": int(getattr(summary, "handoff_staged_rows_ok", 0) or 0),
                "promotable": int(getattr(summary, "handoff_promotable_rows", 0) or 0),
                "unique": int(getattr(summary, "handoff_unique_param_candidates", 0) or 0),
                "pool": str(getattr(summary, "handoff_selection_pool", "") or "—"),
                "fragments": int(getattr(summary, "handoff_fragment_count", 0) or 0),
                "full_ring": "yes" if bool(getattr(summary, "handoff_has_full_ring", False)) else "no",
                "suite": str(getattr(summary, "handoff_suite_family", "") or "—"),
            }
        )
    return rows


def handoff_quality_score(row: Mapping[str, Any]) -> float:
    valid_rows = max(0, int(row.get("valid_rows", 0) or 0))
    promotable = max(0, int(row.get("promotable", 0) or 0))
    unique = max(0, int(row.get("unique", 0) or 0))
    seeds = max(0, int(row.get("seeds", 0) or 0))
    full_ring_bonus = 1.0 if str(row.get("full_ring") or "").strip().lower() == "yes" else 0.0
    status_text = str(row.get("status") or "").strip().upper()
    status_bonus = 1.0 if status_text == "DONE" else (0.5 if status_text == "PARTIAL" else 0.0)
    promotable_share = float(promotable) / float(max(1, valid_rows))
    seed_fill = min(1.0, float(seeds) / float(max(1, unique)))
    score = 100.0 * (
        0.40 * promotable_share
        + 0.30 * seed_fill
        + 0.20 * full_ring_bonus
        + 0.10 * status_bonus
    )
    return round(float(score), 1)


def enrich_handoff_overview_rows(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in list(rows or ()):
        rec = dict(row)
        rec["quality_score"] = handoff_quality_score(rec)
        out.append(rec)
    return out


def filter_handoff_overview_rows(
    rows: Sequence[Mapping[str, Any]],
    *,
    full_ring_only: bool = False,
    done_only: bool = False,
    min_seeds: int = 0,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    min_seed_count = max(0, int(min_seeds or 0))
    for row in list(rows or ()):
        rec = dict(row)
        if full_ring_only and str(rec.get("full_ring") or "").strip().lower() != "yes":
            continue
        if done_only and str(rec.get("status") or "").strip().upper() != "DONE":
            continue
        if int(rec.get("seeds", 0) or 0) < min_seed_count:
            continue
        out.append(rec)
    return out


def sort_handoff_overview_rows(
    rows: Sequence[Mapping[str, Any]],
    *,
    sort_mode: str,
) -> list[dict[str, Any]]:
    items = [dict(row) for row in list(rows or ())]
    mode = str(sort_mode or HANDOFF_SORT_OPTIONS[0]).strip()
    if mode == "Минимальный budget":
        return sorted(
            items,
            key=lambda row: (
                0 if str(row.get("live_now") or "") == "LIVE" else 1,
                int(row.get("budget", 0) or 0),
                -float(row.get("quality_score", 0.0) or 0.0),
                -int(row.get("seeds", 0) or 0),
                str(row.get("run") or ""),
            ),
        )
    if mode == "Качество seed-bridge":
        return sorted(
            items,
            key=lambda row: (
                0 if str(row.get("live_now") or "") == "LIVE" else 1,
                -float(row.get("quality_score", 0.0) or 0.0),
                -int(row.get("promotable", 0) or 0),
                -int(row.get("unique", 0) or 0),
                int(row.get("budget", 0) or 0),
                str(row.get("run") or ""),
            ),
        )
    return sorted(
        items,
        key=lambda row: (
            0 if str(row.get("live_now") or "") == "LIVE" else 1,
            0 if str(row.get("full_ring") or "").strip().lower() == "yes" else 1,
            0 if str(row.get("status") or "").strip().upper() == "DONE" else 1,
            -float(row.get("quality_score", 0.0) or 0.0),
            -int(row.get("seeds", 0) or 0),
            int(row.get("budget", 0) or 0),
            str(row.get("run") or ""),
        ),
    )


def render_workspace_handoff_overview(
    st: Any,
    summaries: Sequence[Any],
    *,
    active_job: Any = None,
    active_launch_context: Mapping[str, Any] | None = None,
    active_runtime_summary: Mapping[str, Any] | None = None,
    start_handoff_fn: Callable[[Path], bool] | None = None,
) -> bool:
    rows = enrich_handoff_overview_rows(
        build_handoff_overview_rows(
            summaries,
            active_job=active_job,
            active_launch_context=active_launch_context,
        )
    )
    if not rows:
        return False
    import pandas as pd

    st.markdown("**Сравнение handoff-решений между staged run**")
    st.caption(
        "Сводка показывает, какой full-ring preset staged-фильтр рекомендовал для каждого кольца: "
        "preset, budget и качество seed-bridge видны рядом без открытия JSON."
    )
    c1, c2, c3, c4 = st.columns([1.6, 1.0, 1.0, 0.9])
    with c1:
        sort_mode = st.selectbox(
            "Ranking handoff",
            options=list(HANDOFF_SORT_OPTIONS),
            index=0,
            key="__opt_handoff_sort_mode",
            help="Быстрый triage handoff-кандидатов: по continuation, по quality или по budget.",
        )
    with c2:
        full_ring_only = bool(
            st.checkbox(
                "Только full-ring",
                value=False,
                key="__opt_handoff_full_ring_only",
            )
        )
    with c3:
        done_only = bool(
            st.checkbox(
                "Только DONE",
                value=False,
                key="__opt_handoff_done_only",
            )
        )
    with c4:
        min_seeds = int(
            st.number_input(
                "Мин. seeds",
                min_value=0,
                max_value=999,
                value=0,
                step=1,
                key="__opt_handoff_min_seeds",
            )
        )
    rows_filtered = filter_handoff_overview_rows(
        rows,
        full_ring_only=full_ring_only,
        done_only=done_only,
        min_seeds=min_seeds,
    )
    if not rows_filtered:
        st.caption("После quick-filter подходящих staged handoff сейчас нет.")
        return False
    rows_ranked = sort_handoff_overview_rows(rows_filtered, sort_mode=sort_mode)
    best = rows_ranked[0]
    live_rows = [row for row in rows_ranked if str(row.get("live_now") or "") == "LIVE"]
    if live_rows:
        live_row = live_rows[0]
        st.info(
            "LIVE NOW: сейчас full-ring coordinator уже выполняется для "
            f"staged run `{live_row['run']}` с preset `{live_row['preset']}`."
        )
        progress_caption = active_runtime_progress_caption(
            active_runtime_summary,
            prefix="Active handoff progress",
        )
        if progress_caption:
            st.caption(progress_caption)
        trial_health_caption = active_runtime_trial_health_caption(
            active_runtime_summary,
            prefix="Active handoff trial health",
        )
        if trial_health_caption:
            st.caption(trial_health_caption)
        penalty_gate_caption = active_runtime_penalty_gate_caption(
            active_runtime_summary,
            prefix="Active handoff penalty gate",
        )
        if penalty_gate_caption:
            st.caption(penalty_gate_caption)
        recent_errors_caption = active_runtime_recent_errors_caption(
            active_runtime_summary,
            prefix="Recent handoff errors",
        )
        if recent_errors_caption:
            st.caption(recent_errors_caption)
        provenance_caption = active_handoff_provenance_caption(
            active_runtime_summary,
            prefix="Handoff provenance",
        )
        if provenance_caption:
            st.caption(provenance_caption)
    st.caption(
        "Quick best handoff сейчас: "
        f"run={best['run']}, preset={best['preset']}, score={best['quality_score']}, "
        f"budget={best['budget']}, seeds={best['seeds']}."
    )
    if start_handoff_fn is not None:
        best_run_dir = Path(str(best.get("__run_dir") or "")).resolve()
        if st.button(
            f"Запустить лучший handoff ({best['preset']})",
            key="__opt_handoff_start_best",
            help=(
                "Продолжить лучший staged run из quick-ranking сразу в seeded full-ring coordinator. "
                f"run={best['run']}, budget={best['budget']}, seeds={best['seeds']}."
            ),
            type="primary",
        ):
            session_state = getattr(st, "session_state", None)
            previous_selected = None if session_state is None else session_state.get(_HISTORY_SELECTED_RUN_DIR_KEY)
            target_run_dir = _run_dir_key(best.get("__target_run_dir") or best.get("__run_dir"))
            if session_state is not None and target_run_dir:
                session_state[_HISTORY_SELECTED_RUN_DIR_KEY] = target_run_dir
            started = bool(start_handoff_fn(best_run_dir))
            if not started and session_state is not None:
                if previous_selected is None:
                    session_state.pop(_HISTORY_SELECTED_RUN_DIR_KEY, None)
                else:
                    session_state[_HISTORY_SELECTED_RUN_DIR_KEY] = previous_selected
            return started
    display_rows = [{k: v for k, v in row.items() if not str(k).startswith("__")} for row in rows_ranked]
    st.dataframe(pd.DataFrame(display_rows), use_container_width=True, hide_index=True)
    return True


def render_workspace_run_history_block(
    st: Any,
    *,
    workspace_dir: Path,
    active_job: Any,
    session_state: Mapping[str, Any],
    default_objectives: Sequence[str],
    objectives_text_fn: Callable[[Sequence[str]], str],
    penalty_key_default: str,
    current_penalty_tol: Any,
    load_log_text: Callable[[Path], str],
    rerun_fn: Callable[[Any], None],
    start_handoff_fn: Callable[[Path], bool] | None = None,
    current_problem_hash: str = "",
    current_problem_hash_mode: str = "",
    discover_runs_fn: Callable[..., list[Any]] = discover_workspace_optimization_runs,
    format_run_choice_fn: Callable[[Any], str] = format_run_choice,
    render_details_fn: Callable[..., Any] = render_selected_optimization_run_details,
    render_pointer_actions_fn: Callable[..., Any] = render_optimization_run_pointer_actions,
    render_handoff_overview_fn: Callable[..., Any] | None = render_workspace_handoff_overview,
    active_runtime_summary: Mapping[str, Any] | None = None,
) -> None:
    active_run_dir = getattr(active_job, "run_dir", None) if active_job is not None else None
    active_launch_context = _active_launch_context_map(session_state)
    summaries = with_active_job_placeholder(
        discover_runs_fn(workspace_dir, active_run_dir=active_run_dir),
        active_job=active_job,
    )
    if not summaries:
        st.info("В текущем workspace ещё нет запусков оптимизации на диске.")
        return

    st.caption(
        "Если вы запускаете оптимизации последовательно (например, сначала StageRunner, потом coordinator), "
        "это нормальный инженерный сценарий. staged и coordinator run dirs показаны одновременно, чтобы второй запуск "
        "не затирал понимание первого."
    )
    if render_handoff_overview_fn is not None:
        render_handoff_overview_fn(
            st,
            summaries,
            active_job=active_job,
            active_launch_context=active_launch_context,
            active_runtime_summary=active_runtime_summary,
            start_handoff_fn=start_handoff_fn,
        )

    option_map = {_run_dir_key(item.run_dir): item for item in summaries}
    option_keys = list(option_map.keys())
    preferred = _run_dir_key(st.session_state.get(_HISTORY_SELECTED_RUN_DIR_KEY) or option_keys[0])
    if preferred not in option_map:
        preferred = option_keys[0]
    selected_run_dir = st.selectbox(
        "Выберите run для разбора",
        options=option_keys,
        index=option_keys.index(preferred),
        key=_HISTORY_SELECTED_RUN_DIR_KEY,
        format_func=lambda key: format_run_choice_fn(option_map[key]),
        help=(
            "Здесь сохраняется последовательность запусков по папкам run_dir. Это нужно, когда сначала был StageRunner, "
            "а потом coordinator (или наоборот)."
        ),
    )
    summary = option_map[selected_run_dir]

    cols = st.columns([1.2, 1.0, 1.0, 1.0])
    with cols[0]:
        st.metric("Статус", summary.status_label)
    with cols[1]:
        if summary.pipeline_mode == "staged":
            st.metric("Rows", int(summary.row_count))
        else:
            st.metric("DONE", int(summary.done_count))
    with cols[2]:
        if summary.pipeline_mode == "staged":
            st.metric("Pipeline", summary.backend)
        else:
            st.metric("ERROR", int(summary.error_count))
    with cols[3]:
        if summary.pipeline_mode == "coordinator":
            st.metric("RUNNING", int(summary.running_count))
        else:
            st.metric("Run dir", summary.run_dir.name)

    render_details_fn(
        st,
        summary,
        current_objective_keys=tuple(
            current_objective_keys(
                session_state,
                default_objectives=default_objectives,
                objectives_text_fn=objectives_text_fn,
            )
        ),
        current_penalty_key=str(
            session_state.get("opt_penalty_key", penalty_key_default) or penalty_key_default
        ).strip(),
        current_penalty_tol=current_penalty_tol,
        load_log_text=load_log_text,
        current_problem_hash=current_problem_hash,
        current_problem_hash_mode=current_problem_hash_mode,
        start_handoff_fn=start_handoff_fn,
        active_run_dir=active_run_dir,
        active_launch_context=active_launch_context,
        active_runtime_summary=dict(active_runtime_summary or {}),
    )

    render_pointer_actions_fn(
        st,
        summary,
        key_prefix="opt_history",
        active_run_dir=active_run_dir,
        active_launch_context=active_launch_context,
        active_runtime_summary=dict(active_runtime_summary or {}),
        rerun_fn=rerun_fn,
        selected_from="optimization_history",
        make_latest_label="Сделать текущей «последней оптимизацией»",
        make_latest_help="Перепривязать глобальный latest_optimization pointer к выбранному run_dir.",
        open_results_label="Открыть результаты выбранного run",
        open_results_help="Сначала перепривязать latest_optimization, затем открыть страницу результатов.",
        results_page="pages/20_DistributedOptimization.py",
    )


__all__ = [
    "build_handoff_overview_rows",
    "enrich_handoff_overview_rows",
    "filter_handoff_overview_rows",
    "handoff_quality_score",
    "render_workspace_run_history_block",
    "render_workspace_handoff_overview",
    "sort_handoff_overview_rows",
    "with_active_job_placeholder",
]
