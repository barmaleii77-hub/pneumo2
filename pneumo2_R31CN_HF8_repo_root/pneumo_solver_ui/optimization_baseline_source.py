from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Mapping, Optional

from pneumo_solver_ui.name_sanitize import sanitize_id
from pneumo_solver_ui.workspace_contract import resolve_effective_workspace_dir

BASELINE_SOURCE_KIND_SCOPED = "scoped"
BASELINE_SOURCE_KIND_GLOBAL = "global"
BASELINE_SOURCE_KIND_NONE = "none"


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def workspace_baseline_dir(
    *,
    env: Mapping[str, str] | None = None,
    workspace_dir: Path | str | None = None,
    repo_root: Path | str | None = None,
) -> Path:
    if workspace_dir is not None:
        return Path(workspace_dir).resolve() / "baselines"
    root = Path(repo_root) if repo_root is not None else _repo_root()
    effective_workspace = resolve_effective_workspace_dir(
        root,
        env=dict(env) if env is not None else None,
    )
    return effective_workspace / "baselines"


def baseline_problem_scope_dir(baseline_dir: Path | str, problem_hash: str | None) -> Path:
    token = sanitize_id(str(problem_hash or "").strip()) or "unknown_problem"
    return Path(baseline_dir) / "by_problem" / f"p_{token}"


def baseline_source_label(source_kind: str) -> str:
    kind = str(source_kind or "").strip().lower()
    if kind == BASELINE_SOURCE_KIND_SCOPED:
        return "scoped baseline"
    if kind == BASELINE_SOURCE_KIND_GLOBAL:
        return "global baseline fallback"
    return "default_base.json only"


def baseline_source_short_label(source_kind: str) -> str:
    kind = str(source_kind or "").strip().lower()
    if kind == BASELINE_SOURCE_KIND_SCOPED:
        return "scoped"
    if kind == BASELINE_SOURCE_KIND_GLOBAL:
        return "global"
    return "default-only"


def resolve_workspace_baseline_source(
    problem_hash: str | None = None,
    *,
    env: Mapping[str, str] | None = None,
    workspace_dir: Path | str | None = None,
    baseline_dir: Path | str | None = None,
    repo_root: Path | str | None = None,
) -> dict[str, Any]:
    env_map = env if env is not None else os.environ
    current_problem_hash = str(
        problem_hash
        if problem_hash is not None
        else env_map.get("PNEUMO_OPT_PROBLEM_HASH", "")
    ).strip()
    current_baseline_dir = (
        Path(baseline_dir).resolve()
        if baseline_dir is not None
        else workspace_baseline_dir(
            env=env_map,
            workspace_dir=workspace_dir,
            repo_root=repo_root,
        )
    )
    scope_dir = baseline_problem_scope_dir(current_baseline_dir, current_problem_hash)
    scoped_path = scope_dir / "baseline_best.json"
    global_path = current_baseline_dir / "baseline_best.json"

    selected_path: Optional[Path] = None
    source_kind = BASELINE_SOURCE_KIND_NONE
    if current_problem_hash and scoped_path.exists():
        source_kind = BASELINE_SOURCE_KIND_SCOPED
        selected_path = scoped_path
    elif global_path.exists():
        source_kind = BASELINE_SOURCE_KIND_GLOBAL
        selected_path = global_path

    return {
        "version": "baseline_source_v1",
        "problem_hash": current_problem_hash,
        "source_kind": source_kind,
        "source_label": baseline_source_label(source_kind),
        "baseline_path": str(selected_path) if selected_path is not None else "",
        "baseline_dir": str(current_baseline_dir),
        "workspace_dir": str(current_baseline_dir.parent),
        "scope_dir": str(scope_dir),
        "scope_token": scope_dir.name.removeprefix("p_"),
    }


def resolve_workspace_baseline_override_path(
    problem_hash: str | None = None,
    *,
    env: Mapping[str, str] | None = None,
    workspace_dir: Path | str | None = None,
    baseline_dir: Path | str | None = None,
    repo_root: Path | str | None = None,
) -> Optional[Path]:
    payload = resolve_workspace_baseline_source(
        problem_hash=problem_hash,
        env=env,
        workspace_dir=workspace_dir,
        baseline_dir=baseline_dir,
        repo_root=repo_root,
    )
    raw_path = str(payload.get("baseline_path") or "").strip()
    if not raw_path:
        return None
    return Path(raw_path)


def baseline_source_artifact_path(run_dir: Path | str) -> Path:
    return Path(run_dir) / "baseline_source.json"


def write_baseline_source_artifact(run_dir: Path | str, payload: Mapping[str, Any]) -> Path:
    path = baseline_source_artifact_path(run_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(dict(payload or {}), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


def read_baseline_source_artifact(run_dir: Path | str) -> dict[str, Any]:
    path = baseline_source_artifact_path(run_dir)
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return dict(obj) if isinstance(obj, dict) else {}


__all__ = [
    "BASELINE_SOURCE_KIND_GLOBAL",
    "BASELINE_SOURCE_KIND_NONE",
    "BASELINE_SOURCE_KIND_SCOPED",
    "baseline_problem_scope_dir",
    "baseline_source_artifact_path",
    "baseline_source_label",
    "baseline_source_short_label",
    "read_baseline_source_artifact",
    "resolve_workspace_baseline_override_path",
    "resolve_workspace_baseline_source",
    "workspace_baseline_dir",
    "write_baseline_source_artifact",
]
