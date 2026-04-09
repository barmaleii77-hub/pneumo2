from __future__ import annotations

from dataclasses import dataclass
from functools import partial
from typing import Any, Callable

from pneumo_solver_ui.ui_unit_helpers import (
    gauge_to_pa_abs,
    infer_plot_unit_and_transform,
    pa_abs_to_gauge,
    param_unit_label,
    si_to_ui_value,
    ui_to_si_value,
)


@dataclass(frozen=True)
class PressureGaugeProfile:
    unit_label: str
    pressure_from_pa: Callable[[float], float]
    pressure_to_pa_abs: Callable[[float], float]


@dataclass(frozen=True)
class UIUnitProfile:
    unit_label: str
    infer_unit_and_transform: Callable[[str], tuple[str, Callable[[Any], Any] | None, str]]
    pressure_from_pa: Callable[[float], float]
    pressure_to_pa_abs: Callable[[float], float]
    param_unit: Callable[[str], str]
    si_to_ui: Callable[[str, Any, str], Any]
    ui_to_si: Callable[[str, float, str], float]


def build_plot_unit_transformer(
    *,
    pressure_unit_label: str,
    pressure_offset_pa: float | int | Callable[[], float | int],
    pressure_divisor_pa: float | int | Callable[[], float | int],
    length_unit_label: str,
    length_scale: float,
) -> Callable[[str], tuple[str, Callable[[Any], Any] | None, str]]:
    return partial(
        infer_plot_unit_and_transform,
        pressure_unit_label=pressure_unit_label,
        pressure_offset_pa=pressure_offset_pa,
        pressure_divisor_pa=pressure_divisor_pa,
        length_unit_label=length_unit_label,
        length_scale=length_scale,
    )


def build_pressure_gauge_converters(
    *,
    pressure_offset_pa: float | int | Callable[[], float | int],
    pressure_divisor_pa: float | int | Callable[[], float | int],
) -> tuple[Callable[[float], float], Callable[[float], float]]:
    return (
        partial(
            pa_abs_to_gauge,
            pressure_offset_pa=pressure_offset_pa,
            pressure_divisor_pa=pressure_divisor_pa,
        ),
        partial(
            gauge_to_pa_abs,
            pressure_offset_pa=pressure_offset_pa,
            pressure_divisor_pa=pressure_divisor_pa,
        ),
    )


def build_param_unit_labeler(
    *,
    pressure_unit_label: str,
    is_pressure_param_fn: Callable[[str], bool],
    is_volume_param_fn: Callable[[str], bool],
    is_small_volume_param_fn: Callable[[str], bool],
) -> Callable[[str], str]:
    return partial(
        param_unit_label,
        pressure_unit_label=pressure_unit_label,
        is_pressure_param_fn=is_pressure_param_fn,
        is_volume_param_fn=is_volume_param_fn,
        is_small_volume_param_fn=is_small_volume_param_fn,
    )


def build_si_ui_converters(
    *,
    p_atm: float | Callable[[], float],
    bar_pa: float | Callable[[], float],
) -> tuple[Callable[[str, Any, str], Any], Callable[[str, float, str], float]]:
    def _resolve(value: float | Callable[[], float]) -> float:
        return float(value() if callable(value) else value)

    def _si_to_ui(name: str, value: Any, kind: str) -> Any:
        return si_to_ui_value(name, value, kind, p_atm=_resolve(p_atm), bar_pa=_resolve(bar_pa))

    def _ui_to_si(name: str, value: float, kind: str) -> float:
        return ui_to_si_value(name, value, kind, p_atm=_resolve(p_atm), bar_pa=_resolve(bar_pa))

    return (
        _si_to_ui,
        _ui_to_si,
    )


def build_gauge_pressure_profile(
    *,
    unit_label: str,
    pressure_offset_pa: float | int | Callable[[], float | int],
    pressure_divisor_pa: float | int | Callable[[], float | int],
) -> PressureGaugeProfile:
    pressure_from_pa, pressure_to_pa_abs = build_pressure_gauge_converters(
        pressure_offset_pa=pressure_offset_pa,
        pressure_divisor_pa=pressure_divisor_pa,
    )
    return PressureGaugeProfile(
        unit_label=unit_label,
        pressure_from_pa=pressure_from_pa,
        pressure_to_pa_abs=pressure_to_pa_abs,
    )


def build_ui_unit_profile(
    *,
    pressure_unit_label: str,
    pressure_offset_pa: float | int | Callable[[], float | int],
    pressure_divisor_pa: float | int | Callable[[], float | int],
    length_unit_label: str,
    length_scale: float,
    is_pressure_param_fn: Callable[[str], bool],
    is_volume_param_fn: Callable[[str], bool],
    is_small_volume_param_fn: Callable[[str], bool],
    p_atm: float | Callable[[], float],
    bar_pa: float | Callable[[], float],
) -> UIUnitProfile:
    pressure_profile = build_gauge_pressure_profile(
        unit_label=pressure_unit_label,
        pressure_offset_pa=pressure_offset_pa,
        pressure_divisor_pa=pressure_divisor_pa,
    )
    si_to_ui, ui_to_si = build_si_ui_converters(
        p_atm=p_atm,
        bar_pa=bar_pa,
    )
    return UIUnitProfile(
        unit_label=pressure_unit_label,
        infer_unit_and_transform=build_plot_unit_transformer(
            pressure_unit_label=pressure_unit_label,
            pressure_offset_pa=pressure_offset_pa,
            pressure_divisor_pa=pressure_divisor_pa,
            length_unit_label=length_unit_label,
            length_scale=length_scale,
        ),
        pressure_from_pa=pressure_profile.pressure_from_pa,
        pressure_to_pa_abs=pressure_profile.pressure_to_pa_abs,
        param_unit=build_param_unit_labeler(
            pressure_unit_label=pressure_unit_label,
            is_pressure_param_fn=is_pressure_param_fn,
            is_volume_param_fn=is_volume_param_fn,
            is_small_volume_param_fn=is_small_volume_param_fn,
        ),
        si_to_ui=si_to_ui,
        ui_to_si=ui_to_si,
    )
