from __future__ import annotations

import ast
from pathlib import Path


APP_PATH = Path(__file__).resolve().parents[1] / "pneumo_solver_ui" / "pneumo_ui_app.py"


def test_pneumo_ui_app_does_not_contain_bare_lock_expression_statement() -> None:
    tree = ast.parse(APP_PATH.read_text(encoding="utf-8"))

    offenders: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Expr):
            continue
        if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            continue
        if isinstance(node.value, ast.Name) and node.value.id == "_UI_LOG_WRITE_LOCK":
            offenders.append((node.lineno, node.value.id))

    assert offenders == []
