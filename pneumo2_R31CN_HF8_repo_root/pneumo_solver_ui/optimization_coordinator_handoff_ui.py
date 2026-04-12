from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from pneumo_solver_ui.optimization_coordinator_handoff_summary import (
    handoff_preset_tag,
    handoff_recommendation_reason_lines,
    recommended_handoff_button_help,
    recommended_handoff_button_label,
    summarize_handoff_payload,
)
from pneumo_solver_ui.optimization_coordinator_handoff_runtime import (
    coordinator_handoff_plan_path,
    load_coordinator_handoff_payload,
)

def summarize_coordinator_handoff(source_run_dir: Path | str) -> dict[str, Any]:
    run_dir = Path(source_run_dir).resolve()
    plan_path = coordinator_handoff_plan_path(run_dir)
    if not plan_path.exists():
        return {
            "available": False,
            "source_run_dir": run_dir,
            "plan_path": plan_path,
        }
    payload = load_coordinator_handoff_payload(run_dir)
    return summarize_handoff_payload(payload, source_run_dir=run_dir, plan_path=plan_path)


def render_coordinator_handoff_action(
    st: Any,
    *,
    source_run_dir: Path | str,
    start_handoff_fn: Callable[[Path], bool] | None,
    button_label: str = "",
    button_help: str = "",
    button_key: str,
    missing_caption: str = "",
    recommended_action: bool = True,
) -> bool:
    summary = summarize_coordinator_handoff(source_run_dir)
    if not bool(summary.get("available")):
        if str(missing_caption or "").strip():
            st.caption(str(missing_caption))
        return False

    backend = str(summary.get("backend") or "coordinator")
    proposer = str(summary.get("proposer") or "auto")
    q_eff = max(1, int(summary.get("q", 1) or 1))
    budget = int(summary.get("budget", 0) or 0)
    seed_count = int(summary.get("seed_count", 0) or 0)
    suite_family = str(summary.get("suite_family") or "unknown")
    preset_tag = handoff_preset_tag(summary)
    if recommended_action:
        st.caption(f"Рекомендуемое следующее действие: full-ring handoff `{preset_tag}`.")
    st.caption(
        "Рекомендуемый full-ring preset: "
        f"suite={suite_family}, backend={backend}, proposer={proposer}, q={q_eff}, "
        f"budget={budget}, seed-candidates={seed_count}."
    )
    for line in handoff_recommendation_reason_lines(summary):
        st.caption(line)
    if bool(summary.get("requires_full_ring_validation", False)):
        st.caption(
            "Этот handoff сохраняет обязательную full-ring проверку: длинные пользовательские кольца "
            "остаются финальным критерием, а не заменяются короткими фрагментами."
        )
    if start_handoff_fn is None:
        return False
    label_eff = str(button_label or "").strip() or recommended_handoff_button_label(summary)
    help_eff = str(button_help or "").strip() or recommended_handoff_button_help(summary)
    if st.button(
        label_eff,
        key=button_key,
        help=help_eff,
        type="primary" if recommended_action else "secondary",
    ):
        return bool(start_handoff_fn(Path(summary["source_run_dir"])))
    return False


__all__ = [
    "handoff_preset_tag",
    "handoff_recommendation_reason_lines",
    "render_coordinator_handoff_action",
    "recommended_handoff_button_help",
    "recommended_handoff_button_label",
    "summarize_coordinator_handoff",
]
