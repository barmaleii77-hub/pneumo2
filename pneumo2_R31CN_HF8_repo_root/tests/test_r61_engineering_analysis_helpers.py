from __future__ import annotations

import math
from pathlib import Path

import numpy as np

from pneumo_solver_ui.desktop_animator.data_bundle import DataBundle, NpzTable
from pneumo_solver_ui.desktop_animator.engineering_analysis import (
    build_multifactor_analysis_payload,
    collect_analysis_catalog,
    rank_global_focus_metrics,
)


def _build_bundle() -> DataBundle:
    t = np.linspace(0.0, 4.0 * math.pi, 121)
    roll = 0.025 * np.sin(t)
    pitch = 0.018 * np.cos(t)
    heave = 0.010 * np.sin(0.5 * t)
    az_body = 1.8 * np.sin(t)
    az_wheel = 2.2 * np.sin(t + 0.05)
    road = 0.003 * np.sin(1.7 * t)
    travel = 0.040 * np.sin(t)
    stroke = 0.034 * np.sin(t)

    corners = {
        "ЛП": heave + roll + pitch,
        "ПП": heave - roll + pitch,
        "ЛЗ": heave + roll - pitch,
        "ПЗ": heave - roll - pitch,
    }

    cols = ["время_с"]
    values = [t]
    for corner, body_z in corners.items():
        cols.extend(
            [
                f"рама_угол_{corner}_z_м",
                f"рама_угол_{corner}_v_м_с",
                f"рама_угол_{corner}_a_м_с2",
                f"перемещение_колеса_{corner}_м",
                f"скорость_колеса_{corner}_м_с",
                f"ускорение_колеса_{corner}_м_с2",
                f"дорога_{corner}_м",
                f"положение_штока_{corner}_м",
                f"нормальная_сила_шины_{corner}_Н",
                f"колесо_в_воздухе_{corner}",
            ]
        )
        wheel_z = body_z + travel
        tire_force = 4200.0 + (700.0 * np.sin(t)) + (320.0 if "Л" in corner else -320.0)
        wheel_air = np.where((corner == "ЛП") & (np.sin(t) > 0.85), 1.0, 0.0)
        values.extend(
            [
                body_z,
                np.gradient(body_z, t),
                az_body + (0.20 if "Л" in corner else -0.20),
                wheel_z,
                np.gradient(wheel_z, t),
                az_wheel + (0.15 if "П" in corner else -0.15),
                road,
                stroke + (0.004 if "П" in corner else -0.004),
                tire_force,
                wheel_air,
            ]
        )

    cols.extend(
        [
            "давление_ресивер1_Па",
            "давление_ресивер2_Па",
            "давление_ресивер3_Па",
            "давление_аккумулятор_Па",
        ]
    )
    values.extend(
        [
            540000.0 + (28000.0 * np.sin(t)),
            500000.0 + (16000.0 * np.sin(t + 0.4)),
            470000.0 + (9000.0 * np.cos(t)),
            520000.0 + (12000.0 * np.sin(t - 0.2)),
        ]
    )

    main = NpzTable(cols=cols, values=np.vstack(values).T.astype(float))
    return DataBundle(npz_path=Path("synthetic.npz"), main=main, meta={"geometry": {"wheelbase_m": 2.8}})


def test_collect_analysis_catalog_builds_global_and_corner_metric_maps() -> None:
    bundle = _build_bundle()
    catalog = collect_analysis_catalog(bundle)

    assert catalog.t.shape == (121,)
    assert "roll_proxy" in catalog.global_series
    assert "pressure_spread_bar" in catalog.global_series
    assert set(catalog.corner_series["wheel_road"]) == {"ЛП", "ПП", "ЛЗ", "ПЗ"}
    assert catalog.global_scales["wheel_az_mean"] > 0.1
    assert catalog.corner_family_scales["stroke"] > 0.001


def test_multifactor_payload_detects_strong_global_coupling_and_airborne_heuristic() -> None:
    bundle = _build_bundle()
    catalog = collect_analysis_catalog(bundle)
    payload = build_multifactor_analysis_payload(
        catalog,
        idx=16,
        mode="all_all",
        window_s=3.0,
    )

    names = list(payload["names"])
    matrix = np.asarray(payload["matrix"], dtype=float)
    i_body = names.index("body_az_mean")
    i_wheel = names.index("wheel_az_mean")

    assert matrix.shape[0] == len(names)
    assert matrix[i_body, i_wheel] > 0.90
    assert any("wheel-in-air" in item or "wheel-in-air" in item.lower() for item in payload["insights"])


def test_multifactor_payload_corner_mode_uses_requested_family_for_all_corners() -> None:
    bundle = _build_bundle()
    catalog = collect_analysis_catalog(bundle)
    payload = build_multifactor_analysis_payload(
        catalog,
        idx=80,
        mode="corner_corner",
        corner_metric="stroke",
        window_s=2.0,
    )

    assert list(payload["names"]) == ["ЛП", "ПП", "ЛЗ", "ПЗ"]
    assert payload["corner_cloud"]["ЛП"]["label"] == "Положение штока"
    assert payload["current_text"]["ПП"].endswith("м")


def test_rank_global_focus_metrics_surfaces_dynamic_body_or_wheel_acceleration_first() -> None:
    bundle = _build_bundle()
    catalog = collect_analysis_catalog(bundle)
    ranked = rank_global_focus_metrics(catalog, idx=16, window_s=3.0)

    assert ranked
    assert float(ranked[0]["score"]) >= float(ranked[1]["score"])
    assert str(ranked[0]["metric"]) in {"body_az_mean", "wheel_az_mean"}
