from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pneumo_solver_ui.optimization_run_history import (
    summarize_optimization_run,
    summarize_run_packaging_snapshot,
)
from pneumo_solver_ui.optimization_stage_policy_live import summarize_stage_policy_runtime
from pneumo_solver_ui.run_artifacts import load_last_opt_ptr


def load_last_optimization_pointer_snapshot() -> dict[str, Any]:
    raw = dict(load_last_opt_ptr() or {})
    meta = dict(raw.get("meta") or {})

    run_dir = None
    raw_run_dir = raw.get("run_dir")
    if isinstance(raw_run_dir, str) and raw_run_dir.strip():
        try:
            run_dir = Path(raw_run_dir).expanduser()
        except Exception:
            run_dir = None

    mode_label = "—"
    if run_dir is not None:
        try:
            parts_lower = {str(part).lower() for part in run_dir.parts}
        except Exception:
            parts_lower = set()
        if (run_dir / "sp.json").exists() or "staged" in parts_lower:
            mode_label = "StageRunner"
        else:
            backend = str(meta.get("backend") or "").strip()
            mode_label = f"Distributed coordinator ({backend})" if backend else "Distributed coordinator"

    live_policy = {}
    if run_dir is not None and run_dir.exists():
        try:
            stage_dirs = sorted(
                [p for p in run_dir.iterdir() if p.is_dir() and p.name.startswith("s") and p.name[1:].isdigit()],
                key=lambda p: int(p.name[1:] or 0),
            )
        except Exception:
            stage_dirs = []
        if stage_dirs:
            last_stage = stage_dirs[-1]
            try:
                stage_idx = int(last_stage.name[1:] or 0)
            except Exception:
                stage_idx = 0
            stage_name = {
                0: "stage0_relevance",
                1: "stage1_long",
                2: "stage2_final",
            }.get(stage_idx, f"stage{stage_idx}")
            try:
                live_policy = summarize_stage_policy_runtime(run_dir, stage_idx=stage_idx, stage_name=stage_name) or {}
            except Exception:
                live_policy = {}

    sp_payload = {}
    if run_dir is not None and (run_dir / "sp.json").exists():
        try:
            sp_payload = json.loads((run_dir / "sp.json").read_text(encoding="utf-8"))
        except Exception:
            sp_payload = {}

    opt_summary = None
    packaging_snapshot = None
    if run_dir is not None and run_dir.exists():
        try:
            opt_summary = summarize_optimization_run(run_dir)
        except Exception:
            opt_summary = None
        if opt_summary is not None:
            try:
                packaging_snapshot = summarize_run_packaging_snapshot(opt_summary.result_path)
            except Exception:
                packaging_snapshot = None

    return {
        "raw": raw,
        "meta": meta,
        "run_dir": run_dir,
        "mode_label": mode_label,
        "live_policy": live_policy,
        "sp_payload": sp_payload,
        "opt_summary": opt_summary,
        "packaging_snapshot": packaging_snapshot,
    }


__all__ = [
    "load_last_optimization_pointer_snapshot",
]
