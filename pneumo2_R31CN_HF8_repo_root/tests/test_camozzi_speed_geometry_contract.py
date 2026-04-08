from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from pneumo_solver_ui import model_pneumo_v9_doublewishbone_camozzi as camozzi
from pneumo_solver_ui.desktop_animator.data_bundle import load_npz
from pneumo_solver_ui.desktop_animator.self_checks import run_self_checks


ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = ROOT / "pneumo_solver_ui" / "model_pneumo_v9_doublewishbone_camozzi.py"
BASE_PATH = ROOT / "pneumo_solver_ui" / "default_base.json"


def _base() -> dict:
    return json.loads(BASE_PATH.read_text(encoding="utf-8"))


def _smoke_df(vx0_mps: float = 11.11111111111111):
    df_main, *_ = camozzi.simulate(
        _base(),
        {
            "имя": "smoke",
            "vx0_м_с": float(vx0_mps),
            "ax_func": lambda t: 0.0,
            "ay_func": lambda t: 0.0,
        },
        dt=0.01,
        t_end=0.05,
        record_full=False,
        max_steps=20,
    )
    return df_main


def test_camozzi_source_uses_canonical_speed_and_wheel_radius_keys() -> None:
    src = MODEL_PATH.read_text(encoding="utf-8")
    assert "скорость_vx0_м_с" not in src
    assert "колесо_радиус_м" not in src
    assert "params.get('wheel_coord_mode'" not in src
    assert "test.get('vx0_м_с'" in src
    assert "params.get('радиус_колеса_м'" in src
    assert "params.get('колесо_координата'" in src


def test_camozzi_runtime_respects_canonical_speed_and_center_geometry() -> None:
    vx0 = 11.11111111111111
    df_main = _smoke_df(vx0)

    assert abs(float(df_main["скорость_vx_м_с"].iloc[0]) - vx0) <= 1e-9
    assert float(df_main["путь_x_м"].iloc[-1]) > 0.5
    assert float(df_main["колесо_относительно_дороги_ЛП_м"].iloc[0]) > 0.0
    assert float(df_main["рама_относительно_дороги_ЛП_м"].iloc[0]) > 0.0
    assert abs(float(df_main["колесо_контакт_ЛП_м"].iloc[0]) - (float(df_main["перемещение_колеса_ЛП_м"].iloc[0]) - 0.3)) <= 1e-9


def test_camozzi_dual_spring_runtime_exports_explicit_family_columns() -> None:
    params = _base()
    params.update(
        {
            "механика_пружина_режим": "dual",
            "пружина_Ц1_перед_масштаб": 1.1,
            "пружина_Ц1_зад_масштаб": 1.2,
            "пружина_Ц2_перед_масштаб": 1.3,
            "пружина_Ц2_зад_масштаб": 1.4,
            "пружина_Ц1_перед_длина_свободная_м": 0.30,
            "пружина_Ц1_зад_длина_свободная_м": 0.31,
            "пружина_Ц2_перед_длина_свободная_м": 0.32,
            "пружина_Ц2_зад_длина_свободная_м": 0.33,
        }
    )

    df_main, *_ = camozzi.simulate(
        params,
        {
            "имя": "dual-smoke",
            "vx0_м_с": 5.0,
            "ax_func": lambda t: 0.0,
            "ay_func": lambda t: 0.0,
        },
        dt=0.01,
        t_end=0.02,
        record_full=False,
        max_steps=10,
    )

    assert float(df_main["пружина_режим_семейства_id"].iloc[0]) == 3.0
    assert float(df_main["пружина_Ц1_ЛП_активна"].iloc[0]) == 1.0
    assert float(df_main["пружина_Ц2_ЛП_активна"].iloc[0]) == 1.0
    assert np.isfinite(float(df_main["пружина_Ц1_ЛП_длина_м"].iloc[0]))
    assert np.isfinite(float(df_main["пружина_Ц2_ЛП_длина_м"].iloc[0]))
    assert abs(float(df_main["пружина_Ц1_ЛП_длина_м"].iloc[0]) - float(df_main["пружина_Ц2_ЛП_длина_м"].iloc[0])) > 1e-6


def test_desktop_animator_selfcheck_accepts_camozzi_canonical_speed_and_wheel_pose(tmp_path: Path) -> None:
    vx0 = 11.11111111111111
    df_main = _smoke_df(vx0)
    npz_path = tmp_path / "camozzi_smoke.npz"
    meta_json = {
        "vx0_м_с": vx0,
        "geometry": {
            "wheelbase_m": 1.5,
            "track_m": 1.0,
            "wheel_radius_m": 0.3,
        },
    }
    np.savez(
        npz_path,
        main_cols=np.asarray(df_main.columns.tolist(), dtype=object),
        main_values=df_main.to_numpy(dtype=float),
        meta_json=json.dumps(meta_json, ensure_ascii=False),
    )

    bundle = load_npz(npz_path)
    report = run_self_checks(bundle, wheel_radius_m=0.3, track_m=1.0, wheelbase_m=1.5)

    assert report.level != "FAIL"
    assert report.stats.get("speed_meta_vx0_t0_err_mps", 1.0) <= 1e-9
    assert report.stats.get("wheel_xy_pose_max_err_m", 1.0) <= 1e-9
