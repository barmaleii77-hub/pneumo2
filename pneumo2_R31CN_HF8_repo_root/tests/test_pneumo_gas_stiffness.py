# -*- coding: utf-8 -*-

import math

import numpy as np


def test_gas_stiffness_axial_double_basic():
    from pneumo_solver_ui.pneumo_gas_stiffness import gas_stiffness_axial_double

    P = 200000.0  # Pa abs
    n = 1.4
    A = 1e-2  # m^2
    V = 1e-3  # m^3

    k = gas_stiffness_axial_double(
        p_cap_abs_Pa=P,
        p_rod_abs_Pa=P,
        A_cap_m2=A,
        A_rod_m2=A,
        V_cap_m3=V,
        V_rod_m3=V,
        n_poly=n,
    )

    expected = n * P * (A * A / V + A * A / V)
    assert math.isfinite(k)
    assert abs(k - expected) / expected < 1e-12


def test_gas_stiffness_from_geometry_midstroke_symmetry():
    from pneumo_solver_ui.pneumo_gas_stiffness import gas_stiffness_axial_from_geometry

    P = 300000.0
    n = 1.3
    V_dead = 2e-5
    stroke = 0.2
    s_ref = 0.1
    A_cap = 1e-2
    A_rod = 8e-3

    k = gas_stiffness_axial_from_geometry(
        p_ref_abs_Pa=P,
        A_cap_m2=A_cap,
        A_rod_m2=A_rod,
        V_dead_m3=V_dead,
        stroke_m=stroke,
        s_ref_m=s_ref,
        n_poly=n,
        volume_factor=1.0,
    )

    V_cap = V_dead + A_cap * s_ref
    V_rod = V_dead + A_rod * (stroke - s_ref)
    expected = n * P * (A_cap**2 / V_cap + A_rod**2 / V_rod)
    assert math.isfinite(k)
    assert abs(k - expected) / expected < 1e-12


def test_p_abs_from_param_threshold_behavior():
    from pneumo_solver_ui.pneumo_gas_stiffness import p_abs_from_param

    P_ATM = 101325.0
    # Treat small numbers as gauge
    assert p_abs_from_param(0.0, p_atm_Pa=P_ATM) == P_ATM
    assert p_abs_from_param(1000.0, p_atm_Pa=P_ATM) == P_ATM + 1000.0

    # Large numbers are assumed to be absolute (pass-through)
    assert p_abs_from_param(200000.0, p_atm_Pa=P_ATM) == 200000.0


def test_volume_factor_scales_inverse():
    from pneumo_solver_ui.pneumo_gas_stiffness import gas_stiffness_axial_double

    P = 200000.0
    n = 1.4
    A = 1e-2
    V = 1e-3

    k1 = gas_stiffness_axial_double(P, P, A, A, V, V, n_poly=n, volume_factor=1.0)
    k2 = gas_stiffness_axial_double(P, P, A, A, V, V, n_poly=n, volume_factor=2.0)
    assert k2 > 0.0
    assert abs(k2 - 0.5 * k1) / k1 < 1e-12

