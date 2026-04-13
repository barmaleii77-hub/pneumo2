from __future__ import annotations

from typing import Any

from pneumo_solver_ui.optimization_active_runtime_summary import (
    active_handoff_provenance_caption,
    active_runtime_penalty_gate_caption,
    active_runtime_progress_caption,
    active_runtime_recent_errors_caption,
    active_runtime_trial_health_caption,
)
from pneumo_solver_ui.optimization_baseline_source_ui import (
    render_baseline_source_summary,
)
from pneumo_solver_ui.optimization_contract_summary_ui import (
    render_objective_contract_summary,
)
from pneumo_solver_ui.optimization_packaging_snapshot_ui import (
    render_packaging_snapshot_summary,
)
from pneumo_solver_ui.optimization_problem_scope_ui import (
    render_problem_scope_summary,
)


def _run_dir_key(raw: Any) -> str:
    text = str(raw or "").strip()
    if not text:
        return ""
    try:
        from pathlib import Path

        return str(Path(text).resolve())
    except Exception:
        return text


def _render_last_pointer_live_now(
    st: Any,
    *,
    run_dir: Any,
    active_run_dir: Any = None,
    active_launch_context: dict[str, Any] | None = None,
    active_runtime_summary: dict[str, Any] | None = None,
) -> bool:
    snapshot_run_dir = _run_dir_key(run_dir)
    current_active_run_dir = _run_dir_key(active_run_dir)
    context = dict(active_launch_context or {})
    if not current_active_run_dir:
        return False

    from pathlib import Path

    active_name = Path(current_active_run_dir).name if current_active_run_dir else "active run"
    source_run_dir = _run_dir_key(context.get("source_run_dir"))
    source_name = Path(source_run_dir).name if source_run_dir else "staged run"
    is_handoff = str(context.get("kind") or "").strip() == "handoff"
    progress_caption = active_runtime_progress_caption(
        active_runtime_summary,
        prefix="Active handoff progress" if is_handoff else "Active run progress",
    )
    trial_health_caption = active_runtime_trial_health_caption(
        active_runtime_summary,
        prefix="Active handoff trial health" if is_handoff else "Active run trial health",
    )
    penalty_gate_caption = active_runtime_penalty_gate_caption(
        active_runtime_summary,
        prefix="Active handoff penalty gate" if is_handoff else "Active run penalty gate",
    )
    recent_errors_caption = active_runtime_recent_errors_caption(
        active_runtime_summary,
        prefix="Recent handoff errors" if is_handoff else "Recent run errors",
    )
    provenance_caption = active_handoff_provenance_caption(
        active_runtime_summary,
        prefix="Handoff provenance" if is_handoff else "Run provenance",
    )

    if snapshot_run_dir and snapshot_run_dir == current_active_run_dir:
        if is_handoff:
            st.info(
                "LIVE NOW: этот snapshot уже совпадает с активным seeded full-ring coordinator handoff "
                f"из staged run `{source_name}`."
            )
        else:
            st.info("LIVE NOW: этот snapshot совпадает с активным optimization run текущей сессии.")
        if progress_caption:
            st.caption(progress_caption)
        if trial_health_caption:
            st.caption(trial_health_caption)
        if penalty_gate_caption:
            st.caption(penalty_gate_caption)
        if recent_errors_caption:
            st.caption(recent_errors_caption)
        if provenance_caption:
            st.caption(provenance_caption)
        return True

    if is_handoff:
        snapshot_name = Path(snapshot_run_dir).name if snapshot_run_dir else "latest pointer"
        st.info(
            "LIVE NOW: сейчас выполняется seeded full-ring coordinator handoff "
            f"`{active_name}` из staged run `{source_name}`. "
            f"Snapshot ниже пока указывает на последний закреплённый run `{snapshot_name}`."
        )
        if progress_caption:
            st.caption(progress_caption)
        if trial_health_caption:
            st.caption(trial_health_caption)
        if penalty_gate_caption:
            st.caption(penalty_gate_caption)
        if recent_errors_caption:
            st.caption(recent_errors_caption)
        if provenance_caption:
            st.caption(provenance_caption)
        return True

    return False


def _render_last_pointer_live_policy(st: Any, live_policy: dict[str, Any]) -> None:
    st.markdown("**Политика отбора и продвижения (текущая стадия)**")
    if bool(live_policy.get("available")):
        st.caption(
            f"requested={live_policy.get('requested_mode') or '—'} → "
            f"effective={live_policy.get('effective_mode') or '—'}; "
            f"policy={live_policy.get('policy_name') or '—'}"
        )
        if str(live_policy.get("summary_line") or "").strip():
            st.caption(str(live_policy.get("summary_line") or ""))
        return
    st.caption("Будет видно после staged run, когда появятся stage artifacts и live policy summary.")


def _render_last_pointer_final_runtime_summary(
    st: Any,
    *,
    summary: Any,
    run_dir: Any,
    active_run_dir: Any = None,
) -> bool:
    snapshot_run_dir = _run_dir_key(run_dir)
    current_active_run_dir = _run_dir_key(active_run_dir)
    if snapshot_run_dir and current_active_run_dir and snapshot_run_dir == current_active_run_dir:
        return False
    runtime_summary = dict(getattr(summary, "runtime_summary", None) or {})
    if not runtime_summary:
        return False
    is_handoff = str(getattr(summary, "backend", "") or "").startswith("Handoff/")
    progress_caption = active_runtime_progress_caption(
        runtime_summary,
        prefix="Final handoff progress" if is_handoff else "Final run progress",
    )
    trial_health_caption = active_runtime_trial_health_caption(
        runtime_summary,
        prefix="Final handoff trial health" if is_handoff else "Final run trial health",
    )
    penalty_gate_caption = active_runtime_penalty_gate_caption(
        runtime_summary,
        prefix="Final handoff penalty gate" if is_handoff else "Final run penalty gate",
    )
    recent_errors_caption = active_runtime_recent_errors_caption(
        runtime_summary,
        prefix="Recent handoff errors" if is_handoff else "Recent run errors",
    )
    provenance_caption = active_handoff_provenance_caption(
        runtime_summary,
        prefix="Handoff provenance" if is_handoff else "Run provenance",
    )
    diagnostic_lines = [
        text
        for text in (
            progress_caption,
            trial_health_caption,
            penalty_gate_caption,
            recent_errors_caption,
            provenance_caption,
        )
        if str(text or "").strip()
    ]
    if not diagnostic_lines:
        return False
    st.write("**Final runtime diagnostics**")
    for line in diagnostic_lines:
        st.caption(str(line))
    return True


def render_last_optimization_pointer_summary(
    st: Any,
    snap: dict[str, Any],
    *,
    compact: bool = False,
    missing_message: str,
    success_message: str | None = None,
    packaging_heading: str = "Сводка по геометрии узлов (последний run)",
    packaging_interference_prefix: str = "В последнем run есть признаки пересечений по геометрии узлов",
    current_problem_hash: str = "",
    current_problem_hash_mode: str = "",
    active_run_dir: Any = None,
    active_launch_context: dict[str, Any] | None = None,
    active_runtime_summary: dict[str, Any] | None = None,
) -> bool:
    raw = snap.get("raw") or {}
    meta = snap.get("meta") or {}
    run_dir = snap.get("run_dir") or raw.get("run_dir")

    if not raw or not run_dir:
        st.info(missing_message)
        _render_last_pointer_live_policy(st, {})
        return False

    if success_message:
        st.success(success_message)

    _render_last_pointer_live_now(
        st,
        run_dir=run_dir,
        active_run_dir=active_run_dir,
        active_launch_context=active_launch_context,
        active_runtime_summary=active_runtime_summary,
    )

    mode_label = str(snap.get("mode_label") or "—")
    if compact:
        st.write(f"**Путь:** `{run_dir}`")
        st.caption(f"Режим: {mode_label}")
        st.caption(f"Время: {meta.get('ts', raw.get('updated_at', '—'))}")
    else:
        cols = st.columns(3)
        with cols[0]:
            st.metric("Последний режим", mode_label)
        with cols[1]:
            st.metric("Backend", str(meta.get("backend") or "—"))
        with cols[2]:
            st.metric("Время", str(meta.get("ts") or raw.get("updated_at") or "—"))
        st.caption(f"Папка: `{run_dir}`")

    render_objective_contract_summary(
        st,
        objective_keys=meta.get("objective_keys"),
        penalty_key=meta.get("penalty_key"),
        penalty_tol=meta.get("penalty_tol"),
    )
    render_baseline_source_summary(
        st,
        summary=snap.get("opt_summary"),
        run_dir=run_dir,
    )
    render_problem_scope_summary(
        st,
        summary=snap.get("opt_summary"),
        run_dir=run_dir,
        current_problem_hash=current_problem_hash,
        current_problem_hash_mode=current_problem_hash_mode,
    )
    opt_summary = snap.get("opt_summary")
    if opt_summary is not None and str(getattr(opt_summary, "handoff_preset_tag", "") or "").strip():
        st.write("**Coordinator handoff:** " + str(getattr(opt_summary, "handoff_preset_tag", "") or ""))
        st.caption(
            "Рекомендуемый full-ring handoff: "
            f"budget={int(getattr(opt_summary, 'handoff_budget', 0) or 0)}, "
            f"seed-candidates={int(getattr(opt_summary, 'handoff_seed_count', 0) or 0)}, "
            f"suite={str(getattr(opt_summary, 'handoff_suite_family', '') or 'unknown')}."
        )
        for line in tuple(getattr(opt_summary, "handoff_reason_lines", ()) or ()):
            st.caption(str(line))
        if bool(getattr(opt_summary, "handoff_requires_full_ring_validation", False)):
            st.caption(
                "Этот handoff сохраняет обязательную full-ring проверку на длинных пользовательских кольцах."
            )
    if opt_summary is not None:
        _render_last_pointer_final_runtime_summary(
            st,
            summary=opt_summary,
            run_dir=run_dir,
            active_run_dir=active_run_dir,
        )

    sp_payload = snap.get("sp_payload") or {}
    if sp_payload:
        st.caption(
            "Указатель StageRunner: "
            f"status={sp_payload.get('status') or '—'}, ts={sp_payload.get('ts') or '—'}"
        )

    _render_last_pointer_live_policy(st, snap.get("live_policy") or {})

    packaging_snapshot = snap.get("packaging_snapshot")
    if render_packaging_snapshot_summary(
        st,
        packaging_snapshot,
        compact=compact,
        heading=packaging_heading,
        interference_prefix=packaging_interference_prefix,
    ):
        return True
    if opt_summary is not None and getattr(opt_summary, "result_path", None) is not None:
        st.caption(
            "Последний run уже имеет result-артефакт, но packaging summary columns в нём не найдены. "
            "Подробный разбор доступен на страницах результатов и истории запусков."
        )
    return True


__all__ = [
    "render_last_optimization_pointer_summary",
]
