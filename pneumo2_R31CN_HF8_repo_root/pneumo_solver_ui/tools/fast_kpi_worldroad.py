# -*- coding: utf-8 -*-
"""fast_kpi_worldroad.py

Онлайн-оценка KPI для world-road v9 без построения DataFrame/Excel.

Зачем:
- ускорить перебор параметров/первичную калибровку;
- убрать накладные расходы pandas при тысячах прогонов;
- показать, как использовать compile_only + observe.

Запуск:
    python -m pneumo_solver_ui.tools.fast_kpi_worldroad

Опции:
    --test-index N     взять тест N из default_suite.json (по умолчанию 0)
    --fully-smooth     включить fully_smooth_mode (для дифференцируемого режима)
    --dt DT            переопределить шаг интегрирования
    --t-end T          переопределить длительность
    --json-out PATH    сохранить KPI в JSON

Выход:
- печатает JSON со сводными KPI и несколькими диагностическими полями.

Важно:
- Скрипт демонстрационный и НЕ является частью UI.
- Метрики здесь намеренно простые (онлайн max/min/RMS) —
  при необходимости легко расширяются.
"""

from __future__ import annotations

import argparse
import json
import math
import time
from pathlib import Path
from typing import Any, Dict

# Allow direct execution (`python pneumo_solver_ui/tools/fast_kpi_worldroad.py`)
# in addition to package execution (`python -m pneumo_solver_ui.tools.fast_kpi_worldroad`).
if __name__ == "__main__" and (__package__ is None or __package__ == ""):
    import sys as _sys
    from pathlib import Path as _Path

    _ROOT = _Path(__file__).resolve().parents[2]
    if str(_ROOT) not in _sys.path:
        _sys.path.insert(0, str(_ROOT))
    __package__ = "pneumo_solver_ui.tools"

import numpy as np


def _load_json(path: Path) -> Any:
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def _first_present(mapping: Dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in mapping:
            return mapping[key]
    return None


def _build_time_grid(dt: float, t_end: float) -> np.ndarray:
    dt = float(dt)
    t_end = float(t_end)
    if dt <= 0.0:
        raise ValueError('dt must be > 0')
    n_steps = int(math.floor(max(0.0, t_end) / dt)) + 1
    return np.arange(n_steps, dtype=float) * dt


def _stroke_vector(ctx: Dict[str, Any], params: Dict[str, Any], key: str) -> np.ndarray:
    val = ctx.get(key)
    if val is not None:
        return np.asarray(val, dtype=float)
    return np.full(4, float(params.get('ход_штока', 0.250)), dtype=float)


def _smooth_flags(ctx: Dict[str, Any], params: Dict[str, Any]) -> Dict[str, Any]:
    smooth_info = ctx.get('smooth')
    if smooth_info is not None:
        return dict(smooth_info)
    return {
        'fully_smooth_mode': bool(params.get('fully_smooth_mode', params.get('полностью_гладкий_режим', False))),
        'smooth_contacts': bool(params.get('smooth_contacts', False)),
        'smooth_valves': bool(params.get('smooth_valves', False)),
    }


def _receiver_pressure_pa(obs: Dict[str, Any], node_index: Dict[str, Any]) -> float:
    p = obs.get('p')
    idx = node_index.get('Ресивер3')
    if p is not None and idx is not None:
        p_arr = np.asarray(p, dtype=float).reshape(-1)
        if 0 <= int(idx) < p_arr.size:
            return float(p_arr[int(idx)])
    val = _first_present(obs, 'давление_ресивер3_Па', 'pR3')
    return float(val) if val is not None else float('nan')


def _rod_state_vector(obs: Dict[str, Any], corner_order: list[str], key_array: str, key_prefix: str, fallback_prefix: str = '') -> np.ndarray:
    arr = obs.get(key_array)
    if arr is not None:
        return np.asarray(arr, dtype=float).reshape(-1)
    values = []
    for cname in corner_order[:4]:
        value = obs.get(f'{key_prefix}{cname}_м')
        if value is None and fallback_prefix:
            value = obs.get(f'{fallback_prefix}{cname}_м')
        values.append(float(value or 0.0))
    return np.asarray(values, dtype=float)


def _first_cross_time(t: float, prev_t: float, x: float, prev_x: float, level: float) -> float | None:
    """Линейная интерполяция времени первого пересечения уровня (внутри одного шага)."""
    if (prev_x < level) and (x >= level):
        dx = x - prev_x
        if abs(dx) < 1e-12:
            return float(t)
        w = (level - prev_x) / dx
        return float(prev_t + w * (t - prev_t))
    return None


def eval_fast_kpi_worldroad(model_module, params: Dict[str, Any], test: Dict[str, Any], dt: float, t_end: float) -> Dict[str, Any]:
    """Быстрый KPI-проход: RK2 + observe() на каждом шаге, без DataFrame."""

    ctx = model_module.simulate(params, test, dt=dt, t_end=t_end, compile_only=True)

    state = np.asarray(ctx['state0'], dtype=float)
    step = ctx['rk2_step']
    rhs = ctx['rhs']
    observe = ctx.get('observe', None)
    if not callable(observe):
        raise RuntimeError('compile_only context does not expose observe()')
    dt_eff = float(ctx.get('dt', dt))
    t_end_eff = float(ctx.get('t_end', t_end))
    time_grid = _build_time_grid(dt_eff, t_end_eff)

    corner_order = list(ctx.get('corner_order', ['ЛП', 'ПП', 'ЛЗ', 'ПЗ']))
    node_index = dict(ctx.get('node_index', {}))

    # Геометрия/ходы штоков из модели (точнее, чем пытаться угадать по params)
    stroke_C1 = _stroke_vector(ctx, params, 'stroke_C1_m')
    stroke_C2 = _stroke_vector(ctx, params, 'stroke_C2_m')

    # Диагностика «нулевой позы»: ускорения RHS на t=0
    dst0 = np.asarray(rhs(state, float(time_grid[0])), dtype=float)
    z_ddot0 = float(dst0[7])
    phi_ddot0 = float(dst0[8])
    theta_ddot0 = float(dst0[9])

    # KPI накопители
    pR3_max = -1e300
    roll_max_deg = 0.0
    pitch_max_deg = 0.0

    # RMS вертикального ускорения рамы (по RHS)
    acc2_sum = 0.0
    acc2_n = 0

    # Отрыв колёс
    any_lift_count = 0
    wheel_lift_count = 0
    F_tire_min = 1e300

    # Штоки
    rod_margin_C1_min = 1e300
    rod_margin_C2_min = 1e300
    rod_speed_C1_max = 0.0
    rod_speed_C2_max = 0.0

    # Время пересечения Pmid после t_step (как в оптимизаторе)
    Pmid = float(params.get('давление_Pmid_сброс', params.get('Pmid', 0.0)) or 0.0)
    t_step = float(test.get('t_step', 0.0) or 0.0)
    t_cross = None
    prev_pR3 = None
    prev_t = None
    prev_s1 = None
    prev_s2 = None

    # Проходим по сетке времени
    for k, t in enumerate(time_grid):
        obs = observe(state, float(t))

        # давления
        pR3 = _receiver_pressure_pa(obs, node_index)
        if np.isfinite(pR3):
            pR3_max = max(pR3_max, pR3)

        # пересечение Pmid
        if (Pmid > 0.0) and (float(t) >= t_step):
            if (prev_pR3 is not None) and (prev_t is not None) and (t_cross is None):
                tc = _first_cross_time(float(t), float(prev_t), pR3, float(prev_pR3), Pmid)
                if tc is not None:
                    t_cross = tc

        prev_pR3 = pR3
        prev_t = float(t)

        # крен/тангаж
        phi = float(_first_present(obs, 'phi', 'крен_phi_рад') or 0.0)
        theta = float(_first_present(obs, 'theta', 'тангаж_theta_рад') or 0.0)
        roll_max_deg = max(roll_max_deg, abs(phi) * 180.0 / math.pi)
        pitch_max_deg = max(pitch_max_deg, abs(theta) * 180.0 / math.pi)

        # RMS вертикального ускорения рамы
        az = float(np.asarray(rhs(state, float(t)), dtype=float)[7])
        if np.isfinite(az):
            acc2_sum += float(az * az)
            acc2_n += 1

        # силы в пятне контакта / отрыв колёс
        Ft_arr = np.asarray(_first_present(obs, 'F_tire', 'tire_Fz_N', 'нормальная_сила_шины'), dtype=float).reshape(-1)
        if Ft_arr.size >= 4:
            F_tire_min = min(F_tire_min, float(np.min(Ft_arr)))
            wia_arr = (Ft_arr[:4] <= 1.0).astype(int)
            any_lift_count += int(np.any(wia_arr > 0))
            wheel_lift_count += int(np.sum(wia_arr > 0))

        # штоки: позиции по Ц1/Ц2; скорость восстанавливаем по конечной разности,
        # если observe не даёт явные скорости.
        s1 = _rod_state_vector(obs, corner_order, 's_C1', 'положение_штока_Ц1_', 'положение_штока_')
        s2 = _rod_state_vector(obs, corner_order, 's_C2', 'положение_штока_Ц2_')

        rod_margin_C1_min = min(rod_margin_C1_min, float(np.min(np.minimum(s1, stroke_C1 - s1))))
        rod_margin_C2_min = min(rod_margin_C2_min, float(np.min(np.minimum(s2, stroke_C2 - s2))))

        if prev_s1 is not None:
            rod_speed_C1_max = max(rod_speed_C1_max, float(np.max(np.abs((s1 - prev_s1) / dt_eff))))
        if prev_s2 is not None:
            rod_speed_C2_max = max(rod_speed_C2_max, float(np.max(np.abs((s2 - prev_s2) / dt_eff))))

        prev_s1 = s1
        prev_s2 = s2

        # следующий шаг
        if k < (len(time_grid) - 1):
            state = step(state, float(t), float(dt_eff))

    n_obs = max(1, len(time_grid))
    acc_rms = math.sqrt(acc2_sum / max(1, acc2_n))

    return {
        'dt': float(dt_eff),
        't_end': float(t_end_eff),

        # Нулевая поза (быстрый sanity-check)
        'z_ddot0_mps2': float(z_ddot0),
        'phi_ddot0_rps2': float(phi_ddot0),
        'theta_ddot0_rps2': float(theta_ddot0),

        # Давления
        'pR3_max_bar_abs': float(pR3_max / 1e5) if np.isfinite(pR3_max) else float('nan'),
        't_cross_Pmid_s': float(t_cross) if t_cross is not None else float('nan'),

        # Крен/тангаж
        'roll_max_deg': float(roll_max_deg),
        'pitch_max_deg': float(pitch_max_deg),

        # Вертикальное ускорение рамы
        'acc_z_rms_mps2_rhs': float(acc_rms),

        # Отрыв колёс
        'lift_frac_any': float(any_lift_count / n_obs),
        'lift_frac_mean': float(wheel_lift_count / (4 * n_obs)),
        'F_tire_min_N': float(F_tire_min) if np.isfinite(F_tire_min) else float('nan'),

        # Штоки
        'rod_margin_C1_min_m': float(rod_margin_C1_min),
        'rod_margin_C2_min_m': float(rod_margin_C2_min),
        'rod_speed_C1_max_mps': float(rod_speed_C1_max),
        'rod_speed_C2_max_mps': float(rod_speed_C2_max),

        # Контекст
        'wheel_coord_mode': str(ctx.get('wheel_coord_mode', '')),
        'smooth': _smooth_flags(ctx, params),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--test-index', type=int, default=0)
    ap.add_argument('--fully-smooth', action='store_true')
    ap.add_argument('--dt', type=float, default=None)
    ap.add_argument('--t-end', type=float, default=None)
    ap.add_argument('--json-out', type=str, default='')
    args = ap.parse_args()

    root = Path(__file__).resolve().parents[1]
    base_json = root / 'default_base.json'
    suite_json = root / 'default_suite.json'
    from pneumo_solver_ui import model_pneumo_v9_mech_doublewishbone_worldroad as m

    params = _load_json(base_json)
    suite = _load_json(suite_json)
    if not isinstance(suite, list) or len(suite) == 0:
        raise RuntimeError('default_suite.json пустой или некорректен')

    ti = int(args.test_index)
    ti = max(0, min(ti, len(suite) - 1))
    test = dict(suite[ti])

    # overrides
    if args.fully_smooth:
        params['fully_smooth_mode'] = True
    dt = float(args.dt) if args.dt is not None else float(test.get('dt', 1e-3))
    t_end = float(args.t_end) if args.t_end is not None else float(test.get('t_end', 3.0))

    t0 = time.time()
    kpi = eval_fast_kpi_worldroad(m, params, test, dt=dt, t_end=t_end)
    kpi['wall_time_s'] = float(time.time() - t0)

    print(json.dumps(kpi, ensure_ascii=False, indent=2, sort_keys=True))

    if args.json_out:
        out_path = Path(args.json_out).resolve()
        out_path.write_text(json.dumps(kpi, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
