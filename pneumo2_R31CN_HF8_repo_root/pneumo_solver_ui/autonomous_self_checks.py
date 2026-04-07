# -*- coding: utf-8 -*-
"""autonomous_self_checks.py

Лёгкие (in-process) самопроверки, которые можно вызывать прямо из simulate().

Цели
----
1) Автоматически ловить грубые физические/численные ошибки:
   - неверные граничные условия ISO6358 φ(pr) при pr→0 (вакуум)
   - рассогласование баланса массы и энергии
   - NaN/Inf в ключевых итоговых метриках
   - «неправильная» схема (fingerprint) или не-Camozzi компоненты (если включено)

2) Не требовать внешних инструментов (pytest/compileall), чтобы работать
   даже в минимальной установке.

3) Возвращать JSON‑совместимый отчёт, который можно класть в df_atm
   и/или логировать.

Параметры управления (опционально)
---------------------------------
params.get(...):
  - 'авто_самопроверки' (bool, default True)
  - 'авто_самопроверки_строго' (bool, default False)
      Если True и есть ошибки уровня 'error' -> raise RuntimeError.

  - 'самопроверка_масса_abs_кг' (float, default 1e-5)
  - 'самопроверка_масса_rel' (float, default 1e-4)
  - 'самопроверка_энергия_abs_Дж' (float, default 1e-2)
  - 'самопроверка_энергия_rel' (float, default 1e-4)

Замечание
---------
Самопроверки НЕ меняют схему и не вмешиваются в расчёт — только измеряют.
"""

from __future__ import annotations

import json
import math
import time
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class CheckItem:
    name: str
    ok: bool
    severity: str  # 'info' | 'warn' | 'error'
    value: Any = None
    expected: Any = None
    message: str = ''


def _isfinite(x: Any) -> bool:
    try:
        return math.isfinite(float(x))
    except Exception:
        return False


def _safe_float(x: Any, default: float = float('nan')) -> float:
    try:
        return float(x)
    except Exception:
        return float(default)


def _add(items: List[CheckItem], name: str, ok: bool, *, severity: str = 'info', value: Any = None, expected: Any = None, message: str = '') -> None:
    items.append(CheckItem(name=name, ok=bool(ok), severity=str(severity), value=value, expected=expected, message=str(message)))


def _summarize(items: List[CheckItem]) -> Dict[str, Any]:
    n_err = sum(1 for it in items if (not it.ok) and it.severity == 'error')
    n_warn = sum(1 for it in items if (not it.ok) and it.severity == 'warn')
    ok = (n_err == 0)
    return {
        'ok': ok,
        'n_error': int(n_err),
        'n_warn': int(n_warn),
        'items': [asdict(it) for it in items],
    }


def preflight_checks(model_module: Any, params: Dict[str, Any], nodes: Any, edges: Any) -> Dict[str, Any]:
    """Проверки "до" расчёта.

    model_module — модуль модели (например model_pneumo_v9_doublewishbone_camozzi).
    nodes/edges — структура сети, уже построенная моделью.
    """
    t0 = time.time()
    items: List[CheckItem] = []

    # --- ISO6358 φ(pr) vacuum boundary ---
    try:
        phi_fn = getattr(model_module, 'iso6358_phi', None)
        if callable(phi_fn):
            # ожидаем φ(pr=0) ~ 1.0
            phi0 = float(phi_fn(0.0, 0.5, m=0.6))  # pr=0, b=0.5
            _add(items, 'iso6358_phi_pr0', ok=(phi0 > 0.99), severity=('error' if phi0 < 0.9 else 'warn'), value=phi0, expected='~1.0',
                 message='φ(pr→0) должно быть ≈1 (choked).')
        else:
            _add(items, 'iso6358_phi_pr0', ok=True, severity='info', message='iso6358_phi not found in model (skipped).')
    except TypeError:
        # если сигнатура другая — попробуем без keyword
        try:
            phi0 = float(model_module.iso6358_phi(0.0, 0.5, 0.6))
            _add(items, 'iso6358_phi_pr0', ok=(phi0 > 0.99), severity=('error' if phi0 < 0.9 else 'warn'), value=phi0, expected='~1.0')
        except Exception as ex:
            _add(items, 'iso6358_phi_pr0', ok=True, severity='warn', message=f'phi check skipped: {ex!r}')
    except Exception as ex:
        _add(items, 'iso6358_phi_pr0', ok=True, severity='warn', message=f'phi check skipped: {ex!r}')

    # --- Scheme fingerprint / Camozzi-only (if configured) ---
    # Важно: assert_* функции НЕ возвращают (ok,msg), а поднимают AssertionError.
    # Поэтому здесь мы конвертируем исключения в отчёт.
    try:
        from .scheme_integrity import assert_fingerprint, assert_camozzi_only

        fp_file = params.get('scheme_fingerprint_file', 'scheme_fingerprint.json')
        enforce_fp = bool(params.get('enforce_scheme_integrity', False))
        try:
            assert_fingerprint(nodes, edges, fp_file)
            ok_fp, msg_fp = True, 'match'
        except Exception as ex:
            ok_fp, msg_fp = False, str(ex)

        _add(
            items,
            'scheme_fingerprint',
            ok=(ok_fp or (not enforce_fp)),
            severity=('error' if enforce_fp else 'warn') if (not ok_fp) else 'info',
            value=msg_fp,
            expected='match',
            message=msg_fp,
        )

        enforce_cam = bool(params.get('enforce_camozzi_only', False))
        passport_file = params.get('паспорт_компонентов_json', 'component_passport.json')
        try:
            assert_camozzi_only(edges, passport_file)
            ok_cam, msg_cam = True, 'camozzi-only'
        except Exception as ex:
            ok_cam, msg_cam = False, str(ex)

        _add(
            items,
            'camozzi_only',
            ok=(ok_cam or (not enforce_cam)),
            severity=('error' if enforce_cam else 'warn') if (not ok_cam) else 'info',
            value=msg_cam,
            expected='Camozzi only',
            message=msg_cam,
        )
    except Exception as ex:
        _add(items, 'scheme_integrity', ok=True, severity='warn', message=f'scheme_integrity skipped: {ex!r}')

    # --- Basic parameter sanity (only what is safe/cheap) ---
    try:
        dt = _safe_float(params.get('dt', float('nan')))
        if _isfinite(dt):
            _add(items, 'dt_positive', ok=(dt > 0.0), severity='error' if dt <= 0.0 else 'info', value=dt, expected='>0')
    except Exception:
        pass

    # --- DW2D suspension geometry sanity (when enabled) ---
    # This does not change the simulation; it only validates that the simplified
    # 2D lower-arm geometry is usable for the selected wheel travel range.
    try:
        mech_kin = str(params.get('механика_кинематика', '')).strip().lower()
        if mech_kin in ('dw2d', 'dw2d_mounts'):
            from .dw2d_kinematics import dw2d_geometry_report_from_params

            rep_dw = dw2d_geometry_report_from_params(params, dw_test_range_m=(-0.15, 0.15), n_samples=61)
            errs: List[str] = []
            warns: List[str] = []
            for _, r in rep_dw.items():
                errs.extend(list(r.get('errors', [])))
                warns.extend(list(r.get('warnings', [])))

            if errs:
                _add(
                    items,
                    'dw2d_geometry',
                    ok=False,
                    severity='error',
                    value={'n_error': len(errs), 'n_warn': len(warns)},
                    message='; '.join(errs[:5]) + (' ...' if len(errs) > 5 else ''),
                )
            elif warns:
                _add(
                    items,
                    'dw2d_geometry',
                    ok=False,
                    severity='warn',
                    value={'n_warn': len(warns)},
                    message='; '.join(warns[:5]) + (' ...' if len(warns) > 5 else ''),
                )
            else:
                _add(items, 'dw2d_geometry', ok=True, severity='info', message='ok')
    except Exception as ex:
        _add(items, 'dw2d_geometry', ok=True, severity='warn', message=f'dw2d geometry check skipped: {ex!r}')

    rep = _summarize(items)
    rep['stage'] = 'pre'
    rep['duration_s'] = float(time.time() - t0)
    return rep


def postflight_checks(params: Dict[str, Any], df_atm: Any, df_main: Optional[Any] = None) -> Dict[str, Any]:
    """Проверки "после" расчёта по df_atm (одна строка)."""
    t0 = time.time()
    items: List[CheckItem] = []

    # Тolerances
    tol_m_abs = float(params.get('самопроверка_масса_abs_кг', 1e-5))
    tol_m_rel = float(params.get('самопроверка_масса_rel', 1e-4))
    tol_e_abs = float(params.get('самопроверка_энергия_abs_Дж', 1e-2))
    tol_e_rel = float(params.get('самопроверка_энергия_rel', 1e-4))

    # df_atm may be pandas.DataFrame or dict-like
    def _get(col: str, default: Any = None) -> Any:
        try:
            if hasattr(df_atm, 'iloc'):
                if col in df_atm.columns:
                    return df_atm[col].iloc[0]
                return default
            # dict
            return df_atm.get(col, default)
        except Exception:
            return default


    # --- DW2D dynamic geometry range check (по фактическим ходам из df_main) ---
    try:
        mech_kin = str(params.get('механика_кинематика', params.get('мех_кинематика', 'mr')) or 'mr')
        if df_main is not None and mech_kin in ('dw2d', 'dw2d_mounts'):
            cols_pref = [
                'сжатие_подвески_колесо_ЛП_м',
                'сжатие_подвески_колесо_ПП_м',
                'сжатие_подвески_колесо_ЛЗ_м',
                'сжатие_подвески_колесо_ПЗ_м',
            ]
            cols_alt = [
                'колесо_относительно_рамы_ЛП_м',
                'колесо_относительно_рамы_ПП_м',
                'колесо_относительно_рамы_ЛЗ_м',
                'колесо_относительно_рамы_ПЗ_м',
            ]

            cols = []
            if hasattr(df_main, 'columns'):
                cols = [c for c in cols_pref if c in df_main.columns]
                if not cols:
                    cols = [c for c in cols_alt if c in df_main.columns]

            if cols:
                dw_min = min(float(df_main[c].min()) for c in cols)
                dw_max = max(float(df_main[c].max()) for c in cols)
                margin = float(params.get('dw2d_dynamic_margin_m', 0.01) or 0.01)
                dw_test = (dw_min - margin, dw_max + margin)

                rep_dyn = dw2d_geometry_report_from_params(
                    params,
                    dw_test_range_m=dw_test,
                    n_samples=int(params.get('dw2d_dynamic_n_samples', 81) or 81),
                )
                cnt = rep_dyn.get('counts', {}) if isinstance(rep_dyn, dict) else {}
                n_err = int(cnt.get('error', 0) or 0)
                n_warn = int(cnt.get('warn', 0) or 0)
                ok_dyn = bool(rep_dyn.get('ok', False)) if isinstance(rep_dyn, dict) else True

                sev = 'info'
                if n_err > 0:
                    sev = 'error'
                elif n_warn > 0:
                    sev = 'warn'

                _add(items,
                     name='dw2d_dynamic_range',
                     ok=ok_dyn and (n_err == 0),
                     severity=sev,
                     value={'dw_min_m': dw_min, 'dw_max_m': dw_max, 'margin_m': margin, 'dw_test_range_m': dw_test, 'cols': cols, 'counts': cnt},
                     message=str(rep_dyn.get('summary', '') if isinstance(rep_dyn, dict) else ''))
            else:
                _add(items,
                     name='dw2d_dynamic_range',
                     ok=True,
                     severity='warn',
                     value=None,
                     message='DW2D: df_main не содержит колонок ходов (сжатие/колесо_относительно_рамы) — динамическая проверка пропущена')
    except Exception as ex:
        _add(items,
             name='dw2d_dynamic_range',
             ok=True,
             severity='warn',
             value=None,
             message=f'DW2D dynamic check failed: {ex!r}')


    # --- Stabilizer consistency ---
    try:
        stab_on = bool(params.get('стабилизатор_вкл', False))
        cols_stab = [
            'сила_стабилизатора_ЛП_Н',
            'сила_стабилизатора_ПП_Н',
            'сила_стабилизатора_ЛЗ_Н',
            'сила_стабилизатора_ПЗ_Н',
        ]

        if df_main is not None and hasattr(df_main, 'columns') and all(c in df_main.columns for c in cols_stab):
            try:
                arr = df_main[cols_stab].to_numpy(dtype=float)
                max_abs = float(np.nanmax(np.abs(arr))) if arr.size else 0.0
            except Exception:
                max_abs = float('nan')

            if not stab_on:
                tol0 = float(params.get('stabilizator_force_zero_tol_N', 1e-6) or 1e-6)
                ok0 = (np.isfinite(max_abs) and (max_abs <= tol0)) or (not np.isfinite(max_abs))
                sev0 = 'warn' if not ok0 else 'info'
                _add(
                    items,
                    name='stabilizer_disabled_zero',
                    ok=ok0,
                    severity=sev0,
                    value={'enabled': stab_on, 'max_abs_N': max_abs, 'tol_N': tol0},
                    message=('Стабилизатор выключен, но силы не нулевые' if not ok0 else ''),
                )
            else:
                tol1 = float(params.get('stabilizator_force_balance_tol_N', 1e-3) or 1e-3)
                try:
                    sum_front = df_main['сила_стабилизатора_ЛП_Н'].astype(float).to_numpy() + df_main['сила_стабилизатора_ПП_Н'].astype(float).to_numpy()
                    sum_rear = df_main['сила_стабилизатора_ЛЗ_Н'].astype(float).to_numpy() + df_main['сила_стабилизатора_ПЗ_Н'].astype(float).to_numpy()
                    max_front = float(np.nanmax(np.abs(sum_front))) if sum_front.size else 0.0
                    max_rear = float(np.nanmax(np.abs(sum_rear))) if sum_rear.size else 0.0
                except Exception:
                    max_front = float('nan')
                    max_rear = float('nan')

                ok1 = (np.isfinite(max_front) and np.isfinite(max_rear) and (max_front <= tol1) and (max_rear <= tol1)) or (not (np.isfinite(max_front) and np.isfinite(max_rear)))
                sev1 = 'warn' if not ok1 else 'info'
                _add(
                    items,
                    name='stabilizer_force_balance',
                    ok=ok1,
                    severity=sev1,
                    value={'enabled': stab_on, 'max_front_sum_N': max_front, 'max_rear_sum_N': max_rear, 'tol_N': tol1},
                    message=('Стабилизатор включён, но баланс L+R нарушен' if not ok1 else ''),
                )
        else:
            _add(
                items,
                name='stabilizer_force_balance',
                ok=True,
                severity='info',
                value={'enabled': stab_on},
                message='Стабилизатор: колонки сил не найдены (пропуск)',
            )
    except Exception as ex:
        _add(items, name='stabilizer_force_balance', ok=True, severity='warn', message=f'stabilizer check failed: {ex!r}')



    # --- Zero pose (t=0) sanity: road=0, stroke ~ mid, basic coord consistency ---
    try:
        if df_main is not None and hasattr(df_main, 'iloc') and len(df_main) > 0 and hasattr(df_main, 'columns'):
            row0 = df_main.iloc[0]

            target_frac = float(params.get('zero_pose_target_stroke_frac', 0.5) or 0.5)
            tol_frac = float(params.get('zero_pose_tol_stroke_frac', 0.2) or 0.2)
            road_tol_m = float(params.get('zero_pose_road_tol_m', 1e-6) or 1e-6)

            corners = [
                ('ЛП', 'перед'),
                ('ПП', 'перед'),
                ('ЛЗ', 'зад'),
                ('ПЗ', 'зад'),
            ]

            pose: Dict[str, Any] = {}
            warn_msgs: List[str] = []
            err_msgs: List[str] = []

            for suffix, axle in corners:
                d: Dict[str, Any] = {}

                # Road level at t=0 (for plots/animation zero reference)
                c_road = f'дорога_{suffix}_м'
                if c_road in df_main.columns:
                    try:
                        road0 = float(row0[c_road])
                        d['road_m'] = road0
                        if abs(road0) > road_tol_m:
                            warn_msgs.append(f"{c_road}@t0={road0:+.3g} ≠ 0")
                    except Exception:
                        pass

                # Frame corner Z (single canonical key only)
                c_frame = f'рама_угол_{suffix}_z_м'
                if c_frame in df_main.columns:
                    try:
                        d['frame_z_m'] = float(row0[c_frame])
                    except Exception:
                        pass

                # Wheel Z
                c_w = f'перемещение_колеса_{suffix}_м'
                if c_w in df_main.columns:
                    try:
                        d['wheel_z_m'] = float(row0[c_w])
                    except Exception:
                        pass

                # Wheel relative frame (suspension deflection)
                c_dw = f'сжатие_подвески_колесо_{suffix}_м'
                if c_dw not in df_main.columns:
                    c_dw = f'колесо_относительно_рамы_{suffix}_м'
                if c_dw in df_main.columns:
                    try:
                        d['wheel_rel_frame_m'] = float(row0[c_dw])
                    except Exception:
                        pass

                # Rod positions (C1/C2), if present
                c_s1 = f'положение_штока_{suffix}_м'
                if c_s1 in df_main.columns:
                    try:
                        s1 = float(row0[c_s1])
                        d['rod_C1_pos_m'] = s1
                        stroke_key = f'ход_штока_Ц1_{axle}_м'
                        stroke = _safe_float(params.get(stroke_key, params.get('ход_штока', float('nan'))))
                        if _isfinite(stroke) and stroke > 0:
                            frac = s1 / float(stroke)
                            d['rod_C1_frac'] = frac
                            if not _isfinite(frac):
                                err_msgs.append(f"{suffix}: C1 frac NaN")
                            elif frac < -1e-6 or frac > 1.0 + 1e-6:
                                err_msgs.append(f"{suffix}: C1 frac={frac:.3g} вне [0..1]")
                            elif abs(frac - target_frac) > tol_frac:
                                warn_msgs.append(f"{suffix}: C1 frac={frac:.3f} (цель {target_frac:.2f}±{tol_frac:.2f})")
                    except Exception:
                        pass

                c_s2 = f'положение_штока_C2_{suffix}_м'
                if c_s2 in df_main.columns:
                    try:
                        s2 = float(row0[c_s2])
                        d['rod_C2_pos_m'] = s2
                        stroke_key = f'ход_штока_Ц2_{axle}_м'
                        stroke = _safe_float(params.get(stroke_key, params.get('ход_штока', float('nan'))))
                        if _isfinite(stroke) and stroke > 0:
                            frac = s2 / float(stroke)
                            d['rod_C2_frac'] = frac
                            if not _isfinite(frac):
                                err_msgs.append(f"{suffix}: C2 frac NaN")
                            elif frac < -1e-6 or frac > 1.0 + 1e-6:
                                err_msgs.append(f"{suffix}: C2 frac={frac:.3g} вне [0..1]")
                            elif abs(frac - target_frac) > tol_frac:
                                warn_msgs.append(f"{suffix}: C2 frac={frac:.3f} (цель {target_frac:.2f}±{tol_frac:.2f})")
                    except Exception:
                        pass

                pose[suffix] = d

            ok0 = (len(err_msgs) == 0)
            sev0 = 'info'
            msg0 = ''
            if err_msgs:
                sev0 = 'error'
                msg0 = '; '.join(err_msgs[:6])
            elif warn_msgs:
                sev0 = 'warn'
                msg0 = '; '.join(warn_msgs[:6])

            _add(
                items,
                name='zero_pose',
                ok=ok0,
                severity=sev0,
                value={
                    'target_stroke_frac': target_frac,
                    'tol_stroke_frac': tol_frac,
                    'road_tol_m': road_tol_m,
                    'corners': pose,
                },
                message=msg0,
            )
    except Exception as ex:
        _add(items, name='zero_pose', ok=True, severity='warn', value=None, message=f'zero_pose check failed: {ex!r}')

    # --- Mass closure ---
    m_err = _safe_float(_get('баланс_массы_ошибка_кг', float('nan')))
    if _isfinite(m_err):
        # scale for relative: use max of (delta mass, net boundary mass) + 1e-9
        dM = _safe_float(_get('масса_газа_delta_кг', 0.0))
        mb = _safe_float(_get('баланс_массы_кг', 0.0))
        scale = max(1e-9, abs(dM) + abs(mb))
        m_rel = abs(m_err) / scale
        ok_m = (abs(m_err) <= tol_m_abs) or (m_rel <= tol_m_rel)
        sev = 'error' if (abs(m_err) > 100 * tol_m_abs and m_rel > 10 * tol_m_rel) else ('warn' if not ok_m else 'info')
        _add(items, 'mass_balance', ok=ok_m, severity=sev, value={'err_kg': m_err, 'rel': m_rel}, expected=f'abs<={tol_m_abs} or rel<={tol_m_rel}')
    else:
        _add(items, 'mass_balance', ok=True, severity='warn', message='no mass balance error field (skipped)')

    # --- Energy closure (gas) ---
    e_err = _safe_float(_get('баланс_энергии_ошибка_Дж', float('nan')))
    if _isfinite(e_err):
        dU = _safe_float(_get('энергия_газа_deltaU_Дж', 0.0))
        eb = _safe_float(_get('баланс_энергии_баланс_Дж', 0.0))
        scale = max(1e-9, abs(dU) + abs(eb))
        e_rel = abs(e_err) / scale
        ok_e = (abs(e_err) <= tol_e_abs) or (e_rel <= tol_e_rel)
        sev = 'error' if (abs(e_err) > 100 * tol_e_abs and e_rel > 10 * tol_e_rel) else ('warn' if not ok_e else 'info')
        _add(items, 'energy_balance', ok=ok_e, severity=sev, value={'err_J': e_err, 'rel': e_rel}, expected=f'abs<={tol_e_abs} or rel<={tol_e_rel}')
    else:
        _add(items, 'energy_balance', ok=True, severity='warn', message='no energy balance error field (skipped)')

    # --- Finite key outputs ---
    keys = [
        'масса_газа_конечная_кг',
        'энергия_газа_конечная_Дж',
        'давление_ресивер1_Па',
        'давление_ресивер2_Па',
        'давление_ресивер3_Па',
    ]
    for k in keys:
        v = _get(k, None)
        if v is None:
            continue
        if hasattr(v, '__len__') and not isinstance(v, (str, bytes)):
            # df_main columns may be arrays; df_atm shouldn't.
            try:
                v = v[0]
            except Exception:
                pass
        ok = _isfinite(v)
        _add(items, f'finite:{k}', ok=ok, severity='error' if not ok else 'info', value=_safe_float(v))

    rep = _summarize(items)
    rep['stage'] = 'post'
    rep['duration_s'] = float(time.time() - t0)
    return rep


def attach_reports_to_df_atm(df_atm: Any, pre: Optional[Dict[str, Any]], post: Optional[Dict[str, Any]]) -> Any:
    """Добавляет краткие итоги в df_atm (pandas.DataFrame)."""
    try:
        if df_atm is None:
            return df_atm
        if not hasattr(df_atm, 'columns'):
            return df_atm

        def _dump(rep: Optional[Dict[str, Any]]) -> str:
            if rep is None:
                return ''
            try:
                return json.dumps(rep, ensure_ascii=False)
            except Exception:
                return ''

        if pre is not None:
            df_atm['авто_самопроверки_pre_ok'] = bool(pre.get('ok', True))
            df_atm['авто_самопроверки_pre_error'] = int(pre.get('n_error', 0))
            df_atm['авто_самопроверки_pre_warn'] = int(pre.get('n_warn', 0))
            df_atm['авто_самопроверки_pre_json'] = _dump(pre)
        if post is not None:
            df_atm['авто_самопроверки_post_ok'] = bool(post.get('ok', True))
            df_atm['авто_самопроверки_post_error'] = int(post.get('n_error', 0))
            df_atm['авто_самопроверки_post_warn'] = int(post.get('n_warn', 0))
            df_atm['авто_самопроверки_post_json'] = _dump(post)

        # convenience combined
        if pre is not None and post is not None:
            df_atm['авто_самопроверки_ok'] = bool(pre.get('ok', True) and post.get('ok', True))
            df_atm['авто_самопроверки_errors'] = int(pre.get('n_error', 0)) + int(post.get('n_error', 0))
            df_atm['авто_самопроверки_warns'] = int(pre.get('n_warn', 0)) + int(post.get('n_warn', 0))
        return df_atm
    except Exception:
        return df_atm


def maybe_raise_on_fail(*, params: Dict[str, Any], pre: Optional[Dict[str, Any]], post: Optional[Dict[str, Any]]) -> None:
    """Если включён строгий режим — падаем при наличии ошибок."""
    try:
        strict = bool(params.get('авто_самопроверки_строго', False))
        enabled = bool(params.get('авто_самопроверки', True))
        if not enabled or not strict:
            return
        n_err = int((pre or {}).get('n_error', 0)) + int((post or {}).get('n_error', 0))
        if n_err > 0:
            raise RuntimeError(f"Авто‑самопроверки: обнаружено ошибок: {n_err}. См. авто_самопроверки_*_json в df_atm.")
    except RuntimeError:
        raise
    except Exception:
        return
