from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "pneumo_solver_ui" / "desktop_animator" / "app.py").read_text(encoding="utf-8")


def test_animator_source_adds_depth_fade_scene_fog_layers() -> None:
    for needle in (
        'self._scene_fog_meshes: List["gl.GLMeshItem"] = []',
        "def _scene_fog_face_colors(",
        "theme_rgb: Tuple[int, int, int]",
        "density_u: float",
        "*self._scene_fog_meshes",
        "self._scene_fog_meshes.append(fog)",
        "fog_specs = (",
        "fog_face_colors = self._scene_fog_face_colors(",
        "for fog_item in self._scene_fog_meshes:",
    ):
        assert needle in APP


def test_animator_source_adds_corner_key_light_hierarchy() -> None:
    for needle in (
        'self._corner_key_light_lines: List["gl.GLLinePlotItem"] = []',
        "def _ellipse_arc_vertices(",
        "def _corner_key_light_rgba(",
        "self._corner_key_light_lines.append(key_light)",
        'key=f"corner-key-light-{corners[idx]}-{idx}"',
        "key_light_arc = self._ellipse_arc_vertices(",
        "key_light_rgba = self._corner_key_light_rgba(",
        "for key_light in self._corner_key_light_lines:",
    ):
        assert needle in APP
