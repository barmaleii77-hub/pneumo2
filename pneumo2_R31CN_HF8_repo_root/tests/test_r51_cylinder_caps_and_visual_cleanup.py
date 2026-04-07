from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / 'pneumo_solver_ui' / 'desktop_animator' / 'app.py').read_text(encoding='utf-8')


def test_actuator_meshes_use_explicit_capped_cylinder_geometry() -> None:
    assert 'def _capped_cylinder_mesh(radius: float, length: float, cols: int = 28)' in APP
    assert 'Use an explicit capped mesh instead of the generic helper' in APP
    assert 'self._capped_cylinder_mesh(1.0, 1.0, cols=24)' in APP
    assert 'bottom cap (two-sided for translucent actuators)' in APP
    assert 'top cap' in APP


def test_actuator_body_is_readable_and_internal_chamber_is_not_edge_dominant() -> None:
    assert 'drawFaces=True' in APP
    assert 'edgeColor=(0.18, 0.62, 0.88, 0.26)' in APP
    assert 'color=(0.16, 0.52, 0.78, 0.10)' in APP
    assert 'drawEdges=False' in APP
    assert 'color=(0.20, 0.74, 0.98, 0.08)' in APP
