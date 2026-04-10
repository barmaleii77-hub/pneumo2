from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "pneumo_solver_ui" / "desktop_animator" / "app.py").read_text(encoding="utf-8")


def test_animator_source_adds_refractive_glint_and_caustic_layers_for_cylinder_gas() -> None:
    for needle in (
        'self._cyl_glass_glint_lines: List["gl.GLLinePlotItem"] = []',
        'self._cyl_glass_caustic_lines: List["gl.GLLinePlotItem"] = []',
        "def _cylinder_glass_glint_rgba(",
        "def _cylinder_caustic_halo_rgba(",
        "def _cylinder_surface_glint_vertices(",
        "def _cylinder_caustic_halo_vertices(",
        "def _tapered_line_color_array(",
        "cap_glint_vertices = self._cylinder_surface_glint_vertices(",
        "cap_caustic_vertices = self._cylinder_caustic_halo_vertices(",
        "rod_glint_vertices = self._cylinder_surface_glint_vertices(",
        "rod_caustic_vertices = self._cylinder_caustic_halo_vertices(",
    ):
        assert needle in APP


def test_animator_source_maps_glass_fx_to_cap_and_rod_chambers() -> None:
    for needle in (
        'key=f"{cyl_name}:{corner}:cap_glint"',
        'key=f"{cyl_name}:{corner}:cap_caustic"',
        'key=f"{cyl_name}:{corner}:rod_glint"',
        'key=f"{cyl_name}:{corner}:rod_caustic"',
        "_set_colored_line_item(cap_glint_item, cap_glint_vertices, cap_glint_rgba",
        "_set_colored_line_item(cap_caustic_item, cap_caustic_vertices, cap_caustic_rgba",
        "_set_colored_line_item(rod_glint_item, rod_glint_vertices, rod_glint_rgba",
        "_set_colored_line_item(rod_caustic_item, rod_caustic_vertices, rod_caustic_rgba",
    ):
        assert needle in APP
