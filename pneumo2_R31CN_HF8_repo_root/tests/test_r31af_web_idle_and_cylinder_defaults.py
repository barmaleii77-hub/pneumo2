from __future__ import annotations

import json
import math
from pathlib import Path

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


def test_default_frame_side_cylinder_mounts_snap_to_frame_top_and_side_planes() -> None:
    base = _default_base()
    frame_w = float(base['ширина_рамы'])
    frame_h = float(base['высота_рамы'])
    for key in [
        'верх_Ц1_перед_между_ЛП_ПП_м', 'верх_Ц1_зад_между_ЛЗ_ПЗ_м',
        'верх_Ц2_перед_между_ЛП_ПП_м', 'верх_Ц2_зад_между_ЛЗ_ПЗ_м',
    ]:
        assert math.isclose(float(base[key]), frame_w, rel_tol=0.0, abs_tol=1e-12), key
    for key in [
        'верх_Ц1_перед_z_относительно_рамы_м', 'верх_Ц1_зад_z_относительно_рамы_м',
        'верх_Ц2_перед_z_относительно_рамы_м', 'верх_Ц2_зад_z_относительно_рамы_м',
    ]:
        assert math.isclose(float(base[key]), frame_h, rel_tol=0.0, abs_tol=1e-12), key


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
