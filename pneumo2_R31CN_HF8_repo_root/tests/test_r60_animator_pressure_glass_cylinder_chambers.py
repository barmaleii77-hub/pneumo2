from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "pneumo_solver_ui" / "desktop_animator" / "app.py").read_text(encoding="utf-8")


def test_animator_source_reads_named_cylinder_chamber_pressures_for_glass_materials() -> None:
    for needle in (
        "def _cylinder_chamber_node_name(",
        'return f"Ц{1 if int(cyl_index) == 1 else 2}_{corner}_{chamber_code}"',
        "def _smooth_rgba(",
        "def _sample_cylinder_chamber_pressure_pa(",
        "self._cyl_pressure_visual_min_bar_g = -0.35",
        "self._cyl_pressure_visual_max_bar_g = 10.0",
        'for chamber_kind in ("БП", "ШП"):',
        "self._cyl_pressure_series_map[str(node)] = np.asarray(bundle.p.column(node), dtype=float).reshape(-1)",
        "gauge_hi = float(np.nanpercentile(gauge_all, 98.0))",
    ):
        assert needle in APP


def test_animator_source_adds_pressure_colored_glass_for_cap_and_rod_side_gas_volumes() -> None:
    for needle in (
        "_cyl_rod_chamber_meshes",
        "_cyl_cap_ring_lines",
        "_cyl_gland_ring_lines",
        "def _blend_rgba(",
        "def _cylinder_gas_glass_rgba(",
        "def _apply_mesh_material(",
        "self._sample_cylinder_chamber_pressure_pa(",
        'chamber_kind="БП"',
        'chamber_kind="ШП"',
        'housing_seg = packaging_state.get("housing_seg")',
        'piston_center = packaging_state.get("piston_center")',
        "cap_ring_vertices = self._circle_line_vertices(",
        "gland_ring_vertices = self._circle_line_vertices(",
        "piston_ring_rgba = self._blend_rgba(",
        "rod_core_rgba = tuple(rod_edge_rgba[:3])",
        "self._cyl_rod_chamber_meshes[cyl_mesh_idx]",
    ):
        assert needle in APP
