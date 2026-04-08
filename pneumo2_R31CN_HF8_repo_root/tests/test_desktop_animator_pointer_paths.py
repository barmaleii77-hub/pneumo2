from __future__ import annotations

from pathlib import Path

from pneumo_solver_ui.desktop_animator.pointer_paths import (
    default_anim_pointer_path,
    nearest_anim_pointer_candidates,
    workspace_autoload_pointer_candidates,
    workspace_anim_pointer_candidates,
)
from pneumo_solver_ui.run_artifacts import (
    global_anim_latest_pointer_path,
    global_simulation_pointer_path,
    local_anim_latest_export_paths,
)


def test_workspace_anim_pointer_candidates_use_shared_run_artifacts_helpers(tmp_path: Path) -> None:
    workspace_dir = tmp_path / "workspace"

    candidates = workspace_anim_pointer_candidates(workspace_dir)
    expected_local = local_anim_latest_export_paths(workspace_dir / "exports", ensure_exists=False)[1]
    expected_global = global_anim_latest_pointer_path(workspace_dir, ensure_exists=False)

    assert candidates == [expected_global, expected_local]
    assert (workspace_dir / "_pointers").exists() is False
    assert (workspace_dir / "exports").exists() is False


def test_default_anim_pointer_path_prefers_current_workspace_global_pointer(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / "project"
    current_workspace = tmp_path / "current_workspace"
    monkeypatch.setenv("PNEUMO_WORKSPACE_DIR", str(current_workspace))

    current_pointer = global_anim_latest_pointer_path(current_workspace)
    current_pointer.write_text("{}", encoding="utf-8")

    session_pointer = project_root / "runs" / "ui_sessions" / "UI_001" / "workspace" / "_pointers" / "anim_latest.json"
    session_pointer.parent.mkdir(parents=True, exist_ok=True)
    session_pointer.write_text("{}", encoding="utf-8")

    chosen = default_anim_pointer_path(project_root)

    assert chosen == current_pointer


def test_default_anim_pointer_path_falls_back_to_session_workspace_pointer(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / "project"
    current_workspace = tmp_path / "current_workspace"
    monkeypatch.setenv("PNEUMO_WORKSPACE_DIR", str(current_workspace))

    session_pointer = project_root / "runs" / "ui_sessions" / "UI_002" / "workspace" / "_pointers" / "anim_latest.json"
    session_pointer.parent.mkdir(parents=True, exist_ok=True)
    session_pointer.write_text("{}", encoding="utf-8")

    legacy_pointer = project_root / "pneumo_solver_ui" / "workspace" / "_pointers" / "anim_latest.json"
    legacy_pointer.parent.mkdir(parents=True, exist_ok=True)
    legacy_pointer.write_text("{}", encoding="utf-8")

    chosen = default_anim_pointer_path(project_root)

    assert chosen == session_pointer


def test_nearest_anim_pointer_candidates_cover_local_and_workspace_global_paths(tmp_path: Path) -> None:
    exports_dir = tmp_path / "workspace" / "exports"
    exports_dir.mkdir(parents=True, exist_ok=True)
    npz_path = exports_dir / "anim_latest.npz"
    npz_path.write_bytes(b"npz")

    candidates = nearest_anim_pointer_candidates(npz_path)

    assert candidates[0] == exports_dir / "anim_latest.json"
    assert candidates[1] == tmp_path / "workspace" / "_pointers" / "anim_latest.json"


def test_workspace_autoload_pointer_candidates_include_anim_and_latest_simulation(tmp_path: Path) -> None:
    workspace_dir = tmp_path / "workspace"

    candidates = workspace_autoload_pointer_candidates(workspace_dir)

    assert candidates == [
        global_anim_latest_pointer_path(workspace_dir, ensure_exists=False),
        local_anim_latest_export_paths(workspace_dir / "exports", ensure_exists=False)[1],
        global_simulation_pointer_path(workspace_dir, ensure_exists=False),
    ]
