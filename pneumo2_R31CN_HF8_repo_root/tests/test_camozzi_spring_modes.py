# -*- coding: utf-8 -*-

import numpy as np

from pneumo_solver_ui.suspension_family_runtime import spring_family_runtime_column


def _flat_test_case():
    return {
        "road_func": lambda t: np.zeros(4, dtype=float),
        "ax_func": lambda t: 0.0,
        "ay_func": lambda t: 0.0,
    }


def test_camozzi_manual_spring_x0_exports_and_runtime_columns():
    from pneumo_solver_ui import model_pneumo_v9_doublewishbone_camozzi as m

    x0_manual = np.array([0.01, 0.02, 0.03, 0.04], dtype=float)
    params = {
        "пружина_преднатяг_на_отбое_строго": False,
        "spring_interp_mode": "pchip",
        "spring_x0_mode": "manual",
        "spring_x0_manual_m": x0_manual.tolist(),
    }

    df_main, df_drossel, df_energy, nodes, edges, df_energy_edges, df_energy_groups, df_atm = m.simulate(
        params, _flat_test_case(), dt=1e-3, t_end=0.0, record_full=False
    )

    assert df_atm.loc[0, "spring_mode"] == "c1"
    assert df_atm.loc[0, "spring_interp_mode"] == "pchip"
    assert df_atm.loc[0, "spring_x0_mode"] == "manual"
    assert np.allclose(
        [
            float(df_atm.loc[0, "spring_x0_LP_m"]),
            float(df_atm.loc[0, "spring_x0_PP_m"]),
            float(df_atm.loc[0, "spring_x0_LZ_m"]),
            float(df_atm.loc[0, "spring_x0_PZ_m"]),
        ],
        x0_manual,
        atol=1e-12,
    )
    assert np.allclose(
        [
            float(df_main.loc[0, "пружина_предсжатие_стат_ЛП_м"]),
            float(df_main.loc[0, "пружина_предсжатие_стат_ПП_м"]),
            float(df_main.loc[0, "пружина_предсжатие_стат_ЛЗ_м"]),
            float(df_main.loc[0, "пружина_предсжатие_стат_ПЗ_м"]),
        ],
        x0_manual,
        atol=1e-12,
    )


def test_camozzi_per_axle_spring_x0_keeps_left_right_pairing_and_front_rear_split():
    from pneumo_solver_ui import model_pneumo_v9_doublewishbone_camozzi as m

    params = {
        "пружина_преднатяг_на_отбое_строго": False,
        "spring_interp_mode": "linear",
        "spring_x0_mode": "per_axle",
        "cg_x_m": 0.25,
        "cg_y_m": 0.0,
        "масса_рамы": 800.0,
    }

    df_main, df_drossel, df_energy, nodes, edges, df_energy_edges, df_energy_groups, df_atm = m.simulate(
        params, _flat_test_case(), dt=1e-3, t_end=0.0, record_full=False
    )

    x0_lp = float(df_atm.loc[0, "spring_x0_LP_m"])
    x0_pp = float(df_atm.loc[0, "spring_x0_PP_m"])
    x0_lz = float(df_atm.loc[0, "spring_x0_LZ_m"])
    x0_pz = float(df_atm.loc[0, "spring_x0_PZ_m"])

    assert df_atm.loc[0, "spring_x0_mode"] == "per_axle"
    assert np.isclose(x0_lp, x0_pp, atol=1e-12)
    assert np.isclose(x0_lz, x0_pz, atol=1e-12)
    assert not np.isclose(x0_lp, x0_lz, atol=1e-9)


def test_camozzi_manual_static_mode_disables_geom_sync_and_preserves_family_free_length():
    from pneumo_solver_ui import model_pneumo_v9_doublewishbone_camozzi as m

    manual_free_length = 0.55
    params = {
        "кинематика_режим": "dw2d_mounts",
        "spring_static_mode": "manual",
        "пружина_длина_свободная_м": manual_free_length,
    }

    df_main, df_drossel, df_energy, nodes, edges, df_energy_edges, df_energy_groups, df_atm = m.simulate(
        params, _flat_test_case(), dt=1e-3, t_end=0.0, record_full=False
    )

    free_length_lp = float(df_main.loc[0, spring_family_runtime_column("длина_м", "Ц1", "ЛП")])
    compression_lp = float(df_main.loc[0, spring_family_runtime_column("компрессия_м", "Ц1", "ЛП")])

    assert df_atm.loc[0, "spring_static_mode"] == "manual"
    assert int(df_atm.loc[0, "spring_sync_geom_requested"]) == 0
    assert int(df_atm.loc[0, "spring_sync_geom_applied"]) == 0
    assert int(df_atm.loc[0, "spring_sync_geom_defaulted"]) == 1
    assert np.isclose(free_length_lp + compression_lp, manual_free_length, atol=1e-12)


def test_camozzi_auto_midstroke_static_enables_geom_sync_and_overrides_manual_free_length():
    from pneumo_solver_ui import model_pneumo_v9_doublewishbone_camozzi as m

    seeded_free_length = 0.55
    params = {
        "кинематика_режим": "dw2d_mounts",
        "spring_static_mode": "auto_midstroke_static",
        "пружина_длина_свободная_м": seeded_free_length,
    }

    df_main, df_drossel, df_energy, nodes, edges, df_energy_edges, df_energy_groups, df_atm = m.simulate(
        params, _flat_test_case(), dt=1e-3, t_end=0.0, record_full=False
    )

    free_length_lp = float(df_main.loc[0, spring_family_runtime_column("длина_м", "Ц1", "ЛП")])
    compression_lp = float(df_main.loc[0, spring_family_runtime_column("компрессия_м", "Ц1", "ЛП")])

    assert df_atm.loc[0, "spring_static_mode"] == "auto_midstroke_static"
    assert int(df_atm.loc[0, "spring_sync_geom_requested"]) == 1
    assert int(df_atm.loc[0, "spring_sync_geom_applied"]) == 1
    assert int(df_atm.loc[0, "spring_sync_geom_defaulted"]) == 1
    assert not np.isclose(free_length_lp + compression_lp, seeded_free_length, atol=1e-3)
