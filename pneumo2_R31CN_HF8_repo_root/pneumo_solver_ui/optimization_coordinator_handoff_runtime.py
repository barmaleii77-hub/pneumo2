from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from pneumo_solver_ui.optimization_coordinator_handoff import (
    COORDINATOR_HANDOFF_DIRNAME,
    COORDINATOR_HANDOFF_PLAN_FILENAME,
)
from pneumo_solver_ui.optimization_launch_plan_runtime import (
    LaunchPlan,
    tools_root_from_ui_root,
)
from pneumo_solver_ui.optimization_runtime_paths import (
    console_python_executable,
)


def coordinator_handoff_plan_path(source_run_dir: str | Path) -> Path:
    return Path(source_run_dir).resolve() / COORDINATOR_HANDOFF_DIRNAME / COORDINATOR_HANDOFF_PLAN_FILENAME


def load_coordinator_handoff_payload(
    source_run_dir: str | Path | None = None,
    *,
    handoff_plan_path: str | Path | None = None,
) -> dict[str, Any]:
    path = Path(handoff_plan_path).resolve() if handoff_plan_path is not None else coordinator_handoff_plan_path(source_run_dir or "")
    if not path.exists():
        raise FileNotFoundError(f"Coordinator handoff plan not found: {path}")
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        raise RuntimeError(f"Coordinator handoff plan must be a JSON object: {path}")
    payload = dict(raw)
    cmd_args = payload.get("cmd_args")
    if not isinstance(cmd_args, list) or not all(isinstance(item, str) for item in cmd_args):
        raise RuntimeError(f"Coordinator handoff plan has invalid cmd_args: {path}")
    return payload


def coordinator_handoff_target_run_dir(payload: Mapping[str, Any]) -> Path:
    cmd_args = list(payload.get("cmd_args") or [])
    if "--run-dir" in cmd_args:
        idx = cmd_args.index("--run-dir") + 1
        if idx < len(cmd_args):
            return Path(str(cmd_args[idx])).resolve()
    raise RuntimeError("Coordinator handoff plan is missing --run-dir")


def build_coordinator_handoff_launch_plan(
    source_run_dir: str | Path | None = None,
    *,
    ui_root: Path,
    python_executable: str,
    handoff_plan_path: str | Path | None = None,
) -> LaunchPlan:
    ui_root = Path(ui_root).resolve()
    payload = load_coordinator_handoff_payload(source_run_dir, handoff_plan_path=handoff_plan_path)
    cmd_args = [str(item) for item in list(payload.get("cmd_args") or [])]
    python_exec = console_python_executable(python_executable)
    cmd = [
        python_exec,
        str((tools_root_from_ui_root(ui_root) / "dist_opt_coordinator.py").resolve()),
        *cmd_args,
    ]
    launch_run_dir = coordinator_handoff_target_run_dir(payload)
    budget = int(payload.get("recommended_budget", 0) or 0)
    backend = str(payload.get("recommended_backend") or "ray")
    proposer = str(payload.get("recommended_proposer") or "auto").strip() or "auto"
    q_eff = max(1, int(payload.get("recommended_q", 1) or 1))
    label_bits = [f"Handoff/{backend}"]
    if proposer and proposer != "auto":
        label_bits.append(proposer)
    if q_eff > 1:
        label_bits.append(f"q{q_eff}")
    return LaunchPlan(
        label="/".join(label_bits),
        cmd=cmd,
        pipeline_mode="coordinator",
        progress_path=None,
        budget=budget,
        stop_file=None,
        launch_run_dir=launch_run_dir,
    )


__all__ = [
    "build_coordinator_handoff_launch_plan",
    "coordinator_handoff_plan_path",
    "coordinator_handoff_target_run_dir",
    "load_coordinator_handoff_payload",
]
