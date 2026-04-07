from __future__ import annotations

import json
from pathlib import Path

from pneumo_solver_ui import model_pneumo_v9_doublewishbone_camozzi as model


ROOT = Path(__file__).resolve().parents[1]


def _base_params() -> dict:
    data = json.loads((ROOT / "pneumo_solver_ui" / "default_base.json").read_text(encoding="utf-8"))
    data["enforce_scheme_integrity"] = False
    data["enforce_camozzi_only"] = False
    data["autoself_checks_in_simulate"] = False
    data["use_rel0_columns"] = False
    data["road_field_type"] = "flat"
    return data


def test_camozzi_default_solver_points_export_trapezoids_and_x_split() -> None:
    params = _base_params()
    df_main, *_ = model.simulate(
        params,
        {"road_mode": "world", "road_field_type": "flat"},
        dt=0.01,
        t_end=0.01,
        record_full=False,
        max_steps=3,
    )

    required = [
        "lower_arm_frame_front_ЛП_x_м",
        "lower_arm_frame_rear_ЛП_x_м",
        "lower_arm_hub_front_ЛП_x_м",
        "lower_arm_hub_rear_ЛП_x_м",
        "upper_arm_frame_front_ЛП_x_м",
        "upper_arm_frame_rear_ЛП_x_м",
        "upper_arm_hub_front_ЛП_x_м",
        "upper_arm_hub_rear_ЛП_x_м",
    ]
    for col in required:
        assert col in df_main.columns, col

    row0 = df_main.iloc[0]
    assert row0["cyl1_top_ЛП_x_м"] != row0["cyl2_top_ЛП_x_м"]
    assert row0["cyl1_bot_ЛП_x_м"] != row0["cyl2_bot_ЛП_x_м"]
    assert row0["upper_arm_frame_front_ЛП_x_м"] != row0["upper_arm_frame_rear_ЛП_x_м"]
    assert row0["lower_arm_frame_front_ЛП_x_м"] != row0["lower_arm_frame_rear_ЛП_x_м"]
    # Frame pivots should sit close to frame half-width, and hub joints close to wheel mid-plane.
    assert abs(float(row0["arm_pivot_ЛП_y_м"]) - 0.15) < 1e-6
    assert abs(float(row0["arm_joint_ЛП_y_м"]) - 0.50) < 1e-6
