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
import importlib.util
import json
import math
import time
from pathlib import Path
from typing import Any, Dict

import numpy as np


def _load_json(path: Path) -> Any:
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


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
    time_grid = np.asarray(ctx['time'], dtype=float)

    corner_order = list(ctx.get('corner_order', ['ЛП', 'ПП', 'ЛЗ', 'ПЗ']))

    # Геометрия/ходы штоков из модели (точнее, чем пытаться угадать по params)
    stroke_C1 = np.asarray(ctx.get('stroke_C1_m', np.full(4, float(params.get('ход_штока', 0.250)))), dtype=float)
    stroke_C2 = np.asarray(ctx.get('stroke_C2_m', np.full(4, float(params.get('ход_штока', 0.250)))), dtype=float)

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

    # Проходим по сетке времени
    for k, t in enumerate(time_grid):
        if observe is not None:
            obs = observe(state, float(t))

            # давления
            pR3 = float(obs.get('давление_ресивер3_Па', float('nan')))
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
            phi = float(obs.get('крен_phi_рад', 0.0))
            theta = float(obs.get('тангаж_theta_рад', 0.0))
            roll_max_deg = max(roll_max_deg, abs(phi) * 180.0 / math.pi)
            pitch_max_deg = max(pitch_max_deg, abs(theta) * 180.0 / math.pi)

            # RMS вертикального ускорения
            az = float(obs.get('ускорение_рамы_z_м_с2_rhs', 0.0))
            if np.isfinite(az):
                acc2_sum += float(az * az)
                acc2_n += 1

            # силы в пятне контакта
            Ft = obs.get('F_tire', None)
            wia = obs.get('wheel_in_air', None)
            if Ft is not None:
                Ft_arr = np.asarray(Ft, dtype=float).reshape(-1)
                if Ft_arr.size >= 4:
                    F_tire_min = min(F_tire_min, float(np.min(Ft_arr)))
            if wia is not None:
                wia_arr = np.asarray(wia, dtype=int).reshape(-1)
                if wia_arr.size >= 4:
                    any_lift_count += int(np.any(wia_arr > 0))
                    wheel_lift_count += int(np.sum(wia_arr > 0))

            # штоки: позиции/скорости (по Ц1 и Ц2)
            s1 = []
            s2 = []
            v1 = []
            v2 = []
            for i_c, cname in enumerate(corner_order[:4]):
                s1.append(float(obs.get(f'положение_штока_Ц1_{cname}_м', obs.get(f'положение_штока_{cname}_м', 0.0))))
                s2.append(float(obs.get(f'положение_штока_Ц2_{cname}_м', 0.0)))
                v1.append(float(obs.get(f'скорость_штока_Ц1_{cname}_м_с', obs.get(f'скорость_штока_{cname}_м_с', 0.0))))
                v2.append(float(obs.get(f'скорость_штока_Ц2_{cname}_м_с', 0.0)))

            s1 = np.asarray(s1, dtype=float)
            s2 = np.asarray(s2, dtype=float)
            v1 = np.asarray(v1, dtype=float)
            v2 = np.asarray(v2, dtype=float)

            # margin = min(s, stroke-s)
            rod_margin_C1_min = min(rod_margin_C1_min, float(np.min(np.minimum(s1, stroke_C1 - s1))))
            rod_margin_C2_min = min(rod_margin_C2_min, float(np.min(np.minimum(s2, stroke_C2 - s2))))

            rod_speed_C1_max = max(rod_speed_C1_max, float(np.max(np.abs(v1))))
            rod_speed_C2_max = max(rod_speed_C2_max, float(np.max(np.abs(v2))))

        # следующий шаг
        if k < (len(time_grid) - 1):
            state = step(state, float(t), float(dt))

    n_obs = max(1, len(time_grid))
    acc_rms = math.sqrt(acc2_sum / max(1, acc2_n))

    return {
        'dt': float(dt),
        't_end': float(t_end),

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
        'smooth': ctx.get('smooth', {}),
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
    model_path = root / 'model_pneumo_v9_mech_doublewishbone_worldroad.py'
    base_json = root / 'default_base.json'
    suite_json = root / 'default_suite.json'

    # Load model via importlib (Windows-safe)
    spec = importlib.util.spec_from_file_location('pneumo_model_worldroad', str(model_path))
    if spec is None or spec.loader is None:
        raise RuntimeError(f'Не удалось загрузить модель: {model_path}')
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)  # type: ignore

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
