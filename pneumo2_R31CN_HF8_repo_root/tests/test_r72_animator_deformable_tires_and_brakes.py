from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "pneumo_solver_ui" / "desktop_animator" / "app.py").read_text(encoding="utf-8")


def test_animator_source_adds_deformable_tire_and_brake_helpers() -> None:
    for needle in (
        'self._wheel_brake_rotor_meshes: List["gl.GLMeshItem"] = []',
        'self._wheel_brake_caliper_meshes: List["gl.GLMeshItem"] = []',
        "def _oriented_box_mesh(",
        "def _deformed_wheel_vertices(",
        "def _wheel_tire_material_rgba(",
        "def _wheel_brake_material_rgba(",
    ):
        assert needle in APP


def test_animator_source_builds_brake_meshes_and_updates_tires_per_corner() -> None:
    for needle in (
        "*self._wheel_brake_rotor_meshes",
        "*self._wheel_brake_caliper_meshes",
        "self._wheel_brake_rotor_meshes.append(rotor)",
        "self._wheel_brake_caliper_meshes.append(caliper)",
        "deformed_wheel = self._deformed_wheel_vertices(",
        "wheel_face_rgba, wheel_edge_rgba = self._wheel_tire_material_rgba(",
        "rotor_item = self._wheel_brake_rotor_meshes[idx] if idx < len(self._wheel_brake_rotor_meshes) else None",
        "caliper_item = self._wheel_brake_caliper_meshes[idx] if idx < len(self._wheel_brake_caliper_meshes) else None",
        "_set_mesh_from_segment(rotor_item, rotor_seg, rotor_radius)",
        "caliper_verts, caliper_faces = self._oriented_box_mesh(",
        "caliper_face_rgba, caliper_edge_rgba = self._wheel_brake_material_rgba(",
    ):
        assert needle in APP
