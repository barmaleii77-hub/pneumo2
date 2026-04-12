from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "pneumo_solver_ui" / "desktop_animator" / "app.py").read_text(encoding="utf-8")


def test_animator_source_adds_corner_shaft_meshes_and_camera_facing_axes() -> None:
    for needle in (
        'self._corner_light_shaft_meshes: List["gl.GLMeshItem"] = []',
        "def _camera_facing_card_axes(",
        "def _corner_light_shaft_face_colors(",
        "*self._corner_light_shaft_meshes",
        "self._corner_light_shaft_meshes.append(shaft)",
        "shaft_item = self._corner_light_shaft_meshes[idx] if idx < len(self._corner_light_shaft_meshes) else None",
        "shaft_axis_u, shaft_axis_v = self._camera_facing_card_axes(",
        "shaft_face_colors = self._corner_light_shaft_face_colors(",
    ):
        assert needle in APP


def test_animator_source_adds_focus_halo_for_central_suspension_cluster() -> None:
    for needle in (
        'self._focus_halo_mesh: Optional["gl.GLMeshItem"] = None',
        'self._focus_halo_line: Optional["gl.GLLinePlotItem"] = None',
        "def _focus_halo_rgba(",
        "def _focus_halo_face_colors(",
        "focus_candidates: list[np.ndarray] = []",
        "focus_axis_u, focus_axis_v = self._camera_facing_card_axes(",
        'key="suspension-focus-halo"',
        "_set_poly_mesh(",
        "self._focus_halo_mesh,",
        "_set_line_item_data(self._focus_halo_line, np.asarray(focus_ring, dtype=float), colors_rgba=focus_colors)",
    ):
        assert needle in APP
