# -*- coding: utf-8 -*-
"""Smoke-check: автотюн точности интегрирования (внутренние подшаги).

Этот чек — *быстрая* автономная проверка того, что параметр
`макс_шаг_интегрирования_с` действительно влияет на точность/сходимость.

Почему это важно:
* В проекте используется RK2/Heun на внешнем шаге логгирования `dt`, но
  внутри шага применяется разбиение на подшаги `dt_int` для жёсткой пневматики.
* Если из-за регрессии `dt_int_max` перестанет применяться, оптимизатор/UX
  получат «псевдо-точность»: параметры крутятся, а интегратор фактически грубый.

Идея проверки:
* выполняем 3 коротких прогона одной и той же сцены worldroad (гладкий bump),
  меняя только `макс_шаг_интегрирования_с` (coarse/mid/fine);
* берём "fine" как условный эталон;
* проверяем, что mid ближе к fine, чем coarse, и улучшение заметное.

Чек используется:
* из `tools/autoselfcheck.py` (можно отключить env-переменной);
* как参考 логики для pytest-теста `tests/test_integrator_autotune_accuracy.py`.

Запуск вручную:
    python -m pneumo_solver_ui.tools.integrator_autotune_smoke_check
"""

from __future__ import annotations

import argparse
from typing import Any, Dict, Optional
import sys
from pathlib import Path

import numpy as np


if __name__ == "__main__" and (__package__ is None or __package__ == ""):
    _ROOT = Path(__file__).resolve().parents[2]
    if str(_ROOT) not in sys.path:
        sys.path.insert(0, str(_ROOT))
    __package__ = "pneumo_solver_ui.tools"


def _smooth_bump(t: float, t0: float = 0.01, dur: float = 0.02, A: float = 0.02) -> float:
    """Гладкий подъём дороги: 0 -> A за dur, далее держим A."""
    if t <= t0:
        return 0.0
    if t >= t0 + dur:
        return float(A)
    x = (t - t0) / dur
    return float(A) * 0.5 * (1.0 - float(np.cos(np.pi * x)))


def _stats_from_df(df):
    '''Извлекает диагностические метрики подшагов, если модель их логирует.

    Возвращает None, если колонок нет или данные повреждены.
    '''
    col_n = 'интегратор_подшаги_N'
    col_hmin = 'интегратор_подшаг_мин_с'
    col_hmax = 'интегратор_подшаг_макс_с'
    col_hmean = 'интегратор_подшаг_средн_с'
    col_hmean_legacy = 'интегратор_подшаг_средний_с'
    if col_n not in df.columns:
        return None
    try:
        n = df[col_n].to_numpy(dtype=float)
        mask_n = (n > 0) & np.isfinite(n)
        n_mean = float(np.mean(n[mask_n])) if np.any(mask_n) else float('nan')

        def _nan_stats(cols, fn):
            if isinstance(cols, str):
                cols = (cols,)
            for col in cols:
                if col not in df.columns:
                    continue
                a = df[col].to_numpy(dtype=float)
                m = np.isfinite(a)
                if not np.any(m):
                    return float('nan')
                return float(fn(a[m]))
            return float('nan')

        h_min = _nan_stats(col_hmin, np.min)
        h_max = _nan_stats(col_hmax, np.max)
        h_mean = _nan_stats((col_hmean, col_hmean_legacy), np.mean)

        return {'n_mean': n_mean, 'h_min': h_min, 'h_max': h_max, 'h_mean': h_mean}
    except Exception:
        return None


def run_check(
    *,
    dt: float = 2e-3,
    t_end: float = 0.05,
    fine: float = 7.5e-5,
    mid: float = 1.5e-4,
    coarse: float = 3.0e-4,
    col: str = "давление_ресивер2_Па",
    ratio_min: float = 2.0,
    check_err_control: bool = False,
    ratio_err_min: float = 1.8,
    err_rtol: float | None = None,
    err_atol: float | None = None,
    err_mass_rtol_scale_factor: float | None = None,
    err_group_weight_mass: float | None = None,
) -> Dict[str, Any]:
    """Выполняет проверку и возвращает dict (ok, metrics...)."""
    from pneumo_solver_ui import model_pneumo_v9_mech_doublewishbone_worldroad as m

    scenario = {
        "road_func": lambda t: np.array([_smooth_bump(t), 0.0, 0.0, 0.0], dtype=float),
        "ax_func": lambda t: 0.0,
        "ay_func": lambda t: 0.0,
    }

    base_params: Dict[str, Any] = {
        # держим самопроверку включённой, чтобы ловить регрессии механики
        "mechanics_selfcheck": True,
        "mechanics_selfcheck_tol_m": 1e-6,
        # не требуем строгого преднатяга (может давать дискретности)
        "пружина_преднатяг_на_отбое_строго": False,
    }

    def _run(dt_int_max: float, *, err_control: bool = False):
        params = dict(base_params)
        params["макс_шаг_интегрирования_с"] = float(dt_int_max)
        if bool(err_control):
            # step-doubling контроль локальной ошибки (Matematika6455)
            params["интегратор_контроль_локальной_ошибки"] = True
            if err_rtol is not None:
                params["интегратор_rtol"] = float(err_rtol)
            if err_atol is not None:
                params["интегратор_atol"] = float(err_atol)
            if err_mass_rtol_scale_factor is not None:
                params["интегратор_mass_rtol_scale_factor"] = float(err_mass_rtol_scale_factor)
            if err_group_weight_mass is not None:
                params["интегратор_err_group_weight_mass"] = float(err_group_weight_mass)
        df_main, *_, df_atm = m.simulate(params, scenario, dt=float(dt), t_end=float(t_end), record_full=False)
        return df_main, df_atm

    df_fine, _ = _run(float(fine))
    df_mid, _ = _run(float(mid))
    df_coarse, _ = _run(float(coarse))
    df_coarse_err, df_coarse_err_atm = _run(float(coarse), err_control=True) if bool(check_err_control) else (None, None)

    # одинаковая сетка логирования
    if not (len(df_fine) == len(df_mid) == len(df_coarse) and (df_coarse_err is None or len(df_coarse_err) == len(df_fine))):
        return {
            "ok": False,
            "reason": "grid_length_mismatch",
            "len": {"fine": len(df_fine), "mid": len(df_mid), "coarse": len(df_coarse)},
        }

    for df in (df_fine, df_mid, df_coarse):
        if col not in df.columns:
            return {"ok": False, "reason": "missing_column", "col": col, "columns": list(df.columns)}
        arr = df[col].to_numpy()
        if not np.all(np.isfinite(arr)):
            return {"ok": False, "reason": "non_finite_values", "col": col}

    y_fine = df_fine[col].to_numpy(dtype=float)
    e_coarse = float(np.max(np.abs(df_coarse[col].to_numpy(dtype=float) - y_fine)))
    e_mid = float(np.max(np.abs(df_mid[col].to_numpy(dtype=float) - y_fine)))
    ratio = float(e_coarse / (e_mid + 1e-12))

    e_coarse_err = None
    ratio_err = None
    if df_coarse_err is not None:
        if col not in df_coarse_err.columns:
            return {"ok": False, "reason": "missing_column", "col": col, "columns": list(df_coarse_err.columns)}
        arr = df_coarse_err[col].to_numpy(dtype=float)
        if not np.all(np.isfinite(arr)):
            return {"ok": False, "reason": "non_finite_values", "col": col, "mode": "err_control"}
        e_coarse_err = float(np.max(np.abs(arr - y_fine)))
        ratio_err = float(e_coarse / (e_coarse_err + 1e-12))

    # Дополнительная проверка: сколько подшагов реально сделал интегратор и какие h использовал.
    diag = None
    s_fine = _stats_from_df(df_fine)
    s_mid = _stats_from_df(df_mid)
    s_coarse = _stats_from_df(df_coarse)
    s_coarse_err = _stats_from_df(df_coarse_err) if df_coarse_err is not None else None
    if any(s is not None for s in (s_fine, s_mid, s_coarse)):
        diag = {}
        if s_fine is not None:
            diag['fine'] = s_fine
        if s_mid is not None:
            diag['mid'] = s_mid
        if s_coarse is not None:
            diag['coarse'] = s_coarse
        if s_coarse_err is not None:
            diag['coarse_err_control'] = s_coarse_err

        # Базовая sanity-проверка: фактически использованный максимальный подшаг не должен превышать dt_int_max.
        try:
            if s_fine is not None and np.isfinite(s_fine.get('h_max', np.nan)):
                assert s_fine['h_max'] <= float(fine) * (1.0 + 1e-9) + 1e-15
            if s_mid is not None and np.isfinite(s_mid.get('h_max', np.nan)):
                assert s_mid['h_max'] <= float(mid) * (1.0 + 1e-9) + 1e-15
            if s_coarse is not None and np.isfinite(s_coarse.get('h_max', np.nan)):
                assert s_coarse['h_max'] <= float(coarse) * (1.0 + 1e-9) + 1e-15
            if s_coarse_err is not None and np.isfinite(s_coarse_err.get('h_max', np.nan)):
                assert s_coarse_err['h_max'] <= float(coarse) * (1.0 + 1e-9) + 1e-15
        except AssertionError:
            diag['warning'] = 'h_max_exceeded_dt_int_max'

    ok = (e_mid < e_coarse) and (ratio > float(ratio_min))
    if df_coarse_err is not None:
        ok = bool(ok) and (e_coarse_err < e_coarse) and (ratio_err > float(ratio_err_min))

    err_diag: Dict[str, Any] | None = None
    if df_coarse_err_atm is not None and len(df_coarse_err_atm) > 0:
        row = df_coarse_err_atm.iloc[0]
        err_diag = {
            "err_control_total_rejects": int(row.get("интегратор_total_rejects", 0)),
            "err_control_total_substeps": int(row.get("интегратор_total_substeps", 0)),
            "err_control_dominant_group": str(row.get("интегратор_err_reject_dominant_group", "none")),
            "err_control_weighted_dominant_group": str(row.get("интегратор_err_reject_weighted_dominant_group", "none")),
            "err_control_mass_rtol_scale_factor": float(row.get("интегратор_mass_rtol_scale_factor", float("nan"))),
            "err_control_err_group_weight_mass": float(row.get("интегратор_err_group_weight_mass", float("nan"))),
            "err_control_rtol": float(row.get("интегратор_rtol", float("nan"))),
            "err_control_atol": float(row.get("интегратор_atol", float("nan"))),
        }

    return {
        "ok": bool(ok),
        "col": col,
        "dt": float(dt),
        "t_end": float(t_end),
        "fine": float(fine),
        "mid": float(mid),
        "coarse": float(coarse),
        "e_mid": e_mid,
        "e_coarse": e_coarse,
        "ratio": ratio,
        "e_coarse_err_control": e_coarse_err,
        "ratio_err_control": ratio_err,
        "integrator_stats": diag,
        "ratio_min": float(ratio_min),
        "ratio_err_min": float(ratio_err_min),
        "err_rtol_override": None if err_rtol is None else float(err_rtol),
        "err_atol_override": None if err_atol is None else float(err_atol),
        "err_mass_rtol_scale_factor_override": None if err_mass_rtol_scale_factor is None else float(err_mass_rtol_scale_factor),
        "err_group_weight_mass_override": None if err_group_weight_mass is None else float(err_group_weight_mass),
        **(err_diag or {}),
    }


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Smoke-check: integrator autotune accuracy")
    ap.add_argument("--dt", type=float, default=2e-3)
    ap.add_argument("--t_end", type=float, default=0.05)
    ap.add_argument("--fine", type=float, default=7.5e-5)
    ap.add_argument("--mid", type=float, default=1.5e-4)
    ap.add_argument("--coarse", type=float, default=3.0e-4)
    ap.add_argument("--col", type=str, default="давление_ресивер2_Па")
    ap.add_argument("--ratio_min", type=float, default=2.0)
    ap.add_argument(
        "--check_err_control",
        action="store_true",
        help="Также проверить режим контроля локальной ошибки (step-doubling, Matematika6455).",
    )
    ap.add_argument("--ratio_err_min", type=float, default=1.8)
    ap.add_argument("--err_rtol", type=float, default=None)
    ap.add_argument("--err_atol", type=float, default=None)
    ap.add_argument("--err_mass_rtol_scale_factor", type=float, default=None)
    ap.add_argument("--err_group_weight_mass", type=float, default=None)

    ns = ap.parse_args(argv)
    res = run_check(
        dt=ns.dt,
        t_end=ns.t_end,
        fine=ns.fine,
        mid=ns.mid,
        coarse=ns.coarse,
        col=ns.col,
        ratio_min=ns.ratio_min,
        check_err_control=bool(ns.check_err_control),
        ratio_err_min=ns.ratio_err_min,
        err_rtol=ns.err_rtol,
        err_atol=ns.err_atol,
        err_mass_rtol_scale_factor=ns.err_mass_rtol_scale_factor,
        err_group_weight_mass=ns.err_group_weight_mass,
    )

    if bool(res.get("ok")):
        print(
            "PASS integrator_autotune: "
            f"e_mid={res.get('e_mid'):.3g}, e_coarse={res.get('e_coarse'):.3g}, ratio={res.get('ratio'):.3g}"
        )
        return 0
    print(f"FAIL integrator_autotune: {res}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
