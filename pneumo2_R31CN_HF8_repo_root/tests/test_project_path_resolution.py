from __future__ import annotations

from pathlib import Path

from pneumo_solver_ui.project_path_resolution import resolve_project_py_path


def test_resolve_project_py_path_recovers_same_basename_from_current_release(tmp_path: Path) -> None:
    here = tmp_path / "pneumo_solver_ui"
    here.mkdir(parents=True)
    worker = here / "opt_worker_v3_margins_energy.py"
    worker.write_text("# worker\n", encoding="utf-8")

    requested = r"C:\Users\User\Downloads\old_release\pneumo_solver_ui\opt_worker_v3_margins_energy.py"
    resolved, messages = resolve_project_py_path(requested, here=here, kind="оптимизатор", default_path=worker)

    assert resolved == worker.resolve()
    assert messages
    assert "Найден одноимённый файл" in messages[0]
