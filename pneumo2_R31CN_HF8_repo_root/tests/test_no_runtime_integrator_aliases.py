from pathlib import Path

import numpy as np

from pneumo_solver_ui import model_pneumo_v9_doublewishbone_camozzi as m_cam
from pneumo_solver_ui import model_pneumo_v9_mech_doublewishbone_r48_reference as m_r48
from pneumo_solver_ui import model_pneumo_v9_mech_doublewishbone_worldroad as m_world

ROOT = Path(__file__).resolve().parents[1]
MODEL_FILES = [
    ROOT / "pneumo_solver_ui" / "model_pneumo_v9_doublewishbone_camozzi.py",
    ROOT / "pneumo_solver_ui" / "model_pneumo_v9_mech_doublewishbone_worldroad.py",
    ROOT / "pneumo_solver_ui" / "model_pneumo_v9_mech_doublewishbone_r48_reference.py",
]

LEGACY_OUT_SNIPPETS = [
    "'интегратор_h_min_с': np.zeros(n_steps)",
    "'интегратор_h_max_с': np.zeros(n_steps)",
    "'интегратор_h_mean_с': np.zeros(n_steps)",
    "'интегратор_rejects_N': np.zeros(n_steps, dtype=int)",
    "'интегратор_err_max': np.zeros(n_steps)",
    '# ---- Compatibility aliases',
    'out["интегратор_подшаг_макс_с"] = out["интегратор_h_max_с"]',
    'out["интегратор_подшаг_мин_с"] = out["интегратор_h_min_с"]',
    'out["интегратор_подшаг_средн_с"] = out["интегратор_h_mean_с"]',
    'out["интегратор_отклонения_N"] = out["интегратор_rejects_N"]',
    'out["интегратор_ошибка_max"] = out["интегратор_err_max"]',
]
CANONICAL_COLS = [
    'интегратор_подшаги_N',
    'интегратор_подшаг_мин_с',
    'интегратор_подшаг_макс_с',
    'интегратор_подшаг_средн_с',
    'интегратор_отклонения_N',
    'интегратор_ошибка_max',
]
LEGACY_COLS = [
    'интегратор_h_min_с',
    'интегратор_h_max_с',
    'интегратор_h_mean_с',
    'интегратор_rejects_N',
    'интегратор_err_max',
]


def _scenario():
    return {
        "road_func": lambda t: np.zeros(4, dtype=float),
        "ax_func": lambda t: 0.0,
        "ay_func": lambda t: 0.0,
        "label_func": lambda t: 0,
    }


def _assert_canonical_integrator_columns(df):
    for col in CANONICAL_COLS:
        assert col in df.columns, col
    for col in LEGACY_COLS:
        assert col not in df.columns, col


def test_active_models_do_not_contain_runtime_integrator_alias_blocks():
    for path in MODEL_FILES:
        text = path.read_text('utf-8')
        for snippet in LEGACY_OUT_SNIPPETS:
            assert snippet not in text, f"{path.name} still contains forbidden legacy output snippet: {snippet}"


def test_camozzi_exports_only_canonical_integrator_columns():
    df_main, *_ = m_cam.simulate({"mechanics_selfcheck": False}, _scenario(), dt=1e-3, t_end=0.0, record_full=False)
    _assert_canonical_integrator_columns(df_main)


def test_worldroad_exports_only_canonical_integrator_columns():
    df_main, *_ = m_world.simulate({"mechanics_selfcheck": False, "пружина_преднатяг_на_отбое_строго": False}, _scenario(), dt=1e-3, t_end=0.0, record_full=False)
    _assert_canonical_integrator_columns(df_main)


def test_r48_exports_only_canonical_integrator_columns():
    df_main, *_ = m_r48.simulate({"mechanics_selfcheck": False, "пружина_преднатяг_на_отбое_строго": False}, _scenario(), dt=1e-3, t_end=0.0, record_full=False)
    _assert_canonical_integrator_columns(df_main)
