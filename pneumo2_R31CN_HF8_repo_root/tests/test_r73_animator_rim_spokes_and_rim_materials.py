from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "pneumo_solver_ui" / "desktop_animator" / "app.py").read_text(encoding="utf-8")


def test_animator_source_adds_rim_mesh_layer_and_helpers() -> None:
    for needle in (
        'self._wheel_rim_meshes: List["gl.GLMeshItem"] = []',
        "def _concat_mesh_parts(",
        "def _wheel_rim_mesh(",
        "def _wheel_rim_material_rgba(",
        "*self._wheel_rim_meshes",
        "self._wheel_rim_meshes = []",
        "self._wheel_rim_meshes.append(rim)",
    ):
        assert needle in APP


def test_animator_source_updates_rim_spokes_per_wheel() -> None:
    for needle in (
        "rim_item = self._wheel_rim_meshes[idx] if idx < len(self._wheel_rim_meshes) else None",
        "rim_verts, rim_faces = self._wheel_rim_mesh(",
        "_set_poly_mesh(rim_item, rim_verts, rim_faces)",
        "rim_face_rgba, rim_edge_rgba = self._wheel_rim_material_rgba(",
        'key=f"wheel-rim-{corners[idx]}"',
        'key=f"wheel-rim-scene-face-{corners[idx]}"',
        'key=f"wheel-rim-scene-edge-{corners[idx]}"',
        "for mesh_idx in range(len(wheel_pose_centers), len(self._wheel_rim_meshes)):",
    ):
        assert needle in APP
