"""Limits & constraint report for a simulation run.

Why this exists
--------------
The project requirements explicitly ask for **autonomous checks** to be
"sewn into" the compute pipeline (not only the Streamlit UI).

This module computes a compact set of *limits / constraints* from the main
time-series dataframe (df_main) and evaluates them against optional `target_*`
fields in the current test definition.

The report is designed to be:
* lightweight (pure NumPy/Pandas),
* robust to missing columns (other models may omit some signals),
* compatible with the optimization worker metrics naming.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


def _json_dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2)


def _targets_from_test(test: Optional[Dict[str, Any]]) -> Dict[str, float]:
    """Extract targets from `test` using the same convention as the optimizer.

    `target_<name>` -> `<name>`
    """
    if not isinstance(test, dict):
        return {}
    out: Dict[str, float] = {}
    for k, v in test.items():
        if not (isinstance(k, str) and k.startswith("target_")):
            continue
        if v is None:
            continue
        try:
            out[k.replace("target_", "", 1)] = float(v)
        except Exception:
            # ignore non-numeric targets
            continue
    return out


@dataclass
class LimitItem:
    name: str
    ok: bool
    severity: str  # "error" | "warn" | "info"
    value: Any
    target: Optional[float] = None
    message: str = ""


def compute_limits_metrics(df_main, params: Dict[str, Any]) -> Dict[str, float]:
    """Compute limit metrics from df_main.

    Returns a dict compatible with optimization metrics naming.

    Notes:
    - No exceptions should escape; on failures the corresponding metrics are
      simply omitted.
    """
    import numpy as np

    metrics: Dict[str, float] = {}

    # --- Wheel lift + Fmin ---
    try:
        cols_air = [
            "колесо_в_воздухе_ЛП",
            "колесо_в_воздухе_ПП",
            "колесо_в_воздухе_ЛЗ",
            "колесо_в_воздухе_ПЗ",
        ]
        cols_F = [
            "нормальная_сила_шины_ЛП_Н",
            "нормальная_сила_шины_ПП_Н",
            "нормальная_сила_шины_ЛЗ_Н",
            "нормальная_сила_шины_ПЗ_Н",
        ]
        if all(c in df_main.columns for c in cols_air):
            air = df_main[cols_air].to_numpy(dtype=float)
            frac_any = float((air.max(axis=1) > 0.5).mean())
            metrics["доля_времени_отрыв"] = frac_any
            # also keep per-wheel fractions when available
            for c, col in zip(["ЛП", "ПП", "ЛЗ", "ПЗ"], cols_air):
                metrics[f"доля_времени_отрыв_{c}"] = float(np.mean(df_main[col].to_numpy(dtype=float)))
        if all(c in df_main.columns for c in cols_F):
            Fmin = float(df_main[cols_F].to_numpy(dtype=float).min())
            metrics["Fmin_шины_Н"] = Fmin
    except Exception:
        pass

    # --- Rod stroke margin + rod speed ---
    try:
        from .opt_worker_v3_margins_energy import rod_margin_and_speed

        metrics.update(rod_margin_and_speed(df_main, params))
    except Exception:
        pass

    # --- Roll/pitch breakdown margins (continuous KPI) ---
    try:
        from .opt_worker_v3_margins_energy import запас_до_пробоя_крен_тангаж

        metrics.update(запас_до_пробоя_крен_тангаж(df_main, params))
    except Exception:
        pass

    # --- Pmid margin (as in optimizer) ---
    try:
        Pmid = float(params.get("давление_Pmid_сброс"))
        if "давление_ресивер3_Па" in df_main.columns:
            pR3_max = float(np.max(df_main["давление_ресивер3_Па"].to_numpy(dtype=float)))
            metrics["pR3_max_бар"] = float(pR3_max / 1e5)
            metrics["запас_до_Pmid_бар"] = float((Pmid - pR3_max) / 1e5)
            metrics["запас_свыше_Pmid_бар"] = float((pR3_max - Pmid) / 1e5)
    except Exception:
        pass

    # --- Bump-stops (compression/rebound) margins and force ---
    try:
        cols_bump = [f"запас_до_упора_сжатие_{c}_м" for c in ("ЛП", "ПП", "ЛЗ", "ПЗ")]
        cols_reb = [f"запас_до_упора_отбой_{c}_м" for c in ("ЛП", "ПП", "ЛЗ", "ПЗ")]
        cols_Fstop = [f"сила_отбойника_{c}_Н" for c in ("ЛП", "ПП", "ЛЗ", "ПЗ")]

        if any(c in df_main.columns for c in cols_bump):
            arr = df_main[[c for c in cols_bump if c in df_main.columns]].to_numpy(dtype=float)
            metrics["мин_запас_до_упора_сжатие_все_м"] = float(np.min(arr))
        if any(c in df_main.columns for c in cols_reb):
            arr = df_main[[c for c in cols_reb if c in df_main.columns]].to_numpy(dtype=float)
            metrics["мин_запас_до_упора_отбой_все_м"] = float(np.min(arr))
        if any(c in metrics for c in ("мин_запас_до_упора_сжатие_все_м", "мин_запас_до_упора_отбой_все_м")):
            metrics["мин_запас_до_упора_отбойники_все_м"] = float(
                min(
                    metrics.get("мин_запас_до_упора_сжатие_все_м", float("inf")),
                    metrics.get("мин_запас_до_упора_отбой_все_м", float("inf")),
                )
            )
        if any(c in df_main.columns for c in cols_Fstop):
            arr = df_main[[c for c in cols_Fstop if c in df_main.columns]].to_numpy(dtype=float)
            metrics["макс_сила_отбойника_все_Н"] = float(np.max(arr))
    except Exception:
        pass

    return metrics


def build_limits_report(metrics: Dict[str, float], test: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Evaluate limits against targets + internal safety rules."""
    targets = _targets_from_test(test)

    items: List[LimitItem] = []

    def _add(name: str, ok: bool, value: Any, target: Optional[float] = None, severity: str = "error", message: str = ""):
        items.append(LimitItem(name=name, ok=bool(ok), severity=str(severity), value=value, target=target, message=str(message)))

    # --- Internal physical sanity (independent of targets) ---
    # 1) Rod margin must not be negative (beyond stroke)
    if "мин_запас_до_упора_штока_все_м" in metrics:
        v = float(metrics["мин_запас_до_упора_штока_все_м"])
        if v < -1e-6:
            _add("шток_перешёл_за_упор", ok=False, value=v, severity="error", message="Отрицательный запас до упора штока (модель вышла за ход).")
        elif v < 1e-4:
            _add("шток_почти_в_упоре", ok=False, value=v, severity="warn", message="Запас до упора штока очень мал.")

    # 2) Bump-stops margin should not be negative (penetration)
    if "мин_запас_до_упора_отбойники_все_м" in metrics:
        v = float(metrics["мин_запас_до_упора_отбойники_все_м"])
        if v < -1e-6:
            _add("отбойники_продавлены", ok=False, value=v, severity="error", message="Отрицательный запас до отбойника (продавливание за упор).")
        elif v < 1e-4:
            _add("отбойники_почти", ok=False, value=v, severity="warn", message="Запас до отбойника очень мал (почти упор).")

    # 3) Wheel lift is a physical event, not always an error, but track it.
    if "доля_времени_отрыв" in metrics:
        v = float(metrics["доля_времени_отрыв"])
        if v > 0.0:
            _add("отрыв_колёс", ok=False, value=v, severity="warn", message="Есть отрыв колёс (доля времени, когда хотя бы одно колесо в воздухе).")

    # --- Target-based checks (same naming as optimizer) ---
    # (We follow the optimizer logic: violation if metric beyond target.)
    if "макс_доля_отрыва" in targets and "доля_времени_отрыв" in metrics:
        lim = float(targets["макс_доля_отрыва"])
        v = float(metrics["доля_времени_отрыв"])
        _add(
            "target_макс_доля_отрыва",
            ok=(v <= lim),
            value=v,
            target=lim,
            severity="error",
            message=("Превышена допустимая доля отрыва" if v > lim else "OK"),
        )

    if "мин_Fmin_Н" in targets and "Fmin_шины_Н" in metrics:
        lim = float(targets["мин_Fmin_Н"])
        v = float(metrics["Fmin_шины_Н"])
        _add(
            "target_мин_Fmin_Н",
            ok=(v >= lim),
            value=v,
            target=lim,
            severity="error",
            message=("Недостаточная минимальная нормальная сила" if v < lim else "OK"),
        )

    if "мин_запас_до_Pmid_бар" in targets and "запас_до_Pmid_бар" in metrics:
        lim = float(targets["мин_запас_до_Pmid_бар"])
        v = float(metrics["запас_до_Pmid_бар"])
        _add(
            "target_мин_запас_до_Pmid_бар",
            ok=(v >= lim),
            value=v,
            target=lim,
            severity="error",
            message=("Запас до Pmid меньше требуемого" if v < lim else "OK"),
        )

    if "мин_запас_до_пробоя_крен_град" in targets and "запас_до_пробоя_крен_град" in metrics:
        lim = float(targets["мин_запас_до_пробоя_крен_град"])
        v = float(metrics["запас_до_пробоя_крен_град"])
        _add(
            "target_мин_запас_до_пробоя_крен_град",
            ok=(v >= lim),
            value=v,
            target=lim,
            severity="error",
            message=("Запас до пробоя крена меньше требуемого" if v < lim else "OK"),
        )

    if "мин_запас_до_пробоя_тангаж_град" in targets and "запас_до_пробоя_тангаж_град" in metrics:
        lim = float(targets["мин_запас_до_пробоя_тангаж_град"])
        v = float(metrics["запас_до_пробоя_тангаж_град"])
        _add(
            "target_мин_запас_до_пробоя_тангаж_град",
            ok=(v >= lim),
            value=v,
            target=lim,
            severity="error",
            message=("Запас до пробоя тангажа меньше требуемого" if v < lim else "OK"),
        )

    if "мин_запас_до_упора_штока_м" in targets and "мин_запас_до_упора_штока_все_м" in metrics:
        lim = float(targets["мин_запас_до_упора_штока_м"])
        v = float(metrics["мин_запас_до_упора_штока_все_м"])
        _add(
            "target_мин_запас_до_упора_штока_м",
            ok=(v >= lim),
            value=v,
            target=lim,
            severity="error",
            message=("Запас до упора штока меньше требуемого" if v < lim else "OK"),
        )

    if "лимит_скорости_штока_м_с" in targets and "макс_скорость_штока_все_м_с" in metrics:
        lim = float(targets["лимит_скорости_штока_м_с"])
        v = float(metrics["макс_скорость_штока_все_м_с"])
        _add(
            "target_лимит_скорости_штока_м_с",
            ok=(v <= lim),
            value=v,
            target=lim,
            severity="error",
            message=("Превышен лимит скорости штока" if v > lim else "OK"),
        )

    # Summaries
    n_err = sum((it.severity == "error") and (not it.ok) for it in items)
    n_warn = sum((it.severity == "warn") and (not it.ok) for it in items)
    ok = (n_err == 0)

    return {
        "ok": bool(ok),
        "n_error": int(n_err),
        "n_warn": int(n_warn),
        "items": [it.__dict__ for it in items],
        "targets": targets,
    }


def attach_limits_to_df_atm(df_atm, metrics: Dict[str, float], report: Dict[str, Any]) -> None:
    """Attach a compact limits report to df_atm in-place."""
    try:
        import pandas as pd

        if df_atm is None or not isinstance(df_atm, pd.DataFrame) or len(df_atm) == 0:
            return

        # Keep only a useful subset of metrics as flat columns.
        keep_keys = [
            # wheel lift / contact
            "доля_времени_отрыв",
            "Fmin_шины_Н",
            # rods
            "мин_запас_до_упора_штока_все_м",
            "макс_скорость_штока_все_м_с",
            # bumpstops
            "мин_запас_до_упора_сжатие_все_м",
            "мин_запас_до_упора_отбой_все_м",
            "мин_запас_до_упора_отбойники_все_м",
            "макс_сила_отбойника_все_Н",
            # roll/pitch
            "запас_до_пробоя_крен_град",
            "запас_до_пробоя_тангаж_град",
            # Pmid
            "pR3_max_бар",
            "запас_до_Pmid_бар",
            "запас_свыше_Pmid_бар",
        ]
        for k in keep_keys:
            if k in metrics:
                try:
                    df_atm.loc[df_atm.index[0], k] = float(metrics[k])
                except Exception:
                    pass

        df_atm.loc[df_atm.index[0], "limits_ok"] = bool(report.get("ok", False))
        df_atm.loc[df_atm.index[0], "limits_n_error"] = int(report.get("n_error", 0))
        df_atm.loc[df_atm.index[0], "limits_n_warn"] = int(report.get("n_warn", 0))
        df_atm.loc[df_atm.index[0], "limits_report_json"] = _json_dumps(report)
    except Exception:
        # do not fail the simulation
        return
