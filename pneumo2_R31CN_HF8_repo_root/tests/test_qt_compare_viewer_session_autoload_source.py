from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_qt_compare_viewer_auto_find_npz_scans_session_workspaces_and_pointers() -> None:
    text = (ROOT / "pneumo_solver_ui" / "qt_compare_viewer.py").read_text(encoding="utf-8")

    assert "runs/ui_sessions" in text or "'runs' / 'ui_sessions'" in text or '"runs" / "ui_sessions"' in text
    assert "iter_session_workspaces" in text
    assert "workspace_autoload_pointer_candidates" in text
    assert "base_workspace = base / 'workspace'" in text or 'base_workspace = base / "workspace"' in text
