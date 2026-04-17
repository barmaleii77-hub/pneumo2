from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pneumo_solver_ui import qt_compare_viewer as viewer_mod
from pneumo_solver_ui.compare_session import CompareSession, save_file


ROOT = Path(__file__).resolve().parents[1]


def test_qt_compare_viewer_auto_find_npz_scans_session_workspaces_and_pointers() -> None:
    text = (ROOT / "pneumo_solver_ui" / "qt_compare_viewer.py").read_text(encoding="utf-8")

    assert "runs/ui_sessions" in text or "'runs' / 'ui_sessions'" in text or '"runs" / "ui_sessions"' in text
    assert "iter_session_workspaces" in text
    assert "workspace_autoload_pointer_candidates" in text
    assert "base_workspace = base / 'workspace'" in text or 'base_workspace = base / "workspace"' in text
    assert "last_session" in text
    assert "_load_compare_session_safely" in text
    assert "--current-context" in text
    assert "startup_from_session_refs" in text
    assert "paths = _compare_session_npz_paths(session)" in text


def test_qt_compare_viewer_loads_saved_compare_session_for_autoload(tmp_path: Path) -> None:
    npz = tmp_path / "T01_osc.npz"
    npz.write_bytes(b"placeholder")
    session_path = tmp_path / "compare_session.json"
    save_file(
        CompareSession(
            npz_paths=[str(npz)],
            table="main",
            signals=["p_fr"],
            compare_contract_hash="abc123",
            current_context_ref={"objective_contract_hash": "current"},
        ),
        session_path,
    )

    loaded = viewer_mod._load_compare_session_safely(session_path)
    paths = viewer_mod._compare_session_npz_paths(loaded)

    assert loaded is not None
    assert loaded.compare_contract_hash == "abc123"
    assert paths == [npz.resolve()]
