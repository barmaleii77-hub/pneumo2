from pathlib import Path

import numpy as np

from pneumo_solver_ui import model_pneumo_v9_doublewishbone_camozzi as model


ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = ROOT / "pneumo_solver_ui" / "model_pneumo_v9_doublewishbone_camozzi.py"


def _scenario():
    return {
        "road_func": lambda t: np.zeros(4, dtype=float),
        "ax_func": lambda t: 0.0,
        "ay_func": lambda t: 0.0,
        "label_func": lambda t: 0,
    }


def test_camozzi_source_rel0_block_uses_canonical_yaw_key() -> None:
    src = MODEL_PATH.read_text(encoding="utf-8")
    assert "'yaw_рад'," in src
    assert "'psi_рад'," not in src


def test_camozzi_emits_canonical_yaw_rel0_service_column() -> None:
    df_main, *_ = model.simulate(
        {
            "mechanics_selfcheck": False,
            "пружина_преднатяг_на_отбое_строго": False,
        },
        _scenario(),
        dt=1e-3,
        t_end=0.0,
        record_full=False,
    )

    assert "yaw_рад" in df_main.columns
    assert "yaw_рад_rel0" in df_main.columns
    assert "psi_рад_rel0" not in df_main.columns
    assert abs(float(df_main["yaw_рад_rel0"].iloc[0])) <= 1e-12
