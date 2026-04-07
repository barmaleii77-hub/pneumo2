import math

import pandas as pd

from pneumo_solver_ui.data_contract import build_geometry_meta_from_base
from pneumo_solver_ui.solver_points_geometry import append_solver_points_full_dw2d


def test_build_geometry_meta_includes_cylinder_visual_contract():
    base = {
        'база': 1.5,
        'колея': 1.0,
        'радиус_колеса_м': 0.3,
        'wheel_width_m': 0.22,
        'длина_рамы': 1.8,
        'ширина_рамы': 0.3,
        'высота_рамы': 0.6,
        'диаметр_поршня_Ц1': 0.032,
        'диаметр_штока_Ц1': 0.016,
        'диаметр_поршня_Ц2': 0.05,
        'диаметр_штока_Ц2': 0.014,
        'ход_штока_Ц1_перед_м': 0.25,
        'ход_штока_Ц1_зад_м': 0.24,
        'ход_штока_Ц2_перед_м': 0.23,
        'ход_штока_Ц2_зад_м': 0.22,
        'мёртвый_объём_камеры': 1.5e-5,
    }
    meta = build_geometry_meta_from_base(base)
    assert meta['cyl1_bore_diameter_m'] == 0.032
    assert meta['cyl1_rod_diameter_m'] == 0.016
    assert meta['cyl2_bore_diameter_m'] == 0.05
    assert meta['cyl2_rod_diameter_m'] == 0.014
    assert meta['cyl1_stroke_front_m'] == 0.25
    assert meta['cyl1_stroke_rear_m'] == 0.24
    assert meta['cyl2_stroke_front_m'] == 0.23
    assert meta['cyl2_stroke_rear_m'] == 0.22
    assert meta['dead_volume_chamber_m3'] == 1.5e-5


def test_frame_mounted_points_follow_frame_plane_not_corner_z():
    df = pd.DataFrame({
        'рама_угол_ЛП_z_м': [0.4],
        'рама_угол_ПП_z_м': [0.2],
        'рама_угол_ЛЗ_z_м': [0.4],
        'рама_угол_ПЗ_z_м': [0.2],
        'перемещение_колеса_ЛП_м': [0.30],
        'перемещение_колеса_ПП_м': [0.30],
        'перемещение_колеса_ЛЗ_м': [0.30],
        'перемещение_колеса_ПЗ_м': [0.30],
        'дорога_ЛП_м': [0.0],
        'дорога_ПП_м': [0.0],
        'дорога_ЛЗ_м': [0.0],
        'дорога_ПЗ_м': [0.0],
        'путь_x_м': [0.0],
        'путь_y_м': [0.0],
        'yaw_рад': [0.0],
    })
    out = append_solver_points_full_dw2d(
        df,
        x_pos=[0.75, 0.75, -0.75, -0.75],
        y_pos=[0.5, -0.5, 0.5, -0.5],
        frame_z_cols={c: f'рама_угол_{c}_z_м' for c in ('ЛП', 'ПП', 'ЛЗ', 'ПЗ')},
        wheel_z_cols={c: f'перемещение_колеса_{c}_м' for c in ('ЛП', 'ПП', 'ЛЗ', 'ПЗ')},
        road_z_cols={c: f'дорога_{c}_м' for c in ('ЛП', 'ПП', 'ЛЗ', 'ПЗ')},
        x_path_col='путь_x_м',
        y_path_col='путь_y_м',
        yaw_col='yaw_рад',
        inboard_front_m=0.35,
        inboard_rear_m=0.35,
        pivot_z_front_m=0.0,
        pivot_z_rear_m=0.0,
        lower_arm_len_front_m=0.35,
        lower_arm_len_rear_m=0.35,
        upper_inboard_front_m=0.35,
        upper_inboard_rear_m=0.35,
        upper_pivot_z_front_m=0.10,
        upper_pivot_z_rear_m=0.10,
        upper_arm_len_front_m=0.35,
        upper_arm_len_rear_m=0.35,
        topsep_c1_m=[0.6, 0.6, 0.6, 0.6],
        topz_c1_m=[0.2, 0.2, 0.2, 0.2],
        lowfrac_c1=[0.7, 0.7, 0.7, 0.7],
        topsep_c2_m=[0.6, 0.6, 0.6, 0.6],
        topz_c2_m=[0.2, 0.2, 0.2, 0.2],
        lowfrac_c2=[0.7, 0.7, 0.7, 0.7],
        lower_frame_branch_front_x_m=[0.08, 0.08, 0.08, 0.08],
        lower_frame_branch_rear_x_m=[-0.08, -0.08, -0.08, -0.08],
        lower_hub_branch_front_x_m=[0.04, 0.04, 0.04, 0.04],
        lower_hub_branch_rear_x_m=[-0.04, -0.04, -0.04, -0.04],
        upper_frame_branch_front_x_m=[0.08, 0.08, 0.08, 0.08],
        upper_frame_branch_rear_x_m=[-0.08, -0.08, -0.08, -0.08],
        upper_hub_branch_front_x_m=[0.04, 0.04, 0.04, 0.04],
        upper_hub_branch_rear_x_m=[-0.04, -0.04, -0.04, -0.04],
    )
    # Left front frame point is inboard at y=+0.15. It must follow the rigid frame pose,
    # not stick to the wheel XY or to the left corner Z. For this geometry the rigid-frame
    # expectation is 0.3 + 0.15 * (0.2 / hypot(1.0, 0.2)).
    z_lower_frame_front_lp = float(out.loc[0, 'lower_arm_frame_front_ЛП_z_м'])
    expected_rigid_z = 0.3 + 0.15 * (0.2 / math.hypot(1.0, 0.2))
    assert math.isclose(z_lower_frame_front_lp, expected_rigid_z, rel_tol=0.0, abs_tol=1e-9)
    assert not math.isclose(z_lower_frame_front_lp, 0.4, rel_tol=0.0, abs_tol=1e-9)
