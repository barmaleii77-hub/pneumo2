import json

import numpy as np

from pneumo_solver_ui import model_pneumo_v9_doublewishbone_camozzi as model
from pneumo_solver_ui.desktop_animator.data_bundle import load_npz
from pneumo_solver_ui.desktop_animator.self_checks import run_self_checks


CORNERS = ("ЛП", "ПП", "ЛЗ", "ПЗ")


def _smooth_bump(t: float, t0: float = 0.01, dur: float = 0.02, A: float = 0.02) -> float:
    if t <= t0:
        return 0.0
    if t >= t0 + dur:
        return float(A)
    x = (t - t0) / dur
    return float(A) * 0.5 * (1.0 - np.cos(np.pi * x))


def _mk_scenario():
    return {
        "road_func": lambda t: np.array([_smooth_bump(t), 0.0, 0.0, 0.0], dtype=float),
        "ax_func": lambda t: 0.0,
        "ay_func": lambda t: 0.0,
    }


def test_camozzi_exports_only_canonical_frame_corner_channels():
    df_main, *_ = model.simulate(
        {
            "mechanics_selfcheck": False,
            "пружина_преднатяг_на_отбое_строго": False,
            "макс_шаг_интегрирования_с": 3.0e-4,
        },
        _mk_scenario(),
        dt=2e-3,
        t_end=0.02,
        record_full=False,
    )

    for c in CORNERS:
        assert f"рама_угол_{c}_z_м" in df_main.columns
        assert f"рама_угол_{c}_v_м_с" in df_main.columns
        assert f"рама_угол_{c}_a_м_с2" in df_main.columns
        assert f"frame_corner_{c}_x_м" in df_main.columns
        assert f"frame_corner_{c}_y_м" in df_main.columns
        assert f"frame_corner_{c}_z_м" in df_main.columns
        assert np.allclose(
            np.asarray(df_main[f"frame_corner_{c}_z_м"], dtype=float),
            np.asarray(df_main[f"рама_угол_{c}_z_м"], dtype=float),
            equal_nan=True,
        )

        assert f"рама_{c}_z_м" not in df_main.columns
        assert f"рама_{c}_v_м_с" not in df_main.columns
        assert f"рама_{c}_a_м_с2" not in df_main.columns
        assert f"рама_{c}_vz_м_с" not in df_main.columns
        assert f"рама_{c}_az_м_с2" not in df_main.columns


def test_desktop_animator_accepts_canonical_frame_corner_npz(tmp_path):
    t = np.array([0.0, 0.1, 0.2], dtype=float)
    data = {
        "время_с": t,
        "перемещение_рамы_z_м": np.array([0.50, 0.51, 0.49], dtype=float),
        "скорость_vx_м_с": np.array([10.0, 10.0, 10.0], dtype=float),
        "yaw_рад": np.array([0.0, 0.0, 0.0], dtype=float),
    }
    xy_map = {
        "ЛП": (0.75, 0.50),
        "ПП": (0.75, -0.50),
        "ЛЗ": (-0.75, 0.50),
        "ПЗ": (-0.75, -0.50),
    }
    for c in CORNERS:
        data[f"дорога_{c}_м"] = np.array([0.0, 0.0, 0.0], dtype=float)
        data[f"перемещение_колеса_{c}_м"] = np.array([0.30, 0.31, 0.29], dtype=float)
        data[f"рама_угол_{c}_z_м"] = np.array([0.50, 0.51, 0.49], dtype=float)
        data[f"рама_угол_{c}_v_м_с"] = np.array([0.00, 0.10, -0.10], dtype=float)
        data[f"рама_угол_{c}_a_м_с2"] = np.array([0.00, 1.00, -1.00], dtype=float)
        data[f"frame_corner_{c}_x_м"] = np.array([xy_map[c][0], xy_map[c][0], xy_map[c][0]], dtype=float)
        data[f"frame_corner_{c}_y_м"] = np.array([xy_map[c][1], xy_map[c][1], xy_map[c][1]], dtype=float)
        data[f"frame_corner_{c}_z_м"] = np.array([0.50, 0.51, 0.49], dtype=float)

    cols = list(data.keys())
    values = np.column_stack([data[c] for c in cols]).astype(float)
    npz_path = tmp_path / "canonical_frame_corner_bundle.npz"
    np.savez_compressed(
        npz_path,
        main_cols=np.array(cols, dtype=object),
        main_values=values,
        meta_json=json.dumps({"geometry": {"wheelbase_m": 2.8, "track_m": 1.6}}, ensure_ascii=False),
    )

    b = load_npz(npz_path)
    rep = run_self_checks(b, wheel_radius_m=0.30, track_m=1.6, wheelbase_m=2.8)

    assert np.allclose(b.frame_corner_z("ЛП"), data["рама_угол_ЛП_z_м"])
    assert np.allclose(b.frame_corner_v("ЛП"), data["рама_угол_ЛП_v_м_с"])
    assert np.allclose(b.frame_corner_a("ЛП"), data["рама_угол_ЛП_a_м_с2"])
    frame_xyz = b.frame_corner_xyz("ЛП")
    assert frame_xyz is not None
    assert np.allclose(frame_xyz[:, 0], data["frame_corner_ЛП_x_м"])
    assert np.allclose(frame_xyz[:, 1], data["frame_corner_ЛП_y_м"])
    assert np.allclose(frame_xyz[:, 2], data["frame_corner_ЛП_z_м"])
    assert not any("отсутствуют ABS-каналы геометрии" in msg for msg in rep.messages)
