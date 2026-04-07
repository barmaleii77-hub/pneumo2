from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PNEUMO = ROOT / "pneumo_solver_ui"


def _start_worker_source(path: Path) -> str:
    src = path.read_text(encoding="utf-8")
    mod = ast.parse(src)
    for node in mod.body:
        if isinstance(node, ast.FunctionDef) and node.name == "start_worker":
            return ast.get_source_segment(src, node) or ""
    raise AssertionError(f"start_worker not found in {path}")


def test_r31co_start_worker_closes_parent_log_handles_after_popen() -> None:
    for rel in ("app.py", "pneumo_ui_app.py"):
        src = _start_worker_source(PNEUMO / rel)
        assert "proc = subprocess.Popen(" in src
        assert "finally:" in src
        assert "for _fh in (stdout_f, stderr_f):" in src
        assert "_fh.close()" in src
        assert "ResourceWarning" in src
