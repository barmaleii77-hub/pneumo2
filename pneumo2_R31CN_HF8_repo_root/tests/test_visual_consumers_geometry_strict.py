from __future__ import annotations

from pathlib import Path

from pneumo_solver_ui.data_contract import read_visual_geometry_meta
from pneumo_solver_ui.desktop_animator.data_bundle import _infer_wheelbase_from_meta
from pneumo_solver_ui.desktop_animator.selfcheck_cli import infer_geometry_headless


ROOT = Path(__file__).resolve().parents[1]


def test_read_visual_geometry_meta_ignores_top_level_duplicates() -> None:
    meta = {
        "geometry": {
            "wheelbase_m": 2.7,
            "track_m": 1.64,
            "wheel_radius_front_m": 0.31,
            "wheel_radius_rear_m": 0.32,
            "wheel_width_m": 0.205,
        },
        "wheelbase_m": 2.5,
        "track_m": 1.2,
        "wheel_radius_m": 0.28,
    }

    vis = read_visual_geometry_meta(meta, context="pytest meta")

    assert vis["wheelbase_m"] == 2.7
    assert vis["track_m"] == 1.64
    assert vis["wheel_radius_m"] == 0.31
    assert vis["wheel_width_m"] == 0.205
    assert vis["issues"] == []
    assert any("top-level 'wheelbase_m'" in m or "duplicates canonical geometry key 'wheelbase_m'" in m for m in vis["warnings"])


def test_visual_consumers_do_not_fallback_to_top_level_or_base_geometry() -> None:
    broken_meta = {
        "wheelbase_m": 2.8,
        "track_m": 1.6,
        "wheel_radius_m": 0.31,
        "base": {
            "база": 3.1,
            "колея": 1.9,
            "радиус_колеса_м": 0.35,
        },
    }

    assert _infer_wheelbase_from_meta(broken_meta) is None

    geom = infer_geometry_headless(broken_meta)
    assert geom["wheelbase_m"] == 0.0
    assert geom["track_m"] == 0.0
    assert geom["wheel_radius_m"] == 0.0
    assert geom["geometry_contract_issues"]
    assert any("nested object 'geometry'" in m for m in geom["geometry_contract_issues"])
    assert geom["geometry_contract_warnings"]
    assert any("top-level geometry key 'wheelbase_m'" in m for m in geom["geometry_contract_warnings"])


def test_desktop_animator_source_uses_canonical_frame_helpers_and_no_default_base_fallback() -> None:
    app_text = (ROOT / "pneumo_solver_ui" / "desktop_animator" / "app.py").read_text(encoding="utf-8")

    assert "read_visual_geometry_meta" in app_text
    assert "_load_default_base_params" not in app_text
    assert "default_base.json" not in app_text
    assert 'frame_corner_z("ЛП"' in app_text
    assert 'frame_corner_a(' in app_text
    assert 'frame_corner_v(' in app_text
    assert 'рама_ЛП_z_м' not in app_text
    assert 'рама_ЛП_az_м_с2' not in app_text
    assert 'рама_ЛП_vz_м_с' not in app_text


def test_animation_cockpit_source_reads_only_nested_geometry() -> None:
    web_text = (ROOT / "pneumo_solver_ui" / "animation_cockpit_web.py").read_text(encoding="utf-8")

    assert "read_visual_geometry_meta" in web_text
    assert "_load_default_base_params" not in web_text
    assert "default_base.json" not in web_text
    assert "meta_json.geometry" in web_text
    assert "borrow" in web_text
