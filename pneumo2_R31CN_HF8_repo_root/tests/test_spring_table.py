# -*- coding: utf-8 -*-

import numpy as np


def test_spring_table_linear_roundtrip():
    from pneumo_solver_ui.spring_table import spring_force, spring_inverse_force

    x_tab = np.array([0.0, 1.0], dtype=float)
    f_tab = np.array([0.0, 100.0], dtype=float)

    xq = np.array([0.0, 0.3, 0.8, 1.0], dtype=float)
    fq = spring_force(xq, x_tab, f_tab, mode='linear')
    assert np.allclose(fq, np.array([0.0, 30.0, 80.0, 100.0]))

    x_back = spring_inverse_force(fq, x_tab, f_tab, mode='linear')
    assert np.allclose(x_back, xq)


def test_spring_table_pchip_linear_data_is_linear():
    """На линейных данных PCHIP должен совпадать с линейной интерполяцией."""
    from pneumo_solver_ui.spring_table import spring_force, spring_inverse_force

    x_tab = np.array([0.0, 1.0, 2.0], dtype=float)
    f_tab = np.array([0.0, 100.0, 200.0], dtype=float)

    xq = np.array([0.25, 0.5, 1.5], dtype=float)
    fq = spring_force(xq, x_tab, f_tab, mode='pchip')
    assert np.allclose(fq, np.array([25.0, 50.0, 150.0]), atol=1e-9)

    x_back = spring_inverse_force(fq, x_tab, f_tab, mode='pchip')
    assert np.allclose(x_back, xq, atol=1e-9)


def test_spring_table_inverse_with_plateau_is_stable():
    """Проверка устойчивости на нестрого монотонной таблице (плато)."""
    from pneumo_solver_ui.spring_table import spring_inverse_force

    x_tab = np.array([0.0, 1.0, 2.0], dtype=float)
    f_tab = np.array([0.0, 10.0, 10.0], dtype=float)

    # На силе плато возвращаем максимально возможный ход (консервативно).
    xq = spring_inverse_force(np.array([10.0]), x_tab, f_tab, mode='linear')
    assert float(xq[0]) == 2.0



def test_spring_table_stiffness_linear_piecewise():
    from pneumo_solver_ui.spring_table import spring_stiffness

    x_tab = np.array([0.0, 1.0, 2.0], dtype=float)
    f_tab = np.array([0.0, 100.0, 300.0], dtype=float)

    # slopes: [0..1] -> 100, [1..2] -> 200
    k = spring_stiffness(np.array([0.5, 1.5]), x_tab, f_tab, mode='linear')
    assert np.allclose(k, np.array([100.0, 200.0]))


def test_spring_table_stiffness_pchip_linear_data_constant_slope():
    from pneumo_solver_ui.spring_table import spring_stiffness

    x_tab = np.array([0.0, 1.0, 2.0], dtype=float)
    f_tab = np.array([0.0, 100.0, 200.0], dtype=float)

    k = spring_stiffness(np.array([0.2, 0.8, 1.2, 1.8]), x_tab, f_tab, mode='pchip')
    assert np.allclose(k, 100.0, atol=1e-9)
