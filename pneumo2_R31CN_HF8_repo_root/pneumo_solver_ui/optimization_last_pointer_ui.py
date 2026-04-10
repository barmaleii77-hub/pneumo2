from __future__ import annotations

from typing import Any

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


def _render_last_pointer_live_policy(st: Any, live_policy: dict[str, Any]) -> None:
    st.markdown("**Seed/promotion policy (текущая стадия)**")
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


def render_last_optimization_pointer_summary(
    st: Any,
    snap: dict[str, Any],
    *,
    compact: bool = False,
    missing_message: str,
    success_message: str | None = None,
    packaging_heading: str = "Packaging snapshot (last run)",
    packaging_interference_prefix: str = "В последнем run есть packaging-interference evidence",
    current_problem_hash: str = "",
    current_problem_hash_mode: str = "",
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

    sp_payload = snap.get("sp_payload") or {}
    if sp_payload:
        st.caption(
            "StageRunner pointer: "
            f"status={sp_payload.get('status') or '—'}, ts={sp_payload.get('ts') or '—'}"
        )

    _render_last_pointer_live_policy(st, snap.get("live_policy") or {})

    opt_summary = snap.get("opt_summary")
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
