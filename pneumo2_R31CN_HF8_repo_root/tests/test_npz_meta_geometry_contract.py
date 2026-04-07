from __future__ import annotations

from pathlib import Path

from pneumo_solver_ui.data_contract import (
    build_geometry_meta_from_base,
    extract_geometry_meta,
    normalize_npz_meta,
)
from pneumo_solver_ui.desktop_animator.data_bundle import _infer_wheelbase_from_meta
from pneumo_solver_ui.desktop_animator.selfcheck_cli import infer_geometry_headless


ROOT = Path(__file__).resolve().parents[1]


def test_build_geometry_meta_from_base_exports_only_canonical_keys() -> None:
    base = {
        "база": 2.7,
        "колея": 1.64,
        "радиус_колеса_перед_м": 0.31,
        "радиус_колеса_зад_м": 0.32,
        "wheel_width_m": 0.205,
        "road_width_m": 0.0,
        "длина_рамы": 2.35,
        "ширина_рамы": 0.88,
        "высота_рамы": 0.41,
    }

    geom = build_geometry_meta_from_base(base)

    assert geom["wheelbase_m"] == 2.7
    assert geom["track_m"] == 1.64
    assert geom["wheel_radius_front_m"] == 0.31
    assert geom["wheel_radius_rear_m"] == 0.32
    assert "wheel_radius_m" not in geom  # front/rear differ: no ambiguous generic alias
    assert geom["wheel_width_m"] == 0.205
    assert geom["road_width_m"] == 0.0
    assert geom["frame_length_m"] == 2.35
    assert geom["frame_width_m"] == 0.88
    assert geom["frame_height_m"] == 0.41

    # No legacy/base-source names must leak into nested geometry.
    forbidden = {"база", "колея", "радиус_колеса_перед_м", "радиус_колеса_зад_м", "длина_рамы", "ширина_рамы", "высота_рамы"}
    assert forbidden.isdisjoint(set(geom.keys()))



def test_normalize_npz_meta_audits_legacy_geometry_without_mutation() -> None:
    meta = {
        "geometry": {
            "база": 2.7,
            "wheelbase_m": 2.8,
        }
    }
    messages: list[str] = []

    out = normalize_npz_meta(meta, log=messages.append)

    assert out == meta
    assert any("meta.geometry contains legacy key 'база'" in m for m in messages)



def test_nested_geometry_preferred_by_animator_helpers() -> None:
    meta = {
        "geometry": {
            "wheelbase_m": 2.7,
            "track_m": 1.64,
            "wheel_radius_front_m": 0.31,
            "wheel_radius_rear_m": 0.32,
            "wheel_width_m": 0.205,
        },
        # Deliberately conflicting top-level/base values: helper must prefer nested geometry.
        "wheelbase_m": 2.5,
        "track_m": 1.2,
        "wheel_radius_m": 0.28,
        "base": {
            "база": 1.5,
            "колея": 1.0,
            "радиус_колеса_м": 0.25,
        },
    }

    assert extract_geometry_meta(meta)["wheelbase_m"] == 2.7
    assert _infer_wheelbase_from_meta(meta) == 2.7

    geom = infer_geometry_headless(meta)
    assert geom["wheelbase_m"] == 2.7
    assert geom["track_m"] == 1.64
    # headless helper should take nested front radius before conflicting top-level generic radius.
    assert geom["wheel_radius_m"] == 0.31



def test_ui_sources_write_nested_geometry_contract() -> None:
    ui_text = (ROOT / "pneumo_solver_ui" / "pneumo_ui_app.py").read_text(encoding="utf-8")
    legacy_ui_text = (ROOT / "pneumo_solver_ui" / "app.py").read_text(encoding="utf-8")

    assert "build_geometry_meta_from_base" in ui_text
    assert "_meta_anim['geometry'] = _geom_anim" in ui_text
    assert '"geometry": _build_animator_geometry_meta(base_override)' in ui_text

    assert "build_geometry_meta_from_base" in legacy_ui_text
    assert "supplement_animator_geometry_meta" in legacy_ui_text
    assert '_geom = supplement_animator_geometry_meta(build_geometry_meta_from_base(base_override, log=_APP_LOGGER.warning), log=_APP_LOGGER.warning)' in legacy_ui_text
    assert '"geometry": _geom' in legacy_ui_text
