from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "pneumo_solver_ui" / "desktop_animator" / "app.py").read_text(encoding="utf-8")


def test_update_frame_declares_local_gl_helpers_before_first_use() -> None:
    assert APP.index("        def _set_mesh_from_segment(") < APP.index("                _set_mesh_from_segment(rotor_item, rotor_seg, rotor_radius)")
    assert APP.index("        def _set_poly_mesh(") < APP.index("                _set_poly_mesh(rim_item, rim_verts, rim_faces)")
    assert APP.index("        def _set_line_item_pos(") < APP.index("            _set_line_item_pos(self._wheel_spin_glow_lines[line_idx], None)")
    assert APP.index("        def _set_colored_line_item(") < APP.index("                _set_colored_line_item(")
