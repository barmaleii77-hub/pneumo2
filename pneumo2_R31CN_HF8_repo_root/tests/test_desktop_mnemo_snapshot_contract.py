from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pytest


def test_desktop_mnemo_window_exposes_snapshot_dock() -> None:
    src = (
        Path(__file__).resolve().parents[1]
        / "pneumo_solver_ui"
        / "desktop_mnemo"
        / "app.py"
    ).read_text(encoding="utf-8")

    assert 'obj_name="dock_snapshot"' in src
    assert "class CornerHeatmapWidget" in src
    assert "class PneumoSnapshotPanel" in src
    assert 'self._snapshot_dock = self._add_dock("Приводы", self.snapshot_panel' in src
    assert "self.snapshot_panel.update_frame(self.dataset, self.current_idx)" in src
    assert "Шток: выберите полость/угол" in src


def test_desktop_mnemo_snapshot_native_canvas_exposes_diagnostics_contract() -> None:
    src = (
        Path(__file__).resolve().parents[1]
        / "pneumo_solver_ui"
        / "desktop_mnemo"
        / "app.py"
    ).read_text(encoding="utf-8")

    assert "class MnemoNativeCanvas" in src
    assert "def set_diagnostics(self, diagnostics: dict[str, Any]) -> None:" in src
    assert "_build_mnemo_diagnostics_payload" in src
    assert "def _draw_cylinder_card(" in src
    assert "def _draw_component_badge(" in src


def test_desktop_mnemo_snapshot_uses_cylinder_geometry_and_stroke_channels(tmp_path: Path) -> None:
    pytest.importorskip("PySide6")

    from pneumo_solver_ui.desktop_mnemo.app import (
        _build_cylinder_snapshots,
        _build_edge_activity_snapshots,
        _build_mnemo_diagnostics_payload,
        prepare_dataset,
    )

    t = np.array([0.0, 0.5, 1.0], dtype=float)
    npz_path = tmp_path / "mnemo_snapshot_bundle.npz"
    patm = 101325.0

    meta = {
        "P_ATM": patm,
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
                np.array([0.050, 0.125, 0.200], dtype=float),
                np.array([0.140, 0.180, 0.120], dtype=float),
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
    cylinder_rows = _build_cylinder_snapshots(dataset, 1)
    edge_rows = _build_edge_activity_snapshots(dataset, 1)
    diag_payload = _build_mnemo_diagnostics_payload(
        dataset,
        1,
        selected_edge="РґСЂРѕСЃСЃРµР»СЊ_РІС‹С…Р»РѕРї_Pmid",
        selected_node="Р¦1_Р›Рџ_Р‘Рџ",
    )

    lp_c1 = next(item for item in cylinder_rows if item.corner == "ЛП" and item.cyl_index == 1)
    assert lp_c1.geometry_ready is True
    assert lp_c1.motion_label == "шток выдвигается"
    assert lp_c1.stroke_m == pytest.approx(0.125)
    assert lp_c1.stroke_speed_m_s == pytest.approx(0.180)
    assert lp_c1.stroke_ratio == pytest.approx(0.5)
    assert lp_c1.delta_p_bar == pytest.approx(2.0, abs=1.0e-6)

    cap_area = math.pi * (0.032 * 0.5) ** 2
    rod_area = cap_area - math.pi * (0.016 * 0.5) ** 2
    expected_cap_volume_l = cap_area * (0.010 + (0.250 - 0.125)) * 1000.0
    expected_rod_volume_l = rod_area * (0.012 + 0.125) * 1000.0
    assert lp_c1.cap.volume_l == pytest.approx(expected_cap_volume_l)
    assert lp_c1.rod.volume_l == pytest.approx(expected_rod_volume_l)
    assert lp_c1.cap.fill_ratio == pytest.approx((0.010 + 0.125) / (0.010 + 0.250))
    assert lp_c1.rod.fill_ratio == pytest.approx((0.012 + 0.125) / (0.012 + 0.250))

    assert edge_rows[0].edge_name == "регулятор_до_себя_Pmid_сброс"
    assert edge_rows[0].component_kind == "Регулятор"
    assert edge_rows[0].state_label == "открыт"
    assert any(item.component_kind == "Дроссель" for item in edge_rows)
