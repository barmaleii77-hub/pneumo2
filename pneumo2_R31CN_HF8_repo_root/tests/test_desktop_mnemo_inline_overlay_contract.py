from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest


def test_desktop_mnemo_native_overlay_tokens_exist() -> None:
    root = Path(__file__).resolve().parents[1]
    app_src = (root / "pneumo_solver_ui" / "desktop_mnemo" / "app.py").read_text(encoding="utf-8")

    assert "class MnemoNativeCanvas" in app_src
    assert "def set_diagnostics(self, diagnostics: dict[str, Any]) -> None:" in app_src
    assert "_build_mnemo_diagnostics_payload" in app_src
    assert "def _draw_diagnostics_overlay(self, painter: QtGui.QPainter) -> None:" in app_src
    assert "def _draw_cylinder_card(" in app_src
    assert "def _draw_component_badge(" in app_src
    assert "Native Mnemo canvas" in app_src


def test_desktop_mnemo_inline_overlay_payload_uses_geometry_and_selected_edge(tmp_path: Path) -> None:
    pytest.importorskip("PySide6")

    from pneumo_solver_ui.desktop_mnemo.app import _build_mnemo_diagnostics_payload, prepare_dataset

    t = np.array([0.0, 0.5, 1.0], dtype=float)
    npz_path = tmp_path / "mnemo_inline_overlay_bundle.npz"

    meta = {
        "P_ATM": 101325.0,
        "geometry": {
            "wheelbase_m": 2.8,
            "track_m": 1.6,
            "wheel_radius_m": 0.32,
            "wheel_width_m": 0.24,
            "frame_length_m": 3.2,
            "frame_width_m": 1.7,
            "frame_height_m": 0.25,
            "cyl1_bore_diameter_m": 0.032,
            "cyl1_rod_diameter_m": 0.016,
            "cyl2_bore_diameter_m": 0.050,
            "cyl2_rod_diameter_m": 0.014,
            "cyl1_stroke_front_m": 0.250,
            "cyl1_stroke_rear_m": 0.250,
            "cyl2_stroke_front_m": 0.250,
            "cyl2_stroke_rear_m": 0.250,
            "cyl1_outer_diameter_m": 0.038,
            "cyl2_outer_diameter_m": 0.056,
            "cyl1_dead_cap_length_m": 0.010,
            "cyl1_dead_rod_length_m": 0.012,
            "cyl2_dead_cap_length_m": 0.008,
            "cyl2_dead_rod_length_m": 0.009,
            "cylinder_wall_thickness_m": 0.003,
        },
    }

    np.savez(
        npz_path,
        main_cols=np.array(
            ["время_с", "положение_штока_ЛП_м", "скорость_штока_ЛП_м_с"],
            dtype=object,
        ),
        main_values=np.column_stack(
            [
                t,
                np.array([0.05, 0.125, 0.20], dtype=float),
                np.array([0.14, 0.18, 0.12], dtype=float),
            ]
        ).astype(float),
        p_cols=np.array(
            [
                "время_с",
                "Ресивер3",
                "Ц1_ЛП_БП",
                "Ц1_ЛП_ШП",
                "Ц2_ЛП_БП",
                "Ц2_ЛП_ШП",
            ],
            dtype=object,
        ),
        p_values=np.column_stack(
            [
                t,
                np.array([505000.0, 507000.0, 509000.0], dtype=float),
                np.array([480000.0, 501325.0, 520000.0], dtype=float),
                np.array([290000.0, 301325.0, 315000.0], dtype=float),
                np.array([450000.0, 470000.0, 492000.0], dtype=float),
                np.array([260000.0, 280000.0, 295000.0], dtype=float),
            ]
        ).astype(float),
        q_cols=np.array(
            [
                "время_с",
                "регулятор_до_себя_Pmid_сброс",
                "дроссель_выхлоп_Pmid",
            ],
            dtype=object,
        ),
        q_values=np.column_stack(
            [
                t,
                np.array([0.0010, 0.0016, 0.0011], dtype=float),
                np.array([0.0002, -0.0008, -0.0004], dtype=float),
            ]
        ).astype(float),
        open_cols=np.array(
            [
                "время_с",
                "регулятор_до_себя_Pmid_сброс",
                "дроссель_выхлоп_Pmid",
            ],
            dtype=object,
        ),
        open_values=np.column_stack(
            [
                t,
                np.array([1, 1, 1], dtype=float),
                np.array([0, 1, 1], dtype=float),
            ]
        ).astype(float),
        meta_json=np.array(json.dumps(meta, ensure_ascii=False), dtype=object),
    )

    dataset = prepare_dataset(npz_path)
    payload = _build_mnemo_diagnostics_payload(
        dataset,
        1,
        selected_edge="дроссель_выхлоп_Pmid",
        selected_node="Ц1_ЛП_БП",
    )

    assert payload["focus_corner"] == "ЛП"
    assert payload["selected_edge"] == "дроссель_выхлоп_Pmid"
    assert payload["selected_node"] == "Ц1_ЛП_БП"

    cyl_overlay = next(item for item in payload["cylinders"] if item["id"] == "cyl1_ЛП")
    assert cyl_overlay["geometry_ready"] is True
    assert cyl_overlay["motion_short"] == "EXT"
    assert cyl_overlay["cap"]["node_name"] == "Ц1_ЛП_БП"
    assert cyl_overlay["cap"]["volume_l"] is not None
    assert cyl_overlay["rod"]["volume_l"] is not None

    comp_overlay = next(item for item in payload["components"] if item["edge_name"] == "дроссель_выхлоп_Pmid")
    assert comp_overlay["component_short"] == "THR"
    assert comp_overlay["is_selected"] is True
    assert comp_overlay["state_short"] == "OPEN"
