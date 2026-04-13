from __future__ import annotations

from pathlib import Path

import numpy as np

from pneumo_solver_ui.desktop_animator.data_bundle import DataBundle, NpzTable
from pneumo_solver_ui.solver_points_contract import collect_solver_points_contract_issues, point_cols, POINT_KINDS
from pneumo_solver_ui.visual_contract import collect_visual_contract_status


ROOT = Path(__file__).resolve().parents[1]


def _bundle(cols: list[str], values: np.ndarray) -> DataBundle:
    return DataBundle(npz_path=ROOT / 'dummy.npz', main=NpzTable(cols=cols, values=values), meta={})


def test_solver_points_contract_detects_missing_triplets() -> None:
    cols = ['время_с']
    cols += list(point_cols('arm_pivot', 'ЛП'))
    status = collect_solver_points_contract_issues(cols, context='pytest')

    assert not status['ok']
    assert 'arm_pivot/ПП' in status['missing_triplets']
    assert any('missing canonical solver-point triplets' in msg for msg in status['issues'])


def test_data_bundle_has_solver_points_only_when_full_canonical_contract_present() -> None:
    n = 3
    cols = ['время_с']
    vals = [np.arange(n, dtype=float)]
    for kind in POINT_KINDS:
        for corner in ('ЛП', 'ПП', 'ЛЗ', 'ПЗ'):
            for col in point_cols(kind, corner):
                cols.append(col)
                vals.append(np.zeros(n, dtype=float))
    b = _bundle(cols, np.column_stack(vals))
    assert b.has_solver_points() is True


def test_data_bundle_road_profile_refuses_missing_road_columns() -> None:
    n = 5
    cols = ['время_с', 'скорость_vx_м_с', 'yaw_рад']
    values = np.column_stack([
        np.linspace(0.0, 0.4, n),
        np.ones(n, dtype=float),
        np.zeros(n, dtype=float),
    ])
    b = _bundle(cols, values)
    try:
        b.ensure_road_profile(wheelbase_m=2.8, mode='center')
    except ValueError as exc:
        assert 'NO ROAD DATA' in str(exc) or 'Missing canonical road traces' in str(exc)
    else:
        raise AssertionError('ensure_road_profile must not invent flat road when road traces are missing')


def test_data_bundle_body_velocity_prefers_canonical_solver_channels_over_path_reconstruction() -> None:
    t = np.array([0.0, 0.5, 1.0], dtype=float)
    vx = np.array([1.0, 2.0, 3.0], dtype=float)
    vy = np.array([0.25, 0.5, 0.75], dtype=float)
    cols = ['время_с', 'скорость_vx_м_с', 'скорость_vy_м_с', 'yaw_рад', 'путь_x_м', 'путь_y_м']
    values = np.column_stack([
        t,
        vx,
        vy,
        np.zeros_like(t),
        np.array([0.0, 100.0, 200.0], dtype=float),
        np.zeros_like(t),
    ])
    b = _bundle(cols, values)

    vxb, vyb = b.ensure_body_velocity_xy()

    assert np.allclose(vxb, vx)
    assert np.allclose(vyb, vy)


def test_data_bundle_world_velocity_prefers_rotated_solver_body_velocity_over_path_gradient() -> None:
    t = np.array([0.0, 0.5, 1.0], dtype=float)
    vx = np.array([2.0, 2.0, 2.0], dtype=float)
    vy = np.array([1.0, 1.0, 1.0], dtype=float)
    cols = ['время_с', 'скорость_vx_м_с', 'скорость_vy_м_с', 'yaw_рад', 'путь_x_м', 'путь_y_м']
    values = np.column_stack([
        t,
        vx,
        vy,
        np.zeros_like(t),
        np.array([0.0, 0.0, 0.0], dtype=float),
        np.array([0.0, 0.0, 0.0], dtype=float),
    ])
    b = _bundle(cols, values)

    vxw, vyw = b.ensure_world_velocity_xy()

    assert np.allclose(vxw, vx)
    assert np.allclose(vyw, vy)


def test_data_bundle_world_acceleration_prefers_rotated_solver_body_acceleration_over_velocity_derivative() -> None:
    t = np.array([0.0, 0.5, 1.0], dtype=float)
    ax = np.array([5.0, 5.0, 5.0], dtype=float)
    ay = np.array([1.5, 1.5, 1.5], dtype=float)
    cols = [
        'время_с',
        'скорость_vx_м_с',
        'скорость_vy_м_с',
        'ускорение_продольное_ax_м_с2',
        'ускорение_поперечное_ay_м_с2',
        'yaw_рад',
        'путь_x_м',
        'путь_y_м',
    ]
    values = np.column_stack([
        t,
        np.array([3.0, 3.0, 3.0], dtype=float),
        np.array([0.0, 0.0, 0.0], dtype=float),
        ax,
        ay,
        np.zeros_like(t),
        np.array([0.0, 1.5, 3.0], dtype=float),
        np.zeros_like(t),
    ])
    b = _bundle(cols, values)

    axw, ayw = b.ensure_world_acceleration_xy()

    assert np.allclose(axw, ax)
    assert np.allclose(ayw, ay)


def test_data_bundle_service_fallback_messages_report_validation_degradation() -> None:
    t = np.array([0.0, 0.5, 1.0], dtype=float)
    cols = ['время_с', 'скорость_vx_м_с', 'скорость_vy_м_с', 'yaw_рад']
    values = np.column_stack([
        t,
        np.array([1.0, 1.0, 1.0], dtype=float),
        np.array([0.1, 0.1, 0.1], dtype=float),
        np.array([0.0, 0.1, 0.2], dtype=float),
    ])
    b = _bundle(cols, values)

    b.ensure_world_xy()
    b.ensure_yaw_rate_rad_s()
    b.ensure_world_acceleration_xy()
    b.ensure_body_acceleration_xy()

    msgs = b.service_fallback_messages()

    assert any("falls back to derived world XY" in msg for msg in msgs)
    assert any("falls back to derivative of yaw" in msg for msg in msgs)
    assert any("falls back to derivative of world velocity" in msg for msg in msgs)
    assert any("falls back to rotated world acceleration" in msg for msg in msgs)


def test_data_bundle_service_fallback_messages_stay_empty_when_canonical_motion_channels_exist() -> None:
    t = np.array([0.0, 0.5, 1.0], dtype=float)
    cols = [
        'время_с',
        'скорость_vx_м_с',
        'скорость_vy_м_с',
        'ускорение_продольное_ax_м_с2',
        'ускорение_поперечное_ay_м_с2',
        'yaw_рад',
        'yaw_rate_рад_с',
        'путь_x_м',
        'путь_y_м',
    ]
    values = np.column_stack([
        t,
        np.array([2.0, 2.0, 2.0], dtype=float),
        np.array([0.5, 0.5, 0.5], dtype=float),
        np.array([0.1, 0.1, 0.1], dtype=float),
        np.array([0.2, 0.2, 0.2], dtype=float),
        np.zeros_like(t),
        np.array([0.01, 0.01, 0.01], dtype=float),
        np.array([0.0, 1.0, 2.0], dtype=float),
        np.zeros_like(t),
    ])
    b = _bundle(cols, values)

    b.ensure_world_xy()
    b.ensure_world_velocity_xy()
    b.ensure_body_velocity_xy()
    b.ensure_yaw_rate_rad_s()
    b.ensure_world_acceleration_xy()
    b.ensure_body_acceleration_xy()

    assert b.service_fallback_messages() == []


def test_collect_visual_contract_status_reports_no_data_messages() -> None:
    import pandas as pd

    df = pd.DataFrame({'время_с': [0.0, 0.1], 'дорога_ЛП_м': [0.0, 0.01]})
    status = collect_visual_contract_status(df)

    assert status['road_complete'] is False
    assert 'ПП' in status['road_missing_corners']
    assert str(status['road_overlay_text']).startswith('NO ROAD DATA')
    assert str(status['solver_points_overlay_text']).startswith('NO SOLVER POINTS')


def test_component_sources_contain_explicit_no_data_overlays() -> None:
    files = {
        'mech_anim': ROOT / 'pneumo_solver_ui' / 'components' / 'mech_anim' / 'index.html',
        'mech_anim_quad': ROOT / 'pneumo_solver_ui' / 'components' / 'mech_anim_quad' / 'index.html',
        'mech_car3d': ROOT / 'pneumo_solver_ui' / 'components' / 'mech_car3d' / 'index.html',
        'road_profile_live': ROOT / 'pneumo_solver_ui' / 'components' / 'road_profile_live' / 'index.html',
    }
    texts = {name: path.read_text(encoding='utf-8') for name, path in files.items()}

    assert 'NO SOLVER POINTS' in texts['mech_anim']
    assert 'NO SOLVER POINTS' in texts['mech_anim_quad']
    assert 'NO ROAD DATA' in texts['mech_car3d']
    assert 'NO ROAD DATA' in texts['road_profile_live']
