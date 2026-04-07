from __future__ import annotations

import ast
from pathlib import Path

APP_PATH = Path(__file__).resolve().parents[1] / 'pneumo_solver_ui' / 'desktop_animator' / 'app.py'
APP_SRC = APP_PATH.read_text(encoding='utf-8')


def _find_circle_line_vertices() -> tuple[ast.FunctionDef, list[str]]:
    mod = ast.parse(APP_SRC)
    for node in mod.body:
        if isinstance(node, ast.ClassDef) and node.name == 'Car3DWidget':
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == '_circle_line_vertices':
                    deco_names: list[str] = []
                    for deco in item.decorator_list:
                        if isinstance(deco, ast.Name):
                            deco_names.append(deco.id)
                        elif isinstance(deco, ast.Attribute):
                            deco_names.append(deco.attr)
                    return item, deco_names
    raise AssertionError('Car3DWidget._circle_line_vertices not found')


def test_circle_line_vertices_staticmethod_signature_is_valid() -> None:
    func, deco_names = _find_circle_line_vertices()
    assert 'staticmethod' in deco_names
    arg_names = [a.arg for a in func.args.args]
    assert 'self' not in arg_names, 'staticmethod helper must not declare self positional arg'
    kwonly = [a.arg for a in func.args.kwonlyargs]
    assert kwonly[:3] == ['radius_m', 'center_xyz', 'normal_xyz']


def test_circle_line_vertices_callsite_stays_bound_and_guarded() -> None:
    assert 'self._circle_line_vertices(' in APP_SRC
    assert 'Car3D piston ring polyline build failed; hiding piston ring instead of aborting frame.' in APP_SRC
    assert '_set_line_item_pos(self._cyl_piston_ring_lines[cyl_mesh_idx], ring_vertices)' in APP_SRC
