from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PNEUMO = ROOT / "pneumo_solver_ui"
HELPERS = PNEUMO / "ui_process_helpers.py"


def _function_source(path: Path, name: str) -> str:
    src = path.read_text(encoding="utf-8")
    mod = ast.parse(src)
    for node in mod.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return ast.get_source_segment(src, node) or ""
    raise AssertionError(f"{name} not found in {path}")


def test_r31co_shared_start_background_worker_closes_parent_log_handles_after_popen() -> None:
    src = _function_source(HELPERS, "start_background_worker")
    assert "proc = subprocess.Popen(" in src
    assert "finally:" in src
    assert "for _fh in (stdout_f, stderr_f):" in src
    assert "_fh.close()" in src
    assert "ResourceWarning" in src


def test_r31co_large_ui_entrypoints_use_shared_worker_helper() -> None:
    for rel in ("app.py", "pneumo_ui_app.py"):
        src = (PNEUMO / rel).read_text(encoding="utf-8")
        assert "from pneumo_solver_ui.ui_process_helpers import (" in src
        assert "start_background_worker" in src
        assert "start_worker = partial(" in src
        assert "def start_worker(" not in src
