# -*- coding: utf-8 -*-

import sys
from pathlib import Path

# Ensure project root is on sys.path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pneumo_solver_ui.iso6358_core import anr_info, rho_ANR_kg_m3


def test_iso8778_anr_conditions_and_density_reasonable():
    info = anr_info(use_iso8778=True)
    assert abs(info.p_Pa - 100_000.0) < 1e-9
    assert abs(info.T_K - 293.15) < 1e-12
    assert abs(info.RH_percent - 65.0) < 1e-12

    # Ожидаемая плотность ANR обычно приводится как ~1.185 кг/м^3.
    # Разные источники округляют; здесь проверяем разумный диапазон.
    assert 1.15 < info.rho_kg_m3 < 1.21


def test_engineering_reference_air_is_slightly_denser_than_humid_anr():
    rho_iso = float(rho_ANR_kg_m3(use_iso8778=True))
    rho_dry = float(rho_ANR_kg_m3(use_iso8778=False))
    # При одинаковых p,T сухой воздух должен быть чуть плотнее влажного.
    assert rho_dry >= rho_iso
