# -*- coding: utf-8 -*-
"""smoothing_schedule_v1.py

Генератор *continuation/homotopy* расписания для сглаживающих параметров модели
`model_pneumo_v8_energy_audit_vacuum_patched_smooth_all.py`.

Зачем:
- В калибровке по NPZ мы решаем много-параметрическую нелинейную задачу.
- Реальная модель содержит жёсткие пороги/clip/max/контакты/клапана.
- Даже после "smooth_all" некоторые переходы остаются крутыми.

Инженерный приём: решить последовательность задач "от простой к сложной".
Практически: начинаем с более *гладкой* версии динамики (больше eps, меньше k),
подгоняем параметры, затем постепенно уменьшаем eps и увеличиваем k.

Выход:
- JSON-массив объектов overrides, которые надо MERGE'ить в base_params перед fit.

Пример:
  python smoothing_schedule_v1.py --out_json smooth_schedule.json --n_steps 3 \
      --k_start 20 --k_end 80 --eps_mult_start 8 --eps_mult_end 1

"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List


DEFAULTS = {
    # То, что в модели задано по умолчанию
    "k_smooth_valves": 80.0,
    "smooth_eps_pos_m": 1e-4,
    "smooth_eps_vel_mps": 1e-3,
    "smooth_eps_mass_kg": 1e-8,
    "smooth_eps_vol_m3": 1e-12,
}


def _save_json(obj: Any, p: Path) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def _geom_series(start: float, end: float, n: int) -> List[float]:
    """Геометрическая прогрессия (включая start и end)."""
    n = int(n)
    if n <= 1:
        return [float(end)]
    start = float(start)
    end = float(end)
    if start <= 0 or end <= 0:
        # fallback: линейная интерполяция
        return [float(start + (end - start) * (i / (n - 1))) for i in range(n)]
    r = (end / start) ** (1.0 / (n - 1))
    return [float(start * (r ** i)) for i in range(n)]


def make_smoothing_schedule(
    n_steps: int = 3,
    *,
    k_start: float = 20.0,
    k_end: float = 80.0,
    eps_mult_start: float = 8.0,
    eps_mult_end: float = 1.0,
    enable_all_flags: bool = True,
    labels: bool = True,
) -> List[Dict[str, Any]]:
    """Собрать расписание overrides.

    Параметры:
      n_steps          : число шагов (обычно 2..4)
      k_start/k_end    : диапазон для k_smooth_valves (меньше => более гладко)
      eps_mult_*       : множитель к дефолтным eps (больше => более гладко)

    Возвращает:
      list[dict] — overrides для base_params.
    """
    n_steps = max(1, int(n_steps))

    ks = _geom_series(float(k_start), float(k_end), n_steps)
    eps_mults = _geom_series(float(eps_mult_start), float(eps_mult_end), n_steps)

    sched: List[Dict[str, Any]] = []
    for i in range(n_steps):
        mult = float(eps_mults[i])
        step: Dict[str, Any] = {
            "k_smooth_valves": float(ks[i]),
            "smooth_eps_pos_m": float(DEFAULTS["smooth_eps_pos_m"] * mult),
            "smooth_eps_vel_mps": float(DEFAULTS["smooth_eps_vel_mps"] * mult),
            "smooth_eps_mass_kg": float(DEFAULTS["smooth_eps_mass_kg"] * mult),
            "smooth_eps_vol_m3": float(DEFAULTS["smooth_eps_vol_m3"] * mult),
        }

        if enable_all_flags:
            # Явно включаем, чтобы не зависеть от содержимого base_json
            step.update({
                "smooth_dynamics": True,
                "smooth_mechanics": True,
                "smooth_stroke": True,
                "smooth_contacts": True,
                "smooth_spring": True,
                "smooth_pressure_floor": True,
                "smooth_valves": True,
            })

        if labels:
            step["label"] = f"smooth{i+1}_k{step['k_smooth_valves']:.0f}_mult{mult:g}"
            step["stage"] = int(i)

        sched.append(step)

    return sched


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out_json", required=True)
    ap.add_argument("--n_steps", type=int, default=3)
    ap.add_argument("--k_start", type=float, default=20.0)
    ap.add_argument("--k_end", type=float, default=80.0)
    ap.add_argument("--eps_mult_start", type=float, default=8.0)
    ap.add_argument("--eps_mult_end", type=float, default=1.0)
    ap.add_argument("--disable_flags", action="store_true", help="Не добавлять smooth_* bool флаги (только eps/k)")
    ap.add_argument("--no_labels", action="store_true")

    args = ap.parse_args()

    sched = make_smoothing_schedule(
        n_steps=int(args.n_steps),
        k_start=float(args.k_start),
        k_end=float(args.k_end),
        eps_mult_start=float(args.eps_mult_start),
        eps_mult_end=float(args.eps_mult_end),
        enable_all_flags=(not bool(args.disable_flags)),
        labels=(not bool(args.no_labels)),
    )

    _save_json(sched, Path(args.out_json))
    print(f"Wrote smoothing schedule: {args.out_json} (steps={len(sched)})")


if __name__ == "__main__":
    main()
