from __future__ import annotations

from typing import Any


def render_stage_policy_runtime_snapshot(
    st: Any,
    *,
    progress_payload: dict[str, Any],
    staged_summary: dict[str, Any],
    policy: dict[str, Any],
    waiting_message: str = "StageRunner progress.json ещё не записан — это нормально в первые секунды запуска.",
) -> bool:
    if not progress_payload:
        st.caption(waiting_message)
        return False

    stage_name = str(progress_payload.get("stage") or "")
    stage_idx = int(progress_payload.get("idx", 0) or 0)

    cols = st.columns([1, 1, 1, 1])
    with cols[0]:
        st.metric("Стадия", stage_name or f"stage{stage_idx}")
    with cols[1]:
        st.metric("Stage rows", int(staged_summary.get("stage_rows_current", 0) or 0))
    with cols[2]:
        st.metric("Всего live rows", int(staged_summary.get("total_rows_live", 0) or 0))
    with cols[3]:
        elapsed = staged_summary.get("stage_elapsed_sec")
        st.metric("Время стадии, с", f"{float(elapsed):.1f}" if elapsed is not None else "—")

    if not policy.get("available"):
        return True

    st.markdown("**Seed/promotion policy (текущая стадия)**")
    st.caption(
        f"requested={policy.get('requested_mode') or '—'} → effective={policy.get('effective_mode') or '—'}; "
        f"policy={policy.get('policy_name') or '—'}"
    )
    st.caption(str(policy.get("summary_line") or ""))

    cols = st.columns([1, 1, 1, 1])
    with cols[0]:
        st.metric("Target seeds", int(policy.get("target_seed_count", 0) or 0))
    with cols[1]:
        st.metric("Selected", int((policy.get("selected_counts") or {}).get("total", 0) or 0))
    with cols[2]:
        st.metric("Focus budget", int(policy.get("focus_budget", 0) or 0))
    with cols[3]:
        st.metric("Explore budget", int(policy.get("explore_budget", 0) or 0))

    if policy.get("priority_params"):
        st.caption("Priority params: " + ", ".join(str(x) for x in (policy.get("priority_params") or [])[:8]))
    if policy.get("underfilled"):
        st.warning(
            "Seed budget underfilled: "
            + str(policy.get("underfill_message") or policy.get("underfill_reason") or "see audit")
        )
    gate_preview = str(policy.get("gate_reason_preview") or "").strip()
    if gate_preview:
        st.caption("Main gate reasons: " + gate_preview)
    return True


__all__ = [
    "render_stage_policy_runtime_snapshot",
]
