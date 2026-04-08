from __future__ import annotations

from pathlib import Path

from pneumo_solver_ui.run_artifacts import (
    global_anim_latest_pointer_path,
    global_simulation_pointer_path,
    local_anim_latest_export_paths,
)
from pneumo_solver_ui.tools.send_bundle_contract import ANIM_LOCAL_NPZ, ANIM_LOCAL_POINTER


def _dedupe_paths(paths: list[Path]) -> list[Path]:
    seen: set[str] = set()
    uniq: list[Path] = []
    for path in paths:
        key = str(Path(path))
        if key in seen:
            continue
        seen.add(key)
        uniq.append(Path(path))
    return uniq


def workspace_anim_pointer_candidates(workspace_dir: Path) -> list[Path]:
    ws_dir = Path(workspace_dir)
    _, local_pointer = local_anim_latest_export_paths(ws_dir / "exports", ensure_exists=False)
    global_pointer = global_anim_latest_pointer_path(ws_dir, ensure_exists=False)
    return [global_pointer, local_pointer]


def iter_session_workspaces(project_root: Path, limit: int | None = None) -> list[Path]:
    candidates: list[Path] = []
    ui_parent = Path(project_root) / "runs" / "ui_sessions"
    if not ui_parent.exists():
        return candidates
    try:
        ui_dirs = [path for path in ui_parent.iterdir() if path.is_dir() and path.name.startswith("UI_")]
        ui_dirs.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    except Exception:
        return candidates
    if limit is not None:
        ui_dirs = ui_dirs[: max(0, int(limit))]
    for ui_dir in ui_dirs:
        ws_dir = ui_dir / "workspace"
        if ws_dir.exists() and ws_dir.is_dir():
            candidates.append(ws_dir)
    return _dedupe_paths(candidates)


def session_anim_pointer_candidates(project_root: Path, limit: int = 5) -> list[Path]:
    candidates: list[Path] = []
    for ws_dir in iter_session_workspaces(project_root, limit=limit):
        candidates.extend(workspace_anim_pointer_candidates(ws_dir))
    return _dedupe_paths(candidates)


def legacy_project_anim_pointer_candidates(project_root: Path) -> list[Path]:
    root = Path(project_root)
    candidates: list[Path] = []
    candidates.extend(workspace_anim_pointer_candidates(root / "pneumo_solver_ui" / "workspace"))
    candidates.extend(workspace_anim_pointer_candidates(root / "workspace"))
    candidates.append(root / "pneumo_solver_ui" / "workspace" / Path(ANIM_LOCAL_POINTER).name)
    return _dedupe_paths(candidates)


def default_anim_pointer_candidates(project_root: Path, session_limit: int = 5) -> list[Path]:
    candidates: list[Path] = []
    try:
        current_global = global_anim_latest_pointer_path(ensure_exists=False)
        candidates.extend(workspace_anim_pointer_candidates(current_global.parent.parent))
    except Exception:
        pass
    candidates.extend(session_anim_pointer_candidates(project_root, limit=session_limit))
    candidates.extend(legacy_project_anim_pointer_candidates(project_root))
    return _dedupe_paths(candidates)


def default_anim_pointer_path(project_root: Path, session_limit: int = 5) -> Path:
    candidates = default_anim_pointer_candidates(project_root, session_limit=session_limit)
    for path in candidates:
        try:
            if path.exists():
                return path
        except Exception:
            continue
    if candidates:
        return candidates[0]
    return global_anim_latest_pointer_path(ensure_exists=False)


def nearest_workspace_dirs(path: Path) -> list[Path]:
    probe = Path(path)
    candidates: list[Path] = []
    for anc in [probe.parent, *probe.parents]:
        try:
            if anc.name == "workspace":
                candidates.append(anc)
        except Exception:
            pass
        try:
            child_ws = anc / "workspace"
            if child_ws.exists() and child_ws.is_dir():
                candidates.append(child_ws)
        except Exception:
            pass
    return _dedupe_paths(candidates)


def nearest_anim_pointer_candidates(npz_path: Path) -> list[Path]:
    probe = Path(npz_path)
    candidates: list[Path] = []
    if probe.name.lower() == Path(ANIM_LOCAL_NPZ).name.lower():
        candidates.append(probe.with_name(Path(ANIM_LOCAL_POINTER).name))
    for workspace_dir in nearest_workspace_dirs(probe):
        candidates.extend(workspace_anim_pointer_candidates(workspace_dir))
    return _dedupe_paths(candidates)


def workspace_autoload_pointer_candidates(workspace_dir: Path) -> list[Path]:
    ws_dir = Path(workspace_dir)
    candidates = list(workspace_anim_pointer_candidates(ws_dir))
    candidates.append(global_simulation_pointer_path(ws_dir, ensure_exists=False))
    return _dedupe_paths(candidates)
