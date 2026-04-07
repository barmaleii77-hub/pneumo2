from __future__ import annotations

import json
from pathlib import Path

from pneumo_solver_ui.data_contract import build_geometry_meta_from_base
from pneumo_solver_ui.desktop_animator.selfcheck_cli import infer_geometry_headless

ROOT = Path(__file__).resolve().parents[1]


def test_default_base_declares_canonical_wheel_and_frame_geometry() -> None:
    base = json.loads((ROOT / "pneumo_solver_ui" / "default_base.json").read_text(encoding="utf-8"))

    assert float(base["wheel_width_m"]) > 0.0
    assert float(base["ширина_рамы"]) > 0.0
    assert float(base["высота_рамы"]) > 0.0
    assert float(base["длина_рамы"]) > 0.0
    assert "Не равна клиренсу" in str(base.get("_note", {}).get("высота_рамы", ""))


def test_build_geometry_meta_from_default_base_exports_frame_dims() -> None:
    base = json.loads((ROOT / "pneumo_solver_ui" / "default_base.json").read_text(encoding="utf-8"))
    geom = build_geometry_meta_from_base(base)

    assert geom["wheelbase_m"] == float(base["база"])
    assert geom["track_m"] == float(base["колея"])
    assert geom["wheel_width_m"] == float(base["wheel_width_m"])
    assert geom["frame_length_m"] == float(base["длина_рамы"])
    assert geom["frame_width_m"] == float(base["ширина_рамы"])
    assert geom["frame_height_m"] == float(base["высота_рамы"])


def test_infer_geometry_headless_returns_wheel_width_and_frame_dims() -> None:
    meta = {
        "geometry": {
            "wheelbase_m": 2.7,
            "track_m": 1.64,
            "wheel_radius_front_m": 0.31,
            "wheel_radius_rear_m": 0.31,
            "wheel_width_m": 0.205,
            "frame_length_m": 2.35,
            "frame_width_m": 0.88,
            "frame_height_m": 0.41,
        }
    }

    geom = infer_geometry_headless(meta)
    assert geom["wheel_width_m"] == 0.205
    assert geom["frame_length_m"] == 2.35
    assert geom["frame_width_m"] == 0.88
    assert geom["frame_height_m"] == 0.41


def test_animation_cockpit_source_exposes_frame_dims_in_ui_and_payload() -> None:
    src = (ROOT / "pneumo_solver_ui" / "animation_cockpit_web.py").read_text(encoding="utf-8")

    assert 'key="anim_frame_length_m"' in src
    assert 'key="anim_frame_width_m"' in src
    assert 'key="anim_frame_height_m"' in src
    assert '"body_L_m": float(frame_length_m) * float(dist_scale)' in src
    assert '"body_W_m": float(frame_width_m) * float(dist_scale)' in src
    assert '"body_H_m": float(frame_height_m) * float(dist_scale)' in src
    assert '"body_clearance_u": float(body_clearance_u)' in src


def test_desktop_animator_source_uses_explicit_frame_dimensions() -> None:
    src = (ROOT / "pneumo_solver_ui" / "desktop_animator" / "app.py").read_text(encoding="utf-8")

    assert 'frame_length: float = 0.0' in src
    assert 'frame_width: float = 0.0' in src
    assert 'frame_height: float = 0.0' in src
    assert 'getattr(self.geom, "frame_length", 0.0)' in src
    assert 'getattr(self.geom, "frame_width", 0.0)' in src
    assert 'getattr(self.geom, "frame_height", 0.0)' in src
    assert 'float(self.geom.wheelbase) + 1.6 * float(self.geom.wheel_radius)' not in src
    assert 'float(self.geom.track) + 1.2 * float(self.geom.wheel_width)' not in src
    assert '0.55 * float(self.geom.wheel_radius)' not in src


def test_web_components_have_no_hidden_body_or_clearance_defaults() -> None:
    car3d = (ROOT / "pneumo_solver_ui" / "components" / "mech_car3d" / "index.html").read_text(encoding="utf-8")
    quad2d = (ROOT / "pneumo_solver_ui" / "components" / "mech_anim_quad" / "index.html").read_text(encoding="utf-8")

    assert 'geo.body_L_m ?? 2.4' not in car3d
    assert 'geo.body_W_m ?? 1.2' not in car3d
    assert 'geo.body_H_m ?? 0.35' not in car3d
    assert 'body wireframe disabled' in car3d

    assert 'meta.body_clearance_u || (wheelRadiusU * 1.0)' not in quad2d
    assert 'body vertical offset fallback disabled' in quad2d
