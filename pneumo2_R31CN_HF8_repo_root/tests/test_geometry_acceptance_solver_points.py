import json
from pathlib import Path

import numpy as np

from pneumo_solver_ui.desktop_animator.data_bundle import load_npz
from pneumo_solver_ui.desktop_animator.geometry_acceptance import (
    collect_acceptance_status,
    corner_acceptance_arrays,
    format_acceptance_hud_lines,
)
from pneumo_solver_ui.desktop_animator.self_checks import run_self_checks


CORNERS = ("ЛП", "ПП", "ЛЗ", "ПЗ")


def _write_bundle(tmp_path: Path, *, wheel_road_bias: float = 0.0) -> Path:
    t = np.array([0.0, 0.1, 0.2], dtype=float)
    data: dict[str, np.ndarray] = {
        "время_с": t,
        "перемещение_рамы_z_м": np.array([0.50, 0.51, 0.49], dtype=float),
        "скорость_vx_м_с": np.array([10.0, 10.0, 10.0], dtype=float),
        "yaw_рад": np.array([0.0, 0.0, 0.0], dtype=float),
        "yaw_rate_рад_с": np.array([0.0, 0.0, 0.0], dtype=float),
        "ускорение_продольное_ax_м_с2": np.array([0.0, 0.0, 0.0], dtype=float),
        "ускорение_поперечное_ay_м_с2": np.array([0.0, 0.0, 0.0], dtype=float),
        "скорость_рамы_z_м_с": np.array([0.0, 0.0, 0.0], dtype=float),
        "ускорение_рамы_z_м_с2": np.array([0.0, 0.0, 0.0], dtype=float),
    }
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
        data[f"дорога_{c}_м"] = road_z.copy()
        data[f"перемещение_колеса_{c}_м"] = wheel_z.copy()
        data[f"рама_угол_{c}_z_м"] = frame_z.copy()
        data[f"рама_угол_{c}_v_м_с"] = np.array([0.00, 0.10, -0.10], dtype=float)
        data[f"рама_угол_{c}_a_м_с2"] = np.array([0.00, 1.00, -1.00], dtype=float)
        data[f"колесо_относительно_рамы_{c}_м"] = wheel_z - frame_z
        data[f"колесо_относительно_дороги_{c}_м"] = (wheel_z - road_z) + float(wheel_road_bias)
        data[f"рама_относительно_дороги_{c}_м"] = frame_z - road_z

        data[f"frame_corner_{c}_x_м"] = np.array([x, x, x], dtype=float)
        data[f"frame_corner_{c}_y_м"] = np.array([y, y, y], dtype=float)
        data[f"frame_corner_{c}_z_м"] = frame_z.copy()

        data[f"wheel_center_{c}_x_м"] = np.array([x, x, x], dtype=float)
        data[f"wheel_center_{c}_y_м"] = np.array([y, y, y], dtype=float)
        data[f"wheel_center_{c}_z_м"] = wheel_z.copy()

        data[f"road_contact_{c}_x_м"] = np.array([x, x, x], dtype=float)
        data[f"road_contact_{c}_y_м"] = np.array([y, y, y], dtype=float)
        data[f"road_contact_{c}_z_м"] = road_z.copy()

    cols = list(data.keys())
    values = np.column_stack([data[c] for c in cols]).astype(float)
    npz_path = tmp_path / "geometry_acceptance_bundle.npz"
    np.savez_compressed(
        npz_path,
        main_cols=np.array(cols, dtype=object),
        main_values=values,
        meta_json=json.dumps({"geometry": {
            "wheelbase_m": 1.5,
            "track_m": 1.0,
            "wheel_radius_m": 0.30,
            "wheel_width_m": 0.22,
            "frame_length_m": 2.0,
            "frame_width_m": 1.0,
            "frame_height_m": 0.18,
        }}, ensure_ascii=False),
    )
    return npz_path



def test_geometry_acceptance_helpers_and_hud_lines(tmp_path: Path):
    bundle = load_npz(_write_bundle(tmp_path))
    status = collect_acceptance_status(bundle)
    assert status["ok"] is True
    assert status["missing_triplets"] == []
    assert status["max_invariant_err_m"] <= 1e-12
    assert status["max_xy_err_m"] <= 1e-12
    assert status["max_scalar_err_wheel_road_m"] <= 1e-12
    assert status["max_scalar_err_wheel_frame_m"] <= 1e-12
    assert status["max_scalar_err_frame_road_m"] <= 1e-12

    acc = corner_acceptance_arrays(bundle, "ЛП")
    assert acc["ok"] is True
    assert np.allclose(acc["wheel_frame_m"], np.array([-0.20, -0.20, -0.20], dtype=float))
    assert np.allclose(acc["wheel_road_m"], np.array([0.30, 0.31, 0.29], dtype=float))
    assert np.allclose(acc["frame_road_m"], np.array([0.50, 0.51, 0.49], dtype=float))

    lines = format_acceptance_hud_lines(bundle, 1)
    assert len(lines) >= 2
    assert any("рама‑дорога min" in line for line in lines)
    assert any("Σ" in line and "XYwr" in line for line in lines)

    lines_mid = format_acceptance_hud_lines(bundle, 0, sample_t=0.05)
    assert any("+0.505 м" in line for line in lines_mid)
    assert any("+0.305 м" in line for line in lines_mid)


def test_geometry_acceptance_ignores_frame_xy_offset_in_acceptance_gate(tmp_path: Path):
    bundle = load_npz(_write_bundle(tmp_path))
    # Introduce a structural frame XY offset without touching wheel/road triplets.
    idx = bundle.main.index_of("frame_corner_ПЗ_x_м")
    assert idx is not None
    bundle.main.values[:, idx] = np.asarray(bundle.main.values[:, idx], dtype=float) - 0.03157377177700913

    status = collect_acceptance_status(bundle)
    assert status["ok"] is True
    assert status["max_xy_err_m"] <= 1e-12
    assert float(status["max_xy_frame_wheel_offset_m"]) >= 0.031



def test_geometry_acceptance_selfcheck_fails_on_scalar_mismatch(tmp_path: Path):
    bundle = load_npz(_write_bundle(tmp_path, wheel_road_bias=0.05))
    rep = run_self_checks(bundle, wheel_radius_m=0.30, track_m=1.0, wheelbase_m=1.5)
    assert rep.ok is False
    assert any("solver-point geometry acceptance mismatch" in msg for msg in rep.messages)
    assert float(rep.stats["solver_points_acceptance_max_scalar_err_wheel_road_m"]) >= 0.049



def test_app_source_contains_acceptance_overlay_and_metrics() -> None:
    src = Path("pneumo_solver_ui/desktop_animator/app.py").read_text(encoding="utf-8")
    assert 'format_acceptance_hud_lines' in src
    assert '("frame_road", "рама‑дорога (м)", "m")' in src
    assert '("inv_sum", "инвариант err (мм)", "mm")' in src
    assert '("triplet_xy", "XY err wheel-road (мм)", "mm")' in src
