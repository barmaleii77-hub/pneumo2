from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Mapping, Optional

from pneumo_solver_ui.optimization_progress_live import summarize_staged_progress
from pneumo_solver_ui.optimization_stage_policy_live import summarize_stage_policy_runtime
from pneumo_solver_ui.optimization_stage_policy_runtime_ui import (
    render_stage_policy_runtime_snapshot,
)


def load_json_dict(path: Optional[Path]) -> dict[str, Any]:
    if path is None:
        return {}
    try:
        obj = json.loads(Path(path).read_text(encoding="utf-8"))
        return dict(obj) if isinstance(obj, dict) else {}
    except Exception:
        return {}


def render_stage_policy_runtime_block(
    st: Any,
    job: Any,
    *,
    load_json_fn: Callable[[Optional[Path]], Mapping[str, Any]] = load_json_dict,
    summarize_progress_fn: Callable[[Mapping[str, Any], Path], Mapping[str, Any]] = summarize_staged_progress,
    summarize_policy_fn: Callable[..., Mapping[str, Any]] = summarize_stage_policy_runtime,
    render_snapshot_fn: Callable[..., Any] = render_stage_policy_runtime_snapshot,
) -> None:
    payload = dict(load_json_fn(getattr(job, "progress_path", None)))
    if not payload:
        render_snapshot_fn(
            st,
            progress_payload={},
            staged_summary={},
            policy={},
        )
        return
    stage_name = str(payload.get("stage") or "")
    stage_idx = int(payload.get("idx", 0) or 0)
    staged = dict(summarize_progress_fn(payload, Path(getattr(job, "run_dir"))))
    policy = dict(
        summarize_policy_fn(
            Path(getattr(job, "run_dir")),
            stage_idx=stage_idx,
            stage_name=stage_name,
        )
    )
    render_snapshot_fn(
        st,
        progress_payload=payload,
        staged_summary=staged,
        policy=policy,
    )


__all__ = [
    "load_json_dict",
    "render_stage_policy_runtime_block",
]
