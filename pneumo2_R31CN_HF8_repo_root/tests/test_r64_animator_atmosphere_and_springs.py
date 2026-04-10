from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "pneumo_solver_ui" / "desktop_animator" / "app.py").read_text(encoding="utf-8")


def test_animator_source_reads_family_aware_spring_runtime_and_builds_coil_meshes() -> None:
    for needle in (
        "spring_geometry_key",
        "spring_family_active_flag_column",
        "spring_family_runtime_column",
        "self._spring_metric_series_map: Dict[str, np.ndarray] = {}",
        "self._spring_active_series_map: Dict[str, np.ndarray] = {}",
        'self._spring_meshes: List["gl.GLMeshItem"] = []',
        'self._spring_glow_lines: List["gl.GLLinePlotItem"] = []',
        "def _sample_spring_active_flag(",
        "def _sample_spring_runtime_metric_m(",
        "def _spring_geometry_m(",
        "def _spring_centerline_vertices(",
        "def _tube_mesh_from_polyline(",
        "runtime_col = spring_family_runtime_column(metric, cyl, corner)",
        "active_col = spring_family_active_flag_column(cyl, corner)",
        "spring = gl.GLMeshItem(",
        "spring_glow = gl.GLLinePlotItem(",
        "spring_visual_states.append(spring_state)",
        "spring_path = self._spring_centerline_vertices(",
        "_set_poly_mesh(spring_mesh, spring_verts, spring_faces)",
        "self._spring_visual_rgba(",
    ):
        assert needle in APP


def test_animator_source_adds_contact_glaze_and_accent_rings_around_patch() -> None:
    for needle in (
        'self._contact_glaze_meshes: List["gl.GLMeshItem"] = []',
        'self._contact_accent_rings: List["gl.GLLinePlotItem"] = []',
        "def _ellipse_line_vertices(",
        "def _contact_glaze_face_colors(",
        "def _contact_accent_ring_rgba(",
        "glaze = gl.GLMeshItem(",
        "accent_ring = gl.GLLinePlotItem(",
        "glaze_face_colors = self._contact_glaze_face_colors(",
        "ring_vertices = self._ellipse_line_vertices(",
        "accent_rgba = self._contact_accent_ring_rgba(",
        "face_colors_rgba_u8=glaze_face_colors",
    ):
        assert needle in APP
