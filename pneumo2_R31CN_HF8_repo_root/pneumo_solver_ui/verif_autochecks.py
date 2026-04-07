# -*- coding: utf-8 -*-
"""verif_autochecks.py

Автономные автоматические самопроверки (верификация) для запуска симуляции/
оптимизации.

Цели:
1) Находить скрытые ошибки модели *в процессе оптимизации*, а не постфактум.
2) Давать единый интерфейс для "быстрых" инвариантов (не NaN, баланс энергии,
   неотрицательность энтропийного смешения, механический selfcheck, обязательные
   флаги защиты схемы).
3) Не ломать рабочий pipeline: по умолчанию выдаём штраф, а не исключение.

Важно:
- Файл не тянет тяжёлые зависимости и должен работать на Windows.
- Проверки построены так, чтобы быть "мягкими": если метрика отсутствует,
  проверка пропускается.

Использование:
    from verif_autochecks import check_candidate_metrics
    metrics.update(check_candidate_metrics(metrics, params, test))

Ключи результата (добавляются в metrics):
    "верификация_ok" (0/1)
    "верификация_штраф" (float)
    "верификация_флаги" (str)
    "верификация_сообщение" (str)

"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

import numpy as np


def _is_number(x: Any) -> bool:
    # bool is subclass of int -> исключаем
    return isinstance(x, (int, float, np.floating, np.integer)) and not isinstance(x, bool)


def _as_float(x: Any, default: float = float("nan")) -> float:
    if x is None:
        return float(default)
    try:
        return float(x)
    except Exception:
        return float(default)


def _finite(x: Any) -> bool:
    try:
        return bool(np.isfinite(float(x)))
    except Exception:
        return False


def _get_first(metrics: Dict[str, Any], keys: Iterable[str]) -> Optional[Any]:
    for k in keys:
        if k in metrics:
            return metrics.get(k)
    return None


def check_candidate_metrics(metrics: Dict[str, Any], params: Dict[str, Any], test: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Проверить метрики кандидата и вернуть добавки (штраф/флаги).

    Проверки управляются параметрами (params):
      autoverif_enable: bool (default True)
      autoverif_strict: bool (default False) -> если True, то при провале поднимаем исключение
      autoverif_penalty_nonfinite: float (default 1e6)
      autoverif_penalty_invariant: float (default 1e5)
      autoverif_penalty_selfcheck: float (default 1e5)
      autoverif_energy_err_rel_max: float (default 5e-3)
      autoverif_entropy_mix_min: float (default -1e-9)
      autoverif_require_scheme_lock: bool (default True)
      autoverif_track_expected_m: float (default 1.0)
      autoverif_wheelbase_expected_m: float (default 1.5)
      autoverif_geom_tol_m: float (default 1e-9)

    Любая отсутствующая метрика -> проверка пропускается.
    """

    enable = bool(params.get("autoverif_enable", True))
    if not enable:
        return {
            "верификация_ok": 1,
            "верификация_штраф": 0.0,
            "верификация_флаги": "",
            "верификация_сообщение": "disabled",
        }

    strict = bool(params.get("autoverif_strict", False))

    pen_nonfinite = float(params.get("autoverif_penalty_nonfinite", 1e6))
    pen_invariant = float(params.get("autoverif_penalty_invariant", 1e5))
    pen_selfcheck = float(params.get("autoverif_penalty_selfcheck", 1e5))

    energy_err_rel_max = float(params.get("autoverif_energy_err_rel_max", 5e-3))
    entropy_mix_min = float(params.get("autoverif_entropy_mix_min", -1e-9))
    require_scheme_lock = bool(params.get("autoverif_require_scheme_lock", True))

    track_expected = float(params.get("autoverif_track_expected_m", 1.0))
    wheelbase_expected = float(params.get("autoverif_wheelbase_expected_m", 1.5))
    geom_tol = float(params.get("autoverif_geom_tol_m", 1e-9))

    penalty = 0.0
    flags: List[str] = []
    msgs: List[str] = []

    # --- 1) Флаги защиты схемы ---
    if require_scheme_lock:
        if not bool(params.get("enforce_scheme_integrity", False)):
            penalty += pen_invariant
            flags.append("scheme_lock_off")
            msgs.append("enforce_scheme_integrity=False")
        if not bool(params.get("enforce_camozzi_only", False)):
            penalty += pen_invariant
            flags.append("camozzi_only_off")
            msgs.append("enforce_camozzi_only=False")

    # --- 2) Механический selfcheck (если модель его пишет) ---
    mech_ok = metrics.get("mech_selfcheck_ok", None)
    if mech_ok is not None:
        try:
            if int(mech_ok) == 0:
                penalty += pen_selfcheck
                flags.append("mech_selfcheck_fail")
                mm = str(metrics.get("mech_selfcheck_msg", "")).strip()
                if mm:
                    msgs.append(("mech:" + mm)[:200])
        except Exception:
            # если ключ есть, но не приводится к int — считаем как проблема
            penalty += pen_selfcheck
            flags.append("mech_selfcheck_bad")
            msgs.append("mech_selfcheck_ok not int")

    # --- 3) Неотрицательность энтропийного смешения (S_mix >= 0) ---
    s_mix = _get_first(metrics, ["энтропия_смешение_Дж_К", "энтропия_генерация_смешение_Дж_К"])
    if s_mix is not None and _finite(s_mix):
        s_mix_f = float(s_mix)
        if s_mix_f < float(entropy_mix_min):
            penalty += pen_invariant * max(1.0, abs(s_mix_f - entropy_mix_min))
            flags.append("entropy_mix_negative")
            msgs.append(f"Smix={s_mix_f:.3g} < {entropy_mix_min:.3g}")

    # --- 4) Баланс энергии газа (если метрика есть) ---
    e_err = metrics.get("ошибка_энергии_газа_отн", None)
    if e_err is not None and _finite(e_err):
        ee = abs(float(e_err))
        if ee > float(energy_err_rel_max):
            penalty += pen_invariant * (ee / max(1e-12, float(energy_err_rel_max)))
            flags.append("energy_balance")
            msgs.append(f"Eerr_rel={float(e_err):.3g} > {energy_err_rel_max:.3g}")

    # --- 5) Геометрические константы (колея/база) ---
    # ABSOLUTE LAW: canonical keys only (no "база_м"/"колея_м").
    tr = _as_float(params.get("колея", float("nan")))
    wb = _as_float(params.get("база", float("nan")))
    if _finite(tr) and _finite(track_expected):
        if abs(tr - track_expected) > geom_tol:
            penalty += pen_invariant
            flags.append("track_changed")
            msgs.append(f"track={tr} expected={track_expected}")
    if _finite(wb) and _finite(wheelbase_expected):
        if abs(wb - wheelbase_expected) > geom_tol:
            penalty += pen_invariant
            flags.append("wheelbase_changed")
            msgs.append(f"wheelbase={wb} expected={wheelbase_expected}")

    
    # --- 6) Пружина: запас до coil-bind (смыкание витков) ---
    # Важно: проверка имеет смысл только если задана длина "solid" (пружина_длина_солид_м > 0).
    # Иначе у нас нет геометрии витков, и coil-bind по сути не определён.
    if bool(params.get("autoverif_coilbind_enabled", True)):
        try:
            L_solid = float(params.get("пружина_длина_солид_м", 0.0))
        except Exception:
            L_solid = 0.0

        if L_solid > 1e-9:
            coil_min = _as_float(metrics.get("пружина_запас_до_coil_bind_все_минимум_м", float("nan")))
            coil_req = float(params.get("autoverif_coilbind_min_margin_m", 0.0))
            if _finite(coil_min) and coil_min < coil_req:
                # мягкий штраф: пропорционально недостатку запаса
                denom = max(1e-6, abs(coil_req) if abs(coil_req) > 1e-9 else 1e-3)
                penalty += pen_invariant * (1.0 + (coil_req - coil_min) / denom)
                flags.append("coil_bind_risk")
                msgs.append(f"coil_margin_min={coil_min:.4g} < {coil_req:.4g}")


# --- 6) Non-finite значения в метриках ---
    # Нюанс проекта: некоторые метрики *осознанно* могут быть +inf.
    # Например, t_пересечения_Pmid_с == +inf означает «пересечения не было в пределах теста»
    # и это НЕ является ошибкой физики.
    allow_nonfinite = params.get('autoverif_nonfinite_allowlist', None)
    allow_keys = set()
    if isinstance(allow_nonfinite, (list, tuple, set)):
        allow_keys |= {str(x).strip() for x in allow_nonfinite if str(x).strip()}
    elif isinstance(allow_nonfinite, str):
        allow_keys |= {s.strip() for s in allow_nonfinite.split(',') if s.strip()}

    # базовый allowlist (обратная совместимость)
    allow_keys.add('t_пересечения_Pmid_с')

    nonfinite_keys: List[str] = []
    for k, v in metrics.items():
        if not _is_number(v):
            continue
        if _finite(v):
            continue
        kk = str(k)
        # Разрешаем ТОЛЬКО +inf для некоторых «time-to-event» метрик.
        if kk in allow_keys:
            try:
                fv = float(v)
                if fv == float('inf'):
                    continue
            except Exception:
                pass
        nonfinite_keys.append(kk)

    if nonfinite_keys:
        penalty += pen_nonfinite
        flags.append("nonfinite")
        # ограничим размер
        msgs.append("nonfinite:" + ",".join(nonfinite_keys[:10]))

    ok = 1 if penalty <= 0.0 else 0
    flag_str = ";".join(flags)
    msg_str = "; ".join(msgs)[:800]

    if strict and ok == 0:
        raise RuntimeError("autoverif failed: " + (msg_str or flag_str))

    return {
        "верификация_ok": int(ok),
        "верификация_штраф": float(penalty),
        "верификация_флаги": flag_str,
        "верификация_сообщение": msg_str,
    }
