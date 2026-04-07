from __future__ import annotations

import math
from typing import Any, Callable


NumberSource = float | int | Callable[[], float | int]


def _resolve_number(value_or_fn: NumberSource) -> float:
    if callable(value_or_fn):
        return float(value_or_fn())
    return float(value_or_fn)


def infer_plot_unit_and_transform(
    col: str,
    *,
    pressure_unit_label: str,
    pressure_offset_pa: NumberSource,
    pressure_divisor_pa: NumberSource,
    length_unit_label: str = "m",
    length_scale: float = 1.0,
) -> tuple[str, Callable[[Any], Any] | None, str]:
    c = str(col)
    if c.endswith("_Па") and ("давление" in c or "p_" in c.lower()):
        pressure_offset = _resolve_number(pressure_offset_pa)
        pressure_divisor = _resolve_number(pressure_divisor_pa)
        return (
            pressure_unit_label,
            lambda a, _pressure_offset=pressure_offset, _pressure_divisor=pressure_divisor: (a - _pressure_offset) / _pressure_divisor,
            pressure_unit_label,
        )
    if c.endswith("_рад") or c.endswith("_rad"):
        return ("град", lambda a: a * 180.0 / math.pi, "град")
    if "_м_с" in c or c.endswith("_м/с") or c.endswith("_m_s"):
        return ("м/с", None, "м/с")
    if c.endswith("_м") or c.endswith("_m"):
        if abs(float(length_scale) - 1.0) < 1e-12 and length_unit_label == "м":
            return ("м", None, "м")
        return (length_unit_label, lambda a, _length_scale=float(length_scale): a * _length_scale, length_unit_label)
    if c.endswith("_Н") or c.endswith("_N"):
        return ("Н", None, "Н")
    return ("", None, "")


def pa_abs_to_gauge(p_abs_pa: float, *, pressure_offset_pa: NumberSource, pressure_divisor_pa: NumberSource) -> float:
    return (float(p_abs_pa) - _resolve_number(pressure_offset_pa)) / _resolve_number(pressure_divisor_pa)


def gauge_to_pa_abs(p_gauge: float, *, pressure_offset_pa: NumberSource, pressure_divisor_pa: NumberSource) -> float:
    return _resolve_number(pressure_offset_pa) + float(p_gauge) * _resolve_number(pressure_divisor_pa)


def is_length_param_name(name: str) -> bool:
    if name in {"колея", "база", "ширина_рамы", "ход_штока", "статический_ход_колеса"}:
        return True
    return str(name).endswith("_м") or str(name).endswith("_m")


def param_unit_label(
    name: str,
    *,
    pressure_unit_label: str,
    is_pressure_param_fn: Callable[[str], bool],
    is_volume_param_fn: Callable[[str], bool],
    is_small_volume_param_fn: Callable[[str], bool],
) -> str:
    if is_pressure_param_fn(name):
        return pressure_unit_label
    if is_volume_param_fn(name):
        return "мл" if is_small_volume_param_fn(name) else "л"
    if name.endswith("_град"):
        return "град"
    if "открытие" in name:
        return "доля 0..1"
    if name == "пружина_масштаб":
        return "коэф."
    return "—"


def si_to_ui_value(key: str, x_si: Any, kind: str, *, p_atm: float, bar_pa: float) -> Any:
    del key
    if x_si is None:
        return float("nan")
    if kind == "raw":
        if isinstance(x_si, (str, bool, list, tuple, dict)):
            return x_si
        try:
            import numpy as _np

            if isinstance(x_si, (_np.bool_,)):
                return bool(x_si)
            if isinstance(x_si, (_np.integer,)):
                return int(x_si)
            if isinstance(x_si, (_np.floating,)):
                return float(x_si)
        except Exception:
            pass
        try:
            return float(x_si)
        except Exception:
            return float("nan")
    if kind == "pressure_bar_g":
        return (float(x_si) - float(p_atm)) / float(bar_pa)
    if kind == "pressure_atm_g":
        return (float(x_si) - float(p_atm)) / float(p_atm)
    if kind == "pressure_kPa_abs":
        return float(x_si) / 1000.0
    if kind == "length_mm":
        return float(x_si) * 1000.0
    if kind == "volume_L":
        return float(x_si) * 1000.0
    if kind == "volume_mL":
        return float(x_si) * 1_000_000.0
    if kind == "temperature_C":
        return float(x_si) - 273.15
    try:
        return float(x_si)
    except Exception:
        return float("nan")


def ui_to_si_value(key: str, x_ui: float, kind: str, *, p_atm: float, bar_pa: float) -> float:
    del key
    if kind == "pressure_bar_g":
        return float(p_atm) + float(bar_pa) * float(x_ui)
    if kind == "pressure_atm_g":
        return float(p_atm) * (1.0 + float(x_ui))
    if kind == "pressure_kPa_abs":
        return 1000.0 * float(x_ui)
    if kind == "length_mm":
        return float(x_ui) / 1000.0
    if kind == "volume_L":
        return float(x_ui) / 1000.0
    if kind == "volume_mL":
        return float(x_ui) / 1_000_000.0
    if kind == "temperature_C":
        return float(x_ui) + 273.15
    return float(x_ui)


__all__ = [
    "gauge_to_pa_abs",
    "infer_plot_unit_and_transform",
    "is_length_param_name",
    "pa_abs_to_gauge",
    "param_unit_label",
    "si_to_ui_value",
    "ui_to_si_value",
]
