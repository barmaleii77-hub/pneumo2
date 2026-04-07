from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_PATH = ROOT / 'pneumo_solver_ui' / 'desktop_animator' / 'app.py'
APP_SRC = APP_PATH.read_text(encoding='utf-8')


def _find_car3d_corner_is_front() -> tuple[ast.FunctionDef, list[str]]:
    mod = ast.parse(APP_SRC)
    for node in mod.body:
        if isinstance(node, ast.ClassDef) and node.name == 'Car3DWidget':
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == '_corner_is_front':
                    deco_names: list[str] = []
                    for deco in item.decorator_list:
                        if isinstance(deco, ast.Name):
                            deco_names.append(deco.id)
                        elif isinstance(deco, ast.Attribute):
                            deco_names.append(deco.attr)
                        else:
                            deco_names.append(type(deco).__name__)
                    return item, deco_names
    raise AssertionError('Car3DWidget._corner_is_front not found')


def test_car3d_corner_is_front_is_static_or_bound_correctly() -> None:
    func, deco_names = _find_car3d_corner_is_front()
    args = func.args.args
    first_arg = args[0].arg if args else None
    assert ('staticmethod' in deco_names) or (first_arg == 'self')


def test_car3d_corner_cylinder_contract_still_calls_corner_front_helper() -> None:
    assert 'front = self._corner_is_front(corner)' in APP_SRC
