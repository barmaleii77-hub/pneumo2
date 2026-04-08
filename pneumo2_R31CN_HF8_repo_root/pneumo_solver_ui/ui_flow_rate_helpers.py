from __future__ import annotations


def flow_rate_display_scale_and_unit(
    *,
    p_atm: float,
    model_module,
    fallback_scale: float = 1.0,
    fallback_unit: str = "кг/с",
) -> tuple[float, str]:
    try:
        r_air = float(getattr(model_module, "R_AIR", 287.0))
        t_air = float(getattr(model_module, "T_AIR", 293.15))
        rho_n = float(p_atm) / (r_air * t_air)
        return 1000.0 * 60.0 / rho_n, "Нл/мин"
    except Exception:
        return float(fallback_scale), fallback_unit
