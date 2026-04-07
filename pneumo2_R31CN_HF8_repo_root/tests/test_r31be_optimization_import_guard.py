# -*- coding: utf-8 -*-
from __future__ import annotations

import ast
from pathlib import Path


def _imported_names(tree: ast.AST) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "pneumo_solver_ui.optimization_input_contract":
            names.update(alias.name for alias in node.names)
    return names


def _used_names(tree: ast.AST) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            names.add(node.id)
    return names


def test_pneumo_ui_app_imports_sanitize_optimization_inputs_when_used() -> None:
    path = Path("pneumo_solver_ui/pneumo_ui_app.py")
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    used = _used_names(tree)
    imported = _imported_names(tree)
    assert "sanitize_optimization_inputs" not in used or "sanitize_optimization_inputs" in imported


def test_root_app_imports_sanitize_optimization_inputs_when_used() -> None:
    path = Path("pneumo_solver_ui/app.py")
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    used = _used_names(tree)
    imported = _imported_names(tree)
    assert "sanitize_optimization_inputs" not in used or "sanitize_optimization_inputs" in imported
