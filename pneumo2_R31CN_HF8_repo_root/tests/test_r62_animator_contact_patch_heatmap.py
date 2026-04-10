from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "pneumo_solver_ui" / "desktop_animator" / "app.py").read_text(encoding="utf-8")


def test_animator_source_caches_tire_force_for_contact_patch_visual_scaling() -> None:
    for needle in (
        "self._tire_force_series_map: Dict[str, np.ndarray] = {}",
        "self._tire_force_visual_max_n: float = 4500.0",
        "def _sample_corner_tire_force_n(",
        "corner_cache = _ensure_corner_signal_cache(bundle)",
        'self._tire_force_series_map[str(corner)] = np.asarray(',
        "force_hi = float(np.nanpercentile(finite_force, 98.0))",
    ):
        assert needle in APP


def test_animator_source_builds_pressure_style_heatmap_colors_for_contact_patch_mesh() -> None:
    for needle in (
        "def _contact_patch_marker_rgba(",
        "def _contact_patch_face_colors(",
        "patch_face_colors_all: list[np.ndarray] = []",
        "tire_force_n = float(",
        "marker_rgba = self._contact_patch_marker_rgba(tire_force_n, in_air=in_air)",
        "patch_face_colors_i = self._contact_patch_face_colors(",
        "self._contact_pts.setData(pos=marker_pos, color=marker_cols)",
        "self._contact_links.setData(pos=link_pos, color=link_cols)",
        "meshdata=gl.MeshData(vertexes=patch_verts, faces=patch_faces, faceColors=patch_face_colors)",
    ):
        assert needle in APP
