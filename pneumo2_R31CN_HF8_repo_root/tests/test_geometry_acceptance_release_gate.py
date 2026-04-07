from __future__ import annotations

import numpy as np
import pandas as pd

from pneumo_solver_ui.geometry_acceptance_contract import (
    build_geometry_acceptance_rows,
    collect_geometry_acceptance_from_frame,
    format_geometry_acceptance_summary_lines,
)


CORNERS = ("ЛП", "ПП", "ЛЗ", "ПЗ")


def _base_df() -> pd.DataFrame:
    t = np.array([0.0, 0.1, 0.2], dtype=float)
    data: dict[str, np.ndarray] = {"время_с": t}
    xy_map = {
        "ЛП": (0.75, 0.50),
        "ПП": (0.75, -0.50),
        "ЛЗ": (-0.75, 0.50),
        "ПЗ": (-0.75, -0.50),
    }
    frame_z = np.array([0.50, 0.51, 0.49], dtype=float)
    wheel_z = np.array([0.30, 0.31, 0.29], dtype=float)
    road_z = np.array([0.00, 0.00, 0.00], dtype=float)
    for c in CORNERS:
        x, y = xy_map[c]
        data[f"рама_относительно_дороги_{c}_м"] = frame_z - road_z
        data[f"колесо_относительно_дороги_{c}_м"] = wheel_z - road_z
        data[f"колесо_относительно_рамы_{c}_м"] = wheel_z - frame_z
        data[f"frame_corner_{c}_x_м"] = np.array([x, x, x], dtype=float)
        data[f"frame_corner_{c}_y_м"] = np.array([y, y, y], dtype=float)
        data[f"frame_corner_{c}_z_м"] = frame_z.copy()
        data[f"wheel_center_{c}_x_м"] = np.array([x, x, x], dtype=float)
        data[f"wheel_center_{c}_y_м"] = np.array([y, y, y], dtype=float)
        data[f"wheel_center_{c}_z_м"] = wheel_z.copy()
        data[f"road_contact_{c}_x_м"] = np.array([x, x, x], dtype=float)
        data[f"road_contact_{c}_y_м"] = np.array([y, y, y], dtype=float)
        data[f"road_contact_{c}_z_м"] = road_z.copy()
    return pd.DataFrame(data)


def test_release_gate_pass_and_rows_are_enriched() -> None:
    df = _base_df()
    summary = collect_geometry_acceptance_from_frame(df)
    assert summary["release_gate"] == "PASS"
    assert summary["release_gate_reason"] == "solver-point contract consistent"
    assert summary["min_frame_road_corner"] in CORNERS
    assert summary["min_wheel_road_corner"] in CORNERS
    rows = build_geometry_acceptance_rows(summary)
    assert len(rows) == 4
    assert all(str(r["gate"]) == "PASS" for r in rows)
    lines = format_geometry_acceptance_summary_lines(summary)
    assert any("gate=PASS" in x for x in lines)
    assert any("worst:" in x for x in lines)


def test_release_gate_fail_identifies_corner_metric_and_reason() -> None:
    df = _base_df()
    # Deliberately break wheel-road scalar contract for rear-right corner.
    df["колесо_относительно_дороги_ПЗ_м"] = np.array([0.35, 0.36, 0.34], dtype=float)
    summary = collect_geometry_acceptance_from_frame(df)
    assert summary["release_gate"] == "FAIL"
    assert summary["worst_corner"] == "ПЗ"
    assert summary["worst_metric"] == "WR"
    assert float(summary["worst_value_m"]) >= 0.049
    assert "ПЗ" in str(summary["release_gate_reason"])
    assert "WR mismatch" in str(summary["release_gate_reason"])
    rows = build_geometry_acceptance_rows(summary)
    row_pz = next(r for r in rows if r["угол"] == "ПЗ")
    assert row_pz["gate"] == "FAIL"
    assert "WR mismatch" in str(row_pz["reason"])
    lines = format_geometry_acceptance_summary_lines(summary)
    assert any("metric=WR" in x for x in lines)


def test_release_gate_ignores_structural_frame_xy_offsets_when_wheel_road_xy_is_consistent() -> None:
    df = _base_df()
    # frame_corner is a structural solver point and may legitimately be offset
    # in XY relative to wheel/road while Z/scalar invariants remain consistent.
    df["frame_corner_ПЗ_x_м"] = np.array([-0.7815737717770091, -0.7815737717770091, -0.7815737717770091], dtype=float)
    summary = collect_geometry_acceptance_from_frame(df)
    assert summary["release_gate"] == "PASS"
    assert summary["release_gate_reason"] == "solver-point contract consistent"
    pz = dict(summary["corners"]["ПЗ"])
    assert float(pz["max_xy_err_m"]) <= 1e-12
    assert float(pz["max_xy_frame_wheel_offset_m"]) >= 0.031
    rows = build_geometry_acceptance_rows(summary)
    row_pz = next(r for r in rows if r["угол"] == "ПЗ")
    assert float(row_pz["XY wheel-road err, мм"] or 0.0) <= 1e-9
    assert float(row_pz["XY frame-wheel offset, мм"] or 0.0) >= 31.0
    lines = format_geometry_acceptance_summary_lines(summary)
    assert any("XYwr 0.000 мм" in x for x in lines)
