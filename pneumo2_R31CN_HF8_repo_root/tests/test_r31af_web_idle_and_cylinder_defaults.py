from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def _default_base() -> dict:
    return json.loads((ROOT / "pneumo_solver_ui" / "default_base.json").read_text(encoding="utf-8"))


def test_web_followers_use_very_long_idle_sleep_and_event_driven_wakeups() -> None:
    files = [ROOT / 'pneumo_solver_ui' / 'app.py', ROOT / 'pneumo_solver_ui' / 'pneumo_ui_app.py']
    html_sources = [
        ROOT / 'pneumo_solver_ui' / 'ui_flow_panel_helpers.py',
        ROOT / 'pneumo_solver_ui' / 'ui_svg_html_builders.py',
    ]
    files += html_sources
    files += sorted((ROOT / 'pneumo_solver_ui' / 'components').rglob('*.html'))
    for path in files:
        src = path.read_text(encoding='utf-8')
        assert '__nextIdleMs(60000, 180000, 300000)' not in src, str(path)
        if path in html_sources or path.suffix == '.html':
            assert "window.addEventListener('scroll'" in src, str(path)
            assert "window.addEventListener('resize'" in src, str(path)
            assert 'visibilitychange' in src or 'storage' in src or 'focus' in src, str(path)


def test_default_frame_side_cylinder_mounts_are_explicit_and_not_snapped_to_frame_height() -> None:
    base = _default_base()
    frame_h = float(base['высота_рамы'])
    for key in [
        'верх_Ц1_перед_между_ЛП_ПП_м', 'верх_Ц1_зад_между_ЛЗ_ПЗ_м',
        'верх_Ц2_перед_между_ЛП_ПП_м', 'верх_Ц2_зад_между_ЛЗ_ПЗ_м',
    ]:
        assert math.isfinite(float(base[key])), key
        assert float(base[key]) > 0.0, key
    for key in [
        'верх_Ц1_перед_z_относительно_рамы_м', 'верх_Ц1_зад_z_относительно_рамы_м',
        'верх_Ц2_перед_z_относительно_рамы_м', 'верх_Ц2_зад_z_относительно_рамы_м',
    ]:
        assert math.isfinite(float(base[key])), key
        assert not math.isclose(float(base[key]), frame_h, rel_tol=0.0, abs_tol=1e-12), key


def test_worldroad_allows_upper_mount_coordinates_outside_frame_envelope() -> None:
    from pneumo_solver_ui import model_pneumo_v9_mech_doublewishbone_worldroad as m

    base = _default_base()
    base.update({
        'пружина_преднатяг_на_отбое_строго': False,
        'верх_Ц1_перед_между_ЛП_ПП_м': 0.42,
        'верх_Ц1_зад_между_ЛЗ_ПЗ_м': 0.42,
        'верх_Ц2_перед_между_ЛП_ПП_м': 0.42,
        'верх_Ц2_зад_между_ЛЗ_ПЗ_м': 0.42,
        'верх_Ц1_перед_z_относительно_рамы_м': 0.72,
        'верх_Ц1_зад_z_относительно_рамы_м': 0.72,
        'верх_Ц2_перед_z_относительно_рамы_м': 0.72,
        'верх_Ц2_зад_z_относительно_рамы_м': 0.72,
        'mechanics_selfcheck_expect_static_at_t0': False,
    })
    test = {
        'road_func': lambda t: np.zeros(4, dtype=float),
        'ax_func': lambda t: 0.0,
        'ay_func': lambda t: 0.0,
    }

    df_main, *_rest, df_atm = m.simulate(base, test, dt=2e-3, t_end=0.01, record_full=False)

    assert len(df_main) > 0
    assert 'mech_selfcheck_ok' in df_atm.columns
    assert int(df_atm['mech_selfcheck_ok'].iloc[0]) == 1


def test_active_model_mount_fallbacks_are_not_derived_from_frame_dims() -> None:
    root = ROOT / 'pneumo_solver_ui'
    files = [
        root / 'model_pneumo_v9_mech_doublewishbone_worldroad.py',
        root / 'model_pneumo_v9_mech_doublewishbone.py',
        root / 'model_pneumo_v9_doublewishbone_camozzi.py',
        root / 'model_pneumo_v9_mech_doublewishbone_r48_reference.py',
    ]
    banned = [
        "верх_Ц1_перед_между_ЛП_ПП_м', float(W)",
        "верх_Ц1_зад_между_ЛЗ_ПЗ_м',   float(W)",
        "верх_Ц2_перед_между_ЛП_ПП_м', float(W)",
        "верх_Ц2_зад_между_ЛЗ_ПЗ_м',   float(W)",
        "верх_Ц1_перед_z_относительно_рамы_м', float(H)",
        "верх_Ц1_зад_z_относительно_рамы_м',   float(H)",
        "верх_Ц2_перед_z_относительно_рамы_м', float(H)",
        "верх_Ц2_зад_z_относительно_рамы_м',   float(H)",
        "верх_Ц1_перед_между_ЛП_ПП_м', track",
        "верх_Ц2_перед_между_ЛП_ПП_м', track",
        "верх_Ц1_зад_между_ЛЗ_ПЗ_м', track",
        "верх_Ц2_зад_между_ЛЗ_ПЗ_м', track",
    ]
    for path in files:
        src = path.read_text(encoding='utf-8')
        for token in banned:
            assert token not in src, f'{path}: {token}'


def test_default_strokes_and_contract_lengths_are_explicit_and_finite() -> None:
    base = _default_base()
    dead = float(base['мёртвый_объём_камеры'])
    assert dead > 0.0
    for idx in (1, 2):
        bore = float(base[f'диаметр_поршня_Ц{idx}'])
        rod = float(base[f'диаметр_штока_Ц{idx}'])
        stroke_f = float(base[f'ход_штока_Ц{idx}_перед_м'])
        stroke_r = float(base[f'ход_штока_Ц{idx}_зад_м'])
        assert bore > 0.0 and rod > 0.0 and rod < bore
        assert stroke_f > 0.0 and stroke_r > 0.0
        a_cap = math.pi * (0.5 * bore) ** 2
        a_rod = a_cap - math.pi * (0.5 * rod) ** 2
        dead_cap = dead / a_cap
        dead_rod = dead / a_rod
        assert dead_cap > 0.0 and dead_rod > dead_cap
        assert dead_cap + stroke_f + dead_rod > stroke_f
