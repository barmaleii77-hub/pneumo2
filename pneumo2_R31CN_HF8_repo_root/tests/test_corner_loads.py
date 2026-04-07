import numpy as np

from pneumo_solver_ui.corner_loads import compute_body_corner_loads, parse_cg_offsets_with_geom


def test_corner_loads_equal_default():
    W = 1000.0
    m = W / 9.81
    F, rep = compute_body_corner_loads(m_body=m, g=9.81, wheelbase_m=2.0, track_m=1.6, cg_x_m=0.0, cg_y_m=0.0)
    assert F.shape == (4,)
    assert np.isfinite(F).all()
    assert abs(float(F.sum()) - W) < 1e-6
    assert np.allclose(F, np.full(4, W/4.0), atol=1e-6)
    assert abs(rep.front_frac - 0.5) < 1e-12
    assert abs(rep.left_frac - 0.5) < 1e-12


def test_corner_loads_front_heavier_when_cg_forward():
    m = 500.0
    g = 9.81
    L = 2.0
    T = 1.6
    cg_x = +0.2  # forward
    F, rep = compute_body_corner_loads(m_body=m, g=g, wheelbase_m=L, track_m=T, cg_x_m=cg_x, cg_y_m=0.0)
    # front axle total > rear axle total
    F_front = float(F[0] + F[1])
    F_rear = float(F[2] + F[3])
    assert F_front > F_rear
    assert rep.front_frac > 0.5


def test_parse_cg_offsets_with_geom_x_from_front():
    params = {
        'x_cg_от_передней_оси_м': 1.0,
    }
    wheelbase = 2.0
    # CG at middle => x_from_front = wheelbase/2 => cg_x = 0
    params['x_cg_от_передней_оси_м'] = wheelbase/2
    cg_x, cg_y = parse_cg_offsets_with_geom(params, wheelbase_m=wheelbase, track_m=1.6)
    assert abs(cg_x) < 1e-12
    assert abs(cg_y) < 1e-12


def test_corner_loads_stiffness_matches_cg_for_pure_longitudinal_shift():
    W = 2000.0
    m = W / 9.81
    L = 2.4
    T = 1.6
    cg_x = 0.15  # forward
    # cg_y=0 => no cross term, stiffness and cg-mode should coincide for uniform k
    F_cg, _ = compute_body_corner_loads(m_body=m, g=9.81, wheelbase_m=L, track_m=T, cg_x_m=cg_x, cg_y_m=0.0, mode='cg')
    F_k, rep_k = compute_body_corner_loads(m_body=m, g=9.81, wheelbase_m=L, track_m=T, cg_x_m=cg_x, cg_y_m=0.0,
                                          mode='stiffness', k_corner_N_m=[150000.0]*4)
    assert np.allclose(F_k, F_cg, atol=1e-6)
    assert rep_k.mode == 'stiffness'


def test_corner_loads_stiffness_matches_cg_for_pure_lateral_shift():
    W = 2000.0
    m = W / 9.81
    L = 2.4
    T = 1.6
    cg_y = 0.10  # left
    # cg_x=0 => no cross term, stiffness and cg-mode should coincide for uniform k
    F_cg, _ = compute_body_corner_loads(m_body=m, g=9.81, wheelbase_m=L, track_m=T, cg_x_m=0.0, cg_y_m=cg_y, mode='cg')
    F_k, rep_k = compute_body_corner_loads(m_body=m, g=9.81, wheelbase_m=L, track_m=T, cg_x_m=0.0, cg_y_m=cg_y,
                                          mode='stiffness', k_corner_N_m=[150000.0]*4)
    assert np.allclose(F_k, F_cg, atol=1e-6)
    assert rep_k.mode == 'stiffness'


def test_corner_loads_stiffness_has_zero_cross_weight_for_uniform_k():
    # For uniform stiffness the minimum-energy solution has no diagonal bias
    W = 3000.0
    m = W / 9.81
    L = 2.5
    T = 1.7
    cg_x = 0.2
    cg_y = 0.1
    F_k, rep_k = compute_body_corner_loads(m_body=m, g=9.81, wheelbase_m=L, track_m=T, cg_x_m=cg_x, cg_y_m=cg_y,
                                          mode='stiffness', k_corner_N_m=[200000.0]*4)
    F_cg, rep_cg = compute_body_corner_loads(m_body=m, g=9.81, wheelbase_m=L, track_m=T, cg_x_m=cg_x, cg_y_m=cg_y, mode='cg')
    # stiffness => near-zero diagonal bias
    assert abs(float(rep_k.diag_bias_N)) < 1e-6
    # cg-mode separable => non-zero diagonal bias (cross term)
    assert abs(float(rep_cg.diag_bias_N)) > 0.0
    # total weight is preserved
    assert abs(float(F_k.sum()) - W) < 1e-6
    assert abs(float(F_cg.sum()) - W) < 1e-6


def test_corner_loads_stiffness_asymmetry_creates_diagonal_bias():
    # Asymmetric k_i resolves the indeterminacy and yields diagonal bias even for cg_x=cg_y=0.
    W = 4000.0
    m = W / 9.81
    L = 2.6
    T = 1.6
    k = [250000.0, 150000.0, 150000.0, 250000.0]  # FL & RR stiffer
    F_k, rep_k = compute_body_corner_loads(m_body=m, g=9.81, wheelbase_m=L, track_m=T, cg_x_m=0.0, cg_y_m=0.0,
                                          mode='stiffness', k_corner_N_m=k)
    assert abs(float(F_k.sum()) - W) < 1e-6
    assert abs(float(rep_k.diag_bias_N)) > 1e-3
    # Diagonal with higher stiffness should carry more
    assert float(F_k[0] + F_k[3]) > float(F_k[1] + F_k[2])
