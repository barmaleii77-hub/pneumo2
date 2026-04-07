# -*- coding: utf-8 -*-

import numpy as np


def test_orifice_smooth_matches_piecewise_far_from_transition():
    """Гладкий расход должен быть близок к piecewise вдали от pr_crit."""
    from pneumo_solver_ui import model_pneumo_v9_mech_doublewishbone_worldroad as m

    A = 1e-5
    Cd = 0.8

    # Сильно choked (pr << pr_crit)
    p_up = 300_000.0
    p_dn = 10_000.0
    md_pw = float(m.mdot_orifice(p_up, p_dn, A, Cd))
    md_sm = float(m.mdot_orifice_smooth(p_up, p_dn, A, Cd, k_pr=120.0))
    assert abs(md_sm - md_pw) / max(1e-12, abs(md_pw)) < 1e-3

    # Сильно subsonic (pr >> pr_crit)
    p_up = 300_000.0
    p_dn = 260_000.0
    md_pw = float(m.mdot_orifice(p_up, p_dn, A, Cd))
    md_sm = float(m.mdot_orifice_smooth(p_up, p_dn, A, Cd, k_pr=120.0))
    assert abs(md_sm - md_pw) / max(1e-12, abs(md_pw)) < 1e-3


def test_orifice_signed_smooth_is_approximately_antisymmetric():
    from pneumo_solver_ui import model_pneumo_v9_mech_doublewishbone_worldroad as m

    A = 1e-5
    Cd = 0.8

    p1 = 300_000.0
    p2 = 200_000.0
    f = float(m.mdot_orifice_signed_smooth(p1, p2, A, Cd, k_pr=120.0, k_sign=1e-4, eps_dp_Pa=1.0))
    b = float(m.mdot_orifice_signed_smooth(p2, p1, A, Cd, k_pr=120.0, k_sign=1e-4, eps_dp_Pa=1.0))
    assert abs(f + b) < 1e-9 + 1e-6 * abs(f)

    # near-zero Δp -> near-zero flow
    z = float(m.mdot_orifice_signed_smooth(200_000.0, 200_000.0, A, Cd, k_pr=120.0, k_sign=1e-4, eps_dp_Pa=1.0))
    assert abs(z) < 1e-9


def test_worldroad_smoke_with_smooth_flow_mode():
    """Smoke: симуляция не должна падать при включённом smooth-flow."""
    from pneumo_solver_ui import model_pneumo_v9_mech_doublewishbone_worldroad as m

    params = {
        # важно: не форсим строгий преднатяг на полном отбое для теста нулевой позы
        'пружина_преднатяг_на_отбое_строго': False,
        'mechanics_selfcheck': True,

        # включаем smooth расход
        'pneumo_flow_smooth_mode': True,
        'pneumo_flow_smooth_k_pr': 80.0,
        'pneumo_flow_smooth_k_sign': 1e-4,
        'pneumo_flow_smooth_eps_dp_Pa': 1.0,
    }

    test = {
        'road_func': lambda t: np.zeros(4),
        'ax_func': lambda t: 0.0,
        'ay_func': lambda t: 0.0,
    }

    df_main, df_drossel, df_energy, nodes, edges, df_energy_edges, df_energy_groups, df_atm = m.simulate(
        params, test, dt=1e-3, t_end=0.0, record_full=False
    )

    assert int(df_atm.loc[0, 'mech_selfcheck_ok']) == 1
