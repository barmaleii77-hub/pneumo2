from pathlib import Path

import numpy as np
import pytest

from pneumo_solver_ui import model_pneumo_v9_mech_doublewishbone as mech_v9
from pneumo_solver_ui import model_pneumo_v9_mech_doublewishbone_worldroad as worldroad_v9
from pneumo_solver_ui import model_pneumo_v8_energy_audit_vacuum_patched_smooth_all as energy_v8


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


@pytest.mark.parametrize(
    "model_mod",
    [
        mech_v9,
        worldroad_v9,
        energy_v8,
    ],
)
def test_remaining_generators_export_only_canonical_frame_corner_channels(model_mod):
    df_main, *_ = model_mod.simulate(
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

        assert f"рама_{c}_z_м" not in df_main.columns
        assert f"рама_{c}_v_м_с" not in df_main.columns
        assert f"рама_{c}_a_м_с2" not in df_main.columns
        assert f"рама_{c}_vz_м_с" not in df_main.columns
        assert f"рама_{c}_az_м_с2" not in df_main.columns


def test_generator_source_files_do_not_contain_legacy_frame_corner_literals():
    base = Path(__file__).resolve().parents[1]
    sources = [
        base / "pneumo_solver_ui" / "model_pneumo_v9_doublewishbone_camozzi.py",
        base / "pneumo_solver_ui" / "model_pneumo_v9_mech_doublewishbone_worldroad.py",
        base / "pneumo_solver_ui" / "model_pneumo_v9_mech_doublewishbone.py",
        base / "pneumo_solver_ui" / "model_pneumo_v8_energy_audit_vacuum_patched_smooth_all.py",
    ]
    forbidden = []
    for corner in CORNERS:
        forbidden.extend(
            [
                f"рама_{corner}_z_м",
                f"рама_{corner}_vz_м_с",
                f"рама_{corner}_az_м_с2",
                f"рама_{corner}_v_м_с",
                f"рама_{corner}_a_м_с2",
            ]
        )

    for src in sources:
        text = src.read_text("utf-8")
        for key in forbidden:
            assert key not in text, f"{src.name} still contains legacy key {key}"
