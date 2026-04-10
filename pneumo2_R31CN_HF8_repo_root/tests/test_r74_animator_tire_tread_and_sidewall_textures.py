from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "pneumo_solver_ui" / "desktop_animator" / "app.py").read_text(encoding="utf-8")


def test_animator_source_adds_tire_face_color_texture_helper() -> None:
    for needle in (
        "def _wheel_tire_face_colors(",
        "groove_wave = 0.5 + 0.5 * np.sin(",
        "block_wave = 0.5 + 0.5 * np.sin(",
        "branding_band = np.asarray(",
        "contact_scuff = np.asarray(",
        "return np.asarray(rgba, dtype=np.uint8)",
    ):
        assert needle in APP


def test_animator_source_applies_tire_face_colors_to_wheel_mesh() -> None:
    for needle in (
        "wheel_face_colors = self._wheel_tire_face_colors(",
        "wheel_center_xyz=center,",
        "axle_xyz=axle,",
        "forward_xyz=fwd,",
        "up_xyz=up,",
        "wheel_face_colors = self._scene_grade_color_array(",
        "w.setMeshData(meshdata=gl.MeshData(vertexes=v_wheel, faces=self._wheel_faces, faceColors=wheel_face_colors))",
    ):
        assert needle in APP
