# -*- coding: utf-8 -*-

import numpy as np
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _smooth_bump(t: float, t0: float = 0.01, dur: float = 0.02, A: float = 0.02) -> float:
    """C1-бамп: 0 -> A на интервале [t0, t0+dur] с нулевой производной на концах."""
    if t <= t0:
        return 0.0
    if t >= t0 + dur:
        return float(A)
    x = (t - t0) / dur
    return float(A) * 0.5 * (1.0 - np.cos(np.pi * x))


def test_worldroad_motion_selfcheck_ok():
    """Проверяем, что при движении сохраняются тождества колесо/рама/дорога и кинематика штоков."""
    from pneumo_solver_ui import model_pneumo_v9_mech_doublewishbone_worldroad as m

    params = {
        'пружина_преднатяг_на_отбое_строго': False,
        'mechanics_selfcheck': True,
        # чуть ослабим допуск в тесте, но оставим микрометровый уровень
        'mechanics_selfcheck_tol_m': 1e-6,
    }

    test = {
        'road_func': lambda t: np.array([_smooth_bump(t), 0.0, 0.0, 0.0], dtype=float),
        'ax_func': lambda t: 0.0,
        'ay_func': lambda t: 0.0,
    }

    df_main, df_drossel, df_energy, nodes, edges, df_energy_edges, df_energy_groups, df_atm = m.simulate(
        params, test, dt=2e-3, t_end=0.05, record_full=False
    )

    assert int(df_atm.loc[0, 'mech_selfcheck_ok']) == 1
    assert float(df_atm.loc[0, 'mech_selfcheck_err_wheel_frame_m']) <= 1e-6
    assert float(df_atm.loc[0, 'mech_selfcheck_err_wheel_road_m']) <= 1e-6
    assert float(df_atm.loc[0, 'mech_selfcheck_err_stroke_C1_m']) <= 1e-6
    assert float(df_atm.loc[0, 'mech_selfcheck_err_stroke_C2_m']) <= 1e-6

    # rel0(t0) должен быть около 0
    if 'mech_selfcheck_rel0_t0_maxabs' in df_atm.columns:
        assert float(df_atm.loc[0, 'mech_selfcheck_rel0_t0_maxabs']) <= 1e-9


def test_worldroad_exports_world_xy_path_when_yaw_is_nonzero():
    from pneumo_solver_ui import model_pneumo_v9_mech_doublewishbone_worldroad as m

    params = {
        'пружина_преднатяг_на_отбое_строго': False,
        'mechanics_selfcheck': True,
    }
    test = {
        'road_func': lambda t: np.zeros(4, dtype=float),
        'ax_func': lambda t: 0.0,
        'ay_func': lambda t: 0.8 if t > 0.05 else 0.0,
        'vx0_м_с': 8.0,
    }

    df_main, *_ = m.simulate(params, test, dt=2e-3, t_end=0.20, record_full=False)

    assert 'скорость_vy_м_с' in df_main.columns
    assert 'путь_y_м' in df_main.columns
    assert np.all(np.isfinite(np.asarray(df_main['скорость_vy_м_с'], dtype=float)))
    assert np.all(np.isfinite(np.asarray(df_main['путь_y_м'], dtype=float)))
    assert abs(float(df_main['путь_y_м'].iloc[-1])) > 1e-6


def test_worldroad_exports_force_breakdown_without_mechanical_arb():
    from pneumo_solver_ui import model_pneumo_v9_mech_doublewishbone_worldroad as m

    params = {
        'пружина_преднатяг_на_отбое_строго': False,
        'стабилизатор_вкл': False,
    }
    test = {
        'road_func': lambda t: np.array([_smooth_bump(t), 0.0, 0.0, 0.0], dtype=float),
        'ax_func': lambda t: 0.0,
        'ay_func': lambda t: 0.0,
    }

    df_main, *_ = m.simulate(params, test, dt=2e-3, t_end=0.05, record_full=False)

    expected_cols = [
        'сила_подвески_ЛП_Н',
        'сила_подвески_итого_Н',
        'сила_пружины_ЛП_Н',
        'сила_пружины_итого_Н',
        'сила_пневматики_ЛП_Н',
        'сила_пневматики_итого_Н',
        'сила_пневматики_Ц1_ЛП_Н',
        'сила_пневматики_Ц2_ЛП_Н',
        'сила_отбойника_ЛП_Н',
        'момент_крен_подвеска_Нм',
        'момент_тангаж_итого_Нм',
    ]
    for col in expected_cols:
        assert col in df_main.columns
        vals = np.asarray(df_main[col], dtype=float)
        assert np.all(np.isfinite(vals))

    assert np.allclose(np.asarray(df_main['сила_стабилизатора_перед_Н'], dtype=float), 0.0)
    assert np.allclose(np.asarray(df_main['сила_стабилизатора_зад_Н'], dtype=float), 0.0)


def test_worldroad_default_diagonal_antiphase_keeps_energy_in_stabilizing_branch():
    from pneumo_solver_ui import model_pneumo_v9_mech_doublewishbone_worldroad as m

    A = 0.015
    w = 2.0 * np.pi * 1.5
    params = {
        'пружина_преднатяг_на_отбое_строго': False,
        'стабилизатор_вкл': False,
    }
    test = {
        # Canonical diagonal: right-front + left-rear.
        'road_func': lambda t: np.array([0.0, A * np.sin(w * t), -A * np.sin(w * t), 0.0], dtype=float),
        'ax_func': lambda t: 0.0,
        'ay_func': lambda t: 0.0,
    }

    _, _, df_energy, _, _, df_energy_edges, _, _ = m.simulate(
        params, test, dt=5e-3, t_end=4.0, record_full=False
    )

    diag_mask = df_energy['дроссель'].astype(str).str.contains('дроссель‑диагональ‑Ц2', regex=False)
    exh_mask = df_energy_edges['элемент'].astype(str).str.contains('дроссель_выхлоп_', regex=False)
    diag_energy = float(df_energy.loc[diag_mask, 'энергия_рассеяна_Дж'].sum())
    exhaust_energy = float(df_energy_edges.loc[exh_mask, 'энергия_Дж'].sum())

    assert diag_energy > 0.0
    assert exhaust_energy >= 0.0
    assert diag_energy > exhaust_energy * 1.25


def test_worldroad_hot_path_uses_precomputed_kinematics_constants():
    src = (ROOT / 'pneumo_solver_ui' / 'model_pneumo_v9_mech_doublewishbone_worldroad.py').read_text(encoding='utf-8')

    assert 'dw_L0_C1 = np.maximum(np.sqrt(dw_y_diff_sq_C1 + dw_z_diff0_C1 * dw_z_diff0_C1), 1e-9)' in src
    assert 'dw_L0_C2 = np.maximum(np.sqrt(dw_y_diff_sq_C2 + dw_z_diff0_C2 * dw_z_diff0_C2), 1e-9)' in src
    assert 'idx_C1_cap = np.array([node_index[f\'Ц1_{c}_БП\'] for c in corner_order], dtype=int)' in src
    assert 'edge_specs = tuple(' in src
    assert 'edge_specs_orifice = tuple(' in src
    assert 'y_pos0 = float(y_pos[0])' in src
    assert "p_abs_min = float(params.get('минимальное_абсолютное_давление_Па', 1000.0))" in src
    assert 'wheel_z_offset = wheel_radius if wheel_coord_is_contact else 0.0' in src
    assert 'wheel_coord_is_contact = wheel_coord_mode == "contact"' in src
    assert "road_dfunc_is_default_zero = isinstance(test, dict) and ('road_dfunc' not in test) and (world_cache is None)" in src
    assert 'def _dw_kin_precomputed(' in src
    assert 'def _mechanics_state_compact(' in src
    assert 'def _body_state_from_state(' in src
    assert 'def _pack_pressure_state_cfl(' in src
    assert 'def _compute_pressure_state_cfl(' in src
    assert 'def _compute_single_spring_force_component(' in src
    assert 'def _compute_single_spring_force_only(' in src
    assert 'def _compute_spring_force_components(' in src
    assert 'def _compute_spring_runtime_export_pack(' in src
    assert 'def _spring_force_wheel_only(' in src
    assert "solid_length_vec = np.asarray(spring_family['solid_length_m'], dtype=float)" in src
    assert "coil_bind_margin_min_vec = np.asarray(spring_family['coil_bind_margin_min_m'], dtype=float)" in src
    assert 'solid_length_has_any_C1 = bool(np.any(np.isfinite(solid_length_vec_C1)))' in src
    assert 'solid_length_has_any_C2 = bool(np.any(np.isfinite(solid_length_vec_C2)))' in src
    assert 'solid_length_has_any = bool(np.any(np.isfinite(solid_length_vec)))' in src
    assert 'spring_zero4 = np.zeros(4, dtype=float)' in src
    assert 'def _compute_suspension_force_state(' in src
    assert 'def _compute_suspension_force_rhs_scalars(' in src
    assert 'def _compute_suspension_force_rhs(' in src
    assert 'def _compute_tire_force_rhs_scalars(' in src
    assert 'def _compute_tire_force_rhs_from_state_scalars(' in src
    assert 'def _compute_tire_force_rhs(' in src
    assert 'def _fill_rhs_from_pressure_state(' in src
    assert 'def _rhs_from_pressure_state(' in src
    assert 'def _stroke_outside_range(' in src
    suspension_body = src[src.index('def _compute_suspension_force_state('):src.index('def rhs(')]
    assert 'spring_force: np.ndarray | None = None' in suspension_body
    assert 'full_output: bool = True' in suspension_body
    assert 'if not full_output:' in suspension_body
    assert 'if spring_force is None:' in suspension_body
    assert 'F_sum = F_susp[0] + F_susp[1] + F_susp[2] + F_susp[3]' in suspension_body
    suspension_rhs_body = src[src.index('def _compute_suspension_force_rhs('):src.index('def _rhs_from_pressure_state(')]
    assert 'spring_force: np.ndarray | None = None' not in suspension_rhs_body
    assert 'full_output: bool = True' not in suspension_rhs_body
    assert 'F_susp0, F_susp1, F_susp2, F_susp3, z_ddot, phi_ddot, theta_ddot = _compute_suspension_force_rhs_scalars(' in suspension_rhs_body
    assert 'return np.array([F_susp0, F_susp1, F_susp2, F_susp3], dtype=float), z_ddot, phi_ddot, theta_ddot' in suspension_rhs_body
    suspension_rhs_scalars_body = src[src.index('def _compute_suspension_force_rhs_scalars('):src.index('def _compute_suspension_force_rhs(')]
    assert 'F_spr = _spring_force_wheel_only(' in suspension_rhs_scalars_body
    assert 'F_susp0 = float(F_spr[0]) - (' in suspension_rhs_scalars_body
    assert 'if arb_enabled:' in suspension_rhs_scalars_body
    assert 'if _stroke_outside_range(s_raw_C1, stroke_C1) or _stroke_outside_range(s_raw_C2, stroke_C2):' in suspension_rhs_scalars_body
    spring_force_body = src[src.index('def _spring_force_wheel_only('):src.index('def _build_spring_runtime_state(')]
    assert "if spring_force_eval is None:" in spring_force_body
    assert "if spring_mode == 'delta':" in spring_force_body
    assert "compression = x0_vec + np.asarray(delta_vec, dtype=float)" in spring_force_body
    assert "if dual_spring_mode:" in spring_force_body
    assert "if spring_mode == 'c2':" in spring_force_body
    assert '_compute_single_spring_force_only(' in spring_force_body
    assert '_compute_spring_runtime_components(' not in spring_force_body
    single_spring_force_only_body = src[src.index('def _compute_single_spring_force_only('):src.index('def _compute_spring_force_components(')]
    assert 'return spring_zero4' in single_spring_force_only_body
    assert 'x_query = x0_vec_local + (s0_vec_local - s_cyl)' in single_spring_force_only_body
    assert 'np.clip' not in single_spring_force_only_body
    spring_runtime_components_body = src[src.index('def _compute_spring_runtime_components('):src.index('def _compute_spring_runtime_export_pack(')]
    assert '_ = np.asarray(delta_vec, dtype=float)' not in spring_runtime_components_body
    assert 'if solid_length_has_any_C1:' in spring_runtime_components_body
    assert 'coil_margin_c1 = len_c1 - coil_bind_stop_vec_C1' in spring_runtime_components_body
    assert 'if solid_length_has_any_C2:' in spring_runtime_components_body
    assert 'coil_margin_c2 = len_c2 - coil_bind_stop_vec_C2' in spring_runtime_components_body
    spring_runtime_export_body = src[src.index('def _compute_spring_runtime_export_pack('):src.index('def _spring_force_wheel_only(')]
    assert 'if solid_length_has_any:' in spring_runtime_export_body
    assert 'coil_margin = length - coil_bind_stop_vec' in spring_runtime_export_body
    mechanics_body = src[src.index('def _mechanics_state('):src.index('def _build_pressure_vectors(')]
    assert 'sin_phi = math.sin(phi)' in mechanics_body
    assert 'z_body = np.empty(4, dtype=float)' in mechanics_body
    assert 'delta = np.empty(4, dtype=float)' in mechanics_body
    assert 'y_vel_term = (cos_phi * phi_dot * cos_theta) - (sin_phi * sin_theta * theta_dot)' in mechanics_body
    compact_body = src[src.index('def _mechanics_state_compact('):src.index('def _body_state_from_state(')]
    assert 'z_body = np.empty(4, dtype=float)' not in compact_body
    assert 'delta = np.empty(4, dtype=float)' in compact_body
    body_state_body = src[src.index('def _body_state_from_state('):src.index('def _pack_pressure_state_cfl(')]
    assert 'z_body = np.empty(4, dtype=float)' in body_state_body
    assert 'z_body_dot = np.empty(4, dtype=float)' in body_state_body
    assert 'def _fill_flows(mdots, p):' in src
    flows_body = src[src.index('def _fill_flows(mdots, p):'):src.index('k_stop = float(params.get(')]
    assert 'for ei, n1, n2, area, cd in edge_specs_orifice:' in flows_body
    assert 'for ei, n1, n2, area, cd, dp_crack in edge_specs_check:' in flows_body
    assert 'def _mdot_forward(' in src
    assert "_mdot_orifice_signed_active = lambda pu, pdn, area, cd: mdot_orifice_signed_smooth(" in src
    assert 'if smooth_valves:' in src
    assert "if kind == 'orifice':" not in flows_body
    tire_body = src[src.index('if smooth_contacts:'):src.index('def _compute_suspension_force_state(')]
    assert 'if road_dfunc_is_default_zero:' in tire_body
    assert 'pen_dot = -zw_dot if road_dfunc_is_default_zero else (road_dfunc(t) - zw_dot)' in tire_body
    assert 'pen_dot0 = -zw_dot[0]' in tire_body
    assert 'def _compute_tire_force_rhs_from_state_scalars(t: float, state: np.ndarray)' in tire_body
    assert 'zw0 = float(state[3]); zw1 = float(state[4]); zw2 = float(state[5]); zw3 = float(state[6])' in tire_body
    pressure_vectors_body = src[src.index('def _build_pressure_vectors('):src.index('# Функция объёмов (дифференциальная)')]
    assert 's_node = np.where(chamber_is_C1 == 1, s1[chamber_corner], s2[chamber_corner])' in pressure_vectors_body
    assert 'dV[chamber_indices] = chamber_sign * chamber_area * sdot_node' in pressure_vectors_body
    stop_body = src[src.index('def _stop_force_axial('):src.index('def _compute_suspension_force_state(')]
    assert 'out = np.empty(4, dtype=float)' in stop_body
    assert 'return zero4' in stop_body
    assert 'def _stop_force_axial(' in src
    assert 'spring_runtime_fill_plan = []' in src
    assert 'rhs(state, float(t))' not in src
    assert 'last_mech' not in src
    assert 'build_spring_family_runtime_snapshot(' not in src
    assert 'def compute_pressures_fast(state):' in src
    assert 'def _project_masses(_state: np.ndarray, *, return_prepared: bool = False, include_dv: bool = False):' in src
    assert 'def _project_masses_mid(_state: np.ndarray):' in src
    assert 'prepared_cfl = None' in src
    assert 'if prepared_cfl is None:' in src
    assert 'prepared_log_state = None' in src
    assert 'def _heun_step(' in src
    assert 'rhs_k1_buf = np.empty_like(state0)' in src
    assert 'rhs_k2_buf = np.empty_like(state0)' in src
    assert 'rhs_tmp_buf = np.empty_like(state0)' in src
    assert 'state_mid_buf = np.empty_like(state0)' in src
    assert 'mdots_k1_buf = np.empty(E, dtype=float)' in src
    assert 'mdots_k2_buf = np.empty(E, dtype=float)' in src
    assert 'dm_dt_k1_buf = np.empty(N, dtype=float)' in src
    assert 'dm_dt_log_buf = np.empty(N, dtype=float)' in src
    assert 'p_state_mid_buf = np.empty_like(V0_vec)' in src
    assert 'prepared_mid = _project_masses_mid(mid)' in src
    assert 'prepared_next = _project_masses(y_new, return_prepared=return_prepared, include_dv=return_prepared)' in src
    assert '_state, prepared_cfl = _heun_step(_state, t_loc, h, k1=k1_state, return_prepared=True)' in src
    assert 'state, _istat, prepared_log_state = _advance_with_substeps(' in src
    assert 'prepared_cfl0=prepared_log_state' in src
    assert 'k2 = _fill_rhs_from_pressure_state(' in src
    assert 'k1_state = _fill_rhs_from_pressure_state(' in src
    rhs_body = src[src.index('def _rhs_from_pressure_state('):src.index('def rhs(')]
    assert 'dst = np.empty_like(state)' in rhs_body
    assert 'return _fill_rhs_from_pressure_state(' in rhs_body
    fill_rhs_body = src[src.index('def _fill_rhs_from_pressure_state('):src.index('def _rhs_from_pressure_state(')]
    assert 'dst[14:] = dm_dt' in fill_rhs_body
    assert 'return dst' in fill_rhs_body
    assert 'F_susp0, F_susp1, F_susp2, F_susp3, z_ddot, phi_ddot, theta_ddot = _compute_suspension_force_rhs_scalars(' in fill_rhs_body
    assert 'F_tire0, F_tire1, F_tire2, F_tire3 = _compute_tire_force_rhs_from_state_scalars(t, state)' in fill_rhs_body
    assert "if wheel_coord_mode == 'contact':" not in rhs_body
    project_masses_body = src[src.index('def _project_masses('):src.index('def _advance_with_substeps(')]
    assert '_mechanics_state_compact(z_, phi_, theta_, zw_, z_dot_, phi_dot_, theta_dot_, zw_dot_)' in project_masses_body
    assert '_build_pressure_vectors(s_C1, s_C2, s_dot_C1, s_dot_C2, include_dv=False)' in project_masses_body
    assert 'volumes(z_, phi_, theta_, zw_, z_dot_, phi_dot_, theta_dot_, zw_dot_)[0]' not in project_masses_body
    assert 'V_safe = V_tmp if np.all(V_tmp >= 1e-9) else np.maximum(1e-9, V_tmp)' in project_masses_body
    assert 'np.maximum(m_state, m_floor, out=m_state)' in project_masses_body
    project_masses_mid_body = src[src.index('def _project_masses_mid('):src.index('def _advance_with_substeps(')]
    assert '_build_pressure_vectors(s_C1, s_C2, s_dot_C1, s_dot_C2, include_dv=False)' in project_masses_mid_body
    assert 'np.divide(m_state, V_safe, out=p_state_mid_buf)' in project_masses_mid_body
    assert 'np.multiply(p_state_mid_buf, rt_air, out=p_state_mid_buf)' in project_masses_mid_body
    assert 'None,' in project_masses_mid_body
    fast_pressures_body = src[src.index('def compute_pressures_fast(state):'):src.index('def _compute_pressure_state_cfl(state):')]
    assert 'V_safe = V if np.all(V >= 1e-9) else np.maximum(1e-9, V)' in fast_pressures_body
    assert 'm_floor = (p_abs_min * V_safe) / rt_air' in fast_pressures_body
    assert 'm_safe = m if np.all(m >= m_floor) else np.maximum(m, m_floor)' in fast_pressures_body
    assert 'np.divide(m_safe, V_safe, out=p)' in fast_pressures_body
    cfl_pressures_body = src[src.index('def _compute_pressure_state_cfl(state):'):src.index('# Параметры сглаживания логики клапанов')]
    assert 'V_safe = V if np.all(V >= 1e-9) else np.maximum(1e-9, V)' in cfl_pressures_body
    assert 'm_floor = (p_abs_min * V_safe) / rt_air' in cfl_pressures_body
    assert 'm_safe = m if np.all(m >= m_floor) else np.maximum(m, m_floor)' in cfl_pressures_body
    assert 'np.divide(m_safe, V_safe, out=p)' in cfl_pressures_body
    advance_body = src[src.index('def _advance_with_substeps('):src.index('out.update(spring_family_runtime_series_template')]
    assert ') = _compute_pressure_state_cfl(_state)' in advance_body
    assert 'mdots_ = _fill_flows(mdots_k1_buf, p_) if mdots_cached is None else mdots_cached' in advance_body
    assert 'np.dot(B, mdots_, out=dm_dt_k1_buf)' in advance_body
    assert 'dm_dt_k1_buf[idx_atm] = 0.0' in advance_body
    assert 'dm_dt_ = dm_dt_k1_buf' in advance_body
    assert ') = compute_pressures(_state)' not in advance_body
    assert 'np.multiply(k1, hh, out=state_mid_buf)' in advance_body
    assert 'np.add(state_mid_buf, y, out=state_mid_buf)' in advance_body
    assert 'np.add(k1, k2, out=state_mid_buf)' in advance_body
    assert 'np.multiply(state_mid_buf, 0.5 * hh, out=state_mid_buf)' in advance_body
    assert 'spring_state_now = _build_spring_runtime_state(' not in src
    assert 'spring_force=np.asarray(spring_force_wheel_now, dtype=float)' in src
    assert 'np.dot(B, mdots, out=dm_dt_log_buf)' in src
