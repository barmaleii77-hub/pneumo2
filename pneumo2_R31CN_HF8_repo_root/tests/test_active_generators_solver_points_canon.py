import json
from pathlib import Path

import numpy as np

from pneumo_solver_ui.npz_bundle import export_anim_latest_bundle
from pneumo_solver_ui.data_contract import build_geometry_meta_from_base
from pneumo_solver_ui.desktop_animator.data_bundle import load_npz
from pneumo_solver_ui.desktop_animator.suspension_geometry_diagnostics import collect_suspension_geometry_status
from pneumo_solver_ui.solver_points_contract import CORNERS, collect_solver_points_contract_issues, point_cols
from pneumo_solver_ui import model_pneumo_v9_doublewishbone_camozzi as camozzi
from pneumo_solver_ui import model_pneumo_v9_mech_doublewishbone_worldroad as worldroad


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BASE = ROOT / "pneumo_solver_ui" / "default_base.json"


def _base() -> dict:
    return json.loads(DEFAULT_BASE.read_text("utf-8"))


def _flat_test() -> dict:
    return {
        "road_func": lambda t: np.zeros(4, dtype=float),
        "ax_func": lambda t: 0.0,
        "ay_func": lambda t: 0.0,
        "label_func": lambda t: 0,
    }


def _dynamic_test() -> dict:
    def _bump(t: float, t0: float, dur: float, amp: float) -> float:
        if t <= t0:
            return 0.0
        if t >= t0 + dur:
            return float(amp)
        x = (t - t0) / dur
        return float(amp) * 0.5 * (1.0 - np.cos(np.pi * x))

    return {
        "road_func": lambda t: np.array(
            [
                _bump(t, 0.10, 0.08, 0.020),
                _bump(t, 0.14, 0.08, 0.015),
                _bump(t, 0.22, 0.10, 0.018),
                _bump(t, 0.26, 0.10, 0.012),
            ],
            dtype=float,
        ),
        "ax_func": lambda t: -0.8 if t > 0.18 else 0.0,
        "ay_func": lambda t: 0.5 if 0.20 < t < 0.42 else 0.0,
        "label_func": lambda t: 3,
        "vx0_м_с": 7.0,
    }


def _assert_solver_points(df_main):
    status = collect_solver_points_contract_issues(df_main.columns, context="generator smoke")
    assert status["ok"], status["issues"]
    for corner in CORNERS:
        wz = np.asarray(df_main[f"wheel_center_{corner}_z_м"], dtype=float)
        rz = np.asarray(df_main[f"road_contact_{corner}_z_м"], dtype=float)
        fz = np.asarray(df_main[f"frame_corner_{corner}_z_м"], dtype=float)
        wx = np.asarray(df_main[f"wheel_center_{corner}_x_м"], dtype=float)
        wy = np.asarray(df_main[f"wheel_center_{corner}_y_м"], dtype=float)
        fx = np.asarray(df_main[f"frame_corner_{corner}_x_м"], dtype=float)
        fy = np.asarray(df_main[f"frame_corner_{corner}_y_м"], dtype=float)
        assert np.allclose(wz, np.asarray(df_main[f"перемещение_колеса_{corner}_м"], dtype=float), equal_nan=True)
        assert np.allclose(rz, np.asarray(df_main[f"дорога_{corner}_м"], dtype=float), equal_nan=True)
        assert np.allclose(fz, np.asarray(df_main[f"рама_угол_{corner}_z_м"], dtype=float), equal_nan=True)
        assert np.allclose(fx, wx, equal_nan=True)
        assert np.allclose(fy, wy, equal_nan=True)
        # Upper arm must not collapse into the lower-arm joint.
        arm_joint_z = np.asarray(df_main[f"arm_joint_{corner}_z_м"], dtype=float)
        arm2_joint_z = np.asarray(df_main[f"arm2_joint_{corner}_z_м"], dtype=float)
        assert np.nanmax(np.abs(arm2_joint_z - arm_joint_z)) > 1e-9, f"upper arm joint collapsed for {corner}"
        # C2 bottom must lie on the upper arm interpolation, not on the lower arm path.
        arm2_pivot_y = np.asarray(df_main[f"arm2_pivot_{corner}_y_м"], dtype=float)
        arm2_joint_y = np.asarray(df_main[f"arm2_joint_{corner}_y_м"], dtype=float)
        arm2_pivot_z = np.asarray(df_main[f"arm2_pivot_{corner}_z_м"], dtype=float)
        arm2_joint_z = np.asarray(df_main[f"arm2_joint_{corner}_z_м"], dtype=float)
        cyl2_bot_y = np.asarray(df_main[f"cyl2_bot_{corner}_y_м"], dtype=float)
        cyl2_bot_z = np.asarray(df_main[f"cyl2_bot_{corner}_z_м"], dtype=float)
        denom = arm2_joint_y - arm2_pivot_y
        mask = np.abs(denom) > 1e-12
        frac = np.zeros_like(cyl2_bot_y)
        frac[mask] = (cyl2_bot_y[mask] - arm2_pivot_y[mask]) / denom[mask]
        z_expected = arm2_pivot_z + frac * (arm2_joint_z - arm2_pivot_z)
        assert np.nanmax(np.abs(z_expected - cyl2_bot_z)) < 1e-6, f"cyl2 bottom is off the upper arm for {corner}"
        for kind in ("arm_pivot", "arm_joint", "arm2_pivot", "arm2_joint", "cyl1_top", "cyl1_bot", "cyl2_top", "cyl2_bot", "frame_corner"):
            cols = point_cols(kind, corner)
            for col in cols:
                assert col in df_main.columns
                arr = np.asarray(df_main[col], dtype=float)
                assert arr.shape[0] == len(df_main)
                assert np.all(np.isfinite(arr)), f"non-finite values in {col}"


def test_camozzi_active_generator_emits_canonical_solver_points_and_anim_latest(tmp_path: Path):
    params = _base()
    params["autoself_checks_in_simulate"] = False
    df_main, *_ = camozzi.simulate(params, _flat_test(), dt=1e-3, t_end=0.0, record_full=False)
    _assert_solver_points(df_main)
    npz_path, ptr_path = export_anim_latest_bundle(
        exports_dir=tmp_path,
        df_main=df_main,
        meta={"geometry": build_geometry_meta_from_base(params)},
    )
    assert npz_path.exists()
    assert ptr_path.exists()


def test_worldroad_active_generator_emits_canonical_solver_points_and_anim_latest(tmp_path: Path):
    params = _base()
    params.update({
        "пружина_преднатяг_на_отбое_строго": False,
        "mechanics_selfcheck": True,
    })
    df_main, *_ = worldroad.simulate(params, _flat_test(), dt=1e-3, t_end=0.0, record_full=False)
    _assert_solver_points(df_main)
    npz_path, ptr_path = export_anim_latest_bundle(
        exports_dir=tmp_path,
        df_main=df_main,
        meta={"geometry": build_geometry_meta_from_base(params)},
    )
    assert npz_path.exists()
    assert ptr_path.exists()


def test_active_generators_keep_wheel_upright_hardpoints_rigid_after_export(tmp_path: Path) -> None:
    cam_params = _base()
    cam_params["autoself_checks_in_simulate"] = False
    df_cam, *_ = camozzi.simulate(cam_params, _dynamic_test(), dt=2e-3, t_end=0.55, record_full=False)
    cam_npz, _ = export_anim_latest_bundle(
        exports_dir=tmp_path / "cam",
        df_main=df_cam,
        meta={"geometry": build_geometry_meta_from_base(cam_params)},
        mirror_global_pointer=False,
    )
    cam_bundle = load_npz(cam_npz)
    cam_status = collect_suspension_geometry_status(cam_bundle, tol_m=1e-6)
    assert cam_status["wheel_drift_corners"] == [], cam_status["issues"]

    world_params = _base()
    world_params.update({
        "autoself_checks_in_simulate": False,
        "пружина_преднатяг_на_отбое_строго": False,
        "mechanics_selfcheck": True,
    })
    df_world, *_ = worldroad.simulate(world_params, _dynamic_test(), dt=2e-3, t_end=0.55, record_full=False)
    world_npz, _ = export_anim_latest_bundle(
        exports_dir=tmp_path / "world",
        df_main=df_world,
        meta={"geometry": build_geometry_meta_from_base(world_params)},
        mirror_global_pointer=False,
    )
    world_bundle = load_npz(world_npz)
    world_status = collect_suspension_geometry_status(world_bundle, tol_m=1e-6)
    assert world_status["wheel_drift_corners"] == [], world_status["issues"]



def _configure_explicit_upper_arm(params: dict) -> dict:
    params = dict(params)
    params["autoself_checks_in_simulate"] = False
    params["dw_upper_pivot_inboard_перед_м"] = float(params["dw_lower_pivot_inboard_перед_м"]) + 0.035
    params["dw_upper_pivot_inboard_зад_м"] = float(params["dw_lower_pivot_inboard_зад_м"]) + 0.025
    params["dw_upper_pivot_z_перед_м"] = float(params["dw_lower_pivot_z_перед_м"]) + 0.12
    params["dw_upper_pivot_z_зад_м"] = float(params["dw_lower_pivot_z_зад_м"]) + 0.11
    params["dw_upper_arm_len_перед_м"] = float(params["dw_lower_arm_len_перед_м"]) - 0.015
    params["dw_upper_arm_len_зад_м"] = float(params["dw_lower_arm_len_зад_м"]) - 0.012
    return params



def _assert_source_data_drives_upper_arm(df_main, params: dict) -> None:
    for corner in CORNERS:
        axle = "перед" if corner in ("ЛП", "ПП") else "зад"
        frame_z = float(np.asarray(df_main[f"рама_угол_{corner}_z_м"], dtype=float)[0])
        arm_pivot_y = float(np.asarray(df_main[f"arm_pivot_{corner}_y_м"], dtype=float)[0])
        arm2_pivot_y = float(np.asarray(df_main[f"arm2_pivot_{corner}_y_м"], dtype=float)[0])
        arm_joint_y = float(np.asarray(df_main[f"arm_joint_{corner}_y_м"], dtype=float)[0])
        arm2_joint_y = float(np.asarray(df_main[f"arm2_joint_{corner}_y_м"], dtype=float)[0])
        arm2_pivot_z_rel = float(np.asarray(df_main[f"arm2_pivot_{corner}_z_м"], dtype=float)[0] - frame_z)
        expected_pivot_z = float(params[f"dw_upper_pivot_z_{axle}_м"])
        assert abs(arm2_pivot_z_rel - expected_pivot_z) < 1e-9, (corner, arm2_pivot_z_rel, expected_pivot_z)
        assert abs(arm2_pivot_y - arm_pivot_y) > 1e-9, f"upper pivot y did not use source-data for {corner}"
        assert abs(arm2_joint_y - arm_joint_y) > 1e-9, f"upper joint y did not use source-data for {corner}"



def test_explicit_upper_arm_source_data_changes_solver_points_for_active_generators() -> None:
    params = _configure_explicit_upper_arm(_base())
    df_cam, *_ = camozzi.simulate(params, _flat_test(), dt=1e-3, t_end=0.0, record_full=False)
    _assert_source_data_drives_upper_arm(df_cam, params)

    params_world = dict(params)
    params_world.update({
        "пружина_преднатяг_на_отбое_строго": False,
        "mechanics_selfcheck": True,
    })
    df_world, *_ = worldroad.simulate(params_world, _flat_test(), dt=1e-3, t_end=0.0, record_full=False)
    _assert_source_data_drives_upper_arm(df_world, params_world)
