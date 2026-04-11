from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "pneumo_solver_ui" / "desktop_animator" / "app.py").read_text(encoding="utf-8")


def test_animator_source_adds_scene_curtains_and_portal_layers() -> None:
    for needle in (
        'self._scene_side_curtain_meshes: List["gl.GLMeshItem"] = []',
        'self._scene_portal_line: Optional["gl.GLLinePlotItem"] = None',
        "def _scene_side_curtain_rgba(",
        "def _scene_side_curtain_face_colors(",
        "def _scene_portal_rgba(",
        "self._scene_side_curtain_meshes.append(curtain)",
        "self._scene_portal_line = gl.GLLinePlotItem(",
    ):
        assert needle in APP


def test_animator_source_scene_grade_drives_scene_curtains_and_portal_runtime() -> None:
    for needle in (
        "curtain_face_colors = self._scene_side_curtain_face_colors(",
        'key=f"scene-side-curtain-scene-grade-{curtain_idx}"',
        "portal_rgba = self._scene_portal_rgba(",
        'key="scene-portal-line-scene-grade"',
        "self._scene_portal_line.setData(pos=np.asarray(portal_vertices, dtype=float), color=portal_colors)",
    ):
        assert needle in APP
