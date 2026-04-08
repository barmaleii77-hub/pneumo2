from __future__ import annotations

import math

import pandas as pd

from pneumo_solver_ui.opt_worker_v3_margins_energy import (
    _collect_packaging_penalty_metrics,
    candidate_penalty,
    penalty_target_keys,
)
from pneumo_solver_ui.solver_points_contract import CORNERS
from pneumo_solver_ui.suspension_family_runtime import spring_family_active_flag_column, spring_family_runtime_column


def _base() -> dict:
    base = {
        "база": 2.8,
        "колея": 1.6,
        "диаметр_поршня_Ц1": 0.032,
        "диаметр_штока_Ц1": 0.016,
        "диаметр_поршня_Ц2": 0.05,
        "диаметр_штока_Ц2": 0.014,
        "ход_штока_Ц1_перед_м": 0.25,
        "ход_штока_Ц1_зад_м": 0.25,
        "ход_штока_Ц2_перед_м": 0.25,
        "ход_штока_Ц2_зад_м": 0.25,
        "мёртвый_объём_камеры": 1.5e-5,
        "стенка_толщина_м": 0.003,
    }
    for cyl, mean in (("Ц1", 0.055), ("Ц2", 0.072)):
        for axle in ("перед", "зад"):
            base[f"пружина_{cyl}_{axle}_геом_диаметр_проволоки_м"] = 0.006
            base[f"пружина_{cyl}_{axle}_геом_диаметр_средний_м"] = mean
            base[f"пружина_{cyl}_{axle}_длина_свободная_м"] = 0.30 if cyl == "Ц2" else 0.31
            base[f"пружина_{cyl}_{axle}_длина_солид_м"] = 0.082 if cyl == "Ц2" else 0.085
            base[f"пружина_{cyl}_{axle}_верхний_отступ_от_крышки_м"] = 0.02
            base[f"пружина_{cyl}_{axle}_запас_до_coil_bind_минимум_м"] = 0.005
            base[f"пружина_{cyl}_{axle}_преднатяг_на_отбое_минимум_м"] = 0.01
    return base


def _df(*, pair_dx: float) -> pd.DataFrame:
    data: dict[str, list[float]] = {
        "время_с": [0.0],
    }
    for idx, corner in enumerate(CORNERS):
        base_x = float(idx)
        data[f"cyl1_top_{corner}_x_м"] = [base_x]
        data[f"cyl1_top_{corner}_y_м"] = [0.0]
        data[f"cyl1_top_{corner}_z_м"] = [0.0]
        data[f"cyl1_bot_{corner}_x_м"] = [base_x]
        data[f"cyl1_bot_{corner}_y_м"] = [0.30]
        data[f"cyl1_bot_{corner}_z_м"] = [0.0]

        data[f"cyl2_top_{corner}_x_м"] = [base_x + float(pair_dx)]
        data[f"cyl2_top_{corner}_y_м"] = [0.0]
        data[f"cyl2_top_{corner}_z_м"] = [0.0]
        data[f"cyl2_bot_{corner}_x_м"] = [base_x + float(pair_dx)]
        data[f"cyl2_bot_{corner}_y_м"] = [0.30]
        data[f"cyl2_bot_{corner}_z_м"] = [0.0]

        data[f"длина_цилиндра_{corner}_м"] = [0.30]
        data[f"длина_цилиндра_Ц2_{corner}_м"] = [0.31]
        data[f"положение_штока_{corner}_м"] = [0.10]
        data[f"положение_штока_Ц2_{corner}_м"] = [0.12]

        data[spring_family_active_flag_column("Ц1", corner)] = [1.0]
        data[spring_family_runtime_column("длина_м", "Ц1", corner)] = [0.25]
        data[spring_family_runtime_column("длина_установленная_м", "Ц1", corner)] = [0.25]
        data[spring_family_runtime_column("компрессия_м", "Ц1", corner)] = [0.06]
        data[spring_family_runtime_column("зазор_до_крышки_м", "Ц1", corner)] = [0.014]
        data[spring_family_runtime_column("запас_до_coil_bind_м", "Ц1", corner)] = [0.010]

        data[spring_family_active_flag_column("Ц2", corner)] = [1.0]
        data[spring_family_runtime_column("длина_м", "Ц2", corner)] = [0.24]
        data[spring_family_runtime_column("длина_установленная_м", "Ц2", corner)] = [0.24]
        data[spring_family_runtime_column("компрессия_м", "Ц2", corner)] = [0.05]
        data[spring_family_runtime_column("зазор_до_крышки_м", "Ц2", corner)] = [0.013]
        data[spring_family_runtime_column("запас_до_coil_bind_м", "Ц2", corner)] = [0.008]
    return pd.DataFrame(data)


def test_penalty_target_keys_include_family_packaging_targets() -> None:
    keys = set(penalty_target_keys())
    assert "мин_зазор_пружина_цилиндр_м" in keys
    assert "мин_зазор_пружина_пружина_м" in keys
    assert "макс_ошибка_midstroke_t0_м" in keys
    assert "мин_запас_до_coil_bind_пружины_м" in keys


def test_collect_packaging_penalty_metrics_reports_family_packaging_metrics() -> None:
    metrics = _collect_packaging_penalty_metrics(_base(), _df(pair_dx=0.09))
    assert math.isclose(float(metrics["макс_ошибка_midstroke_t0_м"]), 0.025, rel_tol=0.0, abs_tol=1e-12)
    assert float(metrics["мин_зазор_пружина_цилиндр_м"]) > 0.0
    assert float(metrics["мин_зазор_пружина_пружина_м"]) > 0.0
    assert math.isclose(float(metrics["мин_запас_до_coil_bind_пружины_м"]), 0.008, rel_tol=0.0, abs_tol=1e-12)
    assert int(metrics["число_пересечений_пружина_цилиндр"]) == 0
    assert int(metrics["число_пересечений_пружина_пружина"]) == 0


def test_collect_packaging_penalty_metrics_flags_spring_pair_interference() -> None:
    metrics = _collect_packaging_penalty_metrics(_base(), _df(pair_dx=0.02))
    assert float(metrics["мин_зазор_пружина_пружина_м"]) < 0.0
    assert int(metrics["число_пересечений_пружина_пружина"]) == 4


def test_candidate_penalty_reacts_to_family_packaging_targets() -> None:
    pen = candidate_penalty(
        {
            "мин_зазор_пружина_цилиндр_м": 0.001,
            "мин_зазор_пружина_пружина_м": -0.002,
            "макс_ошибка_midstroke_t0_м": 0.030,
            "мин_запас_до_coil_bind_пружины_м": 0.001,
        },
        {
            "мин_зазор_пружина_цилиндр_м": 0.003,
            "мин_зазор_пружина_пружина_м": 0.004,
            "макс_ошибка_midstroke_t0_м": 0.010,
            "мин_запас_до_coil_bind_пружины_м": 0.005,
        },
    )
    assert pen > 0.0
